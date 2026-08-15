#!/usr/bin/env python3
from __future__ import annotations

import build_market_validation as market
import build_decision_engine_v2 as v2


def score_rows(start='2016-01', n=72, phase=0):
    rows=[]; p=start
    for i in range(n):
        score=-70 + ((i+phase)%24)*(140/23)
        rows.append({'period':p,'score':score})
        p=v2.month_shift(p,1)
    return rows

histories={k:score_rows(phase=i*3) for i,k in enumerate(v2.ALL_DIMS)}
stock={}
p='2016-01'; value=8000.0
for i in range(84):
    value *= 1.0 + (0.012 if i%6 not in (4,5) else -0.008)
    stock[p]=value
    p=v2.month_shift(p,1)

out,dd=market.market_outcomes(histories,stock)
for key in v2.CORE_DIMS:
    assert out[key]['source']=='TWSE'
    assert out[key]['series']==market.MARKET_KEY
    assert out[key]['horizons']['6m']['samples']>30
    assert dd[key]['6m']['samples']>30

risk=market.risk_backtest(histories,stock)
assert risk['status']=='DIAGNOSTIC_ONLY'
assert risk['authority'] is False
assert risk['observations']>=36
pv=risk['policy_vs_static_60_equity']
assert pv['transaction_costs_included'] is False
assert pv['cash_return_assumption_pct']==0.0
assert 'policy_scaled_equity_return_pct' in pv
assert risk['market_series']==market.MARKET_KEY

# Market evidence alone can unlock the risk-observation gate, but it still cannot
# auto-promote v2: prospective journal evidence remains separately mandatory.
wf={k:{'horizons':{'3m':{'oos_predictions':30,'brier_skill_vs_climatology':.10},'6m':{'oos_predictions':30,'brier_skill_vs_climatology':.10}}} for k in v2.CORE_DIMS}
ext={k:{'stock_forward_return':out[k]} for k in v2.CORE_DIMS}
gate=v2.promotion_gate(wf,ext,risk,{'resolved_total':0})
assert gate['gates']['risk_backtest_observations_at_least_36'] is True
assert gate['gates']['prospective_resolved_outcomes_at_least_24'] is False
assert gate['promotion_eligible'] is False
assert gate['automatic_promotion'] is False
assert gate['status']=='CHALLENGER_ONLY'

print('MARKET VALIDATION TEST PASS')
