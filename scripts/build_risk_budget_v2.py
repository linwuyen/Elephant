#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict

from common import TZ, load_json, save_json
import build_decision_engine_v2 as de2

HORIZON_MONTHS = 6
TRAILING_MONTHS = 6
MIN_TRAINING_SAMPLES = 36
NEIGHBORS = 12
NEUTRAL_EQUITY_PCT = 60.0
MIN_EQUITY_PCT = 35.0
MAX_EQUITY_PCT = 85.0
MAX_MONTHLY_CHANGE_PCT_POINTS = 10.0
COST_SENSITIVITY_BPS = (0, 10, 25)

FEATURES = (
    'cycle',
    'growth_persistence',
    'domestic_demand',
    'financial_conditions',
    'ai_concentration',
    'market_momentum_6m',
    'market_trailing_drawdown_6m',
)


def clamp(v, lo, hi):
    return max(lo, min(hi, float(v)))


def trailing_drawdown(values, period, months=TRAILING_MONTHS):
    path = []
    for i in range(months, -1, -1):
        v = values.get(de2.month_shift(period, -i))
        if v is None:
            return None
        path.append(float(v))
    peak = path[0]
    worst = 0.0
    for value in path:
        peak = max(peak, value)
        worst = min(worst, (value / peak - 1.0) * 100.0)
    return worst


def normalized_feature_vector(scores, momentum, trailing_dd):
    return (
        clamp(scores['cycle'], -100, 100) / 100.0,
        clamp(scores['growth_persistence'], -100, 100) / 100.0,
        clamp(scores['domestic_demand'], -100, 100) / 100.0,
        clamp(scores['financial_conditions'], -100, 100) / 100.0,
        (clamp(scores['ai_concentration'], 0, 100) - 50.0) / 50.0,
        clamp(momentum, -30, 30) / 30.0,
        clamp(trailing_dd, -30, 0) / 30.0,
    )


def feature_distance(a, b):
    if len(a) != len(b) or not a:
        raise ValueError('feature vector mismatch')
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)) / len(a))


def percentile_rank(values, x):
    vals = sorted(float(v) for v in values if v is not None)
    if not vals:
        return None
    below = sum(v < float(x) for v in vals)
    equal = sum(v == float(x) for v in vals)
    return (below + 0.5 * equal) / len(vals)


def weighted_mean(rows, key):
    den = sum(r['weight'] for r in rows)
    if den <= 0:
        return None
    return sum(r['weight'] * float(r[key]) for r in rows) / den


def score_maps(histories):
    return {k: de2.as_map(histories.get(k, [])) for k in de2.ALL_DIMS}


def historical_states(histories, stock):
    maps = score_maps(histories)
    if not all(maps.values()) or not stock:
        return []
    periods = sorted(set.intersection(*(set(m) for m in maps.values()), set(stock)))
    out = []
    for p in periods:
        momentum = de2.percent_change(stock, de2.month_shift(p, -TRAILING_MONTHS), p)
        tdd = trailing_drawdown(stock, p, TRAILING_MONTHS)
        if momentum is None or tdd is None:
            continue
        scores = {k: maps[k][p] for k in de2.ALL_DIMS}
        q = de2.month_shift(p, HORIZON_MONTHS)
        future_return = de2.percent_change(stock, p, q)
        future_dd = de2.forward_drawdown(stock, p, HORIZON_MONTHS)
        out.append({
            'period': p,
            'outcome_period': q,
            'scores': scores,
            'market_momentum_6m': momentum,
            'market_trailing_drawdown_6m': tdd,
            'features': normalized_feature_vector(scores, momentum, tdd),
            'future_return_6m_pct': future_return,
            'future_drawdown_6m_pct': future_dd,
        })
    return out


def usable_training(states, prediction_period):
    return [
        x for x in states
        if x.get('future_return_6m_pct') is not None
        and x.get('future_drawdown_6m_pct') is not None
        and x.get('outcome_period') <= prediction_period
    ]


