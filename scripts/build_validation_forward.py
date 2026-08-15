#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math

from common import TZ, load_json, save_json

DIRECTIONAL = ('growth_persistence', 'domestic_demand', 'financial_conditions')
ALL = DIRECTIONAL + ('ai_concentration',)


def month_shift(period, delta):
    try:
        y, m = map(int, str(period).split('-'))
    except Exception:
        return None
    i = y * 12 + m - 1 + delta
    return f'{i // 12:04d}-{i % 12 + 1:02d}'


def month_lag(newer, older):
    try:
        y1, m1 = map(int, str(newer).split('-'))
        y0, m0 = map(int, str(older).split('-'))
    except Exception:
        return None
    return max(0, (y1 - y0) * 12 + (m1 - m0))


def pearson(xs, ys):
    pairs = [(float(x), float(y)) for x, y in zip(xs, ys) if x is not None and y is not None and math.isfinite(float(x)) and math.isfinite(float(y))]
    if len(pairs) < 3:
        return None
    ax = sum(x for x, _ in pairs) / len(pairs)
    ay = sum(y for _, y in pairs) / len(pairs)
    dx = [x - ax for x, _ in pairs]
    dy = [y - ay for _, y in pairs]
    den = math.sqrt(sum(x*x for x in dx) * sum(y*y for y in dy))
    return None if den == 0 else sum(x*y for x, y in zip(dx, dy)) / den


def regime(score):
    if score is None:
        return None
    if score >= 25:
        return 'expansion'
    if score <= -25:
        return 'contraction'
    return 'neutral'


def score_bucket(score):
    if score >= 60:
        return 'strong_positive'
    if score >= 25:
        return 'positive'
    if score > -25:
        return 'neutral'
    if score > -60:
        return 'negative'
    return 'strong_negative'


def hmap(rows):
    return {str(r['period']): r for r in rows if r.get('period') and r.get('score') is not None}


def forward_pairs(signal_rows, cycle_rows, horizon):
    sm = hmap(signal_rows)
    cm = hmap(cycle_rows)
    out = []
    for p, row in sm.items():
        q = month_shift(p, horizon)
        target = cm.get(q)
        if target:
            out.append((p, float(row['score']), float(target['score']), target.get('label')))
    return out


def validate_signal(signal_rows, cycle_rows):
    result = {'target': 'future_cycle_score', 'mode': 'historical_reconstruction_revised_data', 'horizons': {}}
    rels = []
    for horizon in (3, 6):
        pairs = forward_pairs(signal_rows, cycle_rows, horizon)
        corr = pearson([x[1] for x in pairs], [x[2] for x in pairs])
        buckets = {}
        for _, signal, future, _ in pairs:
            b = score_bucket(signal)
            item = buckets.setdefault(b, {'n': 0, 'future_cycle_sum': 0.0, 'expansion': 0, 'contraction': 0})
            item['n'] += 1
            item['future_cycle_sum'] += future
            item['expansion'] += int(regime(future) == 'expansion')
            item['contraction'] += int(regime(future) == 'contraction')
        summaries = {}
        for k, v in buckets.items():
            n = v['n']
            summaries[k] = {
                'n': n,
                'future_cycle_mean': round(v['future_cycle_sum'] / n, 2),
                'future_expansion_rate': round(v['expansion'] / n * 100, 1),
                'future_contraction_rate': round(v['contraction'] / n * 100, 1),
            }
        positive = [x for x in pairs if x[1] >= 25]
        negative = [x for x in pairs if x[1] <= -25]
        discrimination = None
        if len(positive) >= 5 and len(negative) >= 5:
            discrimination = sum(x[2] for x in positive) / len(positive) - sum(x[2] for x in negative) / len(negative)
        reliability = None
        if corr is not None and len(pairs) >= 24:
            reliability = max(0.0, min(100.0, corr * 100.0))
            rels.append(reliability)
        result['horizons'][f'{horizon}m'] = {
            'samples': len(pairs),
            'pearson_to_future_cycle': None if corr is None else round(corr, 3),
            'positive_minus_negative_future_cycle': None if discrimination is None else round(discrimination, 2),
            'reliability': None if reliability is None else round(reliability, 1),
            'buckets': summaries,
        }
    result['reliability'] = None if not rels else round(sum(rels) / len(rels), 1)
    return result


