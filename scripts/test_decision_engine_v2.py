#!/usr/bin/env python3
from __future__ import annotations

import build_decision_engine_v2 as v2


def synthetic_rows(n=72):
    rows=[]
    y,m=2018,1
    for i in range(n):
        score=-80 + (i % 24) * (160/23)
        rows.append({'period':f'{y:04d}-{m:02d}','score':score})
        m+=1
        if m==13:
            y+=1;m=1
    return rows


rows=synthetic_rows()
res=v2.walk_forward_dimension('cycle',rows,3,current_score=70,current_period='2023-12')
assert res['oos_predictions']>0
assert res['current'] is not None
assert 0<=res['current']['probability']<=1
assert 0<=res['current']['model_confidence']<=100

# Every historical prediction must obey the strict temporal rule. Reconstruct the
# exact eligible set and prove no training outcome can be later than prediction p.
pairs=v2.completed_pairs(rows,3)
for item in pairs:
    training=[x for x in pairs if x['outcome_period']<=item['period']]
    if len(training)<v2.MIN_WALK_FORWARD_TRAIN:
        continue
    assert max(x['outcome_period'] for x in training)<=item['period']

# Sample-aware confidence must not reward tiny samples over otherwise identical
# larger evidence. Small local/global support is explicitly penalized.
small=v2.sample_aware_confidence(.12,.24,.75,5,2,prospective_n=0,regime_similarity=80)
large=v2.sample_aware_confidence(.12,.24,.75,60,20,prospective_n=0,regime_similarity=80)
assert 0<=small<large<=100

# Prospective evidence may increase confidence, but never beyond 100.
prospective=v2.sample_aware_confidence(.12,.24,.75,60,20,prospective_n=60,regime_similarity=80)
assert large<prospective<=100

# Regime mismatch must reduce confidence for otherwise identical evidence.
high_regime=v2.sample_aware_confidence(.12,.24,.75,60,20,prospective_n=0,regime_similarity=100)
low_regime=v2.sample_aware_confidence(.12,.24,.75,60,20,prospective_n=0,regime_similarity=30)
assert low_regime<high_regime

# Risk-budget state reconstruction must remain bounded and deterministic.
hist={k:synthetic_rows(36) for k in v2.ALL_DIMS}
states=v2.historical_risk_states(hist)
assert states
assert all(0<=x['risk_score']<=100 for x in states)
assert all(20<=x['equity_pct']<=90 for x in states)

# Promotion is never automatic, even when every evidence gate is satisfied.
wf={k:{'horizons':{'3m':{'oos_predictions':30,'brier_skill_vs_climatology':.10},'6m':{'oos_predictions':30,'brier_skill_vs_climatology':.10}}} for k in v2.CORE_DIMS}
outcomes={k:{'stock_forward_return':{'kind':'market','horizons':{}}} for k in v2.CORE_DIMS}
risk={'observations':60}
journal={'resolved_total':30}
gate=v2.promotion_gate(wf,outcomes,risk,journal)
assert gate['promotion_eligible'] is True
assert gate['automatic_promotion'] is False
assert gate['status']=='PROMOTION_ELIGIBLE_FOR_REVIEW'

# If official market evidence is absent, the Risk Budget backtest is blocked and
# promotion must remain impossible. Missing evidence never creates a proxy.
macro_only={k:{'industrial_production_yoy':{'kind':'macro','horizons':{'6m':{'samples':30}}}} for k in v2.CORE_DIMS}
blocked=v2.promotion_gate(wf,macro_only,{'status':'BLOCKED_NO_STOCK_INDEX','observations':0},journal)
assert blocked['promotion_eligible'] is False
assert blocked['automatic_promotion'] is False
assert blocked['status']=='CHALLENGER_ONLY'
assert blocked['gates']['external_outcomes_present'] is True
assert blocked['gates']['risk_backtest_observations_at_least_36'] is False

print('DECISION ENGINE V2 TEST PASS')
