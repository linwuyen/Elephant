#!/usr/bin/env python3
from __future__ import annotations
import copy
import datetime as dt

import build_validation_os as vos
import build_decision_scores as bds

# Geometric confidence is monotone: degrading a source factor must reduce it.
good=vos.weighted_geometric([(100,.3),(100,.25),(100,.25),(60,.2)])
bad=vos.weighted_geometric([(100,.3),(100,.25),(70,.25),(60,.2)])
assert bad < good < 100

# Same-day vintage collection cannot masquerade as 100% revision stability.
real_load=vos.load_json
try:
    def fake_load(name,default):
        if name=='vintage_manifest.json':
            return {'first_observed_at':'2026-08-16T00:00:00+08:00','revision_observations':0}
        if name=='revisions.json':
            return {'history':[]}
        return real_load(name,default)
    vos.load_json=fake_load
    ev=vos.vintage_evidence_maturity(dt.datetime(2026,8,16,1,0,tzinfo=vos.TZ))
    assert 60 <= ev['score'] < 61
finally:
    vos.load_json=real_load

# Artificial regime novelty must breach HIGH without mutating any model.
real_hist=vos.histories
real_cur=vos.current_dimensions
real_regime=vos.de2.regime_similarity
try:
    rows={}
    for dim in vos.ALL_DIMS:
        rows[dim]=[{'period':f'{2019+i//12:04d}-{i%12+1:02d}','score':float((i%7)-3)} for i in range(72)]
    vos.histories=lambda: rows
    vos.current_dimensions=lambda: {dim:{'score':100.0,'period':'2026-06'} for dim in vos.ALL_DIMS}
    vos.de2.regime_similarity=lambda h,c:{'similarity':20.0,'status':'LOW'}
    sb=vos.structural_break_monitor()
    assert sb['status']=='HIGH'
    assert sb['distribution_similarity']<40
finally:
    vos.histories=real_hist
    vos.current_dimensions=real_cur
    vos.de2.regime_similarity=real_regime

# Equal-weight challenger is an in-memory benchmark and must restore production weights.
before=copy.deepcopy(bds.WEIGHTS)
vos.equal_weight_scores()
assert bds.WEIGHTS==before

# A prospective journal must not count an outcome that was already known at capture.
entries=[{
    'known_latest_score_periods':{'cycle':'2026-06'},
    'scores':{'cycle':{'period':'2026-03','score':50}},
    'forecast_probabilities':{'cycle':{'3m':0.8,'6m':0.8,'12m':0.8}},
}]
hs={dim:[] for dim in vos.ALL_DIMS}
hs['cycle']=[{'period':'2026-06','score':80}]
card=vos.macro_scorecard(entries,hs)
assert card['resolved_total']==0

# Truly later information can resolve.
entries=[{
    'known_latest_score_periods':{'cycle':'2026-03'},
    'scores':{'cycle':{'period':'2026-03','score':50}},
    'forecast_probabilities':{'cycle':{'3m':0.8,'6m':0.8,'12m':0.8}},
}]
card=vos.macro_scorecard(entries,hs)
assert card['resolved_total']==1

print('VALIDATION OS TEST PASS')