def analog_prediction(training, features, regime_similarity=None):
    if len(training) < MIN_TRAINING_SAMPLES:
        return None
    ranked = sorted(
        ({**row, 'distance': feature_distance(features, row['features'])} for row in training),
        key=lambda x: (x['distance'], x['period']),
    )
    neighbors = ranked[:min(NEIGHBORS, len(ranked))]
    weighted = []
    for row in neighbors:
        # Smooth inverse distance: transparent, bounded, and never singular at d=0.
        weighted.append({**row, 'weight': 1.0 / (0.10 + row['distance'])})
    expected_return = weighted_mean(weighted, 'future_return_6m_pct')
    expected_dd = weighted_mean(weighted, 'future_drawdown_6m_pct')
    return_pctile = percentile_rank([x['future_return_6m_pct'] for x in training], expected_return)
    drawdown_pctile = percentile_rank([x['future_drawdown_6m_pct'] for x in training], expected_dd)
    if return_pctile is None or drawdown_pctile is None:
        return None

    allocation_score = 100.0 * (0.5 * return_pctile + 0.5 * drawdown_pctile)
    raw_target = MIN_EQUITY_PCT + (MAX_EQUITY_PCT - MIN_EQUITY_PCT) * allocation_score / 100.0
    mean_distance = sum(x['distance'] for x in neighbors) / len(neighbors)
    similarity = 100.0 * math.exp(-mean_distance)
    sample_score = min(100.0, math.sqrt(len(training) / 72.0) * 100.0)
    evidence_confidence = sample_score * similarity / 100.0
    if regime_similarity is not None:
        evidence_confidence *= 0.70 + 0.30 * clamp(regime_similarity, 0, 100) / 100.0
    evidence_confidence = clamp(evidence_confidence, 0, 100)

    # Weak evidence shrinks toward the static 60% neutral anchor rather than making
    # a large allocation move from a fragile historical analogy.
    target = NEUTRAL_EQUITY_PCT + evidence_confidence / 100.0 * (raw_target - NEUTRAL_EQUITY_PCT)
    target = clamp(target, MIN_EQUITY_PCT, MAX_EQUITY_PCT)
    return {
        'expected_forward_return_6m_pct': round(expected_return, 2),
        'expected_forward_drawdown_6m_pct': round(expected_dd, 2),
        'return_percentile': round(return_pctile * 100.0, 1),
        'drawdown_quality_percentile': round(drawdown_pctile * 100.0, 1),
        'allocation_score': round(allocation_score, 1),
        'raw_target_equity_pct': round(raw_target, 1),
        'evidence_confidence': round(evidence_confidence, 1),
        'target_equity_pct': round(target, 1),
        'mean_neighbor_distance': round(mean_distance, 4),
        'analog_similarity': round(similarity, 1),
        'training_samples': len(training),
        'neighbors': [
            {
                'period': x['period'],
                'distance': round(x['distance'], 4),
                'future_return_6m_pct': round(float(x['future_return_6m_pct']), 2),
                'future_drawdown_6m_pct': round(float(x['future_drawdown_6m_pct']), 2),
            }
            for x in neighbors
        ],
    }


def apply_turnover_cap(previous, requested):
    if previous is None:
        previous = NEUTRAL_EQUITY_PCT
    delta = clamp(float(requested) - float(previous), -MAX_MONTHLY_CHANGE_PCT_POINTS, MAX_MONTHLY_CHANGE_PCT_POINTS)
    return clamp(float(previous) + delta, MIN_EQUITY_PCT, MAX_EQUITY_PCT)


