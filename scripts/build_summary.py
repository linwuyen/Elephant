#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
TZ = dt.timezone(dt.timedelta(hours=8))

def load(name, default=None):
    p = DATA / name
    if not p.exists():
        return {} if default is None else default
    return json.loads(p.read_text(encoding='utf-8'))

def save(name, obj):
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')

def clamp(v, lo=-100.0, hi=100.0):
    return max(lo, min(hi, v))

def round2(v):
    return None if v is None or not math.isfinite(float(v)) else round(float(v), 2)

def pct_change(a, b):
    if a is None or b in (None, 0):
        return None
    return (float(a) / float(b) - 1.0) * 100.0

def latest(series):
    d = (series or {}).get('data', [])
    return d[-1] if d else [None, None]

def metric(series):
    p, v = latest(series)
    return {'period': p, 'value': v, 'unit': (series or {}).get('unit'), 'name': (series or {}).get('name')}

def prev_month(period):
    try:
        y, m = map(int, str(period).split('-'))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        return f'{y:04d}-{m:02d}'
    except Exception:
        return None

def shift_year(period, n=-1):
    try:
        y, m = str(period).split('-', 1)
        return f'{int(y)+n:04d}-{m}'
    except Exception:
        return None

def value_at(data, period):
    if not period:
        return None
    return dict(data).get(period)

def yoy_history(series):
    data = (series or {}).get('data', [])
    out = []
    for p, v in data:
        py = value_at(data, shift_year(str(p), -1))
        y = pct_change(v, py)
        if y is not None and math.isfinite(y) and abs(y) <= 500:
            out.append([str(p), y])
    return out

def percentile_rank(values, x):
    vals = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if not vals or x is None:
        return None
    return 100.0 * sum(v <= x for v in vals) / len(vals)

def series_momentum(series, sid=None):
    yh = yoy_history(series)
    if not yh:
        p, v = latest(series)
        return {'id': sid, 'name': (series or {}).get('name', sid), 'period': p, 'value': v}
    p, yoy = yh[-1]
    prev_yoy = yh[-2][1] if len(yh) >= 2 else None
    accel = yoy - prev_yoy if prev_yoy is not None else None
    last3 = [x[1] for x in yh[-3:]]
    last6 = [x[1] for x in yh[-6:]]
    last12 = [x[1] for x in yh[-12:]]
    pctl = percentile_rank(last12, yoy)
    turn = None
    if prev_yoy is not None:
        if prev_yoy < 0 <= yoy:
            turn = 'recovery_cross'
        elif prev_yoy >= 0 > yoy:
            turn = 'downturn_cross'
        elif yoy < 0 and accel is not None and accel >= 3:
            turn = 'contraction_easing'
        elif yoy > 0 and accel is not None and accel <= -3:
            turn = 'expansion_fading'
        elif accel is not None and accel >= 3:
            turn = 'accelerating'
        elif accel is not None and accel <= -3:
            turn = 'decelerating'
    return {
        'id': sid,
        'name': (series or {}).get('name', sid),
        'period': p,
        'value': value_at((series or {}).get('data', []), p),
        'yoy': round2(yoy),
        'prev_yoy': round2(prev_yoy),
        'acceleration_ppt': round2(accel),
        'yoy_ma3': round2(sum(last3) / len(last3)),
        'yoy_ma6': round2(sum(last6) / len(last6)),
        'yoy_percentile_12m': round2(pctl),
        'turn': turn,
    }

def industry_snapshot(dataset):
    return {sid: series_momentum(s, sid) for sid, s in (dataset or {}).get('series', {}).items()}

def yoy_at(series, p):
    if not series or not p:
        return None
    data = series.get('data', [])
    v = value_at(data, p)
    py = value_at(data, shift_year(p, -1))
    return pct_change(v, py)

def breadth_at(dataset, period):
    vals = []
    for _, s in (dataset or {}).get('series', {}).items():
        y = yoy_at(s, period)
        if y is not None and abs(y) <= 500:
            vals.append(y)
    if not vals:
        return None
    return 100.0 * sum(v > 0 for v in vals) / len(vals)

