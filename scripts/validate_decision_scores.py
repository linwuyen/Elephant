#!/usr/bin/env python3
import json, math, sys
from pathlib import Path
DATA=Path(__file__).resolve().parents[1]/'data'

def fail(msg):
    print('DECISION SCORE VALIDATION ERROR:',msg,file=sys.stderr); raise SystemExit(1)

def load(name):
    p=DATA/name
    if not p.exists():fail('missing '+name)
    return json.loads(p.read_text(encoding='utf-8'))

scores=load('decision_scores.json')
inputs=load('decision_inputs.json')
if scores.get('version')!=1:fail('decision_scores version')
for key in ('growth_persistence','domestic_demand','financial_conditions'):
    cur=scores.get('current',{}).get(key)
    if not cur:fail('missing current '+key)
    if not isinstance(cur.get('score'),(int,float)) or not math.isfinite(cur['score']) or not -100<=cur['score']<=100:fail('invalid score '+key)
    if not 0<=cur.get('confidence',-1)<=100:fail('invalid confidence '+key)
    if len(cur.get('components',[]))<3:fail('too few components '+key)
    total=sum(float(x.get('weight',0)) for x in cur['components'])
    if total<.45:fail('insufficient available weight '+key)
    for x in cur['components']:
        if x.get('score') is None or not -100<=x['score']<=100:fail('invalid component '+key)
        if not x.get('period'):fail('component missing period '+key)
    hist=scores.get('history',{}).get(key,[])
    if len(hist)<12:fail(f'history too short {key}: {len(hist)}')
    periods=[x['period'] for x in hist]
    if periods!=sorted(periods) or len(periods)!=len(set(periods)):fail('history periods '+key)
    if hist[-1]['period']!=cur['period']:fail('history/current period mismatch '+key)
    if abs(hist[-1]['score']-cur['score'])>.01:fail('history/current score mismatch '+key)

if not inputs.get('series'):fail('decision inputs empty')
print('DECISION SCORE VALIDATION PASS')
for k,v in scores['current'].items():print(k,v['score'],v['label'],'confidence',v['confidence'])
print('decision input series:',len(inputs.get('series',{})))
