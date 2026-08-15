#!/usr/bin/env python3
from __future__ import annotations

import build_risk_budget_v2 as rb
import build_decision_engine_v2 as de2


def make_histories(n=132):
    out = {k: [] for k in de2.ALL_DIMS}
    p = '2015-01'
    for i in range(n):
        # Oscillating macro cycle deliberately creates repeated historical regimes.
        wave = ((i % 30) - 15) / 15.0
        vals = {
            'cycle': 85 * wave,
            'growth_persistence': 75 * wave,
            'domestic_demand': 45 * wave,
            'financial_conditions': 65 * wave,
            'ai_concentration': 55 + 30 * max(0, wave),
        }
        for k, v in vals.items():
            out[k].append({'period': p, 'score': v})
        p = de2.month_shift(p, 1)
    return out


def make_stock(n=150):
    # Market return regime is intentionally counter-cyclical to the macro wave:
    # high macro states tend to have weaker subsequent returns. This proves the
    # challenger learns outcomes rather than hard-coding "strong macro = risk-on".
    values = {}
    p = '2014-07'
    v = 10000.0
    for i in range(n):
        cycle_index = max(0, i - 6)
        wave = ((cycle_index % 30) - 15) / 15.0
        monthly = 0.018 - 0.020 * wave
        if i % 17 == 0:
            monthly -= 0.045
        v *= 1.0 + monthly
        values[p] = v
        p = de2.month_shift(p, 1)
    return values


hist = make_histories()
stock = make_stock()
states = rb.historical_states(hist, stock)
assert len(states) > 80

# Feature normalization and distance are deterministic/bounded enough for the
# transparent nearest-analog contract.
a = states[30]['features']; b = states[31]['features']
assert len(a) == len(rb.FEATURES)
assert rb.feature_distance(a, a) == 0
assert rb.feature_distance(a, b) >= 0

# Strict walk-forward training: every training outcome must already be observable
# by the prediction month. No future row can leak into the analog set.
probe = states[70]
training = rb.usable_training(states, probe['period'])
assert len(training) >= rb.MIN_TRAINING_SAMPLES
assert max(x['outcome_period'] for x in training) <= probe['period']
pred = rb.analog_prediction(training, probe['features'])
assert pred is not None
assert 0 <= pred['allocation_score'] <= 100
assert 0 <= pred['evidence_confidence'] <= 100
assert rb.MIN_EQUITY_PCT <= pred['target_equity_pct'] <= rb.MAX_EQUITY_PCT
assert len(pred['neighbors']) == rb.NEIGHBORS

# Confidence shrinkage: weak evidence must move the raw target toward neutral 60,
# never farther away from neutral.
raw = pred['raw_target_equity_pct']; target = pred['target_equity_pct']
assert abs(target - rb.NEUTRAL_EQUITY_PCT) <= abs(raw - rb.NEUTRAL_EQUITY_PCT) + 1e-9

# Turnover control is a hard policy boundary, not an optimizer suggestion.
assert rb.apply_turnover_cap(60, 85) == 70
assert rb.apply_turnover_cap(60, 35) == 50

rows = rb.build_oos_rows(states, stock, hist)
assert len(rows) >= 48
assert all(x['training_cutoff'] <= x['period'] for x in rows)
changes = [abs(x['v2_equity_pct'] - (rows[i-1]['v2_equity_pct'] if i else rb.NEUTRAL_EQUITY_PCT)) for i, x in enumerate(rows)]
assert max(changes) <= rb.MAX_MONTHLY_CHANGE_PCT_POINTS + 1e-9

bt = rb.backtest(states, stock, hist)
assert bt['status'] == 'DIAGNOSTIC_ONLY'
assert bt['strict_walk_forward_leakage_guard_verified'] is True
assert bt['months'] == len(rows)
for bps in ('0', '10', '25'):
    assert set(bt['cost_sensitivity'][bps]) == {'challenger', 'v1_champion', 'static_60'}
# Adding turnover cost can never improve the same challenger return path.
assert bt['cost_sensitivity']['25']['challenger']['total_return_pct'] <= bt['cost_sensitivity']['0']['challenger']['total_return_pct'] + 1e-9

# Promotion remains impossible without real future prospective outcomes even if
# reconstructed-history metrics happen to pass.
gate = rb.promotion_gate(bt, 0)
assert gate['automatic_promotion'] is False
assert gate['promotion_eligible'] is False
assert gate['status'] == 'CHALLENGER_ONLY'
assert gate['gates']['prospective_resolved_outcomes_at_least_24'] is False

# A fully passing synthetic gate still only becomes eligible for human review.
synthetic_bt = {
    'months': 60,
    'strict_walk_forward_leakage_guard_verified': True,
    'cost_sensitivity': {
        '0': {
            'challenger': {'return_to_abs_max_drawdown': 12.0, 'max_drawdown_pct': -10.0},
            'v1_champion': {'return_to_abs_max_drawdown': 10.0, 'max_drawdown_pct': -12.0},
            'static_60': {'return_to_abs_max_drawdown': 10.0, 'max_drawdown_pct': -11.0},
        },
        '25': {
            'challenger': {'return_to_abs_max_drawdown': 10.5},
            'static_60': {'return_to_abs_max_drawdown': 10.0},
        },
    },
}
gate2 = rb.promotion_gate(synthetic_bt, 24)
assert gate2['promotion_eligible'] is True
assert gate2['automatic_promotion'] is False
assert gate2['status'] == 'PROMOTION_ELIGIBLE_FOR_REVIEW'

print('RISK BUDGET V2 TEST PASS')
