#!/usr/bin/env python3
from __future__ import annotations

import subprocess

from common import load_json, num, period_key, request_bytes, save_json
from source_decision import (
    DGBAS_EMP_URL,
    DGBAS_WAGE_URL,
    dedup,
    parse_dgbas_employment,
    parse_dgbas_long,
)
from source_moea import decode_resource, month_period, pick

INVENTORY_URL = 'https://service.moea.gov.tw/EE520/opendata/%E7%B6%93%E6%BF%9F%E9%83%A8%E7%B5%B1%E8%A8%88%E8%99%95_%E8%A3%BD%E9%80%A0%E6%A5%AD%E5%AD%98%E8%B2%A8%E9%87%8F%E6%8C%87%E6%95%B8%EF%BC%8D%E6%8C%89%E5%9B%9B%E5%A4%A7%E8%A1%8C%E6%A5%AD%E5%88%A5%E5%88%86.csv'
INVENTORY_CATALOG = 'https://data.gov.tw/dataset/109753'
ELECTRONIC_ORDERS_URL = 'https://service.moea.gov.tw/EE520/opendata/%E7%B6%93%E6%BF%9F%E9%83%A8%E7%B5%B1%E8%A8%88%E8%99%95_%E9%9B%BB%E5%AD%90%E7%94%A2%E5%93%81%E6%A5%AD%E5%A4%96%E9%8A%B7%E8%A8%82%E5%96%AE%E6%95%B8%E9%87%8F.csv'
ELECTRONIC_ORDERS_CATALOG = 'https://data.gov.tw/dataset/163944'
ICT_ORDERS_URL = 'https://service.moea.gov.tw/EE520/opendata/%E7%B6%93%E6%BF%9F%E9%83%A8%E7%B5%B1%E8%A8%88%E8%99%95_%E8%B3%87%E8%A8%8A%E9%80%9A%E4%BF%A1%E7%94%A2%E5%93%81%E6%A5%AD%E5%A4%96%E9%8A%B7%E8%A8%82%E5%96%AE%E6%95%B8%E9%87%8F.csv'
ICT_ORDERS_CATALOG = 'https://data.gov.tw/dataset/163946'


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
    preferred = ('統計值(指數)', '統計值(數量)', '統計值', '數量', '指數')
    for key in preferred:
        if key in row:
            value = num(row.get(key))
            if value is not None:
                return value
    for key, raw in row.items():
        if any(token in str(key) for token in ('統計值', '數量', '指數')):
            value = num(raw)
            if value is not None:
                return value
    return None


def _period(row):
    raw = pick(row, '資料期(民國年)', '資料期', '年月', '年月份', '日期')
    if not raw:
        return None
    try:
        return month_period(raw)
    except Exception:
        return None


def parse_inventory_index(body):
    rows = decode_resource(body, INVENTORY_URL)
    candidates = {}
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
        if not rank:
            continue
        candidates.setdefault((rank, label or code), []).append([p, v])
    if not candidates:
        raise ValueError('MOEA inventory-index total manufacturing series not found')
    (_, label), data = max(candidates.items(), key=lambda kv: (kv[0][0], len(kv[1])))
    data = dedup(data)
    if len(data) < 24:
        raise ValueError(f'MOEA inventory-index history too short: {len(data)}')
    return {
        'inventory.manufacturing_index': {
            'name': '製造業 / 存貨量指數',
            'unit': 'index',
            'data': data,
            'selection': label,
            'catalog': INVENTORY_CATALOG,
        }
    }