def build_oos_rows(states, stock, histories):
    v1 = {x['period']: x for x in de2.historical_risk_states(histories)}
    rows = []
    previous_v2 = NEUTRAL_EQUITY_PCT
    for state in states:
        p = state['period']
        q1 = de2.month_shift(p, 1)
        market_return = de2.percent_change(stock, p, q1)
        if market_return is None:
            continue
        training = usable_training(states, p)
        if len(training) < MIN_TRAINING_SAMPLES:
            continue
        prediction = analog_prediction(training, state['features'])
        if not prediction:
            continue
        requested = prediction['target_equity_pct']
        target = apply_turnover_cap(previous_v2, requested)
        v1_state = v1.get(p)
        if not v1_state:
            continue
        rows.append({
            'period': p,
            'market_return_1m_pct': float(market_return),
            'v2_requested_equity_pct': float(requested),
            'v2_equity_pct': round(target, 2),
            'v1_equity_pct': round(float(v1_state['equity_pct']), 2),
            'training_samples': len(training),
            'training_cutoff': max(x['outcome_period'] for x in training),
            'mean_neighbor_distance': prediction['mean_neighbor_distance'],
        })
        previous_v2 = target
    return rows


def strategy_metrics(rows, allocation_key, cost_bps=0):
    if not rows:
        return None
    previous = NEUTRAL_EQUITY_PCT
    returns = []
    turnover_points = 0.0
    exposures = []
    for row in rows:
        equity = float(row[allocation_key])
        turnover = abs(equity - previous)
        turnover_points += turnover
        # cost_bps is charged per 100% one-way turnover. A 10 percentage-point
        # rebalance at 25 bps therefore costs 0.025% of portfolio value.
        cost_pct = (turnover / 100.0) * (float(cost_bps) / 100.0)
        returns.append(float(row['market_return_1m_pct']) * equity / 100.0 - cost_pct)
        exposures.append(equity)
        previous = equity
    total, max_dd = de2.compound(returns)
    efficiency = None if max_dd is None or abs(max_dd) < 1e-9 else total / abs(max_dd)
    months = len(rows)
    return {
        'months': months,
        'total_return_pct': round(total, 2),
        'max_drawdown_pct': round(max_dd, 2),
        'return_to_abs_max_drawdown': None if efficiency is None else round(efficiency, 3),
        'average_equity_pct': round(sum(exposures) / len(exposures), 1),
        'annualized_one_way_turnover_pct_points': round(turnover_points / months * 12.0, 1),
        'cost_bps_per_100pct_turnover': int(cost_bps),
    }


def static_metrics(rows, equity_pct=NEUTRAL_EQUITY_PCT):
    if not rows:
        return None
    returns = [float(r['market_return_1m_pct']) * equity_pct / 100.0 for r in rows]
    total, max_dd = de2.compound(returns)
    efficiency = None if abs(max_dd) < 1e-9 else total / abs(max_dd)
    return {
        'months': len(rows),
        'total_return_pct': round(total, 2),
        'max_drawdown_pct': round(max_dd, 2),
        'return_to_abs_max_drawdown': None if efficiency is None else round(efficiency, 3),
        'average_equity_pct': float(equity_pct),
        'annualized_one_way_turnover_pct_points': 0.0,
        'cost_bps_per_100pct_turnover': 0,
    }


def backtest(states, stock, histories):
    rows = build_oos_rows(states, stock, histories)
    if not rows:
        return {'status': 'BLOCKED_INSUFFICIENT_OOS', 'authority': False, 'months': 0}
    costs = {}
    for bps in COST_SENSITIVITY_BPS:
        costs[str(bps)] = {
            'challenger': strategy_metrics(rows, 'v2_equity_pct', bps),
            'v1_champion': strategy_metrics(rows, 'v1_equity_pct', bps),
            'static_60': static_metrics(rows),
        }
    leakage_ok = all(str(x['training_cutoff']) <= str(x['period']) for x in rows)
    return {
        'status': 'DIAGNOSTIC_ONLY',
        'authority': False,
        'months': len(rows),
        'first_period': rows[0]['period'],
        'last_period': rows[-1]['period'],
        'strict_walk_forward_leakage_guard_verified': leakage_ok,
        'max_realized_monthly_equity_change_pct_points': round(max(
            abs(rows[i]['v2_equity_pct'] - (rows[i-1]['v2_equity_pct'] if i else NEUTRAL_EQUITY_PCT))
            for i in range(len(rows))
        ), 2),
        'cost_sensitivity': costs,
        'warning': 'Strict walk-forward model fit, but historical Score features before vintage collection remain revised-series reconstructions. This is not a tradable performance claim.',
    }


