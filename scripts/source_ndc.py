#!/usr/bin/env python3
from __future__ import annotations
import csv
import html
import io
import re
import zipfile
from common import decode_text, num, period_key, request_bytes, save_json

SIGNAL_CATALOG = 'https://data.gov.tw/dataset/6099'
PMI_CATALOG = 'https://data.gov.tw/dataset/6100'
SIGNAL_FALLBACK = 'https://ws.ndc.gov.tw/Download.ashx?icon=.zip&n=5pmv5rCj5oyH5qiZ5Y%2BK54eI6JmfLnppcA%3D%3D&u=LzAwMS9hZG1pbmlzdHJhdG9yLzEwL3JlbGZpbGUvNTc4MS82MzkyL2VhMjM1YmQ5LWQwNTItNGE2OS1hYmZjLWQ1Yzc4NWQzZDBlMi56aXA%3D'
PMI_FALLBACK = 'https://ws.ndc.gov.tw/Download.ashx?icon=.csv&n=6Ie654Gj5o6h6LO857aT55CG5Lq65oyH5pW4KHBtaeWPim5taSkuY3N2&u=LzAwMS9hZG1pbmlzdHJhdG9yLzEwL3JlbGZpbGUvNTc4MS82MzkxL2JmOGE0ZWI3LTEwZmUtNGZhMC1iNjQ2LTMwZTg5MGQwMjE4YS5jc3Y%3D'

FIELD_MAP = {
    'industrial_production': ('工業生產指數',),
    'enterprise_electricity': ('電力(企業)總用電量', '電力（企業）總用電量'),
    'manufacturing_sales_volume': ('製造業銷售量指數',),
    'wholesale_retail_food': ('批發、零售及餐飲業營業額', '批發',),
    'overtime_hours': ('工業及服務業加班工時',),
    'customs_exports': ('海關出口值',),
    'machinery_electrical_imports': ('機械及電機設備進口值',),
    'leading_composite': ('領先指標綜合指數', 'Leading Composite Index'),
    'leading_no_trend': ('領先指標不含趨勢指數',),
    'coincident_composite': ('同時指標綜合指數',),
    'coincident_no_trend': ('同時指標不含趨勢指數',),
    'lagging_composite': ('落後指標綜合指數',),
    'lagging_no_trend': ('落後指標不含趨勢指數',),
    'policy_score': ('景氣對策信號綜合分數',),
    'm1b': ('貨幣總計數M1B',),
    'stock_index': ('股價指數',),
    'unemployment_rate': ('失業率',),
    'unit_labor_cost': ('製造業單位產出勞動成本指數',),
    'new_loan_rate': ('五大銀行新承做放款平均利率',),
    'financial_loans_investments': ('全體金融機構放款與投資',),
    'manufacturing_inventory': ('製造業存貨價值',),
    'export_order_diffusion': ('外銷訂單動向指數',),
    'employee_net_entry_rate': ('工業及服務業受僱員工淨進入率',),
    'building_starts_area': ('建築物開工樓地板面積',),
    'semiconductor_equipment_imports': ('半導體設備進口',),
}

NAMES = {
    'industrial_production': '國發會景氣構成－工業生產指數',
    'enterprise_electricity': '企業總用電量',
    'manufacturing_sales_volume': '國發會景氣構成－製造業銷售量指數',
    'wholesale_retail_food': '批發零售及餐飲業營業額',
    'overtime_hours': '工業及服務業加班工時',
    'customs_exports': '海關出口值',
    'machinery_electrical_imports': '機械及電機設備進口值',
    'leading_composite': '景氣領先指標綜合指數',
    'leading_no_trend': '景氣領先指標不含趨勢指數',
    'coincident_composite': '景氣同時指標綜合指數',
    'coincident_no_trend': '景氣同時指標不含趨勢指數',
    'lagging_composite': '景氣落後指標綜合指數',
    'lagging_no_trend': '景氣落後指標不含趨勢指數',
    'policy_score': '景氣對策信號綜合判斷分數',
    'm1b': '貨幣總計數 M1B',
    'stock_index': '股價指數',
    'unemployment_rate': '失業率',
    'unit_labor_cost': '製造業單位產出勞動成本指數',
    'new_loan_rate': '五大銀行新承做放款平均利率',
    'financial_loans_investments': '全體金融機構放款與投資',
    'manufacturing_inventory': '製造業存貨價值',
    'export_order_diffusion': '外銷訂單動向指數',
    'employee_net_entry_rate': '工業及服務業受僱員工淨進入率',
    'building_starts_area': '建築物開工樓地板面積',
    'semiconductor_equipment_imports': '名目半導體設備進口',
    'pmi': '製造業採購經理人指數 PMI',
    'nmi': '非製造業經理人指數 NMI',
}

