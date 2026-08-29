#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from common import decode_text, num, period_key, request_bytes, save_json

DGBAS_META = {
    'headline_cpi': 'https://data.gov.tw/api/v2/rest/dataset/6019',
    'core_cpi': 'https://data.gov.tw/api/v2/rest/dataset/8237',
    'ppi': 'https://data.gov.tw/api/v2/rest/dataset/148439',
}
CBC_M2_PAGES = [
    'https://www.cbc.gov.tw/tw/lp-643-1.html',
    'https://www.cbc.gov.tw/tw/lp-643-1-2-20.html',
]
CBC_RATE_PAGES = ['https://www.cbc.gov.tw/tw/lp-640-1-1-60.html']


def _local(tag):
    return str(tag).split('}', 1)[-1]


def _resolve_resource(meta_url: str, dataset_id: str) -> str:
    obj = json.loads(decode_text(request_bytes(meta_url)[0]))
    urls = []

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, str) and x.startswith('http') and ('.xml' in x.lower() or 'download' in x.lower()):
            urls.append(x.replace('\\/', '/'))

    walk(obj)
    if not urls:
        raise RuntimeError(f'data.gov dataset {dataset_id}: resource URL not found')
    urls.sort(key=lambda u: ('.xml' not in u.lower(), len(u)))
    return urls[0]


def _month(raw):
    s = str(raw or '').strip().upper().replace('/', '').replace('-', '').replace('.', '')
    m = re.fullmatch(r'(\d{4})(\d{2})', s)
    if m:
        return f'{int(m.group(1)):04d}-{int(m.group(2)):02d}'
    m = re.fullmatch(r'(\d{3})M?(\d{2})', s)
    if m:
        return f'{int(m.group(1)) + 1911:04d}-{int(m.group(2)):02d}'
    return None


def _xml_rows(body: bytes):
    root = ET.fromstring(body)
    rows = []
    for node in root.iter():
        fields = {}
        for child in list(node):
            key = _local(child.tag)
            if key in {'Item', 'TIME_PERIOD', 'FREQ', 'TYPE', 'Item_VALUE'}:
                fields[key] = ''.join(child.itertext()).strip()
        if {'Item', 'TIME_PERIOD', 'Item_VALUE'} <= set(fields):
            rows.append(fields)
    if not rows:
        raise ValueError('DGBAS XML rows not found')
    return rows


def _dedup(data):
    out = {}
    for p, v in data:
        if p and v is not None:
            out[p] = float(v)
    return [[p, out[p]] for p in sorted(out, key=period_key)]


def _yoy_from_index(data):
    vals = dict(data)
    out = []
    for p, value in data:
        y, m = map(int, p.split('-'))
        prior = vals.get(f'{y - 1:04d}-{m:02d}')
        if prior not in (None, 0):
            out.append([p, (float(value) / float(prior) - 1.0) * 100.0])
    return out


def _select_dgbas_yoy(body: bytes, item_re: str):
    rows = _xml_rows(body)
    matched = [r for r in rows if re.search(item_re, r.get('Item', ''), re.I)]
    if not matched:
        sample = ', '.join(sorted({r.get('Item', '') for r in rows})[:12])
        raise ValueError(f'DGBAS target item not found; sample={sample}')
    yoy, level = [], []
    for r in matched:
        p, v = _month(r.get('TIME_PERIOD')), num(r.get('Item_VALUE'))
        if not p or v is None:
            continue
        typ, freq = r.get('TYPE', ''), r.get('FREQ', '')
        if freq and str(freq).upper() not in {'M', 'MONTH', 'MONTHLY', '月'}:
            continue
        if re.search(r'年增|YOY|同期', typ, re.I):
            yoy.append([p, v])
        elif not typ or re.search(r'原始|指數|INDEX|VALUE', typ, re.I):
            level.append([p, v])
    yoy = _dedup(yoy)
    if len(yoy) >= 12:
        return yoy
    derived = _yoy_from_index(_dedup(level))
    if len(derived) < 12:
        raise ValueError(f'DGBAS monthly history too short: yoy={len(yoy)} level={len(level)}')
    return derived


