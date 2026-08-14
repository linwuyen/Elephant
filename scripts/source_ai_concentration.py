#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import re
from io import StringIO

from common import decode_text, load_json, num, period_key, request_bytes, save_json

TRADE_COMMODITY_URL = (
    'https://web02.mof.gov.tw/njswww/webMain.aspx?sys=220&ym=9000&kind=21&type=4'
    '&funid=i8121&cycle=41&outmode=12&compmode=00&outkind=1&fld0=1'
    '&codlst0=1101111010100011110111100111110110100&utf=1'
)
TRADE_COMMODITY_CATALOG = 'https://data.gov.tw/dataset/8380'
MIN_YEAR = 1990
MAX_YEAR = dt.datetime.now().year + 1
PERIOD_HEADER_TOKENS = ('年月', '年/月', '期間', '資料期', '時間', '月別', '年月別')


def _valid_period(year, month):
    try:
        y, m = int(year), int(month)
    except (TypeError, ValueError):
        return None
    if not (MIN_YEAR <= y <= MAX_YEAR and 1 <= m <= 12):
        return None
    return f'{y:04d}-{m:02d}'


def parse_period(raw):
    """Parse only plausible monthly periods; never treat future monetary values as dates."""
    s = str(raw or '').strip()
    if not s:
        return None

    m = re.search(r'(?<!\d)(20\d{2})\D{0,4}(0?[1-9]|1[0-2])(?!\d)', s)
    if m:
        return _valid_period(m.group(1), m.group(2))

    # ROC year/month, e.g. 115年7月 or 115/07.
    m = re.search(r'(?<!\d)(\d{2,3})\s*年?\D{0,3}(0?[1-9]|1[0-2])\s*月?(?!\d)', s)
    if m and int(m.group(1)) < 1911:
        return _valid_period(int(m.group(1)) + 1911, m.group(2))

    # Compact formats are accepted only after plausibility bounding.
    digits = re.sub(r'\D', '', s)
    if len(digits) == 6:
        return _valid_period(digits[:4], digits[4:])
    if len(digits) == 5:
        y, mo = int(digits[:3]), int(digits[3:])
        return _valid_period(y + 1911, mo)
    return None


def _pick_col(fieldnames, needle, *, total=False):
    names = [str(x or '').strip() for x in fieldnames]
    if total:
        cand = [x for x in names if '按美元計算' in x and '總計' in x]
    else:
        cand = [x for x in names if '按美元計算' in x and needle in x]
    return cand[0] if cand else None


def _pick_period_col(fields, rows, metric_cols):
    """Resolve a period column without scanning arbitrary monetary values.

    Prefer a semantically named field. If the publisher changes the label, score
    non-metric columns by how consistently they parse as plausible monthly periods.
    A real period column should parse for most monthly rows; monetary columns should
    not. This also excludes annual-total/footer rows with blank period cells.
    """
    candidates = [f for f in fields if f not in metric_cols]
    explicit = [f for f in candidates if any(token in str(f) for token in PERIOD_HEADER_TOKENS)]
    if explicit:
        return explicit[0]

    scored = []
    sample = rows[:240]
    for field in candidates:
        values = [str(row.get(field) or '').strip() for row in sample]
        nonempty = [v for v in values if v]
        if len(nonempty) < 12:
            continue
        parsed = [parse_period(v) for v in nonempty]
        valid = [p for p in parsed if p]
        ratio = len(valid) / len(nonempty)
        distinct = len(set(valid))
        if ratio >= 0.70 and distinct >= 12:
            scored.append((ratio, distinct, -candidates.index(field), field))
    return max(scored)[-1] if scored else None


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
    rows = list(reader)
    total_col = _pick_col(fields, '', total=True)
    elec_col = _pick_col(fields, '電子零組件')
    ict_col = _pick_col(fields, '資通與視聽產品')
    if not all((total_col, elec_col, ict_col)):
        raise ValueError(f'MOF commodity export columns changed: {fields[:8]}')

    metric_cols = {total_col, elec_col, ict_col}
    period_col = _pick_period_col(fields, rows, metric_cols)
    if not period_col:
        raise ValueError(f'MOF commodity export period column not found: {fields[:8]}')

    total, electronic, ict, ai_core, share = [], [], [], [], []
    for row in rows:
        # No row-wide fallback: footer/aggregate rows often have no period and their
        # monetary values can look like YYYYMM. Such rows must be ignored.
        p = parse_period(row.get(period_col))
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

    # Contract: all persisted periods must be plausible and the latest row may not
    # drift into a fabricated future period.
    for key, s in series.items():
        for p, _ in s['data']:
            y, m = map(int, p.split('-'))
            if not (MIN_YEAR <= y <= MAX_YEAR and 1 <= m <= 12):
                raise ValueError(f'implausible period in {key}: {p}')
    return series


def update(offline=None):
    old = load_json('ai_inputs.json', {'series': {}})
    if offline:
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