def classify_growth(v):
    if v is None: return '資料不足'
    if v >= 5: return '高成長'
    if v >= 3: return '穩健擴張'
    if v >= 1: return '溫和成長'
    if v >= 0: return '低成長'
    return '衰退'

def classify_inflation(v):
    if v is None: return '物價資料不足'
    if v < 0.5: return '低通膨'
    if v <= 2.5: return '通膨溫和'
    if v <= 4: return '通膨偏高'
    return '高通膨'

def cycle_label(score):
    if score >= 60: return '強勁擴張'
    if score >= 25: return '擴張'
    if score >= 5: return '溫和擴張'
    if score > -5: return '中性'
    if score > -25: return '溫和收縮'
    if score > -60: return '收縮'
    return '深度收縮'

def momentum_label(score):
    if score >= 35: return '明顯加速'
    if score >= 10: return '加速'
    if score > -10: return '大致持平'
    if score > -35: return '減速'
    return '明顯減速'

def trend3(series):
    d = (series or {}).get('data', [])
    if len(d) < 4:
        return None
    vals = [float(x[1]) for x in d[-4:] if isinstance(x[1], (int, float))]
    if len(vals) < 4 or vals[0] == 0:
        return None
    return pct_change(vals[-1], vals[0])

def evidence(label, value, source, tab=None, dataset=None, series=None, period=None):
    return {
        'label': label,
        'value': value,
        'source': source,
        'target': {'tab': tab, 'dataset': dataset, 'series': series} if tab else None,
        'period': period,
    }

def ndc_state(ndc):
    s = ndc.get('series', {})
    leading = metric(s.get('leading_no_trend'))
    coincident = metric(s.get('coincident_no_trend'))
    pmi = metric(s.get('pmi'))
    nmi = metric(s.get('nmi'))
    lead3 = trend3(s.get('leading_no_trend'))
    coinc3 = trend3(s.get('coincident_no_trend'))
    sig = (ndc.get('signals') or [])[-1] if ndc.get('signals') else {}
    pmi_v = pmi.get('value')
    if lead3 is None:
        outlook = '資料不足'
    elif lead3 > 0.5 and (pmi_v is None or pmi_v >= 50):
        outlook = '正向'
    elif lead3 > 0:
        outlook = '改善'
    elif lead3 < -0.5 and (pmi_v is not None and pmi_v < 50):
        outlook = '轉弱'
    else:
        outlook = '中性'
    return {
        'latest_period': ndc.get('latest_period'),
        'leading': leading,
        'leading_3m_pct': round2(lead3),
        'coincident': coincident,
        'coincident_3m_pct': round2(coinc3),
        'pmi': pmi,
        'nmi': nmi,
        'policy_signal': sig,
        'outlook': outlook,
    }

