#!/usr/bin/env python3
import json, math, sys
from pathlib import Path

DATA=Path(__file__).resolve().parents[1]/'data'
EXPECTED={
    'growth_persistence':{'orders','exports','production','sales','inventory_balance'},
    'domestic_demand':{'real_wage','employment','retail','food','card_spending'},
    'financial_conditions':{'m1b','m2','credit','interest_rate','exchange_rate'},
}
METHOD_KEYS={
    'growth_persistence':'growth',
    'domestic_demand':'domestic',
    'financial_conditions':'financial',
}

def fail(msg):
    print('DECISION SCORE VALIDATION ERROR:',msg,file=sys.stderr); raise SystemExit(1)

def load(name):
    p=DATA/name
    if not p.exists():fail('missing '+name)
    return json.loads(p.read_text(encoding='utf-8'))

scores=load('decision_scores.json')
inputs=load('decision_inputs.json')
if scores.get('version')!=1:fail('decision_scores version')
if set(scores.get('questions',{}))!=set(EXPECTED):fail('decision question schema')
if set(scores.get('chains',{}))!=set(EXPECTED):fail('decision chain schema')

for key,allowed in EXPECTED.items():
    cur=scores.get('current',{}).get(key)
    if not cur:fail('missing current '+key)
    if not isinstance(cur.get('score'),(int,float)) or not math.isfinite(cur['score']) or not -100<=cur['score']<=100:fail('invalid score '+key)
    if not 0<=cur.get('confidence',-1)<=100:fail('invalid confidence '+key)
    parts=cur.get('components',[])
    if len(parts)<3:fail('too few components '+key)
    keys={x.get('key') for x in parts}
    if not keys<=allowed:fail(f'unexpected components {key}: {sorted(keys-allowed)}')
    total=sum(float(x.get('weight',0)) for x in parts)
    if total<.45:fail('insufficient available weight '+key)
    method=scores.get('methodology',{}).get(METHOD_KEYS[key],{})
    if set(method)!=allowed or abs(sum(float(v) for v in method.values())-1)>.0001:fail('methodology weights '+key)
    for x in parts:
        if x.get('score') is None or not -100<=x['score']<=100:fail('invalid component '+key)
        if not x.get('period'):fail('component missing period '+key)
        expected_weight=float(method[x['key']])
        if abs(float(x.get('weight',0))-expected_weight)>.0001:fail('component weight mismatch '+key+'/'+x['key'])
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
