#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt

from common import TZ, load_json, period_key, save_json

WEIGHTS = {
    'growth': {
        'orders': .30,
        'exports': .20,
        'production': .20,
        'sales': .15,
        'inventory_balance': .15,
    },
    'domestic': {
        'real_wage': .25,
        'employment': .20,
        'retail': .20,
        'food': .15,
        'card_spending': .20,
    },
    'financial': {
        # Exchange-rate direction is economically ambiguous, so its authority is
        # diagnostic-only until prospective validation supports a directional map.
        # The four active components are renormalized from the former 85% total.
        'm1b': 5 / 17,
        'm2': 4 / 17,
        'credit': 5 / 17,
        'interest_rate': 3 / 17,
        'exchange_rate': 0.0,
    },
}

QUESTIONS = {
    'growth_persistence': '這波景氣還能持續嗎？',
    'domestic_demand': '台灣一般人的經濟真的有變好嗎？',
    'financial_conditions': '資金環境是在支持還是壓制景氣？',
}

CHAINS = {
    'growth_persistence': '外銷訂單 → 出口 → 生產 → 銷售 → 庫存',
    'domestic_demand': '實質薪資 → 就業 → 零售 → 餐飲 → 信用卡消費',
    'financial_conditions': 'M1B → M2 → 銀行信用 → 利率；匯率只做 diagnostic',
}


def clamp(v, lo=-100, hi=100):
    return max(lo, min(hi, float(v)))


def month_shift(p, d):
    try:
        y, m = map(int, str(p).split('-'))
    except Exception:
        return None
    i = y * 12 + m - 1 + d
    return f'{i // 12:04d}-{i % 12 + 1:02d}'


def vmap(s):
    return {str(p): v for p, v in (s or {}).get('data', [])}


def value(s, p):
    return vmap(s).get(p)


def latest_before(s, p, max_lag=2):
    for lag in range(max_lag + 1):
        q = month_shift(p, -lag)
        v = value(s, q)
        if v is not None:
            return v, q
    return None, None


def pct(a, b):
    return None if a is None or b in (None, 0) else (float(a) / float(b) - 1) * 100


def real_yoy(nominal_yoy, inflation_yoy):
    """Exact multiplicative deflation of a nominal YoY growth rate.

    If nominal growth is g_n and inflation is pi, real growth is
    (1 + g_n) / (1 + pi) - 1. Inputs and output are percentage points.
    """
    if nominal_yoy is None or inflation_yoy is None:
        return None
    price_factor = 1.0 + float(inflation_yoy) / 100.0
    if price_factor <= 0:
        return None
    nominal_factor = 1.0 + float(nominal_yoy) / 100.0
    return (nominal_factor / price_factor - 1.0) * 100.0


def yoy(s, p):
    return pct(value(s, p), value(s, month_shift(p, -12)))


def change(s, p, n):
    return pct(value(s, p), value(s, month_shift(p, -n)))


def latest_period(s):
    d = (s or {}).get('data', [])
    return str(d[-1][0]) if d else None


def find_series(series, prefix, needles):
    cand = []
    for k, s in series.items():
        if prefix and not k.startswith(prefix):
            continue
        name = k + ' ' + str(s.get('name', ''))
        low = name.lower()
        score = sum(1 for n in needles if n.lower() in low)
        if score:
            cand.append((score, len(s.get('data', [])), -len(name), k, s))
    return max(cand, default=(0, 0, 0, None, None))[4]


def find_inventory(series):
    # The official MOEA total is the canonical Growth input.  It can have a
    # shorter live history than legacy/fallback inventory series, so key
    # authority must beat heuristic name/history tie-breaking.
    canonical = series.get('inventory.manufacturing_index')
    if canonical and canonical.get('data'):
        return canonical

    cand = []
    for k, s in series.items():
        if not k.startswith('inventory.'):
            continue
        name = str(s.get('name', k))
        if '製造業' not in name or '存貨' not in name:
            continue
        exact = 10 if name.startswith('製造業 /') or name.startswith('製造業/') or name == '製造業' else 0
        cand.append((exact, -len(name), len(s.get('data', [])), s))
    return max(cand, default=(0, 0, 0, None))[3]


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


def aggregate(parts):
    parts = [p for p in parts if p]
    w = sum(p['weight'] for p in parts)
    if not parts or w < .45:
        return None
    score = sum(p['score'] * p['weight'] for p in parts) / w
    return round(score, 2), min(100, round(w * 100)), parts


