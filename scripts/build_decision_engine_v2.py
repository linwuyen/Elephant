#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict

from common import TZ, load_json, save_json

HORIZONS = (1, 3, 6, 12)
CORE_DIMS = ('cycle', 'growth_persistence', 'domestic_demand', 'financial_conditions')
ALL_DIMS = CORE_DIMS + ('ai_concentration',)
SCORE_BINS = (-100, -60, -25, -5, 5, 25, 60, 101)
MIN_WALK_FORWARD_TRAIN = 12
RECONSTRUCTION_EVIDENCE_FACTOR = 0.70


def clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, float(v)))


def month_shift(period, delta):
    try:
        y, m = map(int, str(period).split('-'))
    except Exception:
        return None
    idx = y * 12 + m - 1 + int(delta)
    return f'{idx // 12:04d}-{idx % 12 + 1:02d}'


def as_map(rows):
    return {
        str(x.get('period')): float(x.get('score'))
        for x in (rows or [])
        if x.get('period') and x.get('score') is not None
    }


def series_map(series):
    return {str(p): float(v) for p, v in (series or {}).get('data', []) if v is not None}


def score_histories():
    decisions = load_json('decision_scores.json', {'history': {}})
    intel = load_json('intelligence_history.json', {'cycle_history': []})
    out = {'cycle': intel.get('cycle_history') or []}
    for key in ('growth_persistence', 'domestic_demand', 'financial_conditions', 'ai_concentration'):
        out[key] = (decisions.get('history') or {}).get(key) or []
    return out


def current_scores():
    decisions = load_json('decision_scores.json', {'current': {}})
    summary = load_json('summary.json', {})
    out = dict(decisions.get('current') or {})
    cyc = summary.get('cycle') or {}
    if cyc:
        out['cycle'] = {
            'period': cyc.get('as_of'),
            'score': cyc.get('score'),
            'label': cyc.get('label'),
            'confidence': (summary.get('confidence') or {}).get('score'),
        }
    return out


def score_bin(score):
    s = float(score)
    for lo, hi in zip(SCORE_BINS[:-1], SCORE_BINS[1:]):
        if lo <= s < hi:
            return lo, hi
    return SCORE_BINS[-2], SCORE_BINS[-1]


def target_positive(key, score):
    if key == 'ai_concentration':
        return float(score) >= 60
    return float(score) > 0


def logistic_prior(key, score):
    s = float(score)
    x = (s - 60.0) / 14.0 if key == 'ai_concentration' else s / 28.0
    x = max(-8.0, min(8.0, x))
    return 1.0 / (1.0 + math.exp(-x))


def completed_pairs(rows, horizon):
    data = as_map(rows)
    pairs = []
    for p in sorted(data):
        q = month_shift(p, horizon)
        if q in data:
            pairs.append({'period': p, 'score': data[p], 'outcome_period': q, 'future_score': data[q]})
    return pairs


def fit_probability(key, training_pairs, score):
    prior = logistic_prior(key, score)
    lo, hi = score_bin(score)
    local = [x for x in training_pairs if lo <= float(x['score']) < hi]
    n = len(local)
    successes = sum(target_positive(key, x['future_score']) for x in local)
    empirical = (successes + 1) / (n + 2) if n else prior
    weight = n / (n + 8.0)
    probability = weight * empirical + (1.0 - weight) * prior
    expected = sum(float(x['future_score']) for x in local) / n if n else float(score)
    return probability, expected, n, (lo, hi)


def brier_baseline(actuals):
    if not actuals:
        return None
    rate = sum(actuals) / len(actuals)
    return sum((rate - y) ** 2 for y in actuals) / len(actuals)


def sample_adequacy(n, target=60):
    if n <= 0:
        return 0.0
    return round(min(100.0, math.sqrt(float(n) / float(target)) * 100.0), 1)


def sample_aware_confidence(brier, baseline_brier, accuracy, n, local_n, prospective_n=0, regime_similarity=100.0):
    if brier is None or baseline_brier in (None, 0) or n <= 0:
        return 0.0
    skill = 1.0 - float(brier) / float(baseline_brier)
    brier_skill = clamp(skill * 100.0)
    global_sample = sample_adequacy(n, 60)
    local_sample = sample_adequacy(local_n, 20)
    sample_score = 0.7 * global_sample + 0.3 * local_sample
    evidence_factor = RECONSTRUCTION_EVIDENCE_FACTOR + 0.30 * min(1.0, float(prospective_n) / 60.0)
    raw = 0.50 * brier_skill + 0.25 * clamp(float(accuracy) * 100.0) + 0.25 * sample_score
    raw *= evidence_factor
    raw *= 0.70 + 0.30 * clamp(regime_similarity) / 100.0
    return round(clamp(raw), 1)