def validate_persistence(signal_rows):
    sm = hmap(signal_rows)
    result = {'target': 'future_same_dimension_score', 'mode': 'historical_reconstruction_revised_data', 'horizons': {}}
    rels = []
    for horizon in (3, 6):
        pairs = []
        for p, row in sm.items():
            q = month_shift(p, horizon)
            if q in sm:
                pairs.append((float(row['score']), float(sm[q]['score'])))
        corr = pearson([x[0] for x in pairs], [x[1] for x in pairs])
        reliability = max(0, min(100, corr * 100)) if corr is not None and len(pairs) >= 24 else None
        if reliability is not None:
            rels.append(reliability)
        result['horizons'][f'{horizon}m'] = {
            'samples': len(pairs),
            'pearson_to_future_same_dimension': None if corr is None else round(corr, 3),
            'reliability': None if reliability is None else round(reliability, 1),
        }
    result['reliability'] = None if not rels else round(sum(rels) / len(rels), 1)
    return result


def freshness(cur):
    p = cur.get('period')
    parts = cur.get('components', [])
    if not p or not parts:
        return None
    total = sum(float(x.get('weight', 0)) for x in parts) or 1.0
    penalty = 0.0
    for x in parts:
        lag = month_lag(p, x.get('period'))
        if lag is None:
            lag = 6
        penalty += float(x.get('weight', 0)) * min(100, lag * 20)
    return round(max(0.0, 100.0 - penalty / total), 1)


def agreement(cur, ai=False):
    parts = cur.get('components', [])
    if not parts:
        return None
    signed = []
    for x in parts:
        s = float(x.get('score', 0))
        s = (s - 50.0) * 2.0 if ai else s
        signed.append((s, float(x.get('weight', 0))))
    den = sum(abs(s) * w for s, w in signed)
    if den < 1e-9:
        return 100.0
    return round(abs(sum(s * w for s, w in signed)) / den * 100.0, 1)


def confidence_breakdown(cur, reliability, ai=False):
    cov = float(cur.get('confidence', 0))
    fresh = freshness(cur)
    agree = agreement(cur, ai)
    factors = [
        ('coverage', cov, .30),
        ('freshness', fresh, .20),
        ('agreement', agree, .20),
        ('reliability', reliability, .30),
    ]
    used = [(k, v, w) for k, v, w in factors if v is not None]
    total_w = sum(w for _, _, w in used)
    overall = None if not used else sum(v * w for _, v, w in used) / total_w
    return {
        'coverage': round(cov, 1),
        'freshness': fresh,
        'agreement': agree,
        'reliability': reliability,
        'overall': None if overall is None else round(overall, 1),
        'overall_status': 'provisional_historical_reconstruction' if reliability is not None else 'provisional_no_reliability',
        'note': 'Coverage is data availability; reliability is measured separately. Historical reliability is not a real-time vintage backtest.',
    }


def nearest_forward_probabilities(scores, cycle_rows, horizon, limit=36):
    cycle = hmap(cycle_rows)
    gh = hmap(scores.get('history', {}).get('growth_persistence', []))
    fh = hmap(scores.get('history', {}).get('financial_conditions', []))
    current = scores.get('current', {})
    cc = current.get('growth_persistence')
    cf = current.get('financial_conditions')
    cycle_current = cycle_rows[-1] if cycle_rows else None
    if not cc or not cf or not cycle_current:
        return None
    target = (float(cycle_current['score']), float(cc['score']), float(cf['score']))
    candidates = []
    for p, c in cycle.items():
        if p not in gh or p not in fh:
            continue
        q = month_shift(p, horizon)
        if q not in cycle:
            continue
        state = (float(c['score']), float(gh[p]['score']), float(fh[p]['score']))
        dist = math.sqrt(sum(((a - b) / 100.0) ** 2 for a, b in zip(state, target)))
        candidates.append((dist, p, float(cycle[q]['score'])))
    candidates.sort()
    chosen = candidates[:limit]
    if len(chosen) < 12:
        return None
    weighted = {'expansion': 0.0, 'neutral': 0.0, 'contraction': 0.0}
    wsum = 0.0
    for dist, _, future in chosen:
        w = 1.0 / (0.15 + dist)
        weighted[regime(future)] += w
        wsum += w
    probs = {k: round(v / wsum * 100, 1) for k, v in weighted.items()}
    probs['expansion'] = round(probs['expansion'] + round(100.0 - sum(probs.values()), 1), 1)
    return {
        'horizon_months': horizon,
        'method': 'distance-weighted historical analogs on Cycle + Growth Persistence + Financial Conditions',
        'mode': 'historical_reconstruction_revised_data',
        'sample_count': len(chosen),
        'probabilities': probs,
        'nearest_periods': [p for _, p, _ in chosen[:8]],
    }


