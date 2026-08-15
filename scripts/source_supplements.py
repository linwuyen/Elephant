#!/usr/bin/env python3
from __future__ import annotations

import html
import re
import subprocess

from common import decode_text, load_json, num, period_key, request_bytes, save_json
from source_decision import (
    DGBAS_EMP_URL,
    DGBAS_WAGE_URL,
    dedup,
    merge_recent,
    parse_dgbas_employment,
    parse_dgbas_long,
    parse_long_moea,
)
from source_moea import decode_resource, month_period, pick

INVENTORY_URL = 'https://service.moea.gov.tw/EE520/opendata/%E7%B6%93%E6%BF%9F%E9%83%A8%E7%B5%B1%E8%A8%88%E8%99%95_%E8%A3%BD%E9%80%A0%E6%A5%AD%E5%AD%98%E8%B2%A8%E9%87%8F%E6%8C%87%E6%95%B8%EF%BC%8D%E6%8C%89%E5%9B%9B%E5%A4%A7%E8%A1%8C%E6%A5%AD%E5%88%A5%E5%88%86.csv'
INVENTORY_CATALOG = 'https://data.gov.tw/dataset/109753'
ELECTRONIC_ORDERS_URL = 'https://service.moea.gov.tw/EE520/opendata/%E7%B6%93%E6%BF%9F%E9%83%A8%E7%B5%B1%E8%A8%88%E8%99%95_%E5%A4%96%E9%8A%B7%E8%A8%82%E5%96%AE_%E9%9B%BB%E5%AD%90%E7%94%A2%E5%93%81.csv'
ELECTRONIC_ORDERS_CATALOG = 'https://data.gov.tw/dataset/16362'
ICT_ORDERS_URL = 'https://service.moea.gov.tw/EE520/opendata/%E7%B6%93%E6%BF%9F%E9%83%A8%E7%B5%B1%E8%A8%88%E8%99%95_%E5%A4%96%E9%8A%B7%E8%A8%82%E5%96%AE_%E8%B3%87%E8%A8%8A%E9%80%9A%E8%A8%8A%E7%94%A2%E5%93%81.csv'
ICT_ORDERS_CATALOG = 'https://data.gov.tw/dataset/16361'
DGBAS_NEWS_PAGE = 'https://www.dgbas.gov.tw/News.aspx?PageSize=50&_CSN=135&n=3602&sms=10980&page={page}'
DGBAS_NEWS_CATALOG = 'https://www.dgbas.gov.tw/News.aspx?_CSN=135&n=3602&sms=10980'


def verified_fetch(url: str, timeout: int = 75) -> tuple[bytes, str]:
    """Fetch with normal TLS verification; curl is a CA-bundle fallback, never -k."""
    first = None
    try:
        return request_bytes(url, timeout, 2)[0], 'urllib'
    except Exception as exc:
        first = exc
    cmd = [
        'curl', '--fail', '--location', '--silent', '--show-error',
        '--retry', '2', '--retry-all-errors', '--max-time', str(timeout), url,
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout + 15)
    except FileNotFoundError as exc:
        raise RuntimeError(f'verified fetch failed; urllib={first}; curl unavailable') from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f'verified fetch failed; urllib={first}; curl timeout') from exc
    if proc.returncode or not proc.stdout:
        err = proc.stderr.decode('utf-8', 'replace').strip()
        raise RuntimeError(f'verified fetch failed; urllib={first}; curl={err or proc.returncode}')
    return proc.stdout, 'curl-verified'


def _numeric_value(row):
    for key in ('統計值(指數)', '統計值（指數）', '統計值', '指數'):
        if key in row:
            value = num(row.get(key))
            if value is not None:
                return value
    for key, raw in row.items():
        if any(token in str(key) for token in ('統計值', '指數')):
            value = num(raw)
            if value is not None:
                return value
    return None


def _period(row):
    raw = pick(row, '資料期(民國年)', '資料期(民國年月)', '資料期', '年月', '年月份', '日期')
    if not raw:
        for key, value in row.items():
            name = str(key).replace(' ', '')
            if any(token in name for token in ('資料期', '年月', '年月份')) and value not in (None, ''):
                raw = value
                break
    if not raw:
        return None
    try:
        return month_period(raw)
    except Exception:
        return None