UNITS = {
    'policy_score': 'score',
    'unemployment_rate': 'percent',
    'new_loan_rate': 'percent',
    'employee_net_entry_rate': 'percent',
}

def normalize_keys(row):
    return {str(k or '').strip().replace('\ufeff', ''): v for k, v in row.items()}

def period(v):
    s = str(v or '').strip()
    if not s:
        return None
    s = s.replace('/', '-').replace('.', '-')
    m = re.search(r'(\d{4})\D{0,3}(\d{1,2})', s)
    if m:
        y, mo = map(int, m.groups())
        if 1 <= mo <= 12:
            return f'{y:04d}-{mo:02d}'
    m = re.search(r'(\d{2,3})\s*年\s*(\d{1,2})\s*月?', s)
    if m:
        y, mo = map(int, m.groups())
        if 1 <= mo <= 12:
            return f'{y + 1911:04d}-{mo:02d}'
    digits = re.sub(r'\D', '', s)
    if len(digits) == 6:
        y, mo = int(digits[:4]), int(digits[4:])
        if 1900 <= y <= 2200 and 1 <= mo <= 12:
            return f'{y:04d}-{mo:02d}'
    if len(digits) == 5:
        y, mo = int(digits[:3]) + 1911, int(digits[3:])
        if 1 <= mo <= 12:
            return f'{y:04d}-{mo:02d}'
    return None

def find_col(keys, aliases):
    for alias in aliases:
        for k in keys:
            if alias == k or alias in k:
                return k
    return None

def resolve_resource(catalog, extension, fallback):
    try:
        body, _ = request_bytes(catalog, 45, 2)
        text = html.unescape(decode_text(body))
        urls = re.findall(r'https://ws\.ndc\.gov\.tw/Download\.ashx\?[^"\'<> ]+', text)
        for url in urls:
            clean = url.replace('&amp;', '&')
            if f'icon=.{extension}' in clean.lower() or f'.{extension}' in clean.lower():
                return clean
    except Exception:
        pass
    return fallback

def rows_from_csv_bytes(body):
    return [normalize_keys(r) for r in csv.DictReader(decode_text(body).splitlines())]

def candidate_field_coverage(keys):
    """Count semantic NDC fields present in a CSV candidate.

    Dataset 6099 ZIPs can contain several CSVs. Row count is not evidence that a
    file is the canonical wide business-cycle table; a longer composite-only file
    can otherwise outrank the field-rich table and silently drop component series
    such as 股價指數. The source contract is semantic field coverage first.
    """
    keys = list(keys)
    return sum(1 for aliases in FIELD_MAP.values() if find_col(keys, aliases))

def rows_from_zip(body):
    with zipfile.ZipFile(io.BytesIO(body)) as zf:
        candidates = []
        for name in zf.namelist():
            if not name.lower().endswith('.csv'):
                continue
            try:
                rows = rows_from_csv_bytes(zf.read(name))
            except Exception:
                continue
            if not rows:
                continue
            keys = list(rows[0])
            date_col = find_col(keys, ('Date', '日期', '資料期'))
            leading = find_col(keys, FIELD_MAP['leading_no_trend'])
            coincident = find_col(keys, FIELD_MAP['coincident_no_trend'])
            if not date_col or not leading or not coincident:
                continue
            coverage = candidate_field_coverage(keys)
            # Full semantic coverage dominates row count. Existing identity fields
            # only break ties; row count is deliberately last.
            identity = sum(
                1 for aliases in (
                    FIELD_MAP['leading_composite'], FIELD_MAP['policy_score'], FIELD_MAP['stock_index']
                ) if find_col(keys, aliases)
            )
            candidates.append((coverage, identity, len(rows), name, rows))
        if not candidates:
            raise ValueError('NDC ZIP contains no parseable business-cycle CSV with required leading/coincident fields')
        candidates.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
        return candidates[0][4]

