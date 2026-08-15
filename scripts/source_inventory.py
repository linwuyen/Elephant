#!/usr/bin/env python3
from __future__ import annotations

import re

from common import decode_text, load_json, num, period_key, request_bytes, save_json
from source_decision import dedup
from source_moea import RowsParser

INVENTORY_LIVE_URL = 'https://service.moea.gov.tw/EE521/common/Common.aspx?code=D&no=6'
INVENTORY_CATALOG = 'https://data.gov.tw/dataset/109753'


def parse_live_inventory_page(body: bytes, min_observations: int = 13):
    """Parse MOEA's official manufacturing-inventory table.

    The open-data CSV is explicitly "by major industry" and may not expose the
    total-manufacturing row.  MOEA's current statistics table publishes the same
    inventory-index family with 製造業 as the first numeric series.  We consume
    that published total directly instead of synthesising it from sub-industries.
    """
    text = decode_text(body)
    compact = re.sub(r'\s+', '', text)
    if '製造業存貨指數' not in compact or '110年=100' not in compact:
        raise ValueError('MOEA live inventory page signature changed')

    parser = RowsParser()
    parser.feed(text)
    current_year = None
    data = []
    for row in parser.rows:
        # Annual/partial-year rows establish the ROC year for following monthly rows.
        for cell in row:
            m = re.fullmatch(r'(\d{3})年', re.sub(r'\s+', '', cell))
            if m:
                current_year = int(m.group(1)) + 1911
                break

        month_index = next(
            (
                i
                for i, cell in enumerate(row)
                if re.fullmatch(r'\d{1,2}月', re.sub(r'\s+', '', cell))
            ),
            None,
        )
        if month_index is None or current_year is None:
            continue

        month = int(re.sub(r'\D', '', row[month_index]))
        values = [v for v in (num(cell) for cell in row[month_index + 1 :]) if v is not None]
        if not values:
            continue
        # Official table header order: 製造業 total, then four-major/mid industries.
        data.append([f'{current_year:04d}-{month:02d}', float(values[0])])

    data = dedup(data)
    if len(data) < min_observations:
        raise ValueError(f'MOEA live manufacturing inventory history too short: {len(data)}')
    if not all(0 < float(v) < 1000 for _, v in data[-24:]):
        raise ValueError('MOEA live manufacturing inventory values outside plausible index range')

    return {
        'name': '製造業 / 存貨指數',
        'unit': 'index_2021_100',
        'data': data,
        'selection': 'MOEA current statistics table / 製造業 total (first published series)',
        'layout': 'official_live_table',
        'catalog': INVENTORY_CATALOG,
        'source_url': INVENTORY_LIVE_URL,
    }


def update(offline=None):
    if offline:
        return {
            'latest_period': load_json('decision_inputs.json', {}).get('latest_period'),
            'rows': 0,
            'message': 'inventory live source skipped in offline mode',
        }

    body = request_bytes(INVENTORY_LIVE_URL, 75, 2)[0]
    incoming = parse_live_inventory_page(body)

    obj = load_json('decision_inputs.json', {'series': {}, 'catalogs': {}})
    series = dict(obj.get('series', {}))
    series['inventory.manufacturing_index'] = incoming
    obj['series'] = series

    catalogs = dict(obj.get('catalogs', {}))
    catalogs['inventory_manufacturing_live'] = INVENTORY_CATALOG
    obj['catalogs'] = catalogs

    obj['latest_period'] = max(
        (s['data'][-1][0] for s in series.values() if s.get('data')),
        key=period_key,
        default=obj.get('latest_period'),
    )
    notes = list(obj.get('supplement_notes', []))
    note = 'MOEA manufacturing total inventory index is sourced directly from the official current-statistics table; sub-industries are never composited into a synthetic total.'
    if note not in notes:
        notes.append(note)
    obj['supplement_notes'] = notes[-20:]
    save_json('decision_inputs.json', obj)

    return {
        'latest_period': incoming['data'][-1][0],
        'rows': len(incoming['data']),
        'message': 'MOEA official manufacturing total inventory index refreshed from current statistics table',
    }


if __name__ == '__main__':
    print(update())