def label(score):
    if score >= 60:
        return '非常正向'
    if score >= 25:
        return '正向'
    if score >= 5:
        return '略偏正向'
    if score > -5:
        return '中性'
    if score > -25:
        return '略偏負向'
    if score > -60:
        return '負向'
    return '非常負向'


def history_periods(series_list, months=120):
    ps = set()
    for s in series_list:
        for p, _ in (s or {}).get('data', []):
            if len(str(p)) == 7:
                ps.add(str(p))
    return sorted(ps, key=period_key)[-months:]


def growth_score(period, prod, sales, ndc, inputs):
    inp = inputs.get('series', {})
    order = find_series(inp, 'orders.', ('外銷訂單', '總額')) or find_series(inp, 'orders.', ('外銷', '訂單'))
    order_y = yoy(order, period) if order else None
    order_p = period
    if order_y is None:
        diff = ndc.get('export_order_diffusion', {})
        ov, op = latest_before(diff, period, 1)
        order_y = ov
        order_p = op
        order_score = None if ov is None else ((ov - 50) / 15 * 100 if 0 <= ov <= 100 else change(diff, op, 12) or 0)
        order_note = '外銷訂單動向指數 fallback'
    else:
        order_score = order_y / 20 * 100
        order_note = '外銷訂單金額 YoY'

    exp = inp.get('customs.exports_total') or ndc.get('customs_exports', {})
    _, ep = latest_before(exp, period, 1)
    exp_y = yoy(exp, ep) if ep else None
    prod_y = yoy(prod, period)
    _, sp = latest_before(sales, period, 1)
    sales_y = yoy(sales, sp) if sp else None
    inv = find_inventory(inp) or ndc.get('manufacturing_inventory', {})
    _, ip = latest_before(inv, period, 2)
    inv_y = yoy(inv, ip) if ip else None
    gap = None if inv_y is None or sales_y is None else inv_y - sales_y

    parts = [
        component('orders', '外銷訂單', order_y, order_score, WEIGHTS['growth']['orders'], order_p, order_note, 'MOEA'),
        component('exports', '海關出口', exp_y, None if exp_y is None else exp_y / 20 * 100, WEIGHTS['growth']['exports'], ep, '出口總值 YoY', 'Customs'),
        component('production', '製造業生產', prod_y, None if prod_y is None else prod_y / 20 * 100, WEIGHTS['growth']['production'], period, '製造業生產 YoY', 'MOEA'),
        component('sales', '製造業銷售', sales_y, None if sales_y is None else sales_y / 12 * 100, WEIGHTS['growth']['sales'], sp, '銷售資料允許落後 1 個月', 'MOEA'),
        component('inventory_balance', '存貨壓力', gap, None if gap is None else (5 - gap) / 15 * 100, WEIGHTS['growth']['inventory_balance'], ip, '製造業存貨 YoY 減銷售 YoY；差距越低越健康', 'MOEA'),
    ]
    agg = aggregate(parts)
    if not agg:
        return None
    score, conf, parts = agg
    return {'period': period, 'score': score, 'label': label(score), 'confidence': conf, 'components': parts}