def parse_headline_cpi(body: bytes):
    try:
        data = _select_dgbas_yoy(body, r'^總指數$')
    except ValueError:
        data = _select_dgbas_yoy(body, r'總指數')
    return {'dgbas.cpi.monthly_yoy': {'name': '消費者物價指數年增率（月）', 'unit': 'percent', 'frequency': 'monthly', 'dataset_id': 'data.gov.tw/6019', 'data': data}}


def parse_core_cpi(body: bytes):
    data = _select_dgbas_yoy(body, r'核心')
    return {'dgbas.cpi.core_yoy': {'name': '核心消費者物價指數年增率', 'unit': 'percent', 'frequency': 'monthly', 'dataset_id': 'data.gov.tw/8237', 'data': data}}


def parse_ppi(body: bytes):
    try:
        data = _select_dgbas_yoy(body, r'^(總指數|生產者物價總指數)$')
    except ValueError:
        data = _select_dgbas_yoy(body, r'總指數|生產者物價')
    return {'dgbas.ppi.yoy': {'name': '生產者物價指數年增率', 'unit': 'percent', 'frequency': 'monthly', 'dataset_id': 'data.gov.tw/148439', 'data': data}}


def parse_cbc_m2(text: str):
    plain = re.sub(r'<[^>]+>', ' ', text)
    pairs = re.findall(r'(20\d{2})[./-](\d{2})\s+([+-]?\d+(?:\.\d+)?)', plain)
    data = _dedup([[f'{int(y):04d}-{int(m):02d}', float(v)] for y, m, v in pairs])
    if len(data) < 12:
        raise ValueError(f'CBC M2 history too short: {len(data)}')
    return {'cbc.m2.yoy': {'name': '貨幣總計數 M2 年增率', 'unit': 'percent', 'frequency': 'monthly', 'dataset_id': 'cbc.lp-643', 'data': data}}


def parse_cbc_rates(text: str):
    plain = re.sub(r'<[^>]+>', ' ', text)
    pairs = re.findall(r'(20\d{2})/(\d{1,2})/(\d{1,2})\s+([0-9]+(?:\.[0-9]+)?)', plain)
    data = _dedup([[f'{int(y):04d}-{int(m):02d}', float(rate)] for y, m, _d, rate in pairs])
    if not data:
        raise ValueError('CBC discount-rate history empty')
    return {'cbc.discount_rate': {'name': '中央銀行重貼現率', 'unit': 'percent', 'frequency': 'event/month', 'dataset_id': 'cbc.lp-640', 'data': data}}


def _offline(path: Path | None, name: str):
    if path is None:
        return None
    p = path / name
    if not p.exists():
        raise FileNotFoundError(p)
    return p.read_bytes()


def update(offline=None):
    offline = Path(offline) if offline else None
    if offline:
        headline_body = _offline(offline, 'regime_headline_cpi.xml')
        core_body = _offline(offline, 'regime_core_cpi.xml')
        ppi_body = _offline(offline, 'regime_ppi.xml')
        m2_text = decode_text(_offline(offline, 'regime_cbc_m2.html'))
        rate_text = decode_text(_offline(offline, 'regime_cbc_rates.html'))
    else:
        headline_body = request_bytes(_resolve_resource(DGBAS_META['headline_cpi'], '6019'))[0]
        core_body = request_bytes(_resolve_resource(DGBAS_META['core_cpi'], '8237'))[0]
        ppi_body = request_bytes(_resolve_resource(DGBAS_META['ppi'], '148439'))[0]
        m2_text = '\n'.join(decode_text(request_bytes(u)[0]) for u in CBC_M2_PAGES)
        rate_text = '\n'.join(decode_text(request_bytes(u)[0]) for u in CBC_RATE_PAGES)

    series = {}
    series.update(parse_headline_cpi(headline_body))
    series.update(parse_core_cpi(core_body))
    series.update(parse_ppi(ppi_body))
    series.update(parse_cbc_m2(m2_text))
    series.update(parse_cbc_rates(rate_text))
    latest = max((s['data'][-1][0] for s in series.values() if s.get('data')), key=period_key)
    out = {'generated_from': 'first_party_official_sources', 'contract': 'macro-regime-official-v1', 'series': series, 'latest_period': latest}
    save_json('regime_official.json', out)
    return {'latest_period': latest, 'rows': sum(len(s['data']) for s in series.values()), 'message': 'DGBAS monthly headline/core CPI/PPI + CBC M2/discount rate refreshed'}


if __name__ == '__main__':
    print(update())
