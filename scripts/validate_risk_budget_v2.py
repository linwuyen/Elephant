#!/usr/bin/env python3
from __future__ import annotations

import math
from common import load_json


def finite(v):
    try:
        return math.isfinite(float(v))
    except Exception:
        return False


def main():
    obj = load_json('risk_budget_v2.json', {})
    assert obj.get('version') == 2
    assert obj.get('authority') is False
    contract = obj.get('contract') or {}
    for key in (
        'v1_risk_budget_remains_authoritative',
        'cannot_change_deterministic_scores',
        'cannot_change_capital_os',
        'cannot_change_alpha_or_constitution',
        'does_not_choose_individual_securities',
        'no_automatic_trading',
        'no_automatic_promotion',
    ):
        assert contract.get(key) is True, key

    model = obj.get('model') or {}
    assert int(model.get('horizon_months')) == 6
    assert int(model.get('minimum_training_samples')) >= 24
    assert int(model.get('neighbors')) >= 5
    lo, hi = model.get('equity_bounds_pct') or (None, None)
    assert finite(lo) and finite(hi) and 0 <= float(lo) < float(hi) <= 100
    neutral = float(model.get('neutral_equity_pct'))
    assert float(lo) <= neutral <= float(hi)
    assert float(model.get('max_monthly_change_pct_points')) > 0

    # v2.1 publication-availability contract is now part of the published model.
    assert int(model.get('score_availability_lag_months')) == 2
    assert model.get('historical_market_source') == 'NDC stock_index'
    assert model.get('current_market_source') == 'TWSE completed-month TAIEX'

    current = obj.get('current') or {}
    assert current.get('status') in (
        'READY', 'BLOCKED_MISSING_CURRENT_SCORE', 'BLOCKED_NO_CURRENT_MARKET',
        'BLOCKED_SCORE_PERIOD_ALIGNMENT', 'BLOCKED_MARKET_TRAILING_HISTORY',
        'BLOCKED_INSUFFICIENT_TRAINING',
    )
    if current.get('status') == 'READY':
        for key in ('expected_forward_return_6m_pct', 'expected_forward_drawdown_6m_pct', 'allocation_score', 'evidence_confidence', 'target_equity_pct'):
            assert finite(current.get(key)), key
        assert 0 <= float(current['allocation_score']) <= 100
        assert 0 <= float(current['evidence_confidence']) <= 100
        assert float(lo) <= float(current['target_equity_pct']) <= float(hi)
        assert current.get('market_source') == 'TWSE live completed-month window'
        assert int(current.get('market_freshness_gap_months')) in (0, 1)
        assert int(current.get('score_availability_lag_months')) >= 2
        assert str(current.get('score_period')) <= str(current.get('period'))
        env = current.get('allocation_envelope') or {}
        assert finite(env.get('equity_risk_budget_review_pct'))
        assert finite(env.get('cash_or_low_risk_reserve_review_pct'))
        assert abs(float(env['equity_risk_budget_review_pct']) + float(env['cash_or_low_risk_reserve_review_pct']) - 100.0) <= 0.2
        assert 'Capital OS' in str(env.get('within_equity_selection_authority'))
        assert str(current.get('training_cutoff')) <= str(current.get('period'))

    bt = obj.get('walk_forward_backtest') or {}
    assert bt.get('status') in ('DIAGNOSTIC_ONLY', 'BLOCKED_INSUFFICIENT_OOS')
    if bt.get('status') == 'DIAGNOSTIC_ONLY':
        assert bt.get('authority') is False
        assert int(bt.get('months') or 0) > 0
        assert int(bt.get('score_availability_lag_months')) == 2
        assert bt.get('strict_walk_forward_leakage_guard_verified') is True
        assert float(bt.get('max_realized_monthly_equity_change_pct_points')) <= float(model['max_monthly_change_pct_points']) + 1e-9
        costs = bt.get('cost_sensitivity') or {}
        for bps in ('0', '10', '25'):
            assert bps in costs
            for strategy in ('challenger', 'v1_champion', 'static_60'):
                row = (costs[bps] or {}).get(strategy) or {}
                for key in ('months', 'total_return_pct', 'max_drawdown_pct', 'average_equity_pct'):
                    assert finite(row.get(key)), (bps, strategy, key)
                assert int(row['months']) == int(bt['months'])
        assert (costs['0']['static_60'] or {}).get('annualized_one_way_turnover_pct_points') == 0.0

    gate = obj.get('promotion_gate') or {}
    assert gate.get('automatic_promotion') is False
    assert gate.get('status') in ('CHALLENGER_ONLY', 'PROMOTION_ELIGIBLE_FOR_REVIEW')
    gates = gate.get('gates') or {}
    required = {
        'oos_months_at_least_48', 'strict_walk_forward_guard',
        'efficiency_beats_v1_by_5pct', 'efficiency_beats_static_60_by_5pct',
        'max_drawdown_not_worse_than_v1', 'survives_25bps_turnover_cost_vs_static',
        'prospective_resolved_outcomes_at_least_24',
    }
    assert set(gates) == required
    if gate.get('promotion_eligible'):
        assert all(gates.values())
        assert gate.get('status') == 'PROMOTION_ELIGIBLE_FOR_REVIEW'
    else:
        assert gate.get('status') == 'CHALLENGER_ONLY'

    boundary = obj.get('evidence_boundary') or {}
    assert 'two months' in str(boundary.get('historical_availability'))
    assert 'TWSE' in str(boundary.get('current_market_freshness'))
    assert 'NDC' in str(boundary.get('source_roles')) and 'TWSE' in str(boundary.get('source_roles'))

    print('RISK BUDGET V2 VALIDATION PASS')
    print('current:', current.get('status'), current.get('target_equity_pct'))
    print('score/market periods:', current.get('score_period'), current.get('period'))
    print('oos months:', bt.get('months'))
    print('promotion:', gate.get('status'))


if __name__ == '__main__':
    main()
