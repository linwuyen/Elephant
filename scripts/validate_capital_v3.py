#!/usr/bin/env python3
import json,math,sys
from pathlib import Path
DATA=Path(__file__).resolve().parents[1]/'data'
def load(n):
 p=DATA/n
 if not p.exists():raise SystemExit('CAPITAL V3 VALIDATION ERROR missing '+n)
 return json.loads(p.read_text(encoding='utf-8'))
def fail(x):print('CAPITAL V3 VALIDATION ERROR:',x,file=sys.stderr);raise SystemExit(1)
reg=load('model_registry.json');facts=load('opportunity_market_facts.json');oppin=load('opportunity_inputs.json');store=load('security_fact_store.json');pm=load('portfolio_model.json');cap=load('capital_allocation.json');gov=load('model_governance.json');cal=load('investment_calibration.json');state=load('portfolio_state.json');constitution=load('investment_constitution.json');cres=load('investment_constitution_results.json');research=load('constitution_research.json')
if reg.get('model_version')!='capital-v3.1.0':fail('model_version')
if reg.get('investment_constitution',{}).get('required_before_new_capital') is not True:fail('constitution registry authority')
public={x.get('id'):x for x in oppin.get('alternatives',[]) if x.get('id')!='DEBT_REPAYMENT'}
for k in ('2330','TAIWAN_BROAD','GLOBAL_EQUITY','CASH'):
 if k not in public:fail('missing public alternative '+k)
for k in ('TAIWAN_BROAD','GLOBAL_EQUITY','CASH'):
 if public[k].get('status')!='AVAILABLE' or not isinstance(public[k].get('expected_return_pct'),(int,float)):fail('public alternative unavailable '+k)
if oppin.get('public_available_count',0)<4:fail('public opportunity set incomplete')
if state.get('status')!='UNCONFIGURED' or state.get('storage_policy')!='BROWSER_LOCAL_ONLY':fail('portfolio privacy sentinel')
if not store.get('fingerprint') or len(store.get('securities',[]))<7:fail('security fact store')
for s in store.get('securities',[]):
 if s.get('stage')=='DISCOVERY' and s.get('action')=='BUY CANDIDATE':fail('discovery buy authority')
if pm.get('status')!='MODEL_ASSUMPTION' or len(pm.get('factors',[]))<8:fail('portfolio model')
if set(('2330','TAIWAN_BROAD','GLOBAL_EQUITY','CASH'))-set((pm.get('alternative_loadings') or {}).keys()):fail('alternative factor loadings')
if cap.get('version')!=2:fail('capital allocation version')
guards=cap.get('guardrails',{})
for k in ('no_automatic_trading','constitution_required_for_new_capital','constitution_cannot_create_upstream_buy'):
 if guards.get(k) is not True:fail('capital guardrail '+k)
if constitution.get('authority')!='FINAL_CAPITAL_ELIGIBILITY_GATE':fail('constitution authority')
required_gates={'earnings_power','fundamental_driven_return','catalyst','convexity','survival_downside','quarterly_falsifiability'}
if set(constitution.get('rules',{}))!=required_gates:fail('constitution rule set')
if research.get('version')!=1 or not isinstance(research.get('securities'),dict):fail('constitution research contract')
for r in cres.get('securities',[]):
 gates=r.get('gates',{})
 if set(gates)!=required_gates:fail('constitution gates '+str(r.get('ticker')))
 statuses={g.get('status') for g in gates.values()}
 if not statuses <= {'PASS','FAIL','BLOCKED'}:fail('constitution status domain')
 if r.get('constitution_status')=='PASS' and statuses!={'PASS'}:fail('false constitution pass '+str(r.get('ticker')))
 if r.get('capital_eligible') and not (r.get('constitution_status')=='PASS' and r.get('upstream_action')=='BUY CANDIDATE'):fail('false capital eligibility '+str(r.get('ticker')))
cmap={str(r.get('ticker')):r for r in cres.get('securities',[])}
for r in cap.get('lifecycle',[]):
 t=str(r.get('ticker'));cs=cmap.get(t,{}).get('constitution_status','BLOCKED')
 if r.get('constitution_status')!=cs:fail('lifecycle constitution mismatch '+t)
 if r.get('portfolio_action') in ('BUY_REVIEW','ADD_REVIEW') and not (r.get('upstream_action')=='BUY CANDIDATE' and cs=='PASS'):fail('capital bypassed constitution '+t)
for r in cap.get('target_sizing',{}).get('targets',[]):
 if cmap.get(str(r.get('ticker')),{}).get('constitution_status')!='PASS':fail('sizing bypassed constitution '+str(r.get('ticker')))
if gov.get('model_version')!=reg.get('model_version') or not gov.get('artifacts'):fail('model governance')
for r in cal.get('decisions',[]):
 for k in ('decision_fingerprint','model_version','code_commit','evidence_hash'):
  if r.get(k) in (None,''):fail('decision provenance '+k)
print('CAPITAL V3.1 VALIDATION PASS')
print('public alternatives:',oppin.get('public_available_count'))
print('security facts:',len(store.get('securities',[])))
print('constitution pass:',cres.get('pass_count'),'capital eligible:',cres.get('capital_eligible_count'))
print('model version:',reg.get('model_version'))
print('calibration decisions:',len(cal.get('decisions',[])))
