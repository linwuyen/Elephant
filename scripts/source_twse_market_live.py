#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed

from common import TZ, load_json, request_bytes, save_json

REPORT_URL = 'https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={year:04d}{month:02d}01'
REPORT_PAGE = 'https://www.twse.com.tw/indicesReport/MI_5MINS_HIST'
SERIES_KEY = 'twse.taiex_month_end'
LOOKBACK_MONTHS = 9


def month_shift(period: str, delta: int) -> str:
    y, m = map(int, period.split('-'))
    idx = y * 12 + m - 1 + delta
    return f'{idx // 12:04d}-{idx % 12 + 1:02d}'


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
        if not iso or close is None or iso[:7] != expected_period:
            continue
        if not (100 <= close <= 200000):
            raise ValueError(f'TWSE close outside plausible range: {close}')
        parsed.append((iso, close))
    if not parsed:
        raise ValueError(f'TWSE report contained no valid rows for {expected_period}')
    parsed.sort()
    last_date, last_close = parsed[-1]
    return {'period': expected_period, 'last_trading_day': last_date, 'close': float(last_close), 'daily_rows': len(parsed)}


def fetch_month(period: str):
    y, m = map(int, period.split('-'))
    body, _ = request_bytes(REPORT_URL.format(year=y, month=m), 45, 2)
    return parse_month_payload(body, period)


def update(offline=None):
    if offline:
        old = load_json('market_live.json', {'series': {}})
        data = ((old.get('series') or {}).get(SERIES_KEY) or {}).get('data') or []
        return {'latest_period': data[-1][0] if data else None, 'rows': len(data), 'message': 'TWSE live market source skipped in offline mode'}

    end = last_completed_month()
    periods = [month_shift(end, -i) for i in range(LOOKBACK_MONTHS - 1, -1, -1)]
    fetched, failures = [], []
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = {pool.submit(fetch_month, p): p for p in periods}
        for future in as_completed(jobs):
            p = jobs[future]
            try:
                fetched.append(future.result())
            except Exception as exc:
                failures.append(f'{p}:{type(exc).__name__}:{exc}')
    rows = {x['period']: x for x in fetched}
    missing = [p for p in periods if p not in rows]
    if missing:
        raise RuntimeError(f'TWSE live market window incomplete: missing={missing}; failures={failures[:5]}')
    data = [[p, rows[p]['close']] for p in periods]
    metadata = [{k: rows[p][k] for k in ('period', 'last_trading_day', 'daily_rows')} for p in periods]
    obj = {
        'source': 'Taiwan Stock Exchange',
        'generated_at': dt.datetime.now(TZ).replace(microsecond=0).isoformat(),
        'latest_period': end,
        'report_page': REPORT_PAGE,
        'series': {
            SERIES_KEY: {
                'name': 'TWSE 發行量加權股價指數－近期月末收盤',
                'unit': 'index',
                'frequency': 'monthly',
                'data': data,
                'month_metadata': metadata,
                'source_contract': 'official TWSE MI_5MINS_HIST daily OHLC; last trading-day close for each completed calendar month',
            }
        },
        'role': 'Risk Budget v2 current market-state freshness only; historical calibration remains NDC stock_index.',
    }
    save_json('market_live.json', obj)
    return {'latest_period': end, 'rows': len(data), 'message': f'TWSE current market window refreshed through {end} ({len(data)} months)'}


if __name__ == '__main__':
    print(update())
