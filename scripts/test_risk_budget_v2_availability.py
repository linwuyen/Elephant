#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt

import build_decision_engine_v2 as de2
import build_risk_budget_v2 as rb
import build_risk_budget_v2_availability as av


def make_histories(n=150):
    out = {k: [] for k in de2.ALL_DIMS}
    p = '2014-01'
    for i in range(n):
        wave = ((i % 30) - 15) / 15.0
        vals = {
            'cycle': 80 * wave,
            'growth_persistence': 72 * wave,
            'domestic_demand': 44 * wave,
            'financial_conditions': 62 * wave,
            'ai_concentration': 55 + 28 * max(0, wave),
        }
        for k, v in vals.items():
            out[k].append({'period': p, 'score': v})
        p = de2.month_shift(p, 1)
    return out


def make_stock(start='2013-07', n=175):
    values = {}
    p = start
    v = 10000.0
    for i in range(n):
        monthly = 0.012 + 0.018 * (((i % 24) - 12) / 12.0)
        if i % 19 == 0:
            monthly -= 0.05
        v *= 1.0 + monthly
        values[p] = v
        p = de2.month_shift(p, 1)
    return values


hist = make_histories()
stock = make_stock()
states = av.historical_states_lagged(hist, stock)
assert len(states) > 90

# A score labelled 2020-01 cannot affect an allocation until 2020-03 under the
# conservative reconstructed publication-lag contract.
probe = next(x for x in states if x['score_period'] == '2020-01')
assert probe['period'] == '2020-03'
assert probe['outcome_period'] == '2020-09'
assert probe['market_momentum_6m'] == de2.percent_change(stock, '2019-09', '2020-03')
assert probe['features'][-2] == rb.normalized_feature_vector(
    probe['scores'], probe['market_momentum_6m'], probe['market_trailing_drawdown_6m']
)[-2]

training = rb.usable_training(states, probe['period'])
assert all(x['outcome_period'] <= probe['period'] for x in training)

rows = av.build_oos_rows_lagged(states, stock, hist)
assert len(rows) >= 48
assert all(de2.month_shift(x['score_period'], av.SCORE_AVAILABILITY_LAG_MONTHS) == x['period'] for x in rows)
assert all(x['training_cutoff'] <= x['period'] for x in rows)

# v1 comparator must use the same score-period state delayed into the same market
# decision month. It must not silently use the future decision-month Score.
v1_map = {x['period']: x for x in de2.historical_risk_states(hist)}
first = rows[0]
assert first['v1_equity_pct'] == round(float(v1_map[first['score_period']]['equity_pct']), 2)

bt = av.backtest_lagged(states, stock, hist)
assert bt['status'] == 'DIAGNOSTIC_ONLY'
assert bt['score_availability_lag_months'] == 2
assert bt['strict_walk_forward_leakage_guard_verified'] is True
assert bt['months'] == len(rows)

# Current-state contract uses fresh live market data but deliberately lags the
# reconstructed macro Score. With July 2026 market data, latest eligible Score is
# May 2026 or earlier.
live = {p: stock[p] for p in sorted(stock) if '2025-11' <= p <= '2026-07'}
real_current = de2.current_scores
real_load = av.load_json
try:
    de2.current_scores = lambda: {
        k: {'period': '2026-06', 'score': hist[k][-1]['score']} for k in de2.ALL_DIMS
    }
    av.load_json = lambda name, default=None: (
        {'allocation_guardrails': {'target_equity_risk_budget_pct': 75.0}}
        if name == 'risk_budget.json' else real_load(name, default)
    )
    current = av.current_prediction_lagged(states, hist, live, expected_latest='2026-07')
finally:
    de2.current_scores = real_current
    av.load_json = real_load
assert current['status'] == 'READY'
assert current['period'] == '2026-07'
assert current['score_period'] <= '2026-05'
assert current['score_availability_lag_months'] >= 2
assert current['market_freshness_gap_months'] == 0
assert current['market_source'].startswith('TWSE')
assert current['training_cutoff'] <= current['period']

# A stale completed-month window must block rather than quietly use old prices.
stale = av.current_prediction_lagged(states, hist, live, expected_latest='2026-09')
assert stale['status'] == 'BLOCKED_NO_CURRENT_MARKET'
assert 'stale' in stale['reason']

# Promotion remains impossible without genuinely resolved prospective outcomes.
gate = rb.promotion_gate(bt, 0)
assert gate['automatic_promotion'] is False
assert gate['promotion_eligible'] is False
assert gate['status'] == 'CHALLENGER_ONLY'

fixed = dt.datetime(2026, 8, 16, 0, 45, tzinfo=av.TZ)
assert av.last_completed_month(fixed) == '2026-07'

print('RISK BUDGET V2 AVAILABILITY TEST PASS')
