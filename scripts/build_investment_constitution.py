#!/usr/bin/env python3
from __future__ import annotations
import json, math
from common import load_json, save_json

def finite(v): return isinstance(v,(int,float)) and math.isfinite(float(v))
def gate(status,value=None,threshold=None,reason=None,evidence=None): return {'status':status,'value':value,'threshold':threshold,'reason':reason,'evidence':evidence or []}
def required_fields(obj,fields): return all(obj.get(k) not in (None,'',[]) for k in fields)

def evaluate(stock,research,constitution):
 rules=constitution['rules'];price=stock.get('reference_price');earn=research.get('long_horizon_earnings') or {};val=research.get('long_horizon_valuation') or {};cats=research.get('catalysts') or [];surv=research.get('survival') or {};quarterly=research.get('quarterly_checks') or [];g={}
 ep=rules['earnings_power'];ef=['metric','baseline_period','baseline_value','target_period','target_value','target_multiple','horizon_months','evidence_and_assumptions']
 if earn.get('status')!='COMPLETE' or not required_fields(earn,ef) or not finite(earn.get('target_multiple')) or not finite(earn.get('horizon_months')):g['earnings_power']=gate('BLOCKED',reason='Missing structured 24-36m EPS/FCF model.')
 else:
  mult=float(earn['target_multiple']);months=float(earn['horizon_months']);ok=mult>=float(ep['minimum_eps_or_fcf_multiple']) and float(ep['horizon_months_min'])<=months<=float(ep['horizon_months_max']);g['earnings_power']=gate('PASS' if ok else 'FAIL',round(mult,2),f">={ep['minimum_eps_or_fcf_multiple']}x within {ep['horizon_months_min']}-{ep['horizon_months_max']}m",'Earnings power meets constitution.' if ok else 'EPS/FCF path is not close enough to 2x inside 2-3 years.',earn.get('evidence_and_assumptions'))
 vf=['model_type','current_multiple','bull_multiple','bear_fair_value','evidence_and_assumptions'];valuation_complete=val.get('status')=='COMPLETE' and required_fields(val,vf) and all(finite(val.get(k)) for k in ('current_multiple','bull_multiple','bear_fair_value')) and finite(earn.get('target_value')) and finite(price) and float(price)>0
 bull_fv=float(earn['target_value'])*float(val['bull_multiple']) if valuation_complete else None;bull_pm=bull_fv/float(price) if bull_fv is not None else None;bear_ret=(float(val['bear_fair_value'])/float(price)-1)*100 if valuation_complete else None
 fd=rules['fundamental_driven_return'];contrib=expansion=None
 if valuation_complete and finite(earn.get('target_multiple')) and bull_pm and bull_pm>1 and float(earn['target_multiple'])>0:
  contrib=math.log(float(earn['target_multiple']))/math.log(float(bull_pm))*100;expansion=float(val['bull_multiple'])/float(val['current_multiple'])
 if contrib is None or expansion is None:g['fundamental_driven_return']=gate('BLOCKED',reason='Missing comparable 24-36m earnings/valuation decomposition.')
 else:
  ok=contrib>=float(fd['minimum_fundamental_upside_contribution_pct']) and expansion<=float(fd['maximum_valuation_multiple_expansion_ratio']);g['fundamental_driven_return']=gate('PASS' if ok else 'FAIL',{'fundamental_contribution_pct':round(contrib,1),'valuation_expansion_ratio':round(expansion,2)},{'fundamental_contribution_pct':f">={fd['minimum_fundamental_upside_contribution_pct']}",'valuation_expansion_ratio':f"<={fd['maximum_valuation_multiple_expansion_ratio']}"},'Bull return is fundamentally driven.' if ok else 'Bull case relies too much on valuation expansion.',val.get('evidence_and_assumptions'))
 cr=rules['catalyst'];valid_cat=[c for c in cats if required_fields(c,['name','mechanism','kpi','expected_window','source_quality','source_url']) and c.get('source_quality')==cr['required_source_quality']];g['catalyst']=gate('PASS' if len(valid_cat)>=int(cr['minimum_count']) else 'BLOCKED',len(valid_cat),f">={cr['minimum_count']} structured FIRST_PARTY catalyst",'Catalyst is measurable and sourced.' if valid_cat else 'No structured first-party catalyst with mechanism/KPI/window.',valid_cat)
 cv=rules['convexity']
 if bull_pm is None:g['convexity']=gate('BLOCKED',reason='Missing 24-36m bull valuation model.')
 else:
  ok=bull_pm>=float(cv['minimum_bull_price_multiple']);g['convexity']=gate('PASS' if ok else 'FAIL',round(bull_pm,2),f">={cv['minimum_bull_price_multiple']}x",'24-36m Bull convexity clears the hard gate.' if ok else '24-36m Bull case is not at least 2.5x.')
 sd=rules['survival_downside'];down='BLOCKED' if bear_ret is None else ('PASS' if bear_ret>=float(sd['minimum_bear_return_pct']) else 'FAIL');sv='PASS' if surv.get('status')==sd['require_survival_status'] and surv.get('existential_risk')=='NONE' else ('BLOCKED' if surv.get('status') in (None,'INCOMPLETE') or surv.get('existential_risk') in (None,'UNKNOWN') else 'FAIL');combined='FAIL' if 'FAIL' in (down,sv) else ('BLOCKED' if 'BLOCKED' in (down,sv) else 'PASS');g['survival_downside']=gate(combined,None if bear_ret is None else round(bear_ret,1),f">={sd['minimum_bear_return_pct']}% + survival PASS",'Bear case must be survivable without rescue financing.',surv.get('basis') or [])
 qf=rules['quarterly_falsifiability'];valid_q=[q for q in quarterly if required_fields(q,['metric','expected','fail_condition','source'])];g['quarterly_falsifiability']=gate('PASS' if len(valid_q)>=int(qf['minimum_metrics']) else 'BLOCKED',len(valid_q),f">={qf['minimum_metrics']} structured quarterly checks",'Thesis can be falsified every quarter.' if len(valid_q)>=int(qf['minimum_metrics']) else 'Need explicit quarterly metrics and pre-committed fail conditions.',valid_q)
 statuses=[x['status'] for x in g.values()];overall='FAIL' if 'FAIL' in statuses else ('BLOCKED' if 'BLOCKED' in statuses else 'PASS');up=stock.get('action')
 return {'ticker':str(stock.get('ticker')),'name':stock.get('name'),'upstream_action':up,'constitution_status':overall,'capital_eligible':overall=='PASS' and up=='BUY CANDIDATE','gates':g,'bull_price_multiple':None if bull_pm is None else round(bull_pm,2),'bear_return_pct':None if bear_ret is None else round(bear_ret,1),'horizon_months':earn.get('horizon_months'),'next_required_evidence':[k for k,v in g.items() if v['status']=='BLOCKED'],'failed_rules':[k for k,v in g.items() if v['status']=='FAIL']}

def generate():
 constitution=load_json('investment_constitution.json',{});research=(load_json('constitution_research.json',{}).get('securities') or {});alpha=(load_json('alpha_engine.json',{}).get('alpha') or {});rows=[evaluate(s,research.get(str(s.get('ticker')),{ }),constitution) for s in alpha.get('stocks',[])];out={'version':2,'constitution_name':constitution.get('name'),'authority':constitution.get('authority'),'as_of':alpha.get('meta',{}).get('as_of'),'status':'COMPLETE','securities':rows,'pass_count':sum(r['constitution_status']=='PASS' for r in rows),'capital_eligible_count':sum(r['capital_eligible'] for r in rows),'guardrail':'Constitution evaluates a dedicated 24-36m model. It cannot create upstream BUY; missing structured evidence fails closed.'};save_json('investment_constitution_results.json',out);return out
if __name__=='__main__':print(json.dumps(generate(),ensure_ascii=False,indent=2))
