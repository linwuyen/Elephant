#!/usr/bin/env python3
import json,math,re,sys
from pathlib import Path
DATA=Path(__file__).resolve().parents[1]/'data'
def load(n):
 p=DATA/n
 if not p.exists():raise SystemExit('CAPITAL V3 VALIDATION ERROR missing '+n)
 return json.loads(p.read_text(encoding='utf-8'))
def fail(x):print('CAPITAL V3 VALIDATION ERROR:',x,file=sys.stderr);raise SystemExit(1)
reg=load('model_registry.json');facts=load('opportunity_market_facts.json');oppin=load('opportunity_inputs.json');store=load('security_fact_store.json');pm=load('portfolio_model.json');cap=load('capital_allocation.json');gov=load('model_governance.json');cal=load('investment_calibration.json');state=load('portfolio_state.json')
if not re.fullmatch(r'capital-v3\.\d+\.\d+',str(reg.get('model_version') or '')):fail('model_version')
for k in ('TAIWAN_BROAD','GLOBAL_EQUITY','CASH'):
 if int((reg.get('benchmark_models',{}).get(k) or {}).get('max_fact_age_days',9999))>120:fail('benchmark freshness too loose '+k)
public={x.get('id'):x for x in oppin.get('alternatives',[]) if x.get('id')!='DEBT_REPAYMENT'}
for k in ('2330','TAIWAN_BROAD','GLOBAL_EQUITY','CASH'):
 if k not in public:fail('missing public alternative '+k)
for k in ('TAIWAN_BROAD','GLOBAL_EQUITY','CASH'):
 if public[k].get('status')!='AVAILABLE' or not isinstance(public[k].get('expected_return_pct'),(int,float)):fail('public alternative unavailable '+k)
 if isinstance(public[k].get('fact_age_days'),(int,float)) and public[k]['fact_age_days']>120:fail('stale public alternative '+k)
if oppin.get('public_available_count',0)<4:fail('public opportunity set incomplete')
if state.get('status')!='UNCONFIGURED' or state.get('storage_policy')!='BROWSER_LOCAL_ONLY':fail('portfolio privacy sentinel')
if not store.get('fingerprint') or len(store.get('securities',[]))<7:fail('security fact store')
for s in store.get('securities',[]):
 if s.get('stage')=='DISCOVERY' and s.get('action')=='BUY CANDIDATE':fail('discovery buy authority')
if pm.get('status')!='MODEL_ASSUMPTION' or len(pm.get('factors',[]))<8:fail('portfolio model')
if set(('2330','TAIWAN_BROAD','GLOBAL_EQUITY','CASH'))-set((pm.get('alternative_loadings') or {}).keys()):fail('alternative factor loadings')
if not cap.get('guardrails',{}).get('no_automatic_trading'):fail('automatic trading guardrail')
if gov.get('model_version')!=reg.get('model_version') or not gov.get('artifacts'):fail('model governance')
for r in cal.get('decisions',[]):
 for k in ('decision_fingerprint','model_version','code_commit','evidence_hash'):
  if r.get(k) in (None,''):fail('decision provenance '+k)
print('CAPITAL V3 VALIDATION PASS');print('public alternatives:',oppin.get('public_available_count'));print('security facts:',len(store.get('securities',[])));print('model version:',reg.get('model_version'));print('calibration decisions:',len(cal.get('decisions',[])))
