#!/usr/bin/env python3
from __future__ import annotations

import math

from common import load_json

HORIZONS = ('1m', '3m', '6m', '12m')
CORE = ('cycle', 'growth_persistence', 'domestic_demand', 'financial_conditions')


def finite(v):
    try:
        return math.isfinite(float(v))
    except Exception:
        return False


def main():
    obj = load_json('decision_engine_v2.json', {})
    assert obj.get('version') == 2
    assert obj.get('authority') is False
    contract = obj.get('contract') or {}
    assert contract.get('v1_remains_authoritative') is True
    assert contract.get('cannot_change_deterministic_scores') is True
    assert contract.get('cannot_change_risk_budget') is True
    assert contract.get('cannot_change_alpha_action') is True
    assert contract.get('no_automatic_model_promotion') is True
    assert contract.get('strict_walk_forward') is True

    evidence = obj.get('evidence_boundary') or {}
    assert 'outcome_period <= prediction_period' in str(evidence.get('walk_forward_leakage_guard'))

    wf = obj.get('walk_forward_oos') or {}
    for key in CORE:
        assert key in wf, key
        hs = (wf[key] or {}).get('horizons') or {}
        for h in HORIZONS:
            x = hs.get(h)
            assert x is not None, (key, h)
            assert x.get('oos_predictions', 0) >= 0
            assert 0 <= float(x.get('sample_adequacy', 0)) <= 100
            cur = x.get('current') or {}
            if cur:
                assert 0 <= float(cur['probability']) <= 1
                assert 0 <= float(cur['model_confidence']) <= 100
            if x.get('brier_score') is not None:
                assert 0 <= float(x['brier_score']) <= 1
            if x.get('direction_accuracy') is not None:
                assert 0 <= float(x['direction_accuracy']) <= 1

    outcomes = obj.get('external_outcome_validation') or {}
    assert any(k in outcomes for k in CORE)
    market_seen = False
    for key in CORE:
        for target, item in (outcomes.get(key) or {}).items():
            if (item or {}).get('kind') == 'market':
                market_seen = True
            for h, x in ((item or {}).get('horizons') or {}).items():
                assert h in ('3m', '6m', '12m')
                assert int(x.get('samples', 0)) >= 0
                if x.get('direction_accuracy') is not None:
                    assert 0 <= float(x['direction_accuracy']) <= 1
    assert market_seen, 'stock-index external outcome missing'

    risk = obj.get('risk_budget_backtest') or {}
    assert risk.get('authority') is False
    assert risk.get('status') in ('DIAGNOSTIC_ONLY', 'BLOCKED_NO_STOCK_INDEX')
    if risk.get('status') == 'DIAGNOSTIC_ONLY':
        assert int(risk.get('observations', 0)) > 0
        pv = risk.get('policy_vs_static_60_equity') or {}
        assert pv.get('cash_return_assumption_pct') == 0.0
        assert pv.get('transaction_costs_included') is False

    regime = obj.get('regime_similarity') or {}
    assert 0 <= float(regime.get('similarity', 0)) <= 100
    assert regime.get('status') in ('HIGH', 'MEDIUM', 'LOW', 'INSUFFICIENT_HISTORY', 'MISSING_CURRENT_DIMENSION')

    gate = obj.get('promotion_gate') or {}
    assert gate.get('automatic_promotion') is False
    assert gate.get('status') in ('CHALLENGER_ONLY', 'PROMOTION_ELIGIBLE_FOR_REVIEW')
    if gate.get('promotion_eligible'):
        assert all((gate.get('gates') or {}).values())

    conf = obj.get('confidence') or {}
    for k in ('effective_data_confidence', 'sample_aware_model_confidence', 'regime_similarity'):
        if conf.get(k) is not None:
            assert finite(conf[k]) and 0 <= float(conf[k]) <= 100

    print('DECISION ENGINE V2 VALIDATION PASS')


if __name__ == '__main__':
    main()
