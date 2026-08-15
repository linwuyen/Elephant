#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict

from common import TZ, load_json, save_json

DIRECTIONAL = ('growth_persistence', 'domestic_demand', 'financial_conditions')
ALL_DIMS = DIRECTIONAL + ('ai_concentration',)


def month_shift(period, delta):
    try:
        y, m = map(int, str(period).split('-'))
    except Exception:
        return None
    idx = y * 12 + (m - 1) + delta
    return f'{idx // 12:04d}-{idx % 12 + 1:02d}'


def month_lag(newer, older):
    try:
        y1, m1 = map(int, str(newer).split('-'))
        y0, m0 = map(int, str(older).split('-'))
    except Exception:
        return None
    return max(0, (y1 - y0) * 12 + (m1 - m0))


def finite(v):
    try:
        return math.isfinite(float(v))
    except Exception:
        return False


def pearson(xs, ys):
    pairs = [(float(x), float(y)) for x, y in zip(xs, ys) if finite(x) and finite(y)]
    if len(pairs) < 3:
        return None
    mx = sum(x for x, _ in pairs) / len(pairs)
    my = sum(y for _, y in pairs) / len(pairs)
    dx = [x - mx for x, _ in pairs]
    dy = [y - my for _, y in pairs]
    den = math.sqrt(sum(x*x for x in dx) * sum(y*y for y in dy))
    return None if den <= 1e-12 else sum(x*y for x, y in zip(dx, dy)) / den


def regime(score):
    if score >= 25:
        return 'expansion'
    if score <= -25:
        return 'contraction'
    return 'neutral'


def bucket(score):
    if score >= 60:
        return 'strong_positive'
    if score >= 25:
        return 'positive'
    if score > -25:
        return 'neutral'
    if score > -60:
        return 'negative'
    return 'strong_negative'


def as_map(rows):
    return {
        str(x['period']): x for x in (rows or [])
        if x.get('period') and finite(x.get('score'))
    }


def cycle_history():
    hist = load_json('intelligence_history.json', {})
    rows = hist.get('cycle_history', [])
    if rows:
        return rows
    summary = load_json('summary.json', {})
    return summary.get('cycle_history', [])


def cross_dimension(signal_rows, target_rows, horizons=(3, 6)):
    signal = as_map(signal_rows)
    target = as_map(target_rows)
    out = {}
    reliabilities = []
    for horizon in horizons:
        pairs = []
        for period, row in signal.items():
            future_period = month_shift(period, horizon)
            future = target.get(future_period)
            if future:
                pairs.append((period, float(row['score']), float(future['score'])))
        corr = pearson([x[1] for x in pairs], [x[2] for x in pairs])
        grouped = defaultdict(list)
        for _, sig, future in pairs:
            grouped[bucket(sig)].append(future)
        buckets = {}
        for name, vals in sorted(grouped.items()):
            n = len(vals)
            buckets[name] = {
                'n': n,
                'future_cycle_mean': round(sum(vals) / n, 2),
                'future_expansion_rate': round(sum(regime(v) == 'expansion' for v in vals) / n * 100, 1),
                'future_neutral_rate': round(sum(regime(v) == 'neutral' for v in vals) / n * 100, 1),
                'future_contraction_rate': round(sum(regime(v) == 'contraction' for v in vals) / n * 100, 1),
            }
        reliability = None
        if corr is not None and len(pairs) >= 24:
            # Reliability is intentionally conservative: negative correlation is zero,
            # and small samples cannot produce a reliability score.
            reliability = round(max(0.0, min(100.0, corr * 100.0)), 1)
            reliabilities.append(reliability)
        out[f'{horizon}m'] = {
            'samples': len(pairs),
            'pearson_to_future_cycle': None if corr is None else round(corr, 3),
            'reliability': reliability,
            'buckets': buckets,
        }
    return {
        'mode': 'revised_historical_reconstruction',
        'target': 'future_cycle_score',
        'horizons': out,
        'reliability': None if not reliabilities else round(sum(reliabilities) / len(reliabilities), 1),
    }


