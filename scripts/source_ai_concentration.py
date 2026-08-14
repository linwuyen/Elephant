#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
from io import StringIO

from common import decode_text, load_json, num, period_key, request_bytes, save_json

TRADE_COMMODITY_URL = (
    'https://web02.mof.gov.tw/njswww/webMain.aspx?sys=220&ym=9000&kind=21&type=4'
    '&funid=i8121&cycle=41&outmode=12&compmode=00&outkind=1&fld0=1'
    '&codlst0=1101111010100011110111100111110110100&utf=1'
)
TRADE_COMMODITY_CATALOG = 'https://data.gov.tw/dataset/8380'


def parse_period(raw):
    s = str(raw or '').strip()
    if not s:
        return None
    m = re.search(r'(?<!\d)(20\d{2})\D{0,4}(0?[1-9]|1[0-2])(?!\d)', s)
    if m:
        return f'{int(m.group(1)):04d}-{int(m.group(2)):02d}'
    m = re.search(r'(?<!\d)(\d{2,3})\s*年?\D{0,3}(0?[1-9]|1[0-2])\s*月?(?!\d)', s)
    if m and int(m.group(1)) < 1911:
        return f'{int(m.group(1)) + 1911:04d}-{int(m.group(2)):02d}'
    digits = re.sub(r'\D', '', s)
    if len(digits) == 6 and 200001 <= int(digits) <= 209912:
        return f'{digits[:4]}-{digits[4:]}'
    if len(digits) == 5:
        y, mo = int(digits[:3]), int(digits[3:])
        if 1 <= mo <= 12:
            return f'{y + 1911:04d}-{mo:02d}'
    return None


def _pick_col(fieldnames, needle, *, total=False):
    names = [str(x or '').strip() for x in fieldnames]
    if total:
        cand = [x for x in names if '按美元計算' in x and '總計' in x]
    else:
        cand = [x for x in names if '按美元計算' in x and needle in x]
    return cand[0] if cand else None


def parse_trade_csv(body):
    text = decode_text(body).lstrip('\ufeff')
    lines = [line for line in text.splitlines() if line.strip()]
    header_i = next(
        (i for i, line in enumerate(lines[:30]) if '電子零組件' in line and '資通與視聽產品' in line),
        None,
    )
    if header_i is None:
        raise ValueError('MOF commodity export header not found')

    reader = csv.DictReader(StringIO('\n'.join(lines[header_i:])))
    fields = reader.fieldnames or []
    total_col = _pick_col(fields, '', total=True)
    elec_col = _pick_col(fields, '電子零組件')
    ict_col = _pick_col(fields, '資通與視聽產品')
    if not all((total_col, elec_col, ict_col)):
        raise ValueError(f'MOF commodity export columns changed: {fields[:8]}')

    total, electronic, ict, ai_core, share = [], [], [], [], []
    for row in reader:
        p = None
        # Prefer explicit period-like fields, then scan values. The official export
        # format has changed its leading label more than once, so period parsing is
        # deliberately header-agnostic.
        for k, v in row.items():
            if any(token in str(k) for token in ('年月', '年/月', '期間', '資料期', '時間')):
                p = parse_period(v)
                if p:
                    break
        if not p:
            for v in row.values():
                p = parse_period(v)
                if p:
                    break
        tv, ev, iv = num(row.get(total_col)), num(row.get(elec_col)), num(row.get(ict_col))
        if not p or tv is None or ev is None or iv is None or tv <= 0:
            continue
        core = ev + iv
        total.append([p, tv])
        electronic.append([p, ev])
        ict.append([p, iv])
        ai_core.append([p, core])
        share.append([p, core / tv * 100.0])

    def dedup(rows):
        return [[p, v] for p, v in sorted(dict(rows).items(), key=lambda x: period_key(x[0]))]

    series = {
        'exports_total_usd': {'name': '出口總值', 'unit': 'million_usd', 'data': dedup(total)},
        'exports_electronic_components': {'name': '電子零組件出口', 'unit': 'million_usd', 'data': dedup(electronic)},
        'exports_ict': {'name': '資通與視聽產品出口', 'unit': 'million_usd', 'data': dedup(ict)},
        'exports_ai_core': {'name': 'AI 核心出口（電子零組件＋資通與視聽）', 'unit': 'million_usd', 'data': dedup(ai_core)},
        'exports_ai_core_share': {'name': 'AI 核心出口占總出口比重', 'unit': 'percent', 'data': dedup(share)},
    }
    if len(series['exports_ai_core_share']['data']) < 12:
        raise ValueError('MOF commodity export parse returned too few monthly rows')
    return series


def update(offline=None):
    old = load_json('ai_inputs.json', {'series': {}})
    if offline:
        # The regression fixture predates this supplemental source. Preserve the
        # checked-in last-good copy instead of fabricating an offline value.
        if old.get('series'):
            return {'latest_period': old.get('latest_period'), 'rows': 0, 'message': 'AI trade input preserved in offline regression'}
        raise FileNotFoundError('AI trade fixture not present')

    body, _ = request_bytes(TRADE_COMMODITY_URL, 75, 3)
    series = parse_trade_csv(body)
    latest = max((s['data'][-1][0] for s in series.values() if s.get('data')), key=period_key)
    save_json('ai_inputs.json', {
        'source': 'Taiwan Ministry of Finance commodity exports',
        'latest_period': latest,
        'series': series,
        'catalog': TRADE_COMMODITY_CATALOG,
    })
    rows = sum(len(s['data']) for s in series.values())
    return {'latest_period': latest, 'rows': rows, 'message': 'MOF AI-core commodity export inputs refreshed'}