def parse_safe_monthly_total(body, url, name, catalog):
    rows = decode_resource(body, url)
    grouped = {}
    preferred = {}
    for row in rows:
        p = _period(row)
        v = _numeric_value(row)
        if not p or v is None:
            continue
        descriptor = ' / '.join(
            str(x).strip()
            for x in (pick(row, '貨品別', '產品別', '統計項目', '項目', '地區別'),)
            if x and str(x).strip()
        )
        grouped.setdefault(p, []).append((descriptor, v))
        if any(token in descriptor for token in ('總計', '合計', '全部')):
            preferred.setdefault(p, []).append((descriptor, v))
    data = []
    selections = set()
    for p in sorted(grouped, key=period_key):
        pool = preferred.get(p) or grouped[p]
        unique = {}
        for descriptor, value in pool:
            unique.setdefault(round(float(value), 12), descriptor)
        if len(unique) != 1 and not preferred.get(p):
            continue
        value, descriptor = next(iter(unique.items()))
        data.append([p, value])
        if descriptor:
            selections.add(descriptor)
    data = dedup(data)
    if len(data) < 24:
        raise ValueError(f'{name} no unambiguous monthly total ({len(data)} rows)')
    return {
        'name': name,
        'unit': 'official_quantity',
        'data': data,
        'selection': sorted(selections)[:5],
        'catalog': catalog,
        'aggregation_note': 'Only an explicit/unique monthly total is used; heterogeneous quantities are never summed.',
    }


def _merge_into_decision(series_patch, catalogs_patch):
    obj = load_json('decision_inputs.json', {'series': {}, 'catalogs': {}})
    series = dict(obj.get('series', {}))
    series.update(series_patch)
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
    note = 'Verified-TLS supplements: current MOEA inventory index, electronic/ICT order quantities, and DGBAS retry path.'
    if note not in notes:
        notes.append(note)
    obj['supplement_notes'] = notes[-20:]
    save_json('decision_inputs.json', obj)
    return latest


def update(offline=None):
    if offline:
        return {'latest_period': load_json('decision_inputs.json', {}).get('latest_period'), 'rows': 0, 'message': 'supplements skipped in offline mode'}

    patch = {}
    catalogs = {}
    warnings = []
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
            warnings.append(f'{key}: {type(exc).__name__}: {exc}')

    if 'inventory_index' in bodies:
        try:
            parsed = parse_inventory_index(bodies['inventory_index'])
            patch.update(parsed)
            rows += sum(len(x['data']) for x in parsed.values())
            catalogs['inventory_index'] = INVENTORY_CATALOG
        except Exception as exc:
            warnings.append(f'inventory_index_parse: {type(exc).__name__}: {exc}')

    for source_key, output_key, label, catalog, url in [
        ('electronic_orders', 'orders.electronic_products_quantity', '電子產品業外銷訂單數量', ELECTRONIC_ORDERS_CATALOG, ELECTRONIC_ORDERS_URL),
        ('ict_orders', 'orders.ict_products_quantity', '資訊通信產品業外銷訂單數量', ICT_ORDERS_CATALOG, ICT_ORDERS_URL),
    ]:
        if source_key in bodies:
            try:
                series = parse_safe_monthly_total(bodies[source_key], url, label, catalog)
                patch[output_key] = series
                rows += len(series['data'])
                catalogs[source_key] = catalog
            except Exception as exc:
                warnings.append(f'{source_key}_parse: {type(exc).__name__}: {exc}')

    if 'dgbas_wage_retry' in bodies:
        try:
            parsed = parse_dgbas_long(bodies['dgbas_wage_retry'], '工業及服務業平均每月總薪資')
            patch.update(parsed)
            rows += sum(len(x['data']) for x in parsed.values())
        except Exception as exc:
            warnings.append(f'dgbas_wage_retry_parse: {type(exc).__name__}: {exc}')
    if 'dgbas_employment_retry' in bodies:
        try:
            parsed = parse_dgbas_employment(bodies['dgbas_employment_retry'])
            patch.update(parsed)
            rows += sum(len(x['data']) for x in parsed.values())
        except Exception as exc:
            warnings.append(f'dgbas_employment_retry_parse: {type(exc).__name__}: {exc}')

    latest = _merge_into_decision(
        patch,
        {
            **catalogs,
            'dgbas_wage_retry': 'https://data.gov.tw/dataset/9634',
            'dgbas_employment_retry': 'https://data.gov.tw/dataset/177765',
        },
    )
    if not patch:
        raise RuntimeError('no supplement series refreshed: ' + '; '.join(warnings))
    message = f'official supplements refreshed ({len(patch)} series; transports={transports})'
    if warnings:
        message += '; warnings: ' + '; '.join(warnings)
    return {'latest_period': latest, 'rows': rows, 'message': message, 'warnings': warnings, 'transports': transports}


if __name__ == '__main__':
    print(update())
