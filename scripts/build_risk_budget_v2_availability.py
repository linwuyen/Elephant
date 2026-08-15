#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt

from common import TZ, load_json, save_json
import build_decision_engine_v2 as de2
import build_risk_budget_v2 as rb

SCORE_AVAILABILITY_LAG_MONTHS = 2
LIVE_MARKET_STALE_TOLERANCE_MONTHS = 1
LIVE_SERIES_KEY = 'twse.taiex_month_end'


def month_gap(newer, older):
    try:
        ny, nm = map(int, str(newer).split('-'))
        oy, om = map(int, str(older).split('-'))
    except Exception:
        return 999
    return (ny - oy) * 12 + (nm - om)


def last_completed_month(now=None):
    now = now or dt.datetime.now(TZ)
    return de2.month_shift(f'{now.year:04d}-{now.month:02d}', -1)


def historical_states_lagged(histories, stock):
    maps = rb.score_maps(histories)
    if not all(maps.values()) or not stock:
        return []
    score_periods = sorted(set.intersection(*(set(m) for m in maps.values())))
    out = []
    for score_period in score_periods:
        decision_period = de2.month_shift(score_period, SCORE_AVAILABILITY_LAG_MONTHS)
        if decision_period not in stock:
            continue
        momentum = de2.percent_change(stock, de2.month_shift(decision_period, -rb.TRAILING_MONTHS), decision_period)
        tdd = rb.trailing_drawdown(stock, decision_period, rb.TRAILING_MONTHS)
        if momentum is None or tdd is None:
            continue
        scores = {k: maps[k][score_period] for k in de2.ALL_DIMS}
        outcome_period = de2.month_shift(decision_period, rb.HORIZON_MONTHS)
        out.append({
            'score_period': score_period,
            'period': decision_period,
            'outcome_period': outcome_period,
            'scores': scores,
            'market_momentum_6m': momentum,
            'market_trailing_drawdown_6m': tdd,
            'features': rb.normalized_feature_vector(scores, momentum, tdd),
            'future_return_6m_pct': de2.percent_change(stock, decision_period, outcome_period),
            'future_drawdown_6m_pct': de2.forward_drawdown(stock, decision_period, rb.HORIZON_MONTHS),
        })
    return out


def build_oos_rows_lagged(states, stock, histories):
    v1 = {x['period']: x for x in de2.historical_risk_states(histories)}
    rows = []
    previous_v2 = rb.NEUTRAL_EQUITY_PCT
    for state in states:
        decision_period = state['period']
        market_return = de2.percent_change(stock, decision_period, de2.month_shift(decision_period, 1))
        if market_return is None:
            continue
        training = rb.usable_training(states, decision_period)
        if len(training) < rb.MIN_TRAINING_SAMPLES:
            continue
        prediction = rb.analog_prediction(training, state['features'])
        if not prediction:
            continue
        v1_state = v1.get(state['score_period'])
        if not v1_state:
            continue
        target = rb.apply_turnover_cap(previous_v2, prediction['target_equity_pct'])
        rows.append({
            'score_period': state['score_period'],
            'period': decision_period,
            'market_return_1m_pct': float(market_return),
            'v2_requested_equity_pct': float(prediction['target_equity_pct']),
            'v2_equity_pct': round(target, 2),
            'v1_equity_pct': round(float(v1_state['equity_pct']), 2),
            'training_samples': len(training),
            'training_cutoff': max(x['outcome_period'] for x in training),
            'mean_neighbor_distance': prediction['mean_neighbor_distance'],
        })
        previous_v2 = target
    return rows


def backtest_lagged(states, stock, histories):
    rows = build_oos_rows_lagged(states, stock, histories)
    if not rows:
        return {'status': 'BLOCKED_INSUFFICIENT_OOS', 'authority': False, 'months': 0}
    costs = {}
    for bps in rb.COST_SENSITIVITY_BPS:
        costs[str(bps)] = {
            'challenger': rb.strategy_metrics(rows, 'v2_equity_pct', bps),
            'v1_champion': rb.strategy_metrics(rows, 'v1_equity_pct', bps),
            'static_60': rb.static_metrics(rows),
        }
    leakage_ok = all(
        x['training_cutoff'] <= x['period'] and de2.month_shift(x['score_period'], SCORE_AVAILABILITY_LAG_MONTHS) == x['period']
        for x in rows
    )
    return {
        'status': 'DIAGNOSTIC_ONLY',
        'authority': False,
        'months': len(rows),
        'first_period': rows[0]['period'],
        'last_period': rows[-1]['period'],
        'score_availability_lag_months': SCORE_AVAILABILITY_LAG_MONTHS,
        'strict_walk_forward_leakage_guard_verified': leakage_ok,
        'max_realized_monthly_equity_change_pct_points': round(max(
            abs(rows[i]['v2_equity_pct'] - (rows[i-1]['v2_equity_pct'] if i else rb.NEUTRAL_EQUITY_PCT))
            for i in range(len(rows))
        ), 2),
        'cost_sensitivity': costs,
        'warning': 'Availability-corrected strict walk-forward diagnostic: each reconstructed Score month is delayed two months before it can affect allocation. Pre-vintage Score values can still contain official-revision bias.',
    }


