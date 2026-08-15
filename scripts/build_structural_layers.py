#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import math

from common import TZ, load_json, period_key, save_json


def clamp(v, lo=-100.0, hi=100.0):
    return max(lo, min(hi, float(v)))


def value_map(series):
    return {str(p): float(v) for p, v in (series or {}).get('data', []) if v is not None}


def shift(period, delta):
    p = str(period)
    if '-Q' in p:
        try:
            y, q = p.split('-Q')
            idx = int(y) * 4 + int(q) - 1 + delta
            return f'{idx // 4:04d}-Q{idx % 4 + 1}'
        except Exception:
            return None
    try:
        y, m = map(int, p.split('-'))
        idx = y * 12 + m - 1 + delta
        return f'{idx // 12:04d}-{idx % 12 + 1:02d}'
    except Exception:
        return None


def yoy(series, period):
    d = value_map(series)
    prior = shift(period, -4 if '-Q' in str(period) else -12)
    a, b = d.get(str(period)), d.get(prior)
    return None if a is None or b in (None, 0) else (a / b - 1.0) * 100.0


def latest_yoy(series):
    data = (series or {}).get('data', [])
    for p, _ in reversed(data):
        y = yoy(series, str(p))
        if y is not None and math.isfinite(y):
            return y, str(p)
    return None, None


def find_series(series, exact=None, contains=()):
    if exact and exact in series:
        return series[exact], exact
    candidates = []
    for key, item in series.items():
        text = f"{key} {item.get('name','')}".lower()
        hits = sum(1 for token in contains if token.lower() in text)
        if hits:
            candidates.append((hits, len(item.get('data', [])), key, item))
    if not candidates:
        return None, None
    _, _, key, item = max(candidates)
    return item, key


def business_investment(industry, decision_inputs):
    datasets = industry.get('datasets', {})
    inv = datasets.get('moea.manufacturing.investment', {}).get('series', {})
    production = datasets.get('moea.industry.production', {}).get('series', {})
    decision = decision_inputs.get('series', {})

    capex, capex_key = find_series(inv, 'moea.manufacturing.fixed_asset_additions', ('fixed_asset_additions', '固定資產增購'))
    machinery = production.get('29')
    if machinery is None:
        machinery, _ = find_series(production, contains=('機械設備製造業',))
    credit = decision.get('financial.credit')
    if credit is None:
        credit, _ = find_series(decision, contains=('金融機構放款與投資', '銀行信用'))

    parts = []
    raw, period = latest_yoy(capex)
    if raw is not None:
        parts.append({
            'key': 'fixed_asset_additions', 'name': '製造業固定資產增購', 'raw': round(raw, 2),
            'score': round(clamp(raw / 20.0 * 100.0), 2), 'weight': .50, 'period': period,
            'source': 'MOEA', 'source_key': capex_key,
            'note': '季度固定資產增購 YoY；±20% 對應 ±100。',
        })
    raw, period = latest_yoy(machinery)
    if raw is not None:
        parts.append({
            'key': 'machinery_production', 'name': '機械設備製造業生產', 'raw': round(raw, 2),
            'score': round(clamp(raw / 15.0 * 100.0), 2), 'weight': .25, 'period': period,
            'source': 'MOEA', 'source_key': '29',
            'note': '機械設備製造業生產 YoY；±15% 對應 ±100。',
        })
    raw, period = latest_yoy(credit)
    if raw is not None:
        parts.append({
            'key': 'bank_credit', 'name': '銀行信用', 'raw': round(raw, 2),
            'score': round(clamp(raw / 10.0 * 100.0), 2), 'weight': .25, 'period': period,
            'source': 'CBC', 'source_key': 'financial.credit',
            'note': '金融機構放款與投資 YoY；±10% 對應 ±100。',
        })

    coverage = sum(x['weight'] for x in parts)
    if coverage < .50:
        return {
            'status': 'BLOCKED_EVIDENCE',
            'question': '企業是在擴產，還是只是在消化既有需求？',
            'score': None,
            'confidence': round(coverage * 100),
            'components': parts,
            'missing_contract': ['製造業固定資產增購', '機械設備生產', '銀行信用'],
        }
    score = sum(x['score'] * x['weight'] for x in parts) / coverage
    label = '強勁擴產' if score >= 60 else '擴產' if score >= 25 else '中性' if score > -25 else '縮減投資' if score > -60 else '明顯縮減投資'
    return {
        'status': 'READY',
        'question': '企業是在擴產，還是只是在消化既有需求？',
        'score': round(score, 2),
        'label': label,
        'confidence': round(coverage * 100),
        'components': parts,
        'methodology': {
            'weights': {'fixed_asset_additions': .50, 'machinery_production': .25, 'bank_credit': .25},
            'missing': '缺值重新正規化；coverage < 50% 不發布 score。',
            'frequency_note': '季度 capex 與月度 machinery/credit 並列，component 各自保留實際來源期。',
        },
    }


def external_demand(decision_scores):
    growth = decision_scores.get('current', {}).get('growth_persistence', {})
    transmission = []
    for item in growth.get('components', []):
        if item.get('key') in ('orders', 'exports'):
            transmission.append({k: item.get(k) for k in ('key', 'name', 'raw', 'period', 'source')})
    return {
        'status': 'BLOCKED_UPSTREAM',
        'question': '台灣景氣的全球上游需求正在加速還是轉弱？',
        'score': None,
        'reason': '台灣外銷訂單與出口是 transmission signals，不等於全球上游需求本身；在全球半導體週期、主要終端需求/資本支出與主要市場製造業訊號未形成穩定官方/一手資料鏈前不發布假 score。',
        'available_downstream_transmission': transmission,
        'required_contract': [
            'global semiconductor / electronics cycle',
            'US end-demand or capex',
            'China end-demand',
            'global manufacturing demand',
            'trade / freight breadth',
        ],
    }


def regional_vitality(population, status):
    # National population data is already production-grade; the score itself is
    # intentionally blocked until city-level economic activity has broad coverage.
    available = []
    if population.get('national') or population.get('cities') or population.get('counties'):
        available.append('population')
    segis = status.get('sources', {}).get('segis', {})
    if segis.get('status') == 'ok':
        available.append('new_companies_or_establishments')
    required = ['population', 'card_spending', 'new_companies', 'housing_transactions', 'house_prices', 'electricity']
    return {
        'status': 'BLOCKED_EVIDENCE',
        'question': '哪些城市真的在變強？',
        'score': None,
        'available': available,
        'required_contract': required,
        'minimum_publish_rule': '至少 4/6 個 city-level official components 可驗證且 period alignment 合格，才允許發布區域排名；否則只顯示 readiness。',
        'reason': '目前 city-level economic-activity breadth 不足；不以全國數字或單一房價指標替代區域活力。',
    }


def generate():
    industry = load_json('industry.json', {})
    decision_inputs = load_json('decision_inputs.json', {})
    decision_scores = load_json('decision_scores.json', {})
    population = load_json('population.json', {})
    status = load_json('status.json', {})

    out = {
        'version': 1,
        'generated_at': dt.datetime.now(TZ).replace(microsecond=0).isoformat(),
        'contract': 'evidence-gated-structural-layers-v1',
        'layers': {
            'external_demand': external_demand(decision_scores),
            'business_investment': business_investment(industry, decision_inputs),
            'regional_vitality': regional_vitality(population, status),
        },
        'principle': 'A structural layer may be READY, BLOCKED_UPSTREAM, or BLOCKED_EVIDENCE. Missing causal evidence is never converted into a numeric score.',
    }
    save_json('structural_layers.json', out)
    return out


if __name__ == '__main__':
    generate()
