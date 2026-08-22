#!/usr/bin/env python3
from __future__ import annotations

import json

from common import URLS, decode_text, request_bytes
import source_segis


def main():
    catalog_url = URLS['segis_catalog']
    catalog_raw = decode_text(request_bytes(catalog_url, 60, 2)[0])
    service_url = source_segis.validate_catalog(catalog_raw)
    payload_bytes, _ = request_bytes(service_url, 90, 2)
    payload = json.loads(decode_text(payload_bytes))
    normalized = source_segis.normalize_payload(payload, catalog_url, service_url)

    assert normalized['dataset_title'] == source_segis.EXPECTED_TITLE
    assert normalized['latest_period'] == '2025-12'
    assert normalized['row_count'] == len(normalized['rows'])
    assert normalized['row_count'] >= 300
    assert normalized['county_count'] >= 15
    assert normalized['source']['public'] is True
    assert normalized['source']['application_required'] is False
    assert normalized['contract']['deterministic_score_influence'] is False
    assert all(row['business_count'] >= 0 for row in normalized['rows'])
    assert len({row['town_id'] for row in normalized['rows']}) == normalized['row_count']

    print('SEGIS PUBLIC MACHINE CONTRACT PASS')
    print('period:', normalized['latest_period'])
    print('township rows:', normalized['row_count'])
    print('counties represented:', normalized['county_count'])
    print('json service:', service_url)


if __name__ == '__main__':
    main()