def latest_live_market():
    obj = load_json('market_live.json', {})
    series = ((obj.get('series') or {}).get(LIVE_SERIES_KEY) or {})
    data = series.get('data') or []
    values = {str(p): float(v) for p, v in data if v is not None}
    return obj, values


def current_prediction_lagged(states, histories, live_stock, expected_latest=None):
    if not live_stock:
        return {'status': 'BLOCKED_NO_CURRENT_MARKET', 'reason': 'TWSE live market window is unavailable.'}
    market_period = max(live_stock)
    expected_latest = expected_latest or last_completed_month()
    freshness_gap = month_gap(expected_latest, market_period)
    if freshness_gap < 0 or freshness_gap > LIVE_MARKET_STALE_TOLERANCE_MONTHS:
        return {
            'status': 'BLOCKED_NO_CURRENT_MARKET',
            'reason': f'TWSE live market state is stale: latest={market_period}, expected={expected_latest}, gap={freshness_gap}m',
            'period': market_period,
        }

    maps = rb.score_maps(histories)
    target_score_period = de2.month_shift(market_period, -SCORE_AVAILABILITY_LAG_MONTHS)
    common = sorted(set.intersection(*(set(m) for m in maps.values()))) if all(maps.values()) else []
    eligible = [p for p in common if p <= target_score_period]
    if not eligible:
        return {'status': 'BLOCKED_SCORE_PERIOD_ALIGNMENT', 'period': market_period, 'missing': target_score_period}
    score_period = max(eligible)
    scores = {k: maps[k][score_period] for k in de2.ALL_DIMS}
    momentum = de2.percent_change(live_stock, de2.month_shift(market_period, -rb.TRAILING_MONTHS), market_period)
    tdd = rb.trailing_drawdown(live_stock, market_period, rb.TRAILING_MONTHS)
    if momentum is None or tdd is None:
        return {'status': 'BLOCKED_MARKET_TRAILING_HISTORY', 'period': market_period}

    training = rb.usable_training(states, market_period)
    prediction = rb.analog_prediction(training, rb.normalized_feature_vector(scores, momentum, tdd))
    if not prediction:
        return {'status': 'BLOCKED_INSUFFICIENT_TRAINING', 'period': market_period, 'training_samples': len(training)}
    champion = load_json('risk_budget.json', {})
    champion_equity = (champion.get('allocation_guardrails') or {}).get('target_equity_risk_budget_pct')
    target = prediction['target_equity_pct']
    return {
        'status': 'READY',
        'period': market_period,
        'score_period': score_period,
        'score_availability_lag_months': month_gap(market_period, score_period),
        'horizon_months': rb.HORIZON_MONTHS,
        'market_source': 'TWSE live completed-month window',
        'market_freshness_gap_months': freshness_gap,
        'market_state': {
            'momentum_6m_pct': round(momentum, 2),
            'trailing_drawdown_6m_pct': round(tdd, 2),
        },
        **prediction,
        'allocation_envelope': {
            'equity_risk_budget_review_pct': target,
            'cash_or_low_risk_reserve_review_pct': round(100.0 - target, 1),
            'neutral_anchor_equity_pct': rb.NEUTRAL_EQUITY_PCT,
            'max_monthly_equity_change_pct_points': rb.MAX_MONTHLY_CHANGE_PCT_POINTS,
            'v1_champion_target_equity_pct': champion_equity,
            'within_equity_selection_authority': 'Capital OS / Alpha / Investment Constitution remain authoritative; Risk Budget v2 does not choose stocks or geographies.',
        },
        'training_cutoff': max(x['outcome_period'] for x in training),
    }


def generate():
    # Generate the base artifact first so all original v2 authority contracts and
    # policy definitions stay centralized in build_risk_budget_v2.py.
    obj = rb.generate()
    histories = de2.score_histories()
    ndc_stock = de2.series_map((load_json('ndc.json', {}).get('series') or {}).get('stock_index'))
    states = historical_states_lagged(histories, ndc_stock)
    bt = backtest_lagged(states, ndc_stock, histories)
    _, live_stock = latest_live_market()
    current = current_prediction_lagged(states, histories, live_stock)
    gate = rb.promotion_gate(bt, de2.prospective_count())

    obj['generated_at'] = dt.datetime.now(TZ).replace(microsecond=0).isoformat()
    obj['product'] = 'Elephant Risk Budget v2.1 / Availability-Corrected Market-Aware Allocation Challenger'
    obj['model']['score_availability_lag_months'] = SCORE_AVAILABILITY_LAG_MONTHS
    obj['model']['historical_market_source'] = 'NDC stock_index'
    obj['model']['current_market_source'] = 'TWSE completed-month TAIEX'
    obj['current'] = current
    obj['walk_forward_backtest'] = bt
    obj['promotion_gate'] = gate
    obj['evidence_boundary']['historical_availability'] = 'Reconstructed Score month is delayed two months before allocation can use it; this is a conservative publication-lag proxy, not a claim of exact historical release timestamps.'
    obj['evidence_boundary']['current_market_freshness'] = 'Current allocation requires the official TWSE completed-month window to be no more than one month behind the expected completed month.'
    obj['evidence_boundary']['source_roles'] = 'NDC remains the historical calibration source; TWSE is used only for fresh current market state. The roles do not overlap in model fitting.'
    save_json('risk_budget_v2.json', obj)
    return obj


if __name__ == '__main__':
    generate()