def _inventory_header_rank(header):
    text = re.sub(r'\s+', '', str(header or ''))
    if not text:
        return 0
    subindustries = ('金屬機電', '資訊電子', '化學工業', '民生工業', '食品工業')
    if any(x in text for x in subindustries):
        return 0
    if text in ('製造業', '製造業總計', '製造業總指數'):
        return 120
    if '製造業' in text and ('存貨' in text or '指數' in text or '總計' in text):
        return 100
    if text in ('總計', '總指數'):
        return 60
    return 0


def parse_inventory_index(body):
    rows = decode_resource(body, INVENTORY_URL)
    candidates = []

    # Canonical government open-data shape: one observation per row.
    grouped = {}
    for row in rows:
        p = _period(row)
        v = _numeric_value(row)
        if not p or v is None:
            continue
        code = str(pick(row, '行業代碼', '產業代碼', '代碼') or '').strip()
        label = ' / '.join(
            str(x).strip()
            for x in (pick(row, '行業別', '產業別', '行業名稱'), pick(row, '統計項目', '項目'))
            if x and str(x).strip()
        )
        text = f'{code} {label}'
        rank = 0
        if code == 'C':
            rank += 100
        if '製造業' in text:
            rank += 30
        if any(x in text for x in ('總計', '合計', '總指數')):
            rank += 20
        if rank:
            grouped.setdefault((rank, label or code), []).append([p, v])
    for (rank, label), data in grouped.items():
        data = dedup(data)
        if len(data) >= 24:
            candidates.append((rank + 1000, len(data), label or '製造業', data, 'long'))

    # Defensive support for a date-per-row, industry-per-column export.
    if rows:
        headers = list(rows[0].keys())
        for header in headers:
            rank = _inventory_header_rank(header)
            if not rank:
                continue
            data = []
            for row in rows:
                p = _period(row)
                v = num(row.get(header))
                if p and v is not None:
                    data.append([p, v])
            data = dedup(data)
            if len(data) >= 24:
                candidates.append((rank + 500, len(data), str(header), data, 'wide'))

    # Defensive support for an industry-per-row, month-per-column export.
    for row in rows:
        row_text = ' '.join(str(v or '') for v in row.values())
        if '製造業' not in row_text or any(x in row_text for x in ('金屬機電', '資訊電子', '化學工業', '民生工業')):
            continue
        data = []
        for key, raw in row.items():
            try:
                p = month_period(key)
            except Exception:
                continue
            v = num(raw)
            if v is not None:
                data.append([p, v])
        data = dedup(data)
        if len(data) >= 24:
            candidates.append((400, len(data), '製造業', data, 'transposed'))

    if not candidates:
        sample = ', '.join(str(k) for k in list(rows[0].keys())[:12]) if rows else 'no rows'
        raise ValueError(f'MOEA inventory-index total manufacturing series not found; columns={sample}')
    _, _, label, data, layout = max(candidates, key=lambda x: (x[0], x[1]))
    if not all(0 < float(v) < 1000 for _, v in data[-36:]):
        raise ValueError('MOEA inventory-index values outside plausible index range')
    return {
        'inventory.manufacturing_index': {
            'name': '製造業 / 存貨量指數',
            'unit': 'index',
            'data': data,
            'selection': label,
            'layout': layout,
            'catalog': INVENTORY_CATALOG,
        }
    }


def parse_order_family(body, url, family_name, key_prefix, catalog):
    parsed = parse_long_moea(body, url, 'orders')
    if not parsed:
        raise ValueError(f'{family_name} parse empty')
    out = {}
    for idx, (label, series) in enumerate(sorted(parsed.items())):
        item = dict(series)
        item['name'] = f'{family_name} / {label}'
        item['catalog'] = catalog
        item['level_comparability'] = 'not_assumed_across_resources'
        out[f'{key_prefix}.{idx:02d}'] = item
    return out


def _parse_people(value):
    text = re.sub(r'[,，\s]', '', str(value or ''))
    if not text:
        return None
    if '萬' not in text and '千' not in text and '百' not in text:
        v = num(text)
        return None if v is None else float(v)
    total = 0.0
    m = re.search(r'(\d+(?:\.\d+)?)萬', text)
    if m:
        total += float(m.group(1)) * 10000
    m = re.search(r'(\d+(?:\.\d+)?)千', text)
    if m:
        total += float(m.group(1)) * 1000
    m = re.search(r'(\d+(?:\.\d+)?)百', text)
    if m:
        total += float(m.group(1)) * 100
    return total if total else None


