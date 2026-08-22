#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import math
import re
from pathlib import Path
from urllib.parse import urljoin

from common import URLS, decode_text, request_bytes, save_json

DATASET_ID = 'segis.business_count.township'
EXPECTED_TITLE = '114年12月行政區工商家數_鄉鎮市區'
REQUIRED_PAGE_FIELDS = ('工商業總家數', '鄉鎮市區代碼', '鄉鎮市區名稱', '縣市代碼', '縣市名稱')
REQUIRED_ROW_FIELDS = ('INFO_TIME', 'COUNTY_ID', 'COUNTY', 'TOWN_ID', 'TOWN', 'C_CNT')


def visible_text(raw: str) -> str:
    raw = re.sub(r'<script\b[^>]*>.*?</script>', ' ', raw, flags=re.I | re.S)
    raw = re.sub(r'<style\b[^>]*>.*?</style>', ' ', raw, flags=re.I | re.S)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', raw))).strip()


def extract_json_service_url(raw: str, base_url: str | None = None) -> str:
    decoded = html.unescape(raw)
    match = re.search(
        r'''data-url=["']([^"']+GetAdminSTDataForOpenCode\?oCode=[^"']+)["'][^>]*>\s*JSON\b''',
        decoded,
        flags=re.I | re.S,
    )
    if not match:
        raise ValueError('SEGIS JSON service URL not found in canonical product page')
    return urljoin(base_url or URLS['segis_catalog'], match.group(1).replace('&amp;', '&'))


def validate_catalog(raw: str) -> str:
    text = visible_text(raw)
    if EXPECTED_TITLE not in text:
        raise ValueError(f'SEGIS target drifted; expected {EXPECTED_TITLE}')
    if '是否對外公開' not in text or '公開' not in text:
        raise ValueError('SEGIS product is not explicitly public')
    if '是否需申請' not in text or '不需申請' not in text:
        raise ValueError('SEGIS product unexpectedly requires application')
    if '開放服務連結' not in text or 'JSON' not in text:
        raise ValueError('SEGIS product no longer advertises JSON service')
    missing = [field for field in REQUIRED_PAGE_FIELDS if field not in text]
    if missing:
        raise ValueError(f'SEGIS catalog fields missing: {missing}')
    return extract_json_service_url(raw)


def roc_month(value: object) -> str:
    match = re.fullmatch(r'\s*(\d{2,3})Y(\d{1,2})M\s*', str(value or ''), flags=re.I)
    if not match:
        raise ValueError(f'unsupported SEGIS INFO_TIME: {value!r}')
    year = int(match.group(1)) + 1911
    month = int(match.group(2))
    if not 1 <= month <= 12:
        raise ValueError(f'invalid SEGIS month: {month}')
    return f'{year:04d}-{month:02d}'


def finite_nonnegative(value: object, name: str) -> float:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) < 0:
        raise ValueError(f'invalid {name}: {value!r}')
    return float(value)


