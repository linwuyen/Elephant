#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed

from common import TZ, load_json, request_bytes, save_json

START_PERIOD = '2016-01'
REPORT_URL = 'https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={year:04d}{month:02d}01'
CATALOG_URL = 'https://data.gov.tw/dataset/11755'
REPORT_PAGE = 'https://www.twse.com.tw/indicesReport/MI_5MINS_HIST'
SERIES_KEY = 'twse.taiex_month_end'


def month_shift(period: str, delta: int) -> str:
    y, m = map(int, period.split('-'))
    idx = y * 12 + m - 1 + delta
    return f'{idx // 12:04d}-{idx % 12 + 1:02d}'


def month_range(start: str, end: str):
    p = start
    while p <= end:
        yield p
        p = month_shift(p, 1)


def last_completed_month(now=None):
    now = now or dt.datetime.now(TZ)
    return month_shift(f'{now.year:04d}-{now.month:02d}', -1)


def roc_date_to_iso(raw):
    parts = str(raw or '').strip().split('/')
    if len(parts) != 3:
        return None
    try:
        y, m, d = map(int, parts)
    except Exception:
        return None
    y = y + 1911 if y < 1911 else y
    if not (1900 <= y <= 2200 and 1 <= m <= 12 and 1 <= d <= 31):
        return None
    return f'{y:04d}-{m:02d}-{d:02d}'


def numeric(value):
    try:
        v = float(str(value).replace(',', '').strip())
    except Exception:
        return None
    return v if math.isfinite(v) else None


def parse_month_payload(body: bytes, expected_period: str):
    payload = json.loads(body.decode('utf-8-sig'))
    if str(payload.get('stat', '')).upper() != 'OK':
        raise ValueError(f'TWSE report status not OK: {payload.get("stat")}')
    fields = [str(x).strip() for x in (payload.get('fields') or [])]
    rows = payload.get('data') or []
    if not rows:
        raise ValueError(f'TWSE report returned no daily rows for {expected_period}')

    date_idx = next((i for i, x in enumerate(fields) if '日期' in x or x.lower() == 'date'), 0)
    close_idx = next((i for i, x in enumerate(fields) if '收盤指數' in x or 'closing index' in x.lower()), None)
    if close_idx is None:
        # Official report contract is Date/Open/High/Low/Close. Keep the fallback
        # narrow and validate values/period below rather than accepting arbitrary columns.
        if len(fields) >= 5:
            close_idx = 4
        else:
            raise ValueError(f'TWSE close-index field missing: {fields}')

    parsed = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) <= max(date_idx, close_idx):
            continue
        iso = roc_date_to_iso(row[date_idx])
        close = numeric(row[close_idx])
        if not iso or close is None:
            continue
        if iso[:7] != expected_period:
            continue
        if not (100 <= close <= 200000):
            raise ValueError(f'TWSE close outside plausible range: {close}')
        parsed.append((iso, close))
    if not parsed:
        raise ValueError(f'TWSE report contained no valid rows for {expected_period}')
    parsed.sort()
    last_date, last_close = parsed[-1]
    return {
        'period': expected_period,
        'last_trading_day': last_date,
        'close': float(last_close),
        'daily_rows': len(parsed),
    }


def fetch_month(period: str):
    y, m = map(int, period.split('-'))
    url = REPORT_URL.format(year=y, month=m)
    body, _ = request_bytes(url, 45, 2)
    row = parse_month_payload(body, period)
    row['source_url'] = url
    return row


def update(offline=None):
    if offline:
        obj = load_json('market_inputs.json', {'series': {}})
        data = ((obj.get('series') or {}).get(SERIES_KEY) or {}).get('data') or []
        return {
            'latest_period': data[-1][0] if data else None,
            'rows': len(data),
            'message': 'TWSE market source skipped in offline mode',
        }

    old = load_json('market_inputs.json', {'series': {}})
    existing_series = ((old.get('series') or {}).get(SERIES_KEY) or {})
    existing = {str(p): float(v) for p, v in (existing_series.get('data') or []) if v is not None}
    metadata = {str(x.get('period')): x for x in (existing_series.get('month_metadata') or []) if x.get('period')}

    end = last_completed_month()
    requested = [p for p in month_range(START_PERIOD, end) if p not in existing]
    failures = []
    fetched = []
    # Initial historical backfill is bounded (~10 years) and parallelized modestly.
    # Subsequent daily refreshes normally request zero or one completed month.
    if requested:
        with ThreadPoolExecutor(max_workers=4) as pool:
            jobs = {pool.submit(fetch_month, p): p for p in requested}
            for future in as_completed(jobs):
                p = jobs[future]
                try:
                    row = future.result()
                    fetched.append(row)
                except Exception as exc:
                    failures.append(f'{p}:{type(exc).__name__}:{exc}')

    for row in fetched:
        existing[row['period']] = row['close']
        metadata[row['period']] = {
            'period': row['period'],
            'last_trading_day': row['last_trading_day'],
            'daily_rows': row['daily_rows'],
            'source_url': row['source_url'],
        }

    data = [[p, existing[p]] for p in sorted(existing) if START_PERIOD <= p <= end]
    meta_rows = [metadata[p] for p in sorted(metadata) if START_PERIOD <= p <= end]
    expected = list(month_range(START_PERIOD, end))
    missing = [p for p in expected if p not in existing]

    # A partial backfill must remain explicit. The v2 market/risk evidence needs a
    # continuous monthly path; do not silently claim a complete backtest if months are missing.
    if missing:
        preview = ','.join(missing[:12])
        detail = '; '.join(failures[:8])
        raise RuntimeError(f'TWSE month-end history incomplete: missing={len(missing)} [{preview}] failures={detail}')
    if len(data) < 36:
        raise ValueError(f'TWSE month-end history too short: {len(data)}')

    obj = {
        'source': 'Taiwan Stock Exchange',
        'generated_at': dt.datetime.now(TZ).replace(microsecond=0).isoformat(),
        'catalog_url': CATALOG_URL,
        'report_page': REPORT_PAGE,
        'latest_period': data[-1][0],
        'series': {
            SERIES_KEY: {
                'name': 'TWSE 發行量加權股價指數－月末收盤',
                'unit': 'index',
                'frequency': 'monthly',
                'aggregation': 'last trading day close of each completed calendar month',
                'data': data,
                'month_metadata': meta_rows,
                'source_contract': 'official TWSE MI_5MINS_HIST daily OHLC; monthly close derived deterministically from last trading row',
            }
        },
        'notes': [
            'Market evidence only; never enters Elephant economic Scores.',
            'Current incomplete calendar month is excluded from the monthly outcome series.',
            'Historical backfill starts at 2016-01 to overlap the current Decision Score validation window.',
        ],
    }
    save_json('market_inputs.json', obj)
    return {
        'latest_period': data[-1][0],
        'rows': len(data),
        'message': f'TWSE official TAIEX month-end closes refreshed; fetched={len(fetched)}, history={len(data)}, failures=0',
    }


if __name__ == '__main__':
    print(update())
