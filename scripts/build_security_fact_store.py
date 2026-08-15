#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from common import load_json,save_json
import valuation_router

def digest(obj):return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def evidence_summary(r):
 ev=r.get('evidence') or [];first=[x for x in ev if x.get('quality')=='FIRST_PARTY' and x.get('status')=='VERIFIED'];return {'first_party_verified_count':len(first),'metrics':sorted({str(x.get('metric')) for x in first if x.get('metric')}),'latest_observed_at':max((str(x.get('observed_at')) for x in first if x.get('observed_at')),default=None),'evidence_hash':digest(first) if first else None,'sources':[{'metric':x.get('metric'),'period':x.get('period'),'observed_at':x.get('observed_at'),'source_type':x.get('source_type'),'source_url':x.get('source_url')} for x in first]}
def completeness(official,evidence):
 req={'reference_price','earnings_basis','revenue_trend','balance_sheet_cash_flow','material_events','valuation_basis'};have=set(evidence.get('metrics') or []);support={}
 if official.get('income_statement'):have.add('earnings_basis');support['earnings_basis']='official_income_statement'
 if official.get('monthly_revenue'):have.add('revenue_trend');support['revenue_trend']='official_monthly_revenue'
 if official.get('balance_sheet'):
  support['balance_sheet']='official_balance_sheet'
  # A balance sheet is useful evidence but is not a cash-flow statement. The combined
  # Buy/Research requirement stays missing unless upstream first-party evidence has
  # explicitly verified balance_sheet_cash_flow (or a future dedicated cash-flow feed exists).
 if 'balance_sheet_cash_flow' in have:support['balance_sheet_cash_flow']='upstream_first_party_evidence'
 return {'required':sorted(req),'available':sorted(req&have),'missing':sorted(req-have),'coverage_pct':round(len(req&have)/len(req)*100,1),'supporting_facts':support,'cash_flow_status':'VERIFIED' if 'balance_sheet_cash_flow' in have else 'MISSING_DEDICATED_CASH_FLOW_EVIDENCE'}
def normalize(r,stage,official,market=None):
 vm=r.get('valuation_model') or {};arch=valuation_router.classify(r);ev=evidence_summary(r);comp=completeness(official,ev);return {'ticker':str(r.get('ticker')),'name':r.get('name'),'market':market or r.get('market'),'stage':stage,'rank':r.get('rank'),'action':r.get('action'),'grade':r.get('grade'),'alpha_score':r.get('score'),'confidence_score':r.get('confidence_score'),'reference_price':r.get('reference_price'),'reference_price_date':r.get('reference_price_date'),'fundamental_data_as_of':r.get('fundamental_data_as_of'),'revenue_data_as_of':r.get('revenue_data_as_of'),'event_data_as_of':r.get('event_data_as_of'),'archetype':arch,'valuation':{'status':vm.get('status'),'raw_model':vm.get('model_type'),'effective_model':valuation_router.effective_model(r,arch),'expected_return_pct':vm.get('expected_return_pct'),'margin_of_safety_pct':vm.get('margin_of_safety_pct'),'scenarios':vm.get('scenarios')},'alpha_spread_pct':r.get('alpha_spread_pct'),'risk_model':r.get('risk_model'),'thesis_status':r.get('thesis_status'),'thesis':r.get('thesis'),'invalidation_condition':r.get('invalidation_condition'),'official_facts':official,'research_completeness':comp,'evidence':ev}
def generate():
 bundle=load_json('alpha_engine.json',{});alpha=bundle.get('alpha') or {};screen=bundle.get('screen') or {};off=load_json('security_official_facts.json',{}).get('facts') or {};rows=[];bench=alpha.get('benchmark_asset')
 if bench:rows.append(normalize(bench,'BENCHMARK',off.get('2330',{}),'TWSE'))
 researched={str(x.get('ticker')) for x in alpha.get('stocks',[])}
 for r in alpha.get('stocks',[]):rows.append(normalize(r,'RESEARCHED',off.get(str(r.get('ticker')),{})))
 for r in screen.get('deep_research_queue',[]) or []:
  t=str(r.get('ticker'))
  if t not in researched:rows.append(normalize(r,'DISCOVERY',off.get(t,{}),r.get('market')))
 out={'version':3,'source':'Alpha upstream + deterministic listed-market official numeric fact store','as_of':alpha.get('meta',{}).get('as_of'),'securities':rows,'official_source_health':load_json('security_official_facts.json',{}).get('source_health',{}),'guardrail':'Balance-sheet facts never masquerade as cash-flow evidence. Research/Buy completeness remains fail-closed until dedicated first-party cash-flow evidence exists.'};out['fingerprint']=digest(out['securities']);save_json('security_fact_store.json',out);return out
if __name__=='__main__':print(json.dumps(generate(),ensure_ascii=False,indent=2))