def domestic_score(period, ndc, inputs):
    inp = inputs.get('series', {})
    retail = find_series(inp, 'domestic.', ('零售', '營業額')) or find_series(inp, 'domestic.', ('零售',))
    food = find_series(inp, 'domestic.', ('餐飲', '營業額')) or find_series(inp, 'domestic.', ('餐飲',))

    _, rp = latest_before(retail, period, 1)
    retail_y = yoy(retail, rp) if rp else None
    _, fp = latest_before(food, period, 1)
    food_y = yoy(food, fp) if fp else None
    broad = ndc.get('wholesale_retail_food', {})
    _, bp = latest_before(broad, period, 2)
    broad_y = yoy(broad, bp) if bp else None
    if retail_y is None:
        retail_y = broad_y
        rp = bp
        retail_note = '批零餐飲總體 YoY fallback'
    else:
        retail_note = '零售營業額 YoY'

    wage = inp.get('dgbas.total_monthly_salary') or inp.get('labor.avg_monthly_salary')
    _, wp = latest_before(wage, period, 2)
    wage_y = yoy(wage, wp) if wp else None
    cpi = inp.get('labor.cpi_yoy')
    cpi_v, _ = latest_before(cpi, wp or period, 2)
    real_wage = real_yoy(wage_y, cpi_v)

    emp = inp.get('dgbas.employment_total')
    _, emp_p = latest_before(emp, period, 2)
    emp_y = yoy(emp, emp_p) if emp_p else None

    card = inp.get('nccc.card_spending')
    _, card_p = latest_before(card, period, 2)
    card_y = yoy(card, card_p) if card_p else None
    card_cpi, _ = latest_before(cpi, card_p or period, 2)
    card_real_y = real_yoy(card_y, card_cpi)
    card_note = '聯卡中心處理簽帳金額以 CPI YoY 精確乘法實質化；僅作信用卡消費 proxy' if card_cpi is not None else '聯卡中心處理簽帳金額有 YoY，但 CPI 缺值時不產生實質消費 proxy'

    parts = [
        component('real_wage', '實質薪資動能', real_wage, None if real_wage is None else real_wage / 4 * 100, WEIGHTS['domestic']['real_wage'], wp, '平均每月總薪資以 (1+nominal YoY)/(1+CPI YoY)-1 精確實質化', 'DGBAS/MOL'),
        component('employment', '受僱員工人數', emp_y, None if emp_y is None else emp_y / 2 * 100, WEIGHTS['domestic']['employment'], emp_p, '工業及服務業受僱員工人數 YoY', 'DGBAS'),
        component('retail', '零售消費', retail_y, None if retail_y is None else retail_y / 10 * 100, WEIGHTS['domestic']['retail'], rp, retail_note, 'MOEA'),
        component('food', '餐飲消費', food_y, None if food_y is None else food_y / 10 * 100, WEIGHTS['domestic']['food'], fp, '餐飲營業額 YoY', 'MOEA'),
        component('card_spending', '信用卡消費', card_real_y, None if card_real_y is None else card_real_y / 10 * 100, WEIGHTS['domestic']['card_spending'], card_p, card_note, 'FSC/NCCC'),
    ]
    agg = aggregate(parts)
    if not agg:
        return None
    score, conf, parts = agg
    return {'period': period, 'score': score, 'label': label(score), 'confidence': conf, 'components': parts}


def direct_yoy(inp, absolute_key, yoy_key, period, fallback=None):
    ys = inp.get(yoy_key)
    if ys:
        v, p = latest_before(ys, period, 2)
        if v is not None:
            return float(v), p, 'CBC'
    s = inp.get(absolute_key) or fallback
    if s:
        _, p = latest_before(s, period, 2)
        y = yoy(s, p) if p else None
        if y is not None:
            return y, p, 'CBC' if inp.get(absolute_key) else 'NDC/CBC'
    return None, None, None


def financial_score(period, ndc, inputs):
    inp = inputs.get('series', {})
    m1y, m1p, m1src = direct_yoy(inp, 'cbc.m1b', 'cbc.m1b_yoy', period, ndc.get('m1b'))
    m2y, m2p, _ = direct_yoy(inp, 'cbc.m2', 'cbc.m2_yoy', period, None)
    cy, cp, csrc = direct_yoy(inp, 'cbc.credit', 'cbc.credit_yoy', period, ndc.get('financial_loans_investments'))

    rate = inp.get('cbc.interbank_rate') or inp.get('cbc.loan_rate') or ndc.get('new_loan_rate', {})
    rv, rp = latest_before(rate, period, 2)
    r12 = value(rate, month_shift(rp, -12)) if rp else None
    rdelta = None if rv is None or r12 is None else float(rv) - float(r12)

    fx = inp.get('cbc.exchange_rate')
    _, fxp = latest_before(fx, period, 2)
    fx12 = change(fx, fxp, 12) if fxp else None

    parts = [
        component('m1b', 'M1B', m1y, None if m1y is None else m1y / 8 * 100, WEIGHTS['financial']['m1b'], m1p, 'M1B YoY', m1src or 'CBC'),
        component('m2', 'M2', m2y, None if m2y is None else m2y / 7 * 100, WEIGHTS['financial']['m2'], m2p, 'M2 YoY', 'CBC'),
        component('credit', '銀行信用', cy, None if cy is None else cy / 8 * 100, WEIGHTS['financial']['credit'], cp, '金融機構放款與投資 YoY', csrc or 'CBC'),
        component('interest_rate', '短期利率', rdelta, None if rdelta is None else -rdelta / .75 * 100, WEIGHTS['financial']['interest_rate'], rp, '隔夜拆款利率相較一年前下降視為較寬鬆', 'CBC'),
        component('exchange_rate', 'USD/TWD 12M（diagnostic）', fx12, 0.0 if fx12 is not None else None, WEIGHTS['financial']['exchange_rate'], fxp, '匯率同時反映競爭力、輸入型通膨、資金流與 risk-off；方向非單調，驗證前 weight=0、不改 Financial Conditions', 'CBC'),
    ]
    agg = aggregate(parts)
    if not agg:
        return None
    score, conf, parts = agg
    return {'period': period, 'score': score, 'label': label(score), 'confidence': conf, 'components': parts}


