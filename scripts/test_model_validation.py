#!/usr/bin/env python3
import build_model_validation as mv


def make_periods(n=96):
    y,m=2015,1
    out=[]
    for _ in range(n):
        out.append(f'{y:04d}-{m:02d}')
        m+=1
        if m==13: y+=1; m=1
    return out

periods=make_periods()
cycle=[]
for i,p in enumerate(periods):
    score=max(-100,min(100,((i%24)-12)*7))
    cycle.append({'period':p,'score':score})
cycle_map={x['period']:x for x in cycle}
signal=[]
for p in periods:
    future=mv.month_shift(p,3)
    if future in cycle_map:
        signal.append({'period':p,'score':cycle_map[future]['score']})
result=mv.cross_dimension(signal,cycle)
assert result['horizons']['3m']['samples'] > 50
assert result['horizons']['3m']['pearson_to_future_cycle'] > .95

cur={'period':'2026-06','score':50,'confidence':80,'components':[
    {'key':'a','score':80,'weight':.4,'period':'2026-06'},
    {'key':'b','score':20,'weight':.4,'period':'2026-05'},
]}
conf=mv.confidence_decomposition(cur,70)
assert conf['coverage'] == 80
assert 0 <= conf['provisional_overall'] <= 100
stress=mv.reverse_stress(cur)
assert stress['uniform_drop_to_cross_zero'] == 50
sens=mv.weight_sensitivity(cur)
assert sens['max_abs_score_change'] >= 0
print('MODEL VALIDATION LOGIC TEST PASS')