def self_persistence(rows, horizons=(3, 6)):
    data = as_map(rows)
    out = {}
    reliabilities = []
    for horizon in horizons:
        pairs = []
        for p, row in data.items():
            q = month_shift(p, horizon)
            if q in data:
                pairs.append((float(row['score']), float(data[q]['score'])))
        corr = pearson([x[0] for x in pairs], [x[1] for x in pairs])
        rel = None if corr is None or len(pairs) < 24 else round(max(0, min(100, corr * 100)), 1)
        if rel is not None:
            reliabilities.append(rel)
        out[f'{horizon}m'] = {
            'samples': len(pairs),
            'pearson_to_future_same_dimension': None if corr is None else round(corr, 3),
            'reliability': rel,
        }
    return {
        'mode': 'revised_historical_reconstruction',
        'target': 'future_same_dimension_score',
        'horizons': out,
        'reliability': None if not reliabilities else round(sum(reliabilities) / len(reliabilities), 1),
    }


def freshness(cur):
    parts = cur.get('components', [])
    base_period = cur.get('period')
    if not parts or not base_period:
        return None
    den = sum(float(x.get('weight', 0)) for x in parts)
    if den <= 0:
        return None
    penalty = 0.0
    for part in parts:
        lag = month_lag(base_period, part.get('period'))
        if lag is None:
            lag = 6
        # one month of official publication lag costs 15 points; capped.
        penalty += float(part.get('weight', 0)) * min(100.0, lag * 15.0)
    return round(max(0.0, 100.0 - penalty / den), 1)


def agreement(cur, ai=False):
    parts = cur.get('components', [])
    if not parts:
        return None
    signed = []
    for part in parts:
        score = float(part.get('score', 0))
        if ai:
            score = (score - 50.0) * 2.0
        signed.append((score, float(part.get('weight', 0))))
    den = sum(abs(s) * w for s, w in signed)
    if den <= 1e-9:
        return 100.0
    return round(abs(sum(s*w for s, w in signed)) / den * 100.0, 1)


def confidence_decomposition(cur, reliability, ai=False):
    coverage = float(cur.get('confidence', 0))
    fresh = freshness(cur)
    agree = agreement(cur, ai)
    factors = [
        ('coverage', coverage, .30),
        ('freshness', fresh, .20),
        ('agreement', agree, .20),
        ('reliability', reliability, .30),
    ]
    used = [(k, v, w) for k, v, w in factors if v is not None]
    total_w = sum(w for _, _, w in used)
    overall = None if not total_w else sum(v*w for _, v, w in used) / total_w
    return {
        'coverage': round(coverage, 1),
        'freshness': fresh,
        'signal_agreement': agree,
        'historical_reliability': reliability,
        'provisional_overall': None if overall is None else round(overall, 1),
        'authority': False,
        'note': 'Diagnostic decomposition only. It does not replace Decision Engine Data/Model/Decision Confidence.',
    }


def weight_sensitivity(cur):
    parts = cur.get('components', [])
    if len(parts) < 2:
        return None
    original = {x['key']: float(x.get('weight', 0)) for x in parts}
    den = sum(original.values())
    if den <= 0:
        return None
    base = sum(float(x['score']) * original[x['key']] for x in parts) / den
    tests = []
    for part in parts:
        for factor in (.8, 1.2):
            weights = dict(original)
            weights[part['key']] *= factor
            d = sum(weights.values())
            score = sum(float(x['score']) * weights[x['key']] for x in parts) / d
            tests.append({'component': part['key'], 'factor': factor, 'score': round(score, 2), 'delta': round(score-base, 2)})
    maximum = max(abs(x['delta']) for x in tests)
    return {
        'method': 'one component weight ±20%; fixed production weights remain authoritative',
        'baseline': round(base, 2),
        'max_abs_score_change': round(maximum, 2),
        'status': 'locally_robust' if maximum <= 5 else 'weight_sensitive',
        'tests': tests,
    }


def reverse_stress(cur, ai=False):
    if ai:
        return {
            'applicable': False,
            'reason': 'AI Concentration is a concentration index, not a directional economic-health score.',
        }
    parts = cur.get('components', [])
    if not parts:
        return None
    den = sum(float(x.get('weight', 0)) for x in parts)
    if den <= 0:
        return None
    current = sum(float(x['score']) * float(x['weight']) for x in parts) / den
    if current <= 0:
        return {
            'applicable': True,
            'current_score': round(current, 2),
            'uniform_drop_to_cross_zero': 0.0,
            'single_component': [],
        }
    candidates = []
    for part in parts:
        w = float(part.get('weight', 0))
        if w <= 0:
            continue
        required = current * den / w
        candidates.append({
            'component': part['key'],
            'required_score_drop': round(required, 1),
            'feasible_before_-100_floor': required <= float(part['score']) + 100.0,
        })
    return {
        'applicable': True,
        'current_score': round(current, 2),
        'uniform_drop_to_cross_zero': round(current, 1),
        'single_component': sorted(candidates, key=lambda x: x['required_score_drop']),
        'note': 'Reverse stress is a sensitivity threshold, not a forecast probability.',
    }