def current_prediction(states, stock, histories):
    current = de2.current_scores()
    periods = [str((current.get(k) or {}).get('period')) for k in de2.ALL_DIMS if (current.get(k) or {}).get('period')]
    if len(periods) != len(de2.ALL_DIMS):
        return {'status': 'BLOCKED_MISSING_CURRENT_SCORE'}
    period = min(periods)
    if period not in stock:
        eligible = [p for p in stock if p <= period]
        if not eligible:
            return {'status': 'BLOCKED_NO_CURRENT_MARKET'}
        period = max(eligible)
    scores = {}
    maps = score_maps(histories)
    for k in de2.ALL_DIMS:
        cur = (current.get(k) or {}).get('score')
        if (current.get(k) or {}).get('period') == period and cur is not None:
            scores[k] = float(cur)
        elif period in maps.get(k, {}):
            scores[k] = maps[k][period]
        else:
            return {'status': 'BLOCKED_SCORE_PERIOD_ALIGNMENT', 'period': period, 'missing': k}
    momentum = de2.percent_change(stock, de2.month_shift(period, -TRAILING_MONTHS), period)
    tdd = trailing_drawdown(stock, period, TRAILING_MONTHS)
    if momentum is None or tdd is None:
        return {'status': 'BLOCKED_MARKET_TRAILING_HISTORY', 'period': period}
    training = usable_training(states, period)
    regime = de2.regime_similarity(histories, current)
    prediction = analog_prediction(
        training,
        normalized_feature_vector(scores, momentum, tdd),
        regime_similarity=regime.get('similarity'),
    )
    if not prediction:
        return {'status': 'BLOCKED_INSUFFICIENT_TRAINING', 'period': period, 'training_samples': len(training)}
    champion = load_json('risk_budget.json', {})
    champion_equity = (champion.get('allocation_guardrails') or {}).get('target_equity_risk_budget_pct')
    target = prediction['target_equity_pct']
    return {
        'status': 'READY',
        'period': period,
        'horizon_months': HORIZON_MONTHS,
        'market_state': {
            'momentum_6m_pct': round(momentum, 2),
            'trailing_drawdown_6m_pct': round(tdd, 2),
        },
        **prediction,
        'allocation_envelope': {
            'equity_risk_budget_review_pct': target,
            'cash_or_low_risk_reserve_review_pct': round(100.0 - target, 1),
            'neutral_anchor_equity_pct': NEUTRAL_EQUITY_PCT,
            'max_monthly_equity_change_pct_points': MAX_MONTHLY_CHANGE_PCT_POINTS,
            'v1_champion_target_equity_pct': champion_equity,
            'within_equity_selection_authority': 'Capital OS / Alpha / Investment Constitution remain authoritative; Risk Budget v2 does not choose stocks or geographies.',
        },
        'training_cutoff': max(x['outcome_period'] for x in training),
    }


