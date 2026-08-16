#!/usr/bin/env python3
from __future__ import annotations

import math
from common import load_json

ALLOWED_ACTIONS={'BLOCKED','REDUCE_RISK','HOLD_CASH','HOLD_SELECTIVE','DEPLOY_SELECTIVELY'}


def finite(v):
    try:return math.isfinite(float(v))
    except Exception:return False


def main():
    obj=load_json('decision_command.json',{})
    assert obj.get('version')==1
    assert obj.get('authority') is False
    contract=obj.get('contract') or {}
    for key in (
        'presentation_and_policy_compiler_only',
        'v1_risk_budget_remains_authoritative',
        'v2_risk_budget_remains_challenger',
        'alpha_buy_gate_remains_security_action_authority',
        'validation_os_can_only_reduce_reviewed_confidence',
        'does_not_create_buy_candidates',
        'does_not_store_private_portfolio',
        'no_automatic_trading',
    ):
        assert contract.get(key) is True,key

    command=obj.get('command') or {}
    assert command.get('code') in ALLOWED_ACTIONS
    assert command.get('decision_confidence') in ('LOW','MEDIUM','HIGH')
    assert command.get('title') and command.get('action')

    alloc=obj.get('allocation') or {}
    v1=alloc.get('v1_authoritative_equity_pct');v2=alloc.get('v2_market_aware_review_equity_pct')
    if v1 is not None and v2 is not None:
        assert finite(v1) and finite(v2)
        zone=alloc.get('operating_zone_equity_pct')
        assert isinstance(zone,list) and len(zone)==2
        assert abs(float(zone[0])-min(float(v1),float(v2)))<1e-6
        assert abs(float(zone[1])-max(float(v1),float(v2)))<1e-6
        assert 0<=zone[0]<=zone[1]<=100

    alpha=obj.get('alpha') or {}
    assert int(alpha.get('buy_candidate_count') or 0)>=0
    assert int(alpha.get('verify_count') or 0)>=0
    if int(alpha.get('buy_candidate_count') or 0)==0:
        assert command.get('deployment_policy')!='BUY_GATE_ONLY'

    cf=obj.get('counterfactuals') or {}
    if cf.get('status')=='READY':
        assert finite(cf.get('base_target_equity_pct'))
        n=int(cf.get('training_samples') or 0)
        assert n>=36
        rows=cf.get('scenarios') or []
        assert len(rows)>=4
        for row in rows:
            assert row.get('id') and row.get('label')
            assert finite(row.get('target_equity_pct'))
            assert finite(row.get('delta_vs_current_pp'))
            assert int(row.get('training_samples') or 0)==n
            assert 'same training set' in str(row.get('contract'))

    triggers=obj.get('what_changes_my_mind') or {}
    assert len(triggers.get('increase_risk') or [])>=3
    assert len(triggers.get('decrease_risk') or [])>=3
    assert obj.get('evidence_hash') and len(obj['evidence_hash'])==64

    forbidden={'total_assets','current_equity','cash_balance','holdings','debt','personal_portfolio'}
    text=str(obj).lower()
    for key in forbidden:
        assert f"'{key}':" not in text and f'"{key}":' not in text,key

    print('DECISION COMMAND CENTER VALIDATION PASS')
    print('command:',command.get('code'),'-',command.get('title'))
    print('zone:',alloc.get('operating_zone_equity_pct'))
    print('confidence:',command.get('decision_confidence'))
    print('counterfactuals:',len((cf.get('scenarios') or [])))

if __name__=='__main__':main()