def walk_forward_dimension(key, rows, horizon, current_score=None, current_period=None, prospective_n=0, regime_similarity=100.0):
    pairs = completed_pairs(rows, horizon)
    predictions = []
    for item in pairs:
        # Strict information boundary: at prediction month p, a training example is
        # eligible only if its future outcome had already occurred on/before p.
        training = [x for x in pairs if x['outcome_period'] <= item['period']]
        if len(training) < MIN_WALK_FORWARD_TRAIN:
            continue
        prob, expected, local_n, band = fit_probability(key, training, item['score'])
        y = 1.0 if target_positive(key, item['future_score']) else 0.0
        predictions.append({
            'period': item['period'],
            'outcome_period': item['outcome_period'],
            'probability': prob,
            'actual': y,
            'training_samples': len(training),
            'local_samples': local_n,
            'training_cutoff': max(x['outcome_period'] for x in training),
            'score_bin': list(band),
            'expected_score': expected,
        })

    if predictions:
        brier = sum((x['probability'] - x['actual']) ** 2 for x in predictions) / len(predictions)
        actuals = [x['actual'] for x in predictions]
        baseline = brier_baseline(actuals)
        accuracy = sum((x['probability'] >= .5) == bool(x['actual']) for x in predictions) / len(predictions)
    else:
        brier = baseline = accuracy = None

    current = None
    if current_score is not None:
        eligible = [x for x in pairs if current_period is None or x['outcome_period'] <= current_period]
        probability, expected, local_n, band = fit_probability(key, eligible, float(current_score))
        confidence = sample_aware_confidence(
            brier, baseline, accuracy or 0.0, len(predictions), local_n,
            prospective_n=prospective_n, regime_similarity=regime_similarity,
        )
        current = {
            'probability': round(probability, 4),
            'expected_score': round(float(expected), 2),
            'local_sample_size': local_n,
            'completed_training_samples': len(eligible),
            'current_score_bin': list(band),
            'model_confidence': confidence,
        }

    skill = None if brier is None or baseline in (None, 0) else 1.0 - brier / baseline
    return {
        'horizon_months': horizon,
        'method': 'strict expanding-window walk-forward; training outcomes must be observable by prediction month',
        'oos_predictions': len(predictions),
        'brier_score': None if brier is None else round(brier, 4),
        'climatology_brier': None if baseline is None else round(baseline, 4),
        'brier_skill_vs_climatology': None if skill is None else round(skill, 4),
        'direction_accuracy': None if accuracy is None else round(accuracy, 4),
        'sample_adequacy': sample_adequacy(len(predictions), 60),
        'current': current,
        'leakage_guard': 'training outcome_period <= prediction period',
    }


def percent_change(values, p0, p1):
    a, b = values.get(p0), values.get(p1)
    if a in (None, 0) or b is None:
        return None
    return (float(b) / float(a) - 1.0) * 100.0


def yoy_at(values, period):
    return percent_change(values, month_shift(period, -12), period)


def forward_drawdown(values, period, horizon):
    path = []
    for i in range(horizon + 1):
        v = values.get(month_shift(period, i))
        if v is None:
            return None
        path.append(float(v))
    peak = path[0]
    worst = 0.0
    for value in path:
        peak = max(peak, value)
        draw = (value / peak - 1.0) * 100.0
        worst = min(worst, draw)
    return worst