def cycle_score(growth, prod_ds, sales_ds, ndc_info):
    mfg = series_momentum((prod_ds or {}).get('series', {}).get('C', {}), 'C')
    sales = series_momentum((sales_ds or {}).get('series', {}).get('C', {}), 'C')
    latest_period = mfg.get('period')
    breadth = breadth_at(prod_ds, latest_period)
    components = []

    def add(name, raw, score, weight, note):
        if raw is None or score is None:
            return
        components.append({'name': name, 'raw': round2(raw), 'score': round2(clamp(score)), 'weight': weight, 'note': note})

    add('製造業生產 YoY', mfg.get('yoy'), (mfg.get('yoy') or 0) / 20 * 100 if mfg.get('yoy') is not None else None, 0.30, '同步動能')
    add('產業正成長廣度', breadth, ((breadth or 50) - 50) * 2 if breadth is not None else None, 0.20, '擴張廣度')
    add('製造業銷售 YoY', sales.get('yoy'), (sales.get('yoy') or 0) / 12 * 100 if sales.get('yoy') is not None else None, 0.15, '需求/銷售動能')
    lead3 = ndc_info.get('leading_3m_pct')
    add('國發會領先指標 3M', lead3, (lead3 or 0) / 1.5 * 100 if lead3 is not None else None, 0.20, '官方領先訊號')
    pmi = ndc_info.get('pmi', {}).get('value')
    add('PMI', pmi, ((pmi or 50) - 50) / 10 * 100 if pmi is not None else None, 0.10, '企業採購動能')
    g = growth.get('value')
    add('GDP 成長率', g, ((g or 2) - 2) / 6 * 100 if g is not None else None, 0.05, '年度總體背景')

    denom = sum(x['weight'] for x in components) or 1
    score = sum(x['score'] * x['weight'] for x in components) / denom

    accel = mfg.get('acceleration_ppt')
    prev_breadth = breadth_at(prod_ds, prev_month(latest_period)) if latest_period else None
    breadth_delta = breadth - prev_breadth if breadth is not None and prev_breadth is not None else None
    mom_parts = []
    if accel is not None:
        mom_parts.append(clamp(accel / 8 * 100))
    if breadth_delta is not None:
        mom_parts.append(clamp(breadth_delta / 20 * 100))
    if lead3 is not None:
        mom_parts.append(clamp(lead3 / 1.5 * 100))
    momentum_score = sum(mom_parts) / len(mom_parts) if mom_parts else 0

    return {
        'score': round2(score),
        'label': cycle_label(score),
        'momentum_score': round2(momentum_score),
        'momentum': momentum_label(momentum_score),
        'breadth': round2(breadth),
        'breadth_prev': round2(prev_breadth),
        'breadth_delta_ppt': round2(breadth_delta),
        'components': components,
        'method': '透明加權綜合分數；不是官方景氣燈號。分數只用已驗證且當期可用的元件，缺值時重新正規化權重。',
    }

def confidence(status, cycle, ndc_info):
    score = 100
    reasons = []
    for sid in ('dgbas', 'moea', 'ris'):
        st = status.get('sources', {}).get(sid, {}).get('status')
        if st != 'ok':
            score -= 20
            reasons.append(f'{sid} 狀態 {st or "missing"}')
    ndc_st = status.get('sources', {}).get('ndc', {}).get('status')
    if ndc_st != 'ok':
        score -= 15
        reasons.append('國發會領先資料未正常更新')
    if len(cycle.get('components', [])) < 4:
        score -= 15
        reasons.append('Cycle Score 可用元件偏少')
    lead_p = ndc_info.get('leading', {}).get('period')
    pmi_p = ndc_info.get('pmi', {}).get('period')
    if lead_p and pmi_p and lead_p != pmi_p:
        score -= 5
        reasons.append('領先指標與 PMI 最新月份不同')
    score = int(clamp(score, 0, 100))
    label = 'High' if score >= 80 else ('Medium' if score >= 60 else 'Low')
    return {'score': score, 'label': label, 'reasons': reasons or ['核心來源正常且主要訊號完整']}

def turning_points(prod_ds):
    important = {'C', 'I2', '26', '2611', '27', 'I1', 'I3', 'I4', '28', '29', '30'}
    rows = []
    for sid, s in (prod_ds or {}).get('series', {}).items():
        if sid not in important:
            continue
        m = series_momentum(s, sid)
        acc = m.get('acceleration_ppt')
        turn = m.get('turn')
        if not turn and (acc is None or abs(acc) < 3):
            continue
        bonus = 30 if turn in ('recovery_cross', 'downturn_cross') else 15
        significance = min(100, abs(acc or 0) * 8 + bonus)
        title = {
            'recovery_cross': '年增率由負轉正',
            'downturn_cross': '年增率由正轉負',
            'contraction_easing': '收縮快速收斂',
            'expansion_fading': '正成長明顯降速',
            'accelerating': '成長加速',
            'decelerating': '成長減速',
        }.get(turn, '動能變化')
        rows.append({
            **m,
            'signal': title,
            'significance': round2(significance),
            'level': 'major' if significance >= 70 else 'watch',
        })
    rows.sort(key=lambda x: x.get('significance') or 0, reverse=True)
    return rows[:8]

