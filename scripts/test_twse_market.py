#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json

import source_twse_market as twse

payload = {
    'stat': 'OK',
    'fields': ['日期', '開盤指數', '最高指數', '最低指數', '收盤指數'],
    'data': [
        ['115/07/01', '46,234.70', '47,293.10', '46,234.70', '47,018.99'],
        ['115/07/30', '46,000.00', '46,500.00', '45,800.00', '46,100.00'],
        ['115/07/31', '46,100.00', '46,900.00', '46,050.00', '46,777.77'],
    ],
}
row = twse.parse_month_payload(json.dumps(payload, ensure_ascii=False).encode(), '2026-07')
assert row['period'] == '2026-07'
assert row['last_trading_day'] == '2026-07-31'
assert row['close'] == 46777.77
assert row['daily_rows'] == 3
assert twse.roc_date_to_iso('115/07/01') == '2026-07-01'
assert twse.last_completed_month(dt.datetime(2026, 8, 15, tzinfo=twse.TZ)) == '2026-07'
assert list(twse.month_range('2026-05', '2026-07')) == ['2026-05', '2026-06', '2026-07']

# The current/incomplete calendar month is deliberately not a monthly outcome.
assert twse.last_completed_month(dt.datetime(2026, 1, 2, tzinfo=twse.TZ)) == '2025-12'

# Wrong period and malformed status fail closed.
try:
    twse.parse_month_payload(json.dumps(payload, ensure_ascii=False).encode(), '2026-06')
except ValueError as exc:
    assert 'no valid rows' in str(exc)
else:
    raise AssertionError('TWSE payload from another month must not be accepted')

bad = dict(payload); bad['stat'] = '查詢日期大於今日'
try:
    twse.parse_month_payload(json.dumps(bad, ensure_ascii=False).encode(), '2026-07')
except ValueError as exc:
    assert 'not OK' in str(exc)
else:
    raise AssertionError('TWSE non-OK status must fail closed')

print('TWSE MARKET TEST PASS')