def parse_dgbas_news_pages(bodies, min_observations=24):
    """Parse DGBAS salary/productivity news titles without changing score semantics."""
    wage = []
    employment = []
    pattern = re.compile(
        r'(\d{3})年\s*(\d{1,2})月\s*底?\s*工業及服務業受僱員工人數為\s*'
        r'([0-9０-９,.，\s萬千百]+?)\s*人[，,。\s]*'
        r'本月總薪資平均(?:數)?為\s*([0-9０-９,，]+)\s*元'
    )
    for body in bodies:
        text = html.unescape(decode_text(body))
        text = re.sub(r'<script\b.*?</script>|<style\b.*?</style>', ' ', text, flags=re.I | re.S)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        for ry, month, people_raw, wage_raw in pattern.findall(text):
            p = f'{int(ry) + 1911:04d}-{int(month):02d}'
            people = _parse_people(people_raw)
            salary = num(wage_raw.replace('，', ','))
            if people is not None and salary is not None:
                employment.append([p, people])
                wage.append([p, salary])
    employment = dedup(employment)
    wage = dedup(wage)
    if min(len(employment), len(wage)) < min_observations:
        raise ValueError(f'DGBAS news-title history too short: wage={len(wage)} employment={len(employment)}')
    if not all(1_000_000 < float(v) < 20_000_000 for _, v in employment[-24:]):
        raise ValueError('DGBAS news employment outside plausible range')
    if not all(10_000 < float(v) < 500_000 for _, v in wage[-24:]):
        raise ValueError('DGBAS news salary outside plausible range')
    return {
        'dgbas.total_monthly_salary': {
            'name': '工業及服務業平均每月總薪資',
            'unit': 'ntd',
            'data': wage,
            'selection': 'DGBAS official salary/productivity monthly news title fallback',
            'catalog': DGBAS_NEWS_CATALOG,
        },
        'dgbas.employment_total': {
            'name': '工業及服務業受僱員工人數',
            'unit': 'persons',
            'data': employment,
            'selection': 'DGBAS official salary/productivity monthly news title fallback',
            'catalog': DGBAS_NEWS_CATALOG,
        },
    }


def _merge_into_decision(series_patch, catalogs_patch):
    obj = load_json('decision_inputs.json', {'series': {}, 'catalogs': {}})
    series = dict(obj.get('series', {}))
    # Replace only prior supplement namespaces; ordinary orders.* stay authoritative.
    for prefix in ('orders_supplement.electronic.', 'orders_supplement.ict.'):
        series = {k: v for k, v in series.items() if not k.startswith(prefix)}
    for key, incoming in series_patch.items():
        if key.startswith('dgbas.') and key in series:
            merged = merge_recent(series[key], incoming)
            for meta in ('name', 'unit', 'selection', 'catalog'):
                if incoming.get(meta) is not None:
                    merged[meta] = incoming[meta]
            series[key] = merged
        else:
            series[key] = incoming
    obj['series'] = series
    catalogs = dict(obj.get('catalogs', {}))
    catalogs.update(catalogs_patch)
    obj['catalogs'] = catalogs
    latest = max(
        (s['data'][-1][0] for s in series.values() if s.get('data')),
        key=period_key,
        default=obj.get('latest_period'),
    )
    obj['latest_period'] = latest
    notes = list(obj.get('supplement_notes', []))
    note = 'Verified-TLS supplements: MOEA manufacturing inventory index + dedicated electronic/ICT export orders + DGBAS XML with official www.dgbas.gov.tw salary/productivity-news fallback.'
    if note not in notes:
        notes.append(note)
    obj['supplement_notes'] = notes[-20:]
    save_json('decision_inputs.json', obj)
    return latest


def _fetch_dgbas_news_history(transports, errors, max_pages=8):
    bodies = []
    last_error = None
    for page in range(1, max_pages + 1):
        url = DGBAS_NEWS_PAGE.format(page=page)
        try:
            body, transport = verified_fetch(url)
            bodies.append(body)
            transports[f'dgbas_news_page_{page}'] = transport
            try:
                return parse_dgbas_news_pages(bodies)
            except ValueError as exc:
                last_error = exc
        except Exception as exc:
            last_error = exc
    if last_error:
        errors.append(f'dgbas_news_fallback: {type(last_error).__name__}: {last_error}')
    return {}