def historical_analogs(scores, cycle_rows, horizon, max_neighbors=36):
    cycle = as_map(cycle_rows)
    growth = as_map(scores.get('history', {}).get('growth_persistence', []))
    financial = as_map(scores.get('history', {}).get('financial_conditions', []))
    current = scores.get('current', {})
    cur_cycle = cycle_rows[-1] if cycle_rows else None
    cur_growth = current.get('growth_persistence')
    cur_fin = current.get('financial_conditions')
    if not cur_cycle or not cur_growth or not cur_fin:
        return None
    target = (float(cur_cycle['score']), float(cur_growth['score']), float(cur_fin['score']))
    candidates = []
    for p, c in cycle.items():
        q = month_shift(p, horizon)
        if p not in growth or p not in financial or q not in cycle:
            continue
        state = (float(c['score']), float(growth[p]['score']), float(financial[p]['score']))
        dist = math.sqrt(sum(((a-b)/100.0)**2 for a, b in zip(state, target)))
        candidates.append((dist, p, float(cycle[q]['score'])))
    candidates.sort()
    chosen = candidates[:max_neighbors]
    if len(chosen) < 12:
        return None
    weighted = {'expansion': 0.0, 'neutral': 0.0, 'contraction': 0.0}
    total = 0.0
    for dist, _, future in chosen:
        w = 1.0 / (0.15 + dist)
        weighted[regime(future)] += w
        total += w
    probs = {k: round(v/total*100, 1) for k, v in weighted.items()}
    residual = round(100.0 - sum(probs.values()), 1)
    probs['expansion'] = round(probs['expansion'] + residual, 1)
    return {
        'horizon_months': horizon,
        'method': 'distance-weighted historical analogs: Cycle + Growth Persistence + Financial Conditions',
        'mode': 'revised_historical_reconstruction',
        'sample_count': len(chosen),
        'probabilities': probs,
        'nearest_periods': [p for _, p, _ in chosen[:8]],
        'authority': False,
        'note': 'Diagnostic cross-check only; Decision Engine forecast remains authoritative.',
    }


def generate():
    scores = load_json('decision_scores.json', {})
    cycle_rows = cycle_history()
    if not cycle_rows:
        raise RuntimeError('cycle history unavailable')

    validation = {}
    for key in DIRECTIONAL:
        validation[key] = cross_dimension(scores.get('history', {}).get(key, []), cycle_rows)
    validation['ai_concentration'] = self_persistence(scores.get('history', {}).get('ai_concentration', []))

    confidence = {}
    sensitivity = {}
    stress = {}
    for key in ALL_DIMS:
        cur = scores.get('current', {}).get(key)
        if not cur:
            continue
        confidence[key] = confidence_decomposition(cur, validation[key].get('reliability'), key == 'ai_concentration')
        sensitivity[key] = weight_sensitivity(cur)
        stress[key] = reverse_stress(cur, key == 'ai_concentration')

    analogs = {}
    for horizon in (3, 6):
        item = historical_analogs(scores, cycle_rows, horizon)
        if item:
            analogs[f'{horizon}m'] = item

    out = {
        'version': 1,
        'generated_at': dt.datetime.now(TZ).replace(microsecond=0).isoformat(),
        'contract': 'non_authoritative-model-validation-extension-v1',
        'evidence_boundary': {
            'historical_inputs': 'latest-revised official series reconstructed through current formulas',
            'real_time_vintage_validation': False,
            'prospective_vintage_path': 'data/vintages.db + Decision Journal outcomes',
            'warning': 'Historical results may contain official-revision bias and must not be described as point-in-time forecast performance.',
        },
        'cross_dimension_validation': validation,
        'confidence_decomposition': confidence,
        'historical_analog_regime_probability': analogs,
        'weight_sensitivity': sensitivity,
        'reverse_stress': stress,
    }
    save_json('model_validation.json', out)
    return out


if __name__ == '__main__':
    generate()