def normalize_payload(payload: object, catalog_url: str, service_url: str) -> dict:
    if not isinstance(payload, dict):
        raise ValueError('SEGIS payload must be an object')
    info = payload.get('Info')
    columns = payload.get('ColumnList')
    raw_rows = payload.get('RowDataList')
    if not isinstance(info, list) or not info or not isinstance(columns, list) or not isinstance(raw_rows, list):
        raise ValueError('SEGIS payload missing Info/ColumnList/RowDataList arrays')
    if len(raw_rows) < 300 or len(raw_rows) > 500:
        raise ValueError(f'implausible SEGIS township row count: {len(raw_rows)}')
    declared = str((info[0] or {}).get('OutTotal', '')).strip()
    if not declared.isdigit() or int(declared) != len(raw_rows):
        raise ValueError(f'SEGIS OutTotal mismatch: {declared!r} vs {len(raw_rows)}')

    column_names = {str(row.get('COLUMN_NAME')) for row in columns if isinstance(row, dict) and row.get('COLUMN_NAME')}
    missing_columns = [name for name in REQUIRED_ROW_FIELDS if name not in column_names]
    if missing_columns:
        raise ValueError(f'SEGIS machine columns missing: {missing_columns}')

    rows = []
    seen_towns = set()
    periods = set()
    counties = set()
    for raw in raw_rows:
        if not isinstance(raw, dict):
            raise ValueError('SEGIS RowDataList contains non-object row')
        missing = [name for name in REQUIRED_ROW_FIELDS if name not in raw]
        if missing:
            raise ValueError(f'SEGIS row missing fields: {missing}')
        period = roc_month(raw.get('INFO_TIME'))
        county_id = str(raw.get('COUNTY_ID') or '').strip()
        county = str(raw.get('COUNTY') or '').strip()
        town_id = str(raw.get('TOWN_ID') or '').strip()
        town = str(raw.get('TOWN') or '').strip()
        if not county_id or not county or not town_id or not town:
            raise ValueError(f'SEGIS row has blank administrative identity: {raw!r}')
        if town_id in seen_towns:
            raise ValueError(f'duplicate SEGIS TOWN_ID: {town_id}')
        seen_towns.add(town_id)
        periods.add(period)
        counties.add(county_id)
        counts = {}
        for key, value in raw.items():
            if str(key).endswith('_CNT') and value is not None:
                counts[str(key)] = finite_nonnegative(value, str(key))
        business_count = finite_nonnegative(raw.get('C_CNT'), 'C_CNT')
        rows.append({
            'period': period,
            'county_id': county_id,
            'county': county,
            'town_id': town_id,
            'town': town,
            'business_count': business_count,
            'category_counts': counts,
        })

    if len(periods) != 1:
        raise ValueError(f'SEGIS snapshot contains mixed periods: {sorted(periods)}')
    latest_period = next(iter(periods))
    rows.sort(key=lambda row: (row['county_id'], row['town_id']))
    return {
        'version': 1,
        'dataset_id': DATASET_ID,
        'dataset_title': EXPECTED_TITLE,
        'latest_period': latest_period,
        'source': {
            'authority': '內政部社會經濟資料服務平台（SEGIS）',
            'catalog_url': catalog_url,
            'json_service_url': service_url,
            'public': True,
            'application_required': False,
        },
        'row_count': len(rows),
        'county_count': len(counties),
        'columns': columns,
        'rows': rows,
        'contract': {
            'role': 'STRUCTURAL_CONTEXT_ONLY',
            'deterministic_score_influence': False,
            'row_identity': 'town_id',
            'business_count_field': 'C_CNT',
            'period_field': 'INFO_TIME',
        },
        'note': 'Official township/district business-count snapshot. Administrative coverage follows the source product; missing geography is not imputed.',
    }


def _offline_payload(offline_dir: Path) -> tuple[str, object]:
    path = Path(offline_dir) / 'segis.json'
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding='utf-8'))
    return 'offline://segis.json', payload


def update(offline_dir: Path | None = None):
    catalog_url = URLS['segis_catalog']
    if offline_dir:
        service_url, payload = _offline_payload(offline_dir)
    else:
        catalog_raw = decode_text(request_bytes(catalog_url, 60, 2)[0])
        service_url = validate_catalog(catalog_raw)
        payload_bytes, _ = request_bytes(service_url, 90, 2)
        payload = json.loads(decode_text(payload_bytes))
    normalized = normalize_payload(payload, catalog_url, service_url)
    save_json('segis.json', normalized)
    return {
        'latest_period': normalized['latest_period'],
        'rows': normalized['row_count'],
        'message': f"SEGIS official public JSON synced: {normalized['row_count']} township/district rows ({normalized['latest_period']}); structural context only.",
        'source_url': catalog_url,
        'json_service_url': service_url,
    }


if __name__ == '__main__':
    print(json.dumps(update(), ensure_ascii=False, indent=2))