def parse_signal_rows(rows):
    if not rows:
        raise ValueError('NDC business-cycle CSV empty')
    keys = list(rows[0])
    date_col = find_col(keys, ('Date', '日期', '資料期'))
    signal_col = next((k for k in keys if k in ('景氣對策信號', '景氣燈號')), None)
    if not signal_col:
        signal_col = next((k for k in keys if ('景氣對策信號' in k or '景氣燈號' in k) and '分數' not in k), None)
    cols = {key: find_col(keys, aliases) for key, aliases in FIELD_MAP.items()}
    if not date_col or not cols['leading_no_trend'] or not cols['coincident_no_trend']:
        raise ValueError(f'NDC required columns missing: {keys[:20]}')
    series = {k: [] for k in FIELD_MAP}
    signals = []
    for row in rows:
        p = period(row.get(date_col))
        if not p:
            continue
        for key, col in cols.items():
            if col:
                v = num(row.get(col))
                if v is not None:
                    series[key].append([p, v])
        sig = str(row.get(signal_col, '')).strip() if signal_col else ''
        score = num(row.get(cols['policy_score'])) if cols['policy_score'] else None
        if sig or score is not None:
            signals.append({'period': p, 'score': score, 'signal': sig})
    out = {}
    for key, data in series.items():
        dedup = dict(data)
        vals = sorted(dedup.items(), key=lambda x: period_key(x[0]))
        if vals:
            out[key] = {'name': NAMES[key], 'unit': UNITS.get(key, 'index' if 'index' in key or key.endswith('_composite') or key.endswith('_no_trend') else 'value'), 'data': vals}
    signals = list({x['period']: x for x in signals}.values())
    signals.sort(key=lambda x: period_key(x['period']))
    return out, signals

def parse_pmi_rows(rows):
    if not rows:
        return {}
    keys = list(rows[0])
    date_col = find_col(keys, ('Date', '日期', '資料期'))
    pmi_col = find_col(keys, ('PMI',))
    nmi_col = find_col(keys, ('NMI',))
    if not date_col or (not pmi_col and not nmi_col):
        raise ValueError(f'NDC PMI required columns missing: {keys[:15]}')
    out = {}
    for key, col in (('pmi', pmi_col), ('nmi', nmi_col)):
        if not col:
            continue
        data = []
        for row in rows:
            p = period(row.get(date_col))
            v = num(row.get(col))
            if p and v is not None:
                data.append([p, v])
        vals = sorted(dict(data).items(), key=lambda x: period_key(x[0]))
        if vals:
            out[key] = {'name': NAMES[key], 'unit': 'index', 'data': vals}
    return out

def update(offline=None):
    if offline:
        raise FileNotFoundError('NDC offline fixture not bundled')
    signal_url = resolve_resource(SIGNAL_CATALOG, 'zip', SIGNAL_FALLBACK)
    body, _ = request_bytes(signal_url, 90, 3)
    rows = rows_from_zip(body)
    series, signals = parse_signal_rows(rows)

    warnings = []
    pmi_url = resolve_resource(PMI_CATALOG, 'csv', PMI_FALLBACK)
    try:
        pmi_body, _ = request_bytes(pmi_url, 60, 2)
        pmi_rows = rows_from_csv_bytes(pmi_body)
        series.update(parse_pmi_rows(pmi_rows))
    except Exception as e:
        warnings.append(f'PMI endpoint unavailable: {type(e).__name__}')

    if not series.get('leading_no_trend') or not series.get('coincident_no_trend'):
        raise ValueError('NDC leading/coincident series missing after parse')
    latest = max((s['data'][-1][0] for s in series.values() if s.get('data')), key=period_key)
    obj = {
        'source': 'National Development Council',
        'catalog_url': SIGNAL_CATALOG,
        'resource_url': signal_url,
        'pmi_catalog_url': PMI_CATALOG,
        'pmi_resource_url': pmi_url,
        'latest_period': latest,
        'series': series,
        'signals': signals,
        'notes': 'NDC states leading, coincident and lagging historical series may be revised on each monthly release.',
    }
    save_json('ndc.json', obj)
    msg = f'NDC leading/coincident/lagging indicators and business signal refreshed; semantic fields={len(series)}'
    if warnings:
        msg += '; warnings: ' + '; '.join(warnings)
    return {'latest_period': latest, 'rows': len(rows), 'message': msg, 'warnings': warnings}