def divergences(prod_ds, sales_ds, ndc_info):
    out = []
    ps = (prod_ds or {}).get('series', {})
    ss = (sales_ds or {}).get('series', {})
    mfg = series_momentum(ps.get('C', {}), 'C')
    tech = series_momentum(ps.get('I2', {}), 'I2')
    if mfg.get('yoy') is not None and tech.get('yoy') is not None:
        spread = tech['yoy'] - mfg['yoy']
        if abs(spread) >= 5:
            out.append({
                'title': '科技 vs 整體製造業',
                'value': round2(spread),
                'unit': 'ppt',
                'direction': '科技領先' if spread > 0 else '科技落後',
                'text': f"資訊電子 YoY {tech['yoy']:+.1f}%，製造業 {mfg['yoy']:+.1f}%，差 {spread:+.1f} 個百分點。",
                'severity': min(100, abs(spread) * 5),
                'target': {'tab': 'industry', 'dataset': 'moea.industry.production', 'series': 'I2'},
            })

    sales_m = series_momentum(ss.get('C', {}), 'C')
    sp = sales_m.get('period')
    if sp:
        prod_y = yoy_at(ps.get('C', {}), sp)
        sales_y = sales_m.get('yoy')
        if prod_y is not None and sales_y is not None:
            spread = prod_y - sales_y
            if abs(spread) >= 6:
                text = '生產動能明顯快於銷售，需追蹤訂單與庫存是否跟上。' if spread > 0 else '銷售動能快於生產，需觀察供給是否跟上。'
                out.append({
                    'title': '生產 vs 銷售',
                    'value': round2(spread),
                    'unit': 'ppt',
                    'direction': '生產領先' if spread > 0 else '銷售領先',
                    'text': f"{sp} 製造業生產 YoY {prod_y:+.1f}%，銷售指數 YoY {sales_y:+.1f}%。{text}",
                    'severity': min(100, abs(spread) * 5),
                    'target': {'tab': 'industry', 'dataset': 'moea.manufacturing.sales_index_current', 'series': 'C'},
                })

    lead = ndc_info.get('leading_3m_pct')
    coinc = ndc_info.get('coincident_3m_pct')
    if lead is not None and coinc is not None and lead * coinc < 0:
        out.append({
            'title': '領先 vs 同時指標',
            'value': round2(lead - coinc),
            'unit': 'ppt',
            'direction': '未來與當前景氣方向分歧',
            'text': f'國發會領先指標 3 個月變化 {lead:+.2f}%，同時指標 {coinc:+.2f}%。',
            'severity': min(100, abs(lead - coinc) * 30),
            'target': {'tab': 'overview'},
        })
    out.sort(key=lambda x: x['severity'], reverse=True)
    return out[:5]

def signal_alerts(turns, divs, cycle, ndc_info):
    alerts = []
    if abs(cycle.get('breadth_delta_ppt') or 0) >= 10:
        d = cycle['breadth_delta_ppt']
        alerts.append({
            'level': 'major' if abs(d) >= 20 else 'watch',
            'score': min(100, abs(d) * 4),
            'title': '景氣廣度快速' + ('擴散' if d > 0 else '收斂'),
            'text': f"正成長產業占比較前月 {d:+.1f} 個百分點。",
        })
    for x in turns[:4]:
        alerts.append({
            'level': x['level'],
            'score': x['significance'],
            'title': f"{x['name']}：{x['signal']}",
            'text': f"{x['period']} YoY {x.get('yoy'):+.1f}%，較前月年增率變化 {x.get('acceleration_ppt'):+.1f} 個百分點。",
        })
    for x in divs[:3]:
        alerts.append({
            'level': 'watch' if x['severity'] < 70 else 'major',
            'score': round2(x['severity']),
            'title': '背離：' + x['title'],
            'text': x['text'],
        })
    sig = ndc_info.get('policy_signal') or {}
    if sig.get('signal'):
        alerts.append({
            'level': 'info',
            'score': 35,
            'title': f"官方景氣燈號：{sig.get('signal')}",
            'text': f"{sig.get('period')} 國發會景氣對策信號綜合分數 {sig.get('score') if sig.get('score') is not None else '—'}。",
        })
    rank = {'major': 3, 'watch': 2, 'info': 1}
    alerts.sort(key=lambda x: (rank.get(x['level'], 0), x.get('score', 0)), reverse=True)
    return alerts[:6]

