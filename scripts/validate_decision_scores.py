#!/usr/bin/env python3
import json, math, sys
from pathlib import Path

DATA=Path(__file__).resolve().parents[1]/'data'
EXPECTED={
    'growth_persistence':{'orders','exports','production','sales','inventory_balance'},
    'domestic_demand':{'real_wage','employment','retail','food','card_spending'},
    'financial_conditions':{'m1b','m2','credit','interest_rate','exchange_rate'},
}
AI_ALLOWED={'electronic_orders','ai_core_exports','electronic_production','non_electronic_breadth'}
ALL_KEYS=set(EXPECTED)|{'ai_concentration'}
METHOD_KEYS={
    'growth_persistence':'growth',
    'domestic_demand':'domestic',
    'financial_conditions':'financial',
}

def fail(msg):
    print('DECISION SCORE VALIDATION ERROR:',msg,file=sys.stderr); raise SystemExit(1)

def load(name,required=True):
    p=DATA/name
    if not p.exists():
        if required:fail('missing '+name)
        return {}
    return json.loads(p.read_text(encoding='utf-8'))

scores=load('decision_scores.json')
inputs=load('decision_inputs.json')
if scores.get('version')!=2:fail('decision_scores version')
if set(scores.get('questions',{}))!=ALL_KEYS:fail('decision question schema')
if set(scores.get('chains',{}))!=ALL_KEYS:fail('decision chain schema')

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

key='ai_concentration'
cur=scores.get('current',{}).get(key)
if not cur:fail('missing current '+key)
if not isinstance(cur.get('score'),(int,float)) or not math.isfinite(cur['score']) or not 0<=cur['score']<=100:fail('invalid score '+key)
if not 0<=cur.get('confidence',-1)<=100:fail('invalid confidence '+key)
parts=cur.get('components',[])
if len(parts)<2:fail('too few components '+key)
keys={x.get('key') for x in parts}
if not keys<=AI_ALLOWED:fail(f'unexpected components {key}: {sorted(keys-AI_ALLOWED)}')
method=scores.get('methodology',{}).get('ai_concentration',{})
weights=method.get('weights',{})
if set(weights)!=AI_ALLOWED or abs(sum(float(v) for v in weights.values())-1)>.0001:fail('methodology weights '+key)
total=sum(float(x.get('weight',0)) for x in parts)
if total<.35:fail('insufficient available weight '+key)
for x in parts:
    if x.get('score') is None or not 0<=x['score']<=100:fail('invalid component '+key)
    if not x.get('period'):fail('component missing period '+key)
    if abs(float(x.get('weight',0))-float(weights[x['key']]))>.0001:fail('component weight mismatch '+key+'/'+x['key'])
hist=scores.get('history',{}).get(key,[])
if len(hist)<12:fail(f'history too short {key}: {len(hist)}')
periods=[x['period'] for x in hist]
if periods!=sorted(periods) or len(periods)!=len(set(periods)):fail('history periods '+key)
if hist[-1]['period']!=cur['period']:fail('history/current period mismatch '+key)
if abs(hist[-1]['score']-cur['score'])>.01:fail('history/current score mismatch '+key)
if '高分代表成長更集中' not in str(cur.get('interpretation','')):fail('AI concentration interpretation missing')

if not inputs.get('series'):fail('decision inputs empty')
print('DECISION SCORE VALIDATION PASS')
for k,v in scores['current'].items():
    if v:print(k,v['score'],v['label'],'confidence',v['confidence'])
print('decision input series:',len(inputs.get('series',{})))
