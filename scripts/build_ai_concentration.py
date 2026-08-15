#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt

from common import TZ, load_json, period_key, save_json

WEIGHTS = {
    'electronic_orders': .30,
    'ai_core_exports': .30,
    'electronic_production': .25,
    'non_electronic_breadth': .15,
}


def clamp(v, lo=0, hi=100):
    return max(lo, min(hi, float(v)))


def month_shift(p, d):
    try:
        y, m = map(int, str(p).split('-'))
    except Exception:
        return None
    i = y * 12 + m - 1 + d
    return f'{i // 12:04d}-{i % 12 + 1:02d}'


def vmap(s):
    return {str(p): float(v) for p, v in (s or {}).get('data', []) if v is not None}


def value(s, p):
    return vmap(s).get(p)


def yoy(s, p):
    a, b = value(s, p), value(s, month_shift(p, -12))
    return None if a is None or b in (None, 0) else (a / b - 1) * 100


def latest_before(s, p, lag=2):
    m = vmap(s)
    for i in range(lag + 1):
        q = month_shift(p, -i)
        if q in m:
            return m[q], q
    return None, None


def name_of(key, s):
    return f"{key} {str((s or {}).get('name', ''))}".lower()


def find_one(series, prefix, include, exclude=()):
    cand = []
    for key, s in series.items():
        if prefix and not key.startswith(prefix):
            continue
        text = name_of(key, s)
        if any(x.lower() in text for x in exclude):
            continue
        hits = sum(1 for x in include if x.lower() in text)
        if not hits:
            continue
        bonus = 4 if any(x in text for x in ('總計', '總額', '合計', 'total')) else 0
        cand.append((hits + bonus, len(s.get('data', [])), -len(text), key, s))
    return max(cand, default=(0, 0, 0, None, None))[4]


def find_many(series, prefix, groups):
    out = []
    used = set()
    for include in groups:
        s = find_one(series, prefix, include)
        if s and id(s) not in used:
            used.add(id(s))
            out.append(s)
    return out


def combine(series_list, p):
    vals, periods = [], []
    for s in series_list:
        v, q = latest_before(s, p, 1)
        if v is not None:
            vals.append(v)
            periods.append(q)
    if not vals:
        return None, None
    return sum(vals), min(periods)


def label(score):
    if score >= 75:
        return '高度集中'
    if score >= 60:
        return '偏高集中'
    if score >= 40:
        return '中度集中'
    if score >= 25:
        return '較分散'
    return '高度分散'


def component(key, name, raw, score, weight, period, note, source):
    if raw is None or score is None:
        return None
    return {
        'key': key,
        'name': name,
        'raw': round(float(raw), 2),
        'score': round(clamp(score), 2),
        'weight': weight,
        'period': period,
        'note': note,
        'source': source,
    }


def non_electronic_breadth(prod_series, period):
    excluded = {'C', 'Z', 'I2', '26', '27', '2610', '2611', '2612', '2613', '2640'}
    values = []
    for key, s in prod_series.items():
        if key in excluded:
            continue
        y = yoy(s, period)
        if y is not None:
            values.append(y)
    if not values:
        return None
    return sum(1 for x in values if x > 0) / len(values) * 100


def electronic_order_series(inp):
    # Prefer category series that originate from the same general export-order
    # resource as the total because their level units are naturally comparable.
    general = find_many(inp, 'orders.', [
        ('電子產品',),
        ('資訊通信', '資訊通訊'),
    ])
    if general:
        return general, True, 'MOEA general export-order table'

    # Dedicated category resources are authoritative for direction but their level
    # units are not assumed comparable to the general resource. They therefore feed
    # only the YoY growth-dominance fallback below, never a fabricated share.
    supplement = []
    for prefix, needles in [
        ('orders_supplement.electronic.', ('電子產品',)),
        ('orders_supplement.ict.', ('資訊通訊', '資訊通信')),
    ]:
        s = find_one(inp, prefix, needles)
        if s:
            supplement.append(s)
    return supplement, False, 'MOEA dedicated category export-order tables'