def weighted_score(parts, weights=None):
    if not parts:
        return None
    ws = weights or {x['key']: float(x.get('weight', 0)) for x in parts}
    den = sum(ws.get(x['key'], 0) for x in parts)
    if den <= 0:
        return None
    return sum(float(x['score']) * ws.get(x['key'], 0) for x in parts) / den


def sensitivity(cur):
    parts = cur.get('components', [])
    if len(parts) < 2:
        return None
    base = weighted_score(parts)
    changes = []
    for x in parts:
        original = {p['key']: float(p.get('weight', 0)) for p in parts}
        for factor in (.8, 1.2):
            w = dict(original)
            w[x['key']] *= factor
            alt = weighted_score(parts, w)
            changes.append(abs(alt - base))
    max_change = max(changes) if changes else 0.0
    return {
        'method': 'one-component weight ±20%; no automatic re-optimization',
        'max_current_score_change': round(max_change, 2),
        'status': 'locally_robust' if max_change <= 5 else 'weight_sensitive',
    }


def scenario(cur, ai=False):
    parts = cur.get('components', [])
    if not parts:
        return None
    base = weighted_score(parts)
    if ai:
        shocked = [{**x, 'score': max(0.0, float(x['score']) - 25.0)} for x in parts]
        return {
            'type': 'deconcentration_standardized',
            'baseline': round(base, 2),
            'scenario_score': round(weighted_score(shocked), 2),
            'threshold': 60.0,
            'note': 'Sensitivity scenario only; not a probability forecast.',
        }
    shocked = [{**x, 'score': max(-100.0, float(x['score']) - 50.0)} for x in parts]
    coverage = sum(float(x.get('weight', 0)) for x in parts)
    candidates = []
    if base is not None and base > 0 and coverage > 0:
        for x in parts:
            w = float(x.get('weight', 0))
            if w <= 0:
                continue
            required = base * coverage / w
            candidates.append({
                'component': x['key'],
                'required_score_drop_to_cross_zero_alone': round(required, 1),
                'feasible_within_-100_floor': required <= float(x['score']) + 100.0,
            })
    return {
        'type': 'standardized_bear',
        'baseline': round(base, 2),
        'scenario_score': round(weighted_score(shocked), 2),
        'shock': 'each available component score -50 points, floored at -100',
        'reverse_stress': {
            'uniform_component_drop_to_cross_zero': None if base is None or base <= 0 else round(base, 1),
            'single_component_candidates': sorted(candidates, key=lambda x: x['required_score_drop_to_cross_zero_alone']),
        },
        'note': 'Sensitivity scenario only; not a probability forecast.',
    }


def generate():
    scores = load_json('decision_scores.json', {})
    history = load_json('intelligence_history.json', {})
    cycle_rows = history.get('cycle_history', [])
    current = scores.get('current', {})
    validations = {}
    for key in DIRECTIONAL:
        validations[key] = validate_signal(scores.get('history', {}).get(key, []), cycle_rows)
    validations['ai_concentration'] = validate_persistence(scores.get('history', {}).get('ai_concentration', []))

    quality = {}
    scenarios = {}
    calibration = {}
    for key in ALL:
        cur = current.get(key)
        if not cur:
            continue
        rel = validations.get(key, {}).get('reliability')
        quality[key] = confidence_breakdown(cur, rel, key == 'ai_concentration')
        scenarios[key] = scenario(cur, key == 'ai_concentration')
        calibration[key] = sensitivity(cur)

    forward = {}
    for horizon in (3, 6):
        item = nearest_forward_probabilities(scores, cycle_rows, horizon)
        if item:
            forward[f'{horizon}m'] = item

    formula_fp = hashlib.sha256(
        json.dumps(scores.get('methodology', {}), ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    ).hexdigest()[:16]
    out = {
        'version': 1,
        'generated_at': dt.datetime.now(TZ).replace(microsecond=0).isoformat(),
        'contract': 'deterministic-validation-forward-v1',
        'score_formula_fingerprint': formula_fp,
        'evidence_boundary': {
            'historical_reconstruction_is_revised': True,
            'realtime_vintage_backtest_available': False,
            'note': 'Historical validation can measure information value but may contain official-data revision bias. True vintage reliability begins only after immutable Elephant vintages accumulate.',
        },
        'validation': validations,
        'confidence': quality,
        'forward_regime_probability': forward,
        'scenario_engine': scenarios,
        'calibration': calibration,
    }
    save_json('validation_forward.json', out)
    return out


if __name__ == '__main__':
    print(json.dumps(generate(), ensure_ascii=False, indent=2))
