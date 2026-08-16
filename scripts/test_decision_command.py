#!/usr/bin/env python3
from __future__ import annotations

import build_decision_command as dcc
from common import load_json

# Policy must never invent deployment when no stock has passed the Alpha Buy Gate.
p=dcc.command_policy(75.0,66.6,0,'HIGH',[])
assert p['code']=='HOLD_CASH'
assert p['deployment_policy']=='HOLD_CASH_UNTIL_ALPHA_BUY'

# A materially defensive market-aware budget must produce an explicit risk reduction command.
p=dcc.command_policy(70.0,52.0,2,'WATCH',[])
assert p['code']=='REDUCE_RISK'

# Critical source failure blocks action rather than producing fake precision.
p=dcc.command_policy(75.0,66.6,0,'NORMAL',['ndc'])
assert p['code']=='BLOCKED'

# Confidence can be downgraded by structural novelty even when raw data/evidence are strong.
label,reasons=dcc.confidence_label(90.0,80.0,'HIGH',0,[])
assert label=='MEDIUM'
assert any('structural-break' in x for x in reasons)

# Live artifact must preserve the existing v1/v2 authority boundary and use same-sample sensitivities.
obj=dcc.generate()
assert obj['authority'] is False
assert obj['contract']['v1_risk_budget_remains_authoritative'] is True
assert obj['contract']['v2_risk_budget_remains_challenger'] is True
alloc=obj['allocation']
if alloc['v1_authoritative_equity_pct'] is not None and alloc['v2_market_aware_review_equity_pct'] is not None:
    assert alloc['operating_zone_equity_pct']==sorted([
        float(alloc['v1_authoritative_equity_pct']),
        float(alloc['v2_market_aware_review_equity_pct']),
    ])
cf=obj['counterfactuals']
if cf['status']=='READY':
    n=cf['training_samples']
    assert n>=36
    assert all(x['training_samples']==n for x in cf['scenarios'])
    assert any(x['id']=='market_heat_removed' for x in cf['scenarios'])
    assert any(x['id']=='macro_down_15' for x in cf['scenarios'])

# Command compiler must not persist any browser-local portfolio state.
raw=load_json('decision_command.json',{})
assert 'current_equity' not in str(raw)
assert 'total_assets' not in str(raw)

print('DECISION COMMAND CENTER TEST PASS')
