#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data';OUT=DATA/'statistical_challengers.json'
DIMS=('growth_persistence','domestic_demand','financial_conditions')

def load(name,default=None):
 p=DATA/name;return json.loads(p.read_text(encoding='utf-8')) if p.exists() else ({} if default is None else default)

def shift(period,h):
 y,m=map(int,period.split('-'));n=y*12+(m-1)+h;return f'{n//12:04d}-{n%12+1:02d}'

def corr(a,b):
 if len(a)<3:return None
 ma=sum(a)/len(a);mb=sum(b)/len(b);va=sum((x-ma)**2 for x in a);vb=sum((x-mb)**2 for x in b)
 if va<=0 or vb<=0:return None
 return sum((x-ma)*(y-mb) for x,y in zip(a,b))/math.sqrt(va*vb)

def ridge_fit(xs,ys,lam=25.0):
 # y = a + b*x, ridge only the slope. Closed form is deterministic and dependency-free.
 n=len(xs)
 if n<12:return None
 mx=sum(xs)/n;my=sum(ys)/n
 den=sum((x-mx)**2 for x in xs)+lam
 b=sum((x-mx)*(y-my) for x,y in zip(xs,ys))/den
 return my-b*mx,b

def expanding_ridge(rows,h,min_train=36):
 m={x['period']:float(x['score']) for x in rows if x.get('score') is not None};periods=sorted(m);pred=[];actual=[]
 for i,p in enumerate(periods):
  target=shift(p,h)
  if target not in m:continue
  train=[]
  for q in periods[:i]:
   tq=shift(q,h)
   if tq in m:train.append((m[q],m[tq]))
  if len(train)<min_train:continue
  model=ridge_fit([x for x,_ in train],[y for _,y in train])
  if not model:continue
  a,b=model;pred.append(a+b*m[p]);actual.append(m[target])
 return {'samples':len(pred),'pearson':None if (r:=corr(pred,actual)) is None else round(r,3),'minimum_train_samples':min_train}

def ewma(rows,h,alpha=.35):
 m={x['period']:float(x['score']) for x in rows if x.get('score') is not None};periods=sorted(m);state=None;pred=[];actual=[]
 for p in periods:
  x=m[p];state=x if state is None else alpha*x+(1-alpha)*state;t=shift(p,h)
  if t in m:pred.append(state);actual.append(m[t])
 return {'samples':len(pred),'pearson':None if (r:=corr(pred,actual)) is None else round(r,3),'alpha':alpha}

def bayesian_shrinkage(rows,h,prior_strength=12):
 m={x['period']:float(x['score']) for x in rows if x.get('score') is not None};periods=sorted(m);pred=[];actual=[];seen=[]
 for p in periods:
  x=m[p];t=shift(p,h)
  if t in m and len(seen)>=12:
   mean=sum(seen)/len(seen);w=len(seen)/(len(seen)+prior_strength);pred.append(w*x+(1-w)*mean);actual.append(m[t])
  seen.append(x)
 return {'samples':len(pred),'pearson':None if (r:=corr(pred,actual)) is None else round(r,3),'prior_strength':prior_strength}

def build():
 scores=load('decision_scores.json',{});pit=load('point_in_time_validation.json',{});out={}
 for d in DIMS:
  rows=(scores.get('history') or {}).get(d) or []
  out[d]={'3m':{'ridge':expanding_ridge(rows,3),'ewma':ewma(rows,3),'bayesian_shrinkage':bayesian_shrinkage(rows,3)},'6m':{'ridge':expanding_ridge(rows,6),'ewma':ewma(rows,6),'bayesian_shrinkage':bayesian_shrinkage(rows,6)}}
 return {
  'version':1,'contract':'non-authoritative-statistical-challenger-lab-v1','authority':False,
  'historical_mode':'LATEST_REVISED_RECONSTRUCTION','production_promotion_eligible':False,
  'models':out,
  'blocked_models':{
   'DYNAMIC_FACTOR_MODEL':'BLOCKED_POINT_IN_TIME_MIXED_FREQUENCY_HISTORY',
   'MIDAS':'BLOCKED_POINT_IN_TIME_MIXED_FREQUENCY_HISTORY',
   'BAYESIAN_MODEL_AVERAGING':'BLOCKED_UNTIL_COMPONENT_LEVEL_PIT_FEATURE_MATRIX_MATURES'
  },
  'point_in_time_gate':pit.get('status'),
  'guardrail':'These diagnostics test simple statistical calibration on revised history only. No statistical model may replace production heuristics until the preregistered point-in-time promotion contract is satisfied.'
 }

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();obj=build()
 if a.check:assert load('statistical_challengers.json',{})==obj,'statistical_challengers.json stale';print('STATISTICAL CHALLENGERS PASS')
 else:OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(OUT)
if __name__=='__main__':main()
