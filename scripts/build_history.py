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
WEIGHTS = {
    'manufacturing_yoy': 0.30,
    'breadth': 0.20,
    'sales_yoy': 0.15,
    'leading_3m': 0.20,
    'pmi': 0.10,
    'policy_score': 0.05,
}

def load(name, default=None):
    p = DATA / name
    if not p.exists():
        return {} if default is None else default
    return json.loads(p.read_text(encoding='utf-8'))

def save(name, obj):
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')

def clamp(v, lo=-100.0, hi=100.0):
    return max(lo, min(hi, float(v)))

def round2(v):
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return round(x, 2) if math.isfinite(x) else None

def month_shift(period, delta):
    try:
        y, m = map(int, str(period).split('-'))
    except Exception:
        return None
    idx = y * 12 + (m - 1) + delta
    return f'{idx // 12:04d}-{idx % 12 + 1:02d}'

def value_map(series):
    return {str(p): v for p, v in (series or {}).get('data', [])}

def pct(a, b):
    if a is None or b in (None, 0):
        return None
    return (float(a) / float(b) - 1.0) * 100.0

def yoy(series, period):
    d = value_map(series)
    return pct(d.get(period), d.get(month_shift(period, -12)))

def change3(series, period):
    d = value_map(series)
    return pct(d.get(period), d.get(month_shift(period, -3)))

def latest_at_or_before(series, period, max_age=2):
    d = value_map(series)
    for lag in range(max_age + 1):
        p = month_shift(period, -lag)
        if p in d:
            return d[p], p
    return None, None

def breadth_at(dataset, period):
    vals = []
    for s in (dataset or {}).get('series', {}).values():
        y = yoy(s, period)
        if y is not None and math.isfinite(y) and abs(y) <= 500:
            vals.append(y)
    if not vals:
        return None
    return 100.0 * sum(v > 0 for v in vals) / len(vals)

def score_components(prod_ds, sales_series, ndc_series, period):
    mfg = (prod_ds or {}).get('series', {}).get('C', {})
    mfg_yoy = yoy(mfg, period)
    breadth = breadth_at(prod_ds, period)
    sales_yoy = yoy(sales_series, period) if sales_series else None
    lead3 = change3(ndc_series.get('leading_no_trend', {}), period)
    pmi, pmi_p = latest_at_or_before(ndc_series.get('pmi', {}), period, 1)
    policy, policy_p = latest_at_or_before(ndc_series.get('policy_score', {}), period, 1)

    components = []
    def add(key, label, raw, component_score, note, source_period=None):
        if raw is None or component_score is None:
            return
        components.append({
            'key': key,
            'name': label,
            'raw': round2(raw),
            'score': round2(clamp(component_score)),
            'weight': WEIGHTS[key],
            'note': note,
            'period': source_period or period,
        })

    add('manufacturing_yoy', '製造業生產 YoY', mfg_yoy,
        None if mfg_yoy is None else mfg_yoy / 20.0 * 100.0, '同步生產動能')
    add('breadth', '產業正成長廣度', breadth,
        None if breadth is None else (breadth - 50.0) * 2.0, '擴張廣度')
    add('sales_yoy', '製造業銷售 YoY', sales_yoy,
        None if sales_yoy is None else sales_yoy / 12.0 * 100.0, '需求／銷售動能')
    add('leading_3m', '國發會領先指標 3M', lead3,
        None if lead3 is None else lead3 / 1.5 * 100.0, '官方領先訊號')
    add('pmi', 'PMI', pmi,
        None if pmi is None else (float(pmi) - 50.0) / 10.0 * 100.0, '企業採購動能', pmi_p)
    add('policy_score', '官方景氣綜合分數', policy,
        None if policy is None else (float(policy) - 27.0) / 18.0 * 100.0, '官方景氣狀態', policy_p)
    return components, {
        'manufacturing_yoy': round2(mfg_yoy),
        'breadth': round2(breadth),
        'sales_yoy': round2(sales_yoy),
        'leading_3m': round2(lead3),
        'pmi': round2(pmi),
        'policy_score': round2(policy),
    }

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

