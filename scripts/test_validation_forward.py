#!/usr/bin/env python3
from __future__ import annotations

import build_validation_forward as vf


def rows(start_year=2015, n=96, lead=0):
    out=[]; y=start_year; m=1
    for i in range(n):
        p=f'{y:04d}-{m:02d}'
        score=max(-100,min(100,((i % 24)-12)*7+lead))
        out.append({'period':p,'score':score,'label':'x','confidence':100})
        m+=1
        if m==13: y+=1; m=1
    return out

cycle=rows()
signal=[]
for r in cycle:
    q=vf.month_shift(r['period'],-3)
    prev=next((x for x in cycle if x['period']==q), None)
    if prev: signal.append({'period':prev['period'],'score':r['score'],'label':'x','confidence':100})
v=vf.validate_signal(signal,cycle)
assert v['horizons']['3m']['samples'] > 50
assert v['horizons']['3m']['pearson_to_future_cycle'] > .95

cur={'period':'2026-06','score':50,'confidence':80,'components':[
    {'key':'a','score':80,'weight':.4,'period':'2026-06'},
    {'key':'b','score':20,'weight':.4,'period':'2026-05'},
]}
q=vf.confidence_breakdown(cur,70)
assert 0 <= q['overall'] <= 100
assert q['coverage']==80
s=vf.scenario(cur)
assert s['scenario_score'] <= s['baseline']
assert s['reverse_stress']['uniform_component_drop_to_cross_zero'] == 50
c=vf.sensitivity(cur)
assert c['max_current_score_change'] >= 0
print('VALIDATION/FORWARD LOGIC TEST PASS')
