#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json

import source_twse_market_live as twse


def payload(stat='OK', rows=None, fields=None):
    fields = fields or ['日期', '開盤指數', '最高指數', '最低指數', '收盤指數']
    rows = rows if rows is not None else [
        ['115/07/01', '23,000.00', '23,200.00', '22,900.00', '23,100.00'],
        ['115/07/30', '23,500.00', '23,700.00', '23,400.00', '23,650.25'],
        ['115/07/31', '23,700.00', '23,800.00', '23,600.00', '23,777.77'],
    ]
    return json.dumps({'stat': stat, 'fields': fields, 'data': rows}, ensure_ascii=False).encode('utf-8')


row = twse.parse_month_payload(payload(), '2026-07')
assert row['period'] == '2026-07'
assert row['last_trading_day'] == '2026-07-31'
assert row['close'] == 23777.77
assert row['daily_rows'] == 3
assert twse.roc_date_to_iso('115/07/31') == '2026-07-31'
assert twse.roc_date_to_iso('bad') is None

# Rows from another month cannot satisfy the requested-period contract.
try:
    twse.parse_month_payload(payload(rows=[['115/06/30', '1', '1', '1', '22000']]), '2026-07')
except ValueError as exc:
    assert 'no valid rows' in str(exc)
else:
    raise AssertionError('cross-month TWSE row was accepted')

for bad in (
    payload(stat='ERROR'),
    payload(rows=[]),
):
    try:
        twse.parse_month_payload(bad, '2026-07')
    except ValueError:
        pass
    else:
        raise AssertionError('invalid TWSE payload must fail closed')

# Fixed-clock contract: on 2026-08-16 the latest completed month is 2026-07.
fixed = dt.datetime(2026, 8, 16, 0, 45, tzinfo=twse.TZ)
assert twse.last_completed_month(fixed) == '2026-07'

print('TWSE LIVE MARKET TEST PASS')