def update(offline=None):
    if offline:
        return {'latest_period': load_json('decision_inputs.json', {}).get('latest_period'), 'rows': 0, 'message': 'supplements skipped in offline mode'}

    patch = {}
    catalogs = {}
    warnings = []
    dgbas_errors = []
    recoveries = []
    transports = {}
    rows = 0
    tasks = [
        ('inventory_index', INVENTORY_URL),
        ('electronic_orders', ELECTRONIC_ORDERS_URL),
        ('ict_orders', ICT_ORDERS_URL),
        ('dgbas_wage_retry', DGBAS_WAGE_URL),
        ('dgbas_employment_retry', DGBAS_EMP_URL),
    ]
    bodies = {}
    for key, url in tasks:
        try:
            body, transport = verified_fetch(url)
            bodies[key] = body
            transports[key] = transport
        except Exception as exc:
            target = dgbas_errors if key.startswith('dgbas_') else warnings
            target.append(f'{key}: {type(exc).__name__}: {exc}')

    if 'inventory_index' in bodies:
        try:
            parsed = parse_inventory_index(bodies['inventory_index'])
            patch.update(parsed)
            rows += sum(len(x['data']) for x in parsed.values())
            catalogs['inventory_index'] = INVENTORY_CATALOG
        except Exception as exc:
            warnings.append(f'inventory_index_parse: {type(exc).__name__}: {exc}')

    for source_key, family, prefix, catalog, url in [
        ('electronic_orders', '電子產品', 'orders_supplement.electronic', ELECTRONIC_ORDERS_CATALOG, ELECTRONIC_ORDERS_URL),
        ('ict_orders', '資訊通訊產品', 'orders_supplement.ict', ICT_ORDERS_CATALOG, ICT_ORDERS_URL),
    ]:
        if source_key in bodies:
            try:
                parsed = parse_order_family(bodies[source_key], url, family, prefix, catalog)
                patch.update(parsed)
                rows += sum(len(x['data']) for x in parsed.values())
                catalogs[source_key] = catalog
            except Exception as exc:
                warnings.append(f'{source_key}_parse: {type(exc).__name__}: {exc}')

    if 'dgbas_wage_retry' in bodies:
        try:
            parsed = parse_dgbas_long(bodies['dgbas_wage_retry'], '工業及服務業平均每月總薪資')
            patch.update(parsed)
            rows += sum(len(x['data']) for x in parsed.values())
        except Exception as exc:
            dgbas_errors.append(f'dgbas_wage_retry_parse: {type(exc).__name__}: {exc}')
    if 'dgbas_employment_retry' in bodies:
        try:
            parsed = parse_dgbas_employment(bodies['dgbas_employment_retry'])
            patch.update(parsed)
            rows += sum(len(x['data']) for x in parsed.values())
        except Exception as exc:
            dgbas_errors.append(f'dgbas_employment_retry_parse: {type(exc).__name__}: {exc}')

    missing_dgbas = {'dgbas.total_monthly_salary', 'dgbas.employment_total'} - set(patch)
    if missing_dgbas:
        news_errors = []
        news = _fetch_dgbas_news_history(transports, news_errors)
        if news:
            for key in missing_dgbas:
                if key in news:
                    patch[key] = news[key]
                    rows += len(news[key]['data'])
            catalogs['dgbas_news_fallback'] = DGBAS_NEWS_CATALOG
            recoveries.append('DGBAS XML unavailable/invalid; recovered identical wage/employment semantics from official salary/productivity monthly news titles')
        else:
            warnings.extend(dgbas_errors)
            warnings.extend(news_errors)
    elif dgbas_errors:
        recoveries.append('DGBAS verified retry succeeded despite an earlier DGBAS transport/parse attempt failing')

    latest = _merge_into_decision(
        patch,
        {
            **catalogs,
            'dgbas_wage_retry': 'https://data.gov.tw/dataset/9634',
            'dgbas_employment_retry': 'https://data.gov.tw/dataset/177765',
        },
    )
    if not patch:
        raise RuntimeError('no supplement series refreshed: ' + '; '.join(warnings + dgbas_errors))
    message = f'official supplements refreshed ({len(patch)} series; transports={transports})'
    if recoveries:
        message += '; recoveries: ' + '; '.join(recoveries)
    if warnings:
        message += '; warnings: ' + '; '.join(warnings)
    return {
        'latest_period': latest,
        'rows': rows,
        'message': message,
        'warnings': warnings,
        'recoveries': recoveries,
        'transports': transports,
    }


if __name__ == '__main__':
    print(update())