def pearson(xs, ys):
    pairs = [(float(x), float(y)) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 3:
        return None
    mx = sum(x for x, _ in pairs) / len(pairs)
    my = sum(y for _, y in pairs) / len(pairs)
    denx = sum((x - mx) ** 2 for x, _ in pairs)
    deny = sum((y - my) ** 2 for _, y in pairs)
    den = math.sqrt(denx * deny)
    if den <= 1e-12:
        return None
    return sum((x - mx) * (y - my) for x, y in pairs) / den


def external_outcomes(histories):
    ndc = load_json('ndc.json', {}).get('series', {})
    decision = load_json('decision_inputs.json', {}).get('series', {})
    targets = {
        'industrial_production_yoy': ('macro', series_map(ndc.get('industrial_production'))),
        'exports_yoy': ('macro', series_map(ndc.get('customs_exports'))),
        'employment_yoy': ('macro', series_map(decision.get('dgbas.employment_total'))),
        'stock_forward_return': ('market', series_map(ndc.get('stock_index'))),
    }
    out = {}
    for dim in CORE_DIMS:
        signal = as_map(histories.get(dim, []))
        dim_out = {}
        for target_name, (kind, values) in targets.items():
            if not values:
                continue
            horizons = {}
            for h in (3, 6, 12):
                rows = []
                for p, score in signal.items():
                    q = month_shift(p, h)
                    outcome = yoy_at(values, q) if kind == 'macro' else percent_change(values, p, q)
                    if outcome is None:
                        continue
                    rows.append((score, outcome))
                corr = pearson([x[0] for x in rows], [x[1] for x in rows])
                directional = None
                if rows:
                    directional = sum((s > 0) == (o > 0) for s, o in rows) / len(rows)
                horizons[f'{h}m'] = {
                    'samples': len(rows),
                    'pearson': None if corr is None else round(corr, 3),
                    'direction_accuracy': None if directional is None else round(directional, 4),
                }
            dim_out[target_name] = {'kind': kind, 'horizons': horizons}
        out[dim] = dim_out

    stock = series_map(ndc.get('stock_index'))
    if stock:
        drawdown = {}
        for dim in CORE_DIMS:
            signal = as_map(histories.get(dim, []))
            hs = {}
            for h in (3, 6, 12):
                rows = [(score, forward_drawdown(stock, p, h)) for p, score in signal.items()]
                rows = [(s, d) for s, d in rows if d is not None]
                corr = pearson([x[0] for x in rows], [x[1] for x in rows])
                hs[f'{h}m'] = {'samples': len(rows), 'pearson_score_to_forward_drawdown': None if corr is None else round(corr, 3)}
            drawdown[dim] = hs
        out['_market_drawdown'] = drawdown
    return out


def historical_risk_states(histories):
    maps = {k: as_map(histories.get(k, [])) for k in ALL_DIMS}
    periods = sorted(set.intersection(*(set(m) for m in maps.values() if m))) if all(maps.values()) else []
    states = []
    for p in periods:
        cycle = maps['cycle'][p]
        growth = maps['growth_persistence'][p]
        domestic = maps['domestic_demand'][p]
        financial = maps['financial_conditions'][p]
        concentration = maps['ai_concentration'][p]
        base = 50 + .14 * cycle + .16 * growth + .16 * financial + .06 * domestic
        penalty = max(0.0, concentration - 55.0) * .55
        risk_score = clamp(base - penalty)
        equity_pct = clamp(25 + .65 * risk_score, 20, 90)
        states.append({'period': p, 'risk_score': risk_score, 'equity_pct': equity_pct})
    return states


def compound(returns):
    wealth = 1.0
    peak = 1.0
    worst = 0.0
    for r in returns:
        wealth *= 1.0 + float(r) / 100.0
        peak = max(peak, wealth)
        worst = min(worst, (wealth / peak - 1.0) * 100.0)
    return (wealth - 1.0) * 100.0, worst


def risk_budget_backtest(histories):
    ndc = load_json('ndc.json', {}).get('series', {})
    stock = series_map(ndc.get('stock_index'))
    states = historical_risk_states(histories)
    if not stock:
        return {'status': 'BLOCKED_NO_STOCK_INDEX'}

    monthly_policy, monthly_static = [], []
    used = []
    for state in states:
        p, q = state['period'], month_shift(state['period'], 1)
        ret = percent_change(stock, p, q)
        if ret is None:
            continue
        policy_ret = ret * state['equity_pct'] / 100.0
        static_ret = ret * .60
        monthly_policy.append(policy_ret)
        monthly_static.append(static_ret)
        used.append({**state, 'stock_return_1m_pct': ret, 'policy_return_1m_pct': policy_ret})

    policy_total, policy_dd = compound(monthly_policy) if monthly_policy else (None, None)
    static_total, static_dd = compound(monthly_static) if monthly_static else (None, None)

    horizon_stats = {}
    for h in (3, 6, 12):
        rows = []
        for state in states:
            ret = percent_change(stock, state['period'], month_shift(state['period'], h))
            dd = forward_drawdown(stock, state['period'], h)
            if ret is not None and dd is not None:
                rows.append((state['risk_score'], ret, dd))
        buckets = defaultdict(list)
        for risk, ret, dd in rows:
            lo = int(min(80, math.floor(risk / 20) * 20))
            buckets[f'{lo}-{lo+20}'].append((ret, dd))
        horizon_stats[f'{h}m'] = {
            'samples': len(rows),
            'pearson_risk_to_forward_return': None if not rows else round(pearson([x[0] for x in rows], [x[1] for x in rows]) or 0.0, 3),
            'pearson_risk_to_forward_drawdown': None if not rows else round(pearson([x[0] for x in rows], [x[2] for x in rows]) or 0.0, 3),
            'buckets': {
                key: {
                    'n': len(vals),
                    'mean_forward_return_pct': round(sum(x[0] for x in vals) / len(vals), 2),
                    'mean_forward_drawdown_pct': round(sum(x[1] for x in vals) / len(vals), 2),
                }
                for key, vals in sorted(buckets.items())
            },
        }

    return {
        'status': 'DIAGNOSTIC_ONLY',
        'authority': False,
        'observations': len(used),
        'policy_vs_static_60_equity': {
            'policy_scaled_equity_return_pct': None if policy_total is None else round(policy_total, 2),
            'static_60_equity_return_pct': None if static_total is None else round(static_total, 2),
            'policy_max_drawdown_pct': None if policy_dd is None else round(policy_dd, 2),
            'static_60_max_drawdown_pct': None if static_dd is None else round(static_dd, 2),
            'cash_return_assumption_pct': 0.0,
            'transaction_costs_included': False,
        },
        'horizons': horizon_stats,
        'warning': 'Reconstructed-score diagnostic only. It is not a tradable portfolio backtest and cannot alter v1 Risk Budget.',
    }


def regime_similarity(histories, current):
    maps = {k: as_map(histories.get(k, [])) for k in ALL_DIMS}
    if not all(maps.values()):
        return {'similarity': 0.0, 'status': 'INSUFFICIENT_HISTORY'}
    periods = sorted(set.intersection(*(set(m) for m in maps.values())))
    vector = []
    for key in ALL_DIMS:
        score = (current.get(key) or {}).get('score')
        if score is None:
            return {'similarity': 0.0, 'status': 'MISSING_CURRENT_DIMENSION'}
        vector.append(float(score))
    distances = []
    for p in periods[:-1]:
        state = [maps[k][p] for k in ALL_DIMS]
        dist = math.sqrt(sum(((a - b) / 100.0) ** 2 for a, b in zip(state, vector)))
        distances.append((dist, p))
    if not distances:
        return {'similarity': 0.0, 'status': 'INSUFFICIENT_HISTORY'}
    distances.sort()
    nearest = distances[:min(12, len(distances))]
    mean_dist = sum(x[0] for x in nearest) / len(nearest)
    similarity = clamp(math.exp(-mean_dist) * 100.0)
    status = 'HIGH' if similarity >= 75 else 'MEDIUM' if similarity >= 50 else 'LOW'
    return {
        'similarity': round(similarity, 1),
        'status': status,
        'nearest_periods': [p for _, p in nearest[:8]],
        'mean_normalized_distance': round(mean_dist, 3),
        'confidence_penalty_applied': True,
    }


def prospective_count():
    journal = load_json('decision_journal.json', {})
    scorecard = journal.get('scorecard') or {}
    return int(scorecard.get('resolved_forecasts') or 0)


def v2_journal_scorecard(histories):
    journal = load_json('decision_journal.json', {'entries': []})
    maps = {k: as_map(histories.get(k, [])) for k in ALL_DIMS}
    rows = {k: [] for k in ALL_DIMS}
    for entry in journal.get('entries') or []:
        base = entry.get('period')
        if not base:
            continue
        forecasts = entry.get('forecast') or {}
        for key in ALL_DIMS:
            for h in HORIZONS:
                prob = (forecasts.get(key) or {}).get(f'{h}m')
                q = month_shift(base, h)
                actual_score = maps.get(key, {}).get(q)
                if prob is None or actual_score is None:
                    continue
                y = 1.0 if target_positive(key, actual_score) else 0.0
                rows[key].append({
                    'horizon_months': h,
                    'probability': float(prob),
                    'actual': y,
                    'correct_direction': (float(prob) >= .5) == bool(y),
                    'brier': (float(prob) - y) ** 2,
                })
    out = {}
    for key, vals in rows.items():
        out[key] = {
            'resolved': len(vals),
            'direction_hit_rate': None if not vals else round(sum(x['correct_direction'] for x in vals) / len(vals), 4),
            'brier_score': None if not vals else round(sum(x['brier'] for x in vals) / len(vals), 4),
        }
    return {
        'dimensions': out,
        'resolved_total': sum(x['resolved'] for x in out.values()),
        'note': 'Evaluates every recorded dimension independently; no mutation of the v1 journal artifact.',
    }


def promotion_gate(walk_forward, outcome_validation, risk_backtest, journal_scorecard):
    core_metrics = []
    for key in CORE_DIMS:
        dims = walk_forward.get(key, {}).get('horizons', {})
        for h in ('3m', '6m'):
            x = dims.get(h) or {}
            if x.get('oos_predictions', 0) >= 24 and x.get('brier_skill_vs_climatology') is not None:
                core_metrics.append(float(x['brier_skill_vs_climatology']))
    avg_skill = None if not core_metrics else sum(core_metrics) / len(core_metrics)
    risk_n = int(risk_backtest.get('observations') or 0)
    prospective = int(journal_scorecard.get('resolved_total') or 0)
    gates = {
        'core_oos_skill_positive': bool(core_metrics) and avg_skill > 0,
        'core_oos_metric_count_at_least_4': len(core_metrics) >= 4,
        'risk_backtest_observations_at_least_36': risk_n >= 36,
        'prospective_resolved_outcomes_at_least_24': prospective >= 24,
        'external_outcomes_present': any(bool(v) for k, v in outcome_validation.items() if not k.startswith('_')),
    }
    eligible = all(gates.values())
    return {
        'status': 'PROMOTION_ELIGIBLE_FOR_REVIEW' if eligible else 'CHALLENGER_ONLY',
        'automatic_promotion': False,
        'promotion_eligible': eligible,
        'gates': gates,
        'average_core_3m_6m_oos_brier_skill': None if avg_skill is None else round(avg_skill, 4),
        'rule': 'v2 cannot replace v1 automatically; even an eligible challenger requires an explicit reviewed model-version change.',
    }


def generate():
    histories = score_histories()
    current = current_scores()
    prospective_n = prospective_count()
    regime = regime_similarity(histories, current)
    regime_sim = float(regime.get('similarity') or 0.0)

    walk_forward = {}
    confidence_values = []
    for key in ALL_DIMS:
        cur = current.get(key) or {}
        if cur.get('score') is None:
            continue
        hs = {}
        for h in HORIZONS:
            result = walk_forward_dimension(
                key,
                histories.get(key, []),
                h,
                current_score=cur.get('score'),
                current_period=cur.get('period'),
                prospective_n=prospective_n,
                regime_similarity=regime_sim,
            )
            hs[f'{h}m'] = result
            c = (result.get('current') or {}).get('model_confidence')
            if c is not None:
                confidence_values.append(float(c))
        walk_forward[key] = {'period': cur.get('period'), 'score': cur.get('score'), 'horizons': hs}

    validation_v1 = load_json('model_validation.json', {})
    decomposed = validation_v1.get('confidence_decomposition') or {}
    data_conf_values = [float(x.get('provisional_overall')) for x in decomposed.values() if x.get('provisional_overall') is not None]
    effective_data_conf = None if not data_conf_values else round(sum(data_conf_values) / len(data_conf_values), 1)
    model_conf = None if not confidence_values else round(sum(confidence_values) / len(confidence_values), 1)

    outcomes = external_outcomes(histories)
    risk_backtest = risk_budget_backtest(histories)
    journal_scorecard = v2_journal_scorecard(histories)
    gate = promotion_gate(walk_forward, outcomes, risk_backtest, journal_scorecard)

    out = {
        'version': 2,
        'generated_at': dt.datetime.now(TZ).replace(microsecond=0).isoformat(),
        'product': 'Elephant Decision Engine v2 Challenger / Prospective Validation',
        'authority': False,
        'contract': {
            'v1_remains_authoritative': True,
            'cannot_change_deterministic_scores': True,
            'cannot_change_risk_budget': True,
            'cannot_change_alpha_action': True,
            'no_automatic_model_promotion': True,
            'strict_walk_forward': True,
        },
        'evidence_boundary': {
            'historical_score_rows': 'revised-series reconstruction before prospective vintage coverage',
            'walk_forward_leakage_guard': 'only training samples whose outcome_period <= prediction_period',
            'prospective_resolved_outcomes': prospective_n,
            'warning': 'Strict temporal OOS removes calibration leakage, but pre-vintage score histories can still contain official-revision bias.',
        },
        'confidence': {
            'effective_data_confidence': effective_data_conf,
            'sample_aware_model_confidence': model_conf,
            'regime_similarity': regime_sim,
            'prospective_outcomes': prospective_n,
        },
        'regime_similarity': regime,
        'walk_forward_oos': walk_forward,
        'external_outcome_validation': outcomes,
        'risk_budget_backtest': risk_backtest,
        'journal_scorecard_v2': journal_scorecard,
        'promotion_gate': gate,
    }
    save_json('decision_engine_v2.json', out)
    return out


if __name__ == '__main__':
    generate()
