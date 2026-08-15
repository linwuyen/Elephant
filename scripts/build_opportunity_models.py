#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt, json
from common import TZ, load_json, save_json

def age_days(asof,now):
 if not asof:return None
 try:return (now.date()-dt.date.fromisoformat(asof)).days
 except Exception:return None

def equity_er(pe,growth):return None if not isinstance(pe,(int,float)) or pe<=0 else round(100.0/float(pe)+float(growth),2)

def generate():
 now=dt.datetime.now(TZ).replace(microsecond=0);facts=load_json('opportunity_market_facts.json',{}).get('facts',{});registry=load_json('model_registry.json',{});models=registry.get('benchmark_models',{});alts=[]
 alts.append({'id':'2330','name':'台積電','type':'equity_benchmark','source':'ALPHA_ENGINE','expected_return_pct':None,'status':'DERIVED','model':'upstream_scenario_valuation'})
 for key,typ in [('TAIWAN_BROAD','equity_benchmark'),('GLOBAL_EQUITY','equity_benchmark')]:
  f=facts.get(key,{});m=models.get(key,{});age=age_days(f.get('as_of'),now);maxage=int(m.get('max_fact_age_days',f.get('max_age_days',0) or 0));fresh=age is not None and age<=maxage;er=equity_er(f.get('pe'),m.get('sustainable_nominal_growth_pct',4.0)) if fresh else None
  proxy=m.get('proxy') or key;name=('台灣大盤替代資產' if key=='TAIWAN_BROAD' else '全球股票替代資產')+f'（{proxy} proxy）'
  alts.append({'id':key,'name':name,'type':typ,'source':'FIRST_PARTY_ISSUER+MODEL','expected_return_pct':er,'status':'AVAILABLE' if er is not None else 'UNAVAILABLE','model':'earnings_yield_plus_sustainable_nominal_growth','proxy':proxy,'model_inputs':{'pe':f.get('pe'),'sustainable_nominal_growth_pct':m.get('sustainable_nominal_growth_pct',4.0)},'fact_as_of':f.get('as_of'),'fact_age_days':age,'source_url':f.get('source_url'),'warning':'Expected return is an Elephant model estimate, not issuer guidance.'})
 f=facts.get('CASH',{});m=models.get('CASH',{});age=age_days(f.get('as_of'),now);maxage=int(m.get('max_fact_age_days',f.get('max_age_days',0) or 0));rate=f.get('rate_pct') if age is not None and age<=maxage else None
 alts.append({'id':'CASH','name':'現金／短期無風險替代（CBC policy-rate proxy）','type':'cash','source':'CBC_FIRST_PARTY','expected_return_pct':rate,'status':'AVAILABLE' if isinstance(rate,(int,float)) else 'UNAVAILABLE','model':'policy_rate_proxy','fact_as_of':f.get('as_of'),'fact_age_days':age,'source_url':f.get('source_url'),'warning':'Policy rate is a conservative public proxy, not the user account deposit rate.'})
 alts.append({'id':'DEBT_REPAYMENT','name':'償還負債','type':'debt_repayment','source':'BROWSER_LOCAL_ONLY','expected_return_pct':None,'status':'DERIVED_IF_CONFIGURED','model':'user_effective_rate'})
 out={'version':2,'as_of':now.date().isoformat(),'alternatives':alts,'frictions':{'round_trip_friction_pct':1.0,'note':'Conservative public default. Browser-local planner can override actual costs.'},'public_available_count':sum(x.get('status') in ('AVAILABLE','DERIVED') for x in alts if x['id']!='DEBT_REPAYMENT'),'model_version':registry.get('model_version'),'guardrail':'Only fresh reproducible public facts may create a public expected-return alternative; private debt remains browser-local.'}
 save_json('opportunity_inputs.json',out);return out

if __name__=='__main__':print(json.dumps(generate(),ensure_ascii=False,indent=2))
