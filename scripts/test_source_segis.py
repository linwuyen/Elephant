#!/usr/bin/env python3
from __future__ import annotations

import source_segis


def columns():
    return [
        {'COLUMN_NAME': name, 'DATA_TYPE': '文字' if not name.endswith('_CNT') else '數值', 'COLUMN_DESC': name, 'DISPLAY_UNIT': None}
        for name in (*source_segis.REQUIRED_ROW_FIELDS, 'C1_A_CNT')
    ]


def payload(count=300):
    rows = []
    for i in range(count):
        rows.append({
            'INFO_TIME': '114Y12M',
            'COUNTY_ID': f'{(i // 20) + 1:05d}',
            'COUNTY': f'縣市{i // 20}',
            'TOWN_ID': f'{i + 1:08d}',
            'TOWN': f'行政區{i}',
            'C_CNT': float(i + 10),
            'C1_A_CNT': float(i % 7),
        })
    return {'Info': [{'OutTotal': str(count)}], 'ColumnList': columns(), 'RowDataList': rows}


def expect_error(fn, text):
    try:
        fn()
    except ValueError as exc:
        assert text in str(exc), (text, str(exc))
        return
    raise AssertionError(f'expected ValueError containing {text!r}')


def main():
    normalized = source_segis.normalize_payload(payload(), 'catalog', 'service')
    assert normalized['version'] == 1
    assert normalized['dataset_id'] == source_segis.DATASET_ID
    assert normalized['latest_period'] == '2025-12'
    assert normalized['row_count'] == 300
    assert normalized['contract']['deterministic_score_influence'] is False
    assert normalized['rows'][0]['business_count'] >= 0
    assert normalized['rows'][0]['category_counts']['C1_A_CNT'] >= 0
    assert normalized['rows'][0]['period'] == '2025-12'

    duplicate = payload()
    duplicate['RowDataList'][1]['TOWN_ID'] = duplicate['RowDataList'][0]['TOWN_ID']
    expect_error(lambda: source_segis.normalize_payload(duplicate, 'catalog', 'service'), 'duplicate SEGIS TOWN_ID')

    wrong_total = payload()
    wrong_total['Info'][0]['OutTotal'] = '999'
    expect_error(lambda: source_segis.normalize_payload(wrong_total, 'catalog', 'service'), 'OutTotal mismatch')

    mixed = payload()
    mixed['RowDataList'][-1]['INFO_TIME'] = '114Y11M'
    expect_error(lambda: source_segis.normalize_payload(mixed, 'catalog', 'service'), 'mixed periods')

    negative = payload()
    negative['RowDataList'][0]['C_CNT'] = -1
    expect_error(lambda: source_segis.normalize_payload(negative, 'catalog', 'service'), 'invalid C_CNT')

    html = '''<html><body>114年12月行政區工商家數_鄉鎮市區 是否對外公開 公開 是否需申請 不需申請 開放服務連結
      工商業總家數 鄉鎮市區代碼 鄉鎮市區名稱 縣市代碼 縣市名稱
      <a class="col-4 list-group-item" data-url="https://example.test/GetAdminSTDataForOpenCode?oCode=abc">JSON</a>
    </body></html>'''
    assert source_segis.validate_catalog(html) == 'https://example.test/GetAdminSTDataForOpenCode?oCode=abc'
    print('SEGIS SOURCE TEST PASS')


if __name__ == '__main__':
    main()