def watchlist(cycle, divs, weak, ndc_info):
    items = []
    for d in divs:
        if d['title'] == '生產 vs 銷售':
            items.append('製造業銷售是否追上生產，避免生產/需求差距持續擴大。')
        elif d['title'] == '科技 vs 整體製造業':
            items.append('AI／資訊電子強勢能否持續擴散至非電子製造業。')
    if cycle.get('breadth') is not None:
        items.append(f"正成長產業廣度目前 {cycle['breadth']:.0f}%，觀察是否持續高於 60%。")
    if ndc_info.get('leading_3m_pct') is not None:
        items.append(f"國發會領先指標近 3 個月變化 {ndc_info['leading_3m_pct']:+.2f}%，觀察方向能否連續。")
    neg = [x for x in weak if (x.get('yoy') or 0) < 0][:2]
    if neg:
        items.append('弱勢產業是否止跌：' + '、'.join(x['name'] for x in neg) + '。')
    items.append('長期結構：人口自然減少與高齡化對勞動力、消費與地方需求的影響。')
    out = []
    for x in items:
        if x not in out:
            out.append(x)
    return out[:5]

def snapshot_metrics(cycle, industry, population, ndc_info):
    raw = {
        'cycle_score': {'label': 'Cycle Score', 'value': cycle.get('score'), 'unit': 'score'},
        'cycle_momentum': {'label': 'Cycle Momentum', 'value': cycle.get('momentum_score'), 'unit': 'score'},
        'breadth': {'label': '產業正成長廣度', 'value': cycle.get('breadth'), 'unit': 'percent'},
        'manufacturing_yoy': {'label': '製造業生產 YoY', 'value': (industry.get('manufacturing') or {}).get('yoy'), 'unit': 'percent'},
        'information_electronics_yoy': {'label': '資訊電子 YoY', 'value': (industry.get('information_electronics') or {}).get('yoy'), 'unit': 'percent'},
        'sales_yoy': {'label': '製造業銷售 YoY', 'value': (industry.get('manufacturing_sales') or {}).get('yoy'), 'unit': 'percent'},
        'leading_3m': {'label': '國發會領先指標 3M', 'value': ndc_info.get('leading_3m_pct'), 'unit': 'percent'},
        'pmi': {'label': 'PMI', 'value': ndc_info.get('pmi', {}).get('value'), 'unit': 'index'},
        'population_yoy': {'label': '人口 YoY', 'value': population.get('yoy_pct'), 'unit': 'percent'},
        'share_65_plus': {'label': '65+ 占比', 'value': population.get('share_65_plus'), 'unit': 'percent'},
    }
    clean = {k: v for k, v in raw.items() if v.get('value') is not None}
    canonical = json.dumps(clean, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return {
        'fingerprint': hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16],
        'metrics': clean,
    }