def compute_period(prod_ds, sales_series, ndc_series, period):
    components, raw = score_components(prod_ds, sales_series, ndc_series, period)
    weight_sum = sum(x['weight'] for x in components)
    if len(components) < 4 or weight_sum < 0.70:
        return None
    score = sum(x['score'] * x['weight'] for x in components) / weight_sum

    prev = month_shift(period, -1)
    prev_yoy = yoy((prod_ds or {}).get('series', {}).get('C', {}), prev)
    accel = None if raw['manufacturing_yoy'] is None or prev_yoy is None else raw['manufacturing_yoy'] - prev_yoy
    prev_breadth = breadth_at(prod_ds, prev)
    breadth_delta = None if raw['breadth'] is None or prev_breadth is None else raw['breadth'] - prev_breadth
    mom_parts = []
    if accel is not None: mom_parts.append(clamp(accel / 8.0 * 100.0))
    if breadth_delta is not None: mom_parts.append(clamp(breadth_delta / 20.0 * 100.0))
    if raw['leading_3m'] is not None: mom_parts.append(clamp(raw['leading_3m'] / 1.5 * 100.0))
    momentum = sum(mom_parts) / len(mom_parts) if mom_parts else 0.0
    return {
        'period': period,
        'score': round2(score),
        'label': cycle_label(score),
        'momentum_score': round2(momentum),
        'momentum': momentum_label(momentum),
        'breadth': raw['breadth'],
        'manufacturing_yoy': raw['manufacturing_yoy'],
        'sales_yoy': raw['sales_yoy'],
        'leading_3m': raw['leading_3m'],
        'pmi': raw['pmi'],
        'policy_score': raw['policy_score'],
        'components': components,
    }

def backtest(prod_ds, sales_series, ndc_series):
    mfg_periods = [str(p) for p, _ in (prod_ds or {}).get('series', {}).get('C', {}).get('data', [])]
    rows = []
    for p in mfg_periods:
        if p < '2012-01':
            continue
        row = compute_period(prod_ds, sales_series, ndc_series, p)
        if row:
            rows.append(row)
    return rows[-240:]