def promotion_gate(bt, prospective_outcomes):
    zero = ((bt.get('cost_sensitivity') or {}).get('0') or {})
    cost25 = ((bt.get('cost_sensitivity') or {}).get('25') or {})
    c = zero.get('challenger') or {}
    v1 = zero.get('v1_champion') or {}
    static = zero.get('static_60') or {}
    c25 = cost25.get('challenger') or {}
    s25 = cost25.get('static_60') or {}

    def efficiency(row):
        v = row.get('return_to_abs_max_drawdown')
        return None if v is None else float(v)

    ce, ve, se = efficiency(c), efficiency(v1), efficiency(static)
    c25e, s25e = efficiency(c25), efficiency(s25)
    gates = {
        'oos_months_at_least_48': int(bt.get('months') or 0) >= 48,
        'strict_walk_forward_guard': bt.get('strict_walk_forward_leakage_guard_verified') is True,
        'efficiency_beats_v1_by_5pct': ce is not None and ve is not None and ce >= ve * 1.05,
        'efficiency_beats_static_60_by_5pct': ce is not None and se is not None and ce >= se * 1.05,
        'max_drawdown_not_worse_than_v1': c.get('max_drawdown_pct') is not None and v1.get('max_drawdown_pct') is not None and float(c['max_drawdown_pct']) >= float(v1['max_drawdown_pct']),
        'survives_25bps_turnover_cost_vs_static': c25e is not None and s25e is not None and c25e >= s25e,
        'prospective_resolved_outcomes_at_least_24': int(prospective_outcomes) >= 24,
    }
    eligible = all(gates.values())
    return {
        'status': 'PROMOTION_ELIGIBLE_FOR_REVIEW' if eligible else 'CHALLENGER_ONLY',
        'promotion_eligible': eligible,
        'automatic_promotion': False,
        'gates': gates,
        'prospective_resolved_outcomes': int(prospective_outcomes),
        'rule': 'Risk Budget v2 can never self-promote. Historical OOS gates plus prospective outcomes must pass before a reviewed model-version change may replace v1.',
    }


def generate():
    histories = de2.score_histories()
    ndc = load_json('ndc.json', {}).get('series', {})
    stock = de2.series_map(ndc.get('stock_index'))
    states = historical_states(histories, stock)
    bt = backtest(states, stock, histories)
    current = current_prediction(states, stock, histories)
    prospective = de2.prospective_count()
    gate = promotion_gate(bt, prospective)
    out = {
        'version': 2,
        'generated_at': dt.datetime.now(TZ).replace(microsecond=0).isoformat(),
        'product': 'Elephant Risk Budget v2 / Market-Aware Allocation Challenger',
        'authority': False,
        'contract': {
            'v1_risk_budget_remains_authoritative': True,
            'cannot_change_deterministic_scores': True,
            'cannot_change_capital_os': True,
            'cannot_change_alpha_or_constitution': True,
            'does_not_choose_individual_securities': True,
            'no_automatic_trading': True,
            'no_automatic_promotion': True,
        },
        'first_principles': {
            'question': 'Given the macro state and where the market already is, how much aggregate equity risk is justified over the next six months?',
            'separation': 'Economic strength is descriptive state, not assumed expected return. Market momentum/drawdown and realized future market outcomes determine allocation evidence.',
            'neutral_anchor': 'Weak evidence shrinks toward static 60% equity instead of creating extreme risk-on/off exposure.',
        },
        'model': {
            'horizon_months': HORIZON_MONTHS,
            'features': list(FEATURES),
            'method': 'strict walk-forward nearest historical analogs; inverse-distance outcome weighting; equal-weight return/drawdown percentile score',
            'minimum_training_samples': MIN_TRAINING_SAMPLES,
            'neighbors': NEIGHBORS,
            'equity_bounds_pct': [MIN_EQUITY_PCT, MAX_EQUITY_PCT],
            'neutral_equity_pct': NEUTRAL_EQUITY_PCT,
            'max_monthly_change_pct_points': MAX_MONTHLY_CHANGE_PCT_POINTS,
            'cost_sensitivity_bps_per_100pct_turnover': list(COST_SENSITIVITY_BPS),
        },
        'current': current,
        'walk_forward_backtest': bt,
        'promotion_gate': gate,
        'evidence_boundary': {
            'market_source': 'NDC official stock_index already used by Decision Engine v2',
            'historical_score_bias': 'Pre-vintage Score histories are reconstructed from revised official series.',
            'prospective_requirement': 'At least 24 resolved prospective outcomes are mandatory before promotion review.',
        },
    }
    save_json('risk_budget_v2.json', out)
    return out


if __name__ == '__main__':
    generate()