def generate():
    macro = load('macro.json', {})
    pop = load('population.json', {})
    industry_data = load('industry.json', {})
    status = load('status.json', {})
    ndc = load('ndc.json', {})
    revisions = load('revisions.json', {'new_revisions': [], 'history': []})

    ms = macro.get('series', {})
    ps = pop.get('national', {})
    growth = metric(ms.get('dgbas.gdp.growth_rate'))
    cpi = metric(ms.get('dgbas.cpi.yoy'))
    nominal = metric(ms.get('dgbas.gdp.nominal.production'))

    population_metric = metric(ps.get('ris.pop.year_end_total'))
    pop_data = ps.get('ris.pop.year_end_total', {}).get('data', [])
    prev_pop = pop_data[-2][1] if len(pop_data) >= 2 else None
    pop_change = pct_change(population_metric.get('value'), prev_pop)
    oldshare = metric(ps.get('ris.pop.share_65_plus'))
    births = metric(ps.get('ris.pop.births'))
    deaths = metric(ps.get('ris.pop.deaths'))
    natural = None
    if births.get('value') is not None and deaths.get('value') is not None:
        natural = births['value'] - deaths['value']
    population = {
        'period': population_metric.get('period'),
        'population': population_metric.get('value'),
        'yoy_pct': round2(pop_change),
        'share_65_plus': oldshare.get('value'),
        'births': births.get('value'),
        'deaths': deaths.get('value'),
        'natural_increase': natural,
    }

    datasets = industry_data.get('datasets', {})
    prod_ds = datasets.get('moea.industry.production', {})
    sales_ds = datasets.get('moea.manufacturing.sales_index_current', {})
    prod = industry_snapshot(prod_ds)
    sales = industry_snapshot(sales_ds)
    mfg = prod.get('C') or prod.get('Z')
    info = prod.get('I2')
    electronics = prod.get('26')
    ic = prod.get('2611')
    optics = prod.get('27')
    current_sales = sales.get('C')

    latest_prod_period = max((x.get('period') for x in prod.values() if x.get('period')), default=None)
    comparable = [x for x in prod.values() if x.get('period') == latest_prod_period and x.get('yoy') is not None]
    ranked = sorted(comparable, key=lambda x: x['yoy'], reverse=True)
    top = ranked[:5]
    weak = list(reversed(ranked[-5:])) if ranked else []

    annual_regime = f"{classify_growth(growth.get('value'))}、{classify_inflation(cpi.get('value'))}"
    ndc_info = ndc_state(ndc)
    cycle = cycle_score(growth, prod_ds, sales_ds, ndc_info)
    conf = confidence(status, cycle, ndc_info)
    turns = turning_points(prod_ds)
    divs = divergences(prod_ds, sales_ds, ndc_info)
    alerts = signal_alerts(turns, divs, cycle, ndc_info)

    ind_out = {
        'latest_period': latest_prod_period,
        'manufacturing': mfg,
        'information_electronics': info,
        'electronics_components': electronics,
        'integrated_circuits': ic,
        'computer_optics': optics,
        'manufacturing_sales': current_sales,
        'positive_breadth_pct': cycle.get('breadth'),
        'breadth_delta_ppt': cycle.get('breadth_delta_ppt'),
        'top_yoy': top,
        'weak_yoy': weak,
    }

    takeaways = []
    takeaways.append({
        'level': 'positive' if (cycle.get('score') or 0) >= 25 else ('warning' if (cycle.get('score') or 0) < -5 else 'neutral'),
        'title': f"景氣總判讀：{cycle['label']}，動能{cycle['momentum']}",
        'text': f"Elephant Cycle Score {cycle['score']:+.0f}/100；產業正成長廣度 {cycle.get('breadth') or 0:.0f}%。這是透明規則式綜合分數，不等同國發會官方景氣燈號。",
        'evidence': [
            evidence('製造業生產', f"{(mfg or {}).get('yoy', 0):+.1f}% YoY", 'MOEA', 'industry', 'moea.industry.production', 'C', (mfg or {}).get('period')),
            evidence('產業廣度', f"{cycle.get('breadth') or 0:.0f}%", 'MOEA', 'industry'),
        ],
    })

    if ndc_info.get('leading', {}).get('value') is not None:
        sig = ndc_info.get('policy_signal') or {}
        signal_text = f"，官方燈號 {sig.get('signal')} / {sig.get('score')} 分" if sig.get('signal') else ''
        takeaways.append({
            'level': 'positive' if ndc_info.get('outlook') in ('正向', '改善') else ('warning' if ndc_info.get('outlook') == '轉弱' else 'neutral'),
            'title': f"領先訊號：{ndc_info.get('outlook')}",
            'text': f"國發會領先指標近 3 個月 {ndc_info.get('leading_3m_pct'):+.2f}%，同時指標 {ndc_info.get('coincident_3m_pct'):+.2f}%{signal_text}。",
            'evidence': [
                evidence('領先指標', f"{ndc_info.get('leading_3m_pct'):+.2f}% / 3M", 'NDC', period=ndc_info.get('leading', {}).get('period')),
                evidence('PMI', f"{ndc_info.get('pmi', {}).get('value'):.1f}" if ndc_info.get('pmi', {}).get('value') is not None else '—', 'NDC', period=ndc_info.get('pmi', {}).get('period')),
            ],
        })

    if mfg:
        sales_text = f"，銷售 {current_sales['yoy']:+.1f}%" if current_sales and current_sales.get('yoy') is not None else ''
        takeaways.append({
            'level': 'positive' if (mfg.get('yoy') or 0) >= 3 else ('warning' if (mfg.get('yoy') or 0) < 0 else 'neutral'),
            'title': '最新產業動能',
            'text': f"{mfg['period']} 製造業生產 YoY {mfg.get('yoy'):+.1f}%，較前月年增率變化 {mfg.get('acceleration_ppt'):+.1f} 個百分點；資訊電子 {(info or {}).get('yoy', 0):+.1f}%{sales_text}。",
            'evidence': [
                evidence('製造業', f"{mfg.get('yoy'):+.1f}% YoY", 'MOEA', 'industry', 'moea.industry.production', 'C', mfg.get('period')),
                evidence('資訊電子', f"{(info or {}).get('yoy', 0):+.1f}% YoY", 'MOEA', 'industry', 'moea.industry.production', 'I2', (info or {}).get('period')),
            ],
        })

    if divs:
        d = divs[0]
        takeaways.append({
            'level': 'warning',
            'title': '目前最重要背離：' + d['title'],
            'text': d['text'],
            'evidence': [evidence(d['direction'], f"{d['value']:+.1f} {d['unit']}", 'Elephant', d.get('target', {}).get('tab'), d.get('target', {}).get('dataset'), d.get('target', {}).get('series'))],
        })

    if population.get('population') is not None:
        takeaways.append({
            'level': 'warning' if (population.get('yoy_pct') or 0) < 0 else 'neutral',
            'title': '人口結構：總量下降與高齡化',
            'text': f"{population['period']} 年底人口 {population['population']:,.0f} 人，年變化 {population.get('yoy_pct'):+.2f}%；65 歲以上占 {population.get('share_65_plus'):.2f}%，自然增加 {population.get('natural_increase'):,.0f} 人。",
            'evidence': [
                evidence('總人口', f"{population['population']:,.0f}", 'RIS', 'population', period=population.get('period')),
                evidence('65+ 占比', f"{population.get('share_65_plus'):.2f}%", 'RIS', 'population', period=population.get('period')),
            ],
        })

    warnings = []
    for sid, s in status.get('sources', {}).items():
        if s.get('status') != 'ok':
            warnings.append(f"{sid}: {s.get('status')} — {s.get('message', '')}")
        for w in s.get('warnings', []) or []:
            warnings.append(f'{sid}: {w}')

    headline = f"{cycle['label']}、動能{cycle['momentum']}"
    if ndc_info.get('outlook') and ndc_info.get('outlook') != '資料不足':
        headline += f"；領先訊號{ndc_info['outlook']}"
    if population.get('yoy_pct') is not None and population['yoy_pct'] < 0:
        headline += '；人口續減'

    watch = watchlist(cycle, divs, weak, ndc_info)
    snapshot = snapshot_metrics(cycle, ind_out, population, ndc_info)

    out = {
        'version': 2,
        'generated_at': dt.datetime.now(TZ).replace(microsecond=0).isoformat(),
        'data_last_check_at': status.get('last_check_at'),
        'headline': headline,
        'stance': f"Elephant 目前判讀：{headline}。",
        'cycle': cycle,
        'confidence': conf,
        'leading': ndc_info,
        'takeaways': takeaways[:5],
        'turning_points': turns,
        'divergences': divs,
        'alerts': alerts,
        'watchlist': watch,
        'macro': {'growth': growth, 'cpi_yoy': cpi, 'nominal_gdp': nominal, 'regime': annual_regime},
        'industry': ind_out,
        'population': population,
        'revisions': {
            'new': revisions.get('new_revisions', [])[:20],
            'history_count': len(revisions.get('history', []) or []),
            'last_scan_at': revisions.get('last_scan_at'),
        },
        'snapshot': snapshot,
        'warnings': warnings,
        'methodology': '規則式經濟情報引擎：只使用 Elephant 已驗證官方資料；月度產業採同月 YoY，計算加速度、3M/6M 動能、12M 百分位、廣度、背離與轉折；不同基期序列不硬接。Cycle Score 為透明自訂分數，不等同國發會官方燈號；生成式 AI 不參與事實或分數計算。',
    }
    save('summary.json', out)
    return out

if __name__ == '__main__':
    print(json.dumps(generate(), ensure_ascii=False, indent=2))