def update_summary(summary, backtest_rows):
    if not backtest_rows:
        return summary
    current = backtest_rows[-1]
    cycle = summary.setdefault('cycle', {})
    cycle.update({
        'score': current['score'],
        'label': current['label'],
        'momentum_score': current['momentum_score'],
        'momentum': current['momentum'],
        'breadth': current['breadth'],
        'components': current['components'],
        'as_of': current['period'],
        'method': '月度透明加權綜合分數：製造業生產30%、產業廣度20%、製造業銷售15%、國發會領先指標20%、PMI 10%、官方景氣綜合分數5%；缺值時重新正規化權重。不是國發會官方景氣燈號。',
    })
    scores = [r['score'] for r in backtest_rows if r.get('score') is not None]
    if scores:
        cycle['historical_percentile'] = round2(100.0 * sum(v <= current['score'] for v in scores) / len(scores))
        cycle['history_points'] = len(scores)

    lead = summary.get('leading', {})
    pop = summary.get('population', {})
    headline_parts = [current['label'], f"動能{current['momentum']}"]
    if lead.get('outlook'):
        headline_parts.append(f"領先訊號{lead['outlook']}")
    if (pop.get('yoy_pct') or 0) < 0:
        headline_parts.append('人口續減')
    summary['headline'] = '；'.join(headline_parts)
    summary['stance'] = 'Elephant 目前判讀：' + summary['headline'] + '。'
    if summary.get('takeaways'):
        summary['takeaways'][0]['title'] = f"景氣總判讀：{current['label']}，動能{current['momentum']}"
        summary['takeaways'][0]['text'] = (
            f"Elephant Cycle Score {current['score']:+.0f}/100；產業正成長廣度 "
            f"{current['breadth']:.0f}%。分數使用月度／高頻資料，避免把年度 GDP 混入月度景氣計分。"
        )

    snap = summary.setdefault('snapshot', {})
    metrics = snap.setdefault('metrics', {})
    metrics['cycle'] = {'label': 'Cycle Score', 'value': current['score'], 'unit': 'score'}
    metrics['momentum'] = {'label': 'Momentum', 'value': current['momentum_score'], 'unit': 'score'}
    metrics['breadth'] = {'label': 'Breadth', 'value': current['breadth'], 'unit': 'percent'}
    stable = json.dumps(metrics, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    snap['fingerprint'] = hashlib.sha256(stable.encode('utf-8')).hexdigest()[:16]
    summary['methodology'] = (
        '規則式經濟情報引擎：只使用 Elephant 已驗證官方資料；月度產業採同月 YoY，'
        '計算加速度、3M/6M 動能、12M 百分位、廣度、背離與轉折。Cycle Score 僅使用月度／高頻資料，'
        '可做歷史重建；不同基期序列不硬接。Cycle Score 為透明自訂分數，不等同國發會官方燈號；'
        '生成式 AI 不參與事實或分數計算。'
    )
    return summary

def append_snapshot(history, summary):
    snap = summary.get('snapshot', {})
    fp = snap.get('fingerprint')
    if not fp:
        return
    rows = history.setdefault('snapshots', [])
    if rows and rows[-1].get('fingerprint') == fp:
        return
    c = summary.get('cycle', {})
    i = summary.get('industry', {})
    lead = summary.get('leading', {})
    pop = summary.get('population', {})
    rows.append({
        'fingerprint': fp,
        'recorded_at': summary.get('generated_at'),
        'data_last_check_at': summary.get('data_last_check_at'),
        'headline': summary.get('headline'),
        'cycle_score': c.get('score'),
        'cycle_label': c.get('label'),
        'momentum_score': c.get('momentum_score'),
        'momentum': c.get('momentum'),
        'breadth': c.get('breadth'),
        'manufacturing_yoy': (i.get('manufacturing') or {}).get('yoy'),
        'information_electronics_yoy': (i.get('information_electronics') or {}).get('yoy'),
        'leading_3m': lead.get('leading_3m_pct'),
        'pmi': (lead.get('pmi') or {}).get('value'),
        'policy_score': (lead.get('policy_signal') or {}).get('score'),
        'population_yoy': pop.get('yoy_pct'),
    })
    history['snapshots'] = rows[-400:]

def regime_changes(rows):
    out, prev = [], None
    for r in rows:
        label = r.get('label')
        if prev and label != prev['label']:
            out.append({'period': r['period'], 'from': prev['label'], 'to': label, 'score': r['score']})
        prev = r
    return out[-50:]

def generate():
    industry = load('industry.json', {})
    ndc = load('ndc.json', {})
    summary = load('summary.json', {})
    history = load('intelligence_history.json', {'version': 1, 'snapshots': []})

    prod_ds = industry.get('datasets', {}).get('moea.industry.production', {})
    ndc_series = ndc.get('series', {})
    sales_series = ndc_series.get('manufacturing_sales_volume')
    if not sales_series:
        sales_series = (industry.get('datasets', {}).get('moea.manufacturing.sales_index_current', {})
                        .get('series', {}).get('C', {}))

    rows = backtest(prod_ds, sales_series, ndc_series)
    if not rows:
        raise ValueError('historical cycle reconstruction produced no rows')

    summary = update_summary(summary, rows)
    now = dt.datetime.now(TZ).replace(microsecond=0).isoformat()
    summary['generated_at'] = now
    append_snapshot(history, summary)
    history.update({
        'version': 1,
        'generated_at': now,
        'formula_version': 'monthly-v1',
        'formula': {
            'weights': WEIGHTS,
            'note': 'Historical reconstruction uses currently published revised official series; it is not a real-time vintage backtest.',
        },
        'cycle_history': [{k: v for k, v in r.items() if k != 'components'} for r in rows],
        'regime_changes': regime_changes(rows),
    })
    save('summary.json', summary)
    save('intelligence_history.json', history)
    return history

if __name__ == '__main__':
    print(json.dumps(generate(), ensure_ascii=False, indent=2))