def score_for(period, industry, decision_inputs, ai_inputs):
    prod_series = industry.get('datasets', {}).get('moea.industry.production', {}).get('series', {})
    total_prod = prod_series.get('C', {})
    electronic_prod = prod_series.get('I2', {}) or prod_series.get('26', {})
    inp = decision_inputs.get('series', {})

    total_orders = find_one(inp, 'orders.', ('總計',)) or find_one(inp, 'orders.', ('總額',)) or find_one(inp, 'orders.', ('外銷訂單',))
    e_orders, levels_comparable, order_source_note = electronic_order_series(inp)

    order_raw = order_score = order_period = None
    e_value, e_period = combine(e_orders, period)
    t_value, t_period = latest_before(total_orders, period, 1) if total_orders else (None, None)
    if levels_comparable and e_value is not None and t_value and 0 < e_value <= t_value * 1.25:
        order_raw = e_value / t_value * 100
        order_score = clamp((order_raw - 25) / 50 * 100)
        order_period = min(e_period, t_period)
        order_note = '電子產品＋資訊通信外銷訂單占總訂單比重；25%→0、75%→100 線性映射'
    else:
        e_growths = [yoy(s, period) for s in e_orders]
        e_growths = [x for x in e_growths if x is not None]
        total_y = yoy(total_orders, period) if total_orders else None
        if e_growths and total_y is not None:
            gap = sum(e_growths) / len(e_growths) - total_y
            order_raw = gap
            order_score = clamp(50 + gap * 2)
            order_period = period
            order_note = f'電子相關訂單 YoY 相對總訂單 YoY 差距；0ppt→50；{order_source_note}，跨資源不假設 level 可比'
        else:
            order_note = '電子訂單資料不足'

    ai_share = ai_inputs.get('series', {}).get('exports_ai_core_share', {})
    export_raw, export_period = latest_before(ai_share, period, 2)
    export_score = None if export_raw is None else clamp((export_raw - 35) / 45 * 100)

    total_y = yoy(total_prod, period)
    electronic_y = yoy(electronic_prod, period)
    prod_gap = None if total_y is None or electronic_y is None else electronic_y - total_y
    prod_score = None if prod_gap is None else clamp(50 + prod_gap * 2)

    breadth = non_electronic_breadth(prod_series, period)
    breadth_score = None if breadth is None else clamp(100 - breadth)

    parts = [
        component('electronic_orders', '電子相關外銷訂單集中度', order_raw, order_score, WEIGHTS['electronic_orders'], order_period, order_note, 'MOEA'),
        component('ai_core_exports', 'AI 核心出口占比', export_raw, export_score, WEIGHTS['ai_core_exports'], export_period, '電子零組件＋資通與視聽產品占總出口；35%→0、80%→100 線性映射', 'MOF'),
        component('electronic_production', '資訊電子生產領先幅度', prod_gap, prod_score, WEIGHTS['electronic_production'], period, '資訊電子工業 YoY 減製造業總體 YoY；0ppt→50', 'MOEA'),
        component('non_electronic_breadth', '非電子產業正成長廣度反向值', breadth, breadth_score, WEIGHTS['non_electronic_breadth'], period, '非電子生產序列正成長占比；廣度越窄，集中度越高', 'MOEA'),
    ]
    parts = [x for x in parts if x]
    coverage = sum(x['weight'] for x in parts)
    if coverage < .35:
        return None
    score = sum(x['score'] * x['weight'] for x in parts) / coverage
    return {
        'period': period,
        'score': round(score, 2),
        'label': label(score),
        'confidence': min(100, round(coverage * 100)),
        'components': parts,
        'interpretation': '高分代表成長更集中於 AI／電子鏈，不代表景氣本身更好。',
    }


def generate():
    industry = load_json('industry.json', {})
    decision_inputs = load_json('decision_inputs.json', {'series': {}})
    ai_inputs = load_json('ai_inputs.json', {'series': {}})
    scores = load_json('decision_scores.json', {'current': {}, 'history': {}, 'questions': {}, 'chains': {}, 'methodology': {}})
    summary = load_json('summary.json', {})

    prod = industry.get('datasets', {}).get('moea.industry.production', {}).get('series', {}).get('C', {})
    current_period = prod.get('data', [])[-1][0] if prod.get('data') else decision_inputs.get('latest_period')
    current = score_for(current_period, industry, decision_inputs, ai_inputs) if current_period else None

    periods = set()
    for s in industry.get('datasets', {}).get('moea.industry.production', {}).get('series', {}).values():
        periods.update(str(p) for p, _ in s.get('data', []) if len(str(p)) == 7)
    for s in decision_inputs.get('series', {}).values():
        periods.update(str(p) for p, _ in s.get('data', []) if len(str(p)) == 7)
    for s in ai_inputs.get('series', {}).values():
        periods.update(str(p) for p, _ in s.get('data', []) if len(str(p)) == 7)
    periods = sorted(periods, key=period_key)[-120:]
    history = []
    for p in periods:
        r = score_for(p, industry, decision_inputs, ai_inputs)
        if r:
            history.append({k: r[k] for k in ('period', 'score', 'label', 'confidence')})

    scores['version'] = max(2, int(scores.get('version') or 1))
    scores.setdefault('current', {})['ai_concentration'] = current
    scores.setdefault('history', {})['ai_concentration'] = history
    scores.setdefault('questions', {})['ai_concentration'] = '台灣成長有多集中在 AI／電子鏈？'
    scores.setdefault('chains', {})['ai_concentration'] = '電子訂單 → AI 核心出口 → 資訊電子生產 → 非電子 breadth'
    scores.setdefault('methodology', {})['ai_concentration'] = {
        'scale': '0..100 concentration index',
        'weights': WEIGHTS,
        'meaning': '分數越高代表成長越集中於 AI／電子鏈；不是景氣好壞分數。',
        'missing': '缺值只對可用元件重新正規化；Confidence 等於可用原始權重。',
        'export_catalog': ai_inputs.get('catalog'),
    }
    scores['generated_at'] = dt.datetime.now(TZ).replace(microsecond=0).isoformat()
    save_json('decision_scores.json', scores)

    if current:
        summary.setdefault('decision_scores', {})['ai_concentration'] = current
        watch = summary.setdefault('watchlist', [])
        line = f"AI Concentration {current['score']:.0f}/100（{current['label']}）：高分代表成長更依賴 AI／電子鏈，需搭配非電子 breadth 判讀。"
        summary['watchlist'] = [line] + [x for x in watch if not str(x).startswith('AI Concentration ')]
        save_json('summary.json', summary)
    return current


if __name__ == '__main__':
    generate()