def generate():
    industry = load_json('industry.json', {})
    ndcobj = load_json('ndc.json', {})
    inputs = load_json('decision_inputs.json', {'series': {}})
    summary = load_json('summary.json', {})
    ndc = ndcobj.get('series', {})
    prod = industry.get('datasets', {}).get('moea.industry.production', {}).get('series', {}).get('C', {})
    sales = industry.get('datasets', {}).get('moea.manufacturing.sales_index_current', {}).get('series', {}).get('C', {})
    current_period = latest_period(prod) or ndcobj.get('latest_period')

    current = {
        'growth_persistence': growth_score(current_period, prod, sales, ndc, inputs),
        'domestic_demand': domestic_score(current_period, ndc, inputs),
        'financial_conditions': financial_score(current_period, ndc, inputs),
    }

    allseries = [prod, sales, *ndc.values(), *inputs.get('series', {}).values()]
    periods = [p for p in history_periods(allseries, 120) if not current_period or p <= current_period]
    history = {'growth_persistence': [], 'domestic_demand': [], 'financial_conditions': []}
    for p in periods:
        for k, fn in [
            ('growth_persistence', lambda p=p: growth_score(p, prod, sales, ndc, inputs)),
            ('domestic_demand', lambda p=p: domestic_score(p, ndc, inputs)),
            ('financial_conditions', lambda p=p: financial_score(p, ndc, inputs)),
        ]:
            r = fn()
            if r:
                history[k].append({x: r[x] for x in ('period', 'score', 'label', 'confidence')})

    obj = {
        'version': 1,
        'generated_at': dt.datetime.now(TZ).replace(microsecond=0).isoformat(),
        'current': current,
        'history': history,
        'questions': QUESTIONS,
        'chains': CHAINS,
        'methodology': {
            'scale': '-100..+100',
            'common_as_of': current_period,
            'missing': '缺值重新正規化權重，Confidence 依可用權重下降',
            'growth': WEIGHTS['growth'],
            'domestic': WEIGHTS['domestic'],
            'financial': WEIGHTS['financial'],
            'real_growth_formula': '(1+nominal_yoy/100)/(1+cpi_yoy/100)-1',
            'real_growth_policy': 'CPI 缺值時不以 nominal YoY 冒充 real YoY；該 component 缺值並由既有權重正規化與 coverage confidence 處理。',
            'exchange_rate_assumption': 'USD/TWD 只保留為 diagnostic raw signal。因匯率的競爭力、通膨、資金流與風險效果方向不單調，在 prospective validation 支持前 score weight 固定為 0。',
        },
        'sources': inputs.get('catalogs', {}),
    }
    save_json('decision_scores.json', obj)

    summary['decision_scores'] = {k: v for k, v in current.items() if v}
    watch = summary.setdefault('watchlist', [])
    inserts = []
    if current.get('growth_persistence'):
        g = current['growth_persistence']
        inserts.append(f"Growth Persistence {g['score']:+.0f}/100（{g['label']}）：觀察訂單→出口→生產→銷售→存貨是否延續。")
    if current.get('domestic_demand'):
        d = current['domestic_demand']
        inserts.append(f"Domestic Demand {d['score']:+.0f}/100（{d['label']}）：觀察實質薪資→就業→零售→餐飲→信用卡消費是否同步。")
    if current.get('financial_conditions'):
        f = current['financial_conditions']
        inserts.append(f"Financial Conditions {f['score']:+.0f}/100（{f['label']}）：觀察 M1B→M2→銀行信用→利率；匯率暫為 diagnostic-only。")
    summary['watchlist'] = inserts + [x for x in watch if not str(x).startswith(('Growth Persistence ', 'Domestic Demand ', 'Financial Conditions '))]
    save_json('summary.json', summary)
    return obj


if __name__ == '__main__':
    generate()
