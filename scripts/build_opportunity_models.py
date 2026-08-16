#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt, json, math
from common import TZ, load_json, save_json

def age_days(asof,now):
    if not asof:return None
    try:return (now.date()-dt.date.fromisoformat(asof)).days
    except Exception:return None

def equity_er(pe,growth):
    return None if not isinstance(pe,(int,float)) or pe<=0 else round(100.0/float(pe)+float(growth),2)

def annualize_return(total_return_pct,horizon_months):
    if not isinstance(total_return_pct,(int,float)) or not isinstance(horizon_months,(int,float)) or horizon_months<=0:return None
    terminal=1.0+float(total_return_pct)/100.0
    if terminal<=0:return None
    return (terminal**(12.0/float(horizon_months))-1.0)*100.0

def alternative(key,name,typ,source,model,native_return,horizon,status,**extra):
    annual=annualize_return(native_return,horizon) if status=='AVAILABLE' else None
    row={'id':key,'name':name,'type':typ,'source':source,'model':model,
         'native_expected_return_pct':native_return if status=='AVAILABLE' else None,
         'native_horizon_months':horizon,'gross_annualized_expected_return_pct':None if annual is None else round(annual,2),
         'expected_return_pct':None if annual is None else round(annual,2),
         'return_basis':'ANNUALIZED_NOMINAL_PRE_TAX_BEFORE_PERSONAL_FRICTIONS','status':status}
    row.update(extra);return row

def generate():
    now=dt.datetime.now(TZ).replace(microsecond=0);facts=load_json('opportunity_market_facts.json',{}).get('facts',{})
    registry=load_json('model_registry.json',{});models=registry.get('benchmark_models',{});contract=registry.get('return_comparison',{});alts=[]
    hsec=int(contract.get('upstream_security_native_horizon_months',15))
    alts.append(alternative('2330','台積電','equity_benchmark','ALPHA_ENGINE','upstream_scenario_valuation',None,hsec,'DERIVED'))
    for key,name,typ in [('TAIWAN_BROAD','台灣大盤替代資產（0050 proxy）','equity_benchmark'),('GLOBAL_EQUITY','全球股票替代資產（VT proxy）','equity_benchmark')]:
        f=facts.get(key,{});m=models.get(key,{});age=age_days(f.get('as_of'),now);maxage=int(m.get('max_fact_age_days',f.get('max_age_days',0) or 0))
        fresh=age is not None and age<=maxage;native=equity_er(f.get('pe'),m.get('sustainable_nominal_growth_pct',4.0)) if fresh else None
        h=int(m.get('native_horizon_months',contract.get('broad_equity_native_horizon_months',12)))
        alts.append(alternative(key,name,typ,'FIRST_PARTY_ISSUER+MODEL','earnings_yield_plus_sustainable_nominal_growth',native,h,'AVAILABLE' if native is not None else 'UNAVAILABLE',
            model_inputs={'pe':f.get('pe'),'sustainable_nominal_growth_pct':m.get('sustainable_nominal_growth_pct',4.0)},fact_as_of=f.get('as_of'),fact_age_days=age,source_url=f.get('source_url'),warning='Expected return is an Elephant model estimate, not issuer guidance.'))
    f=facts.get('CASH',{});m=models.get('CASH',{});age=age_days(f.get('as_of'),now);maxage=int(m.get('max_fact_age_days',f.get('max_age_days',0) or 0))
    native=f.get('rate_pct') if age is not None and age<=maxage else None;h=int(m.get('native_horizon_months',contract.get('cash_native_horizon_months',12)))
    alts.append(alternative('CASH','現金／短期無風險替代（CBC policy-rate proxy）','cash','CBC_FIRST_PARTY','policy_rate_proxy',native,h,'AVAILABLE' if isinstance(native,(int,float)) else 'UNAVAILABLE',
        fact_as_of=f.get('as_of'),fact_age_days=age,source_url=f.get('source_url'),warning='Policy rate is a conservative public proxy, not the user account deposit rate.'))
    h=int(models.get('DEBT_REPAYMENT',{}).get('native_horizon_months',contract.get('debt_native_horizon_months',12)))
    alts.append(alternative('DEBT_REPAYMENT','償還負債','debt_repayment','BROWSER_LOCAL_ONLY','user_effective_rate',None,h,'DERIVED_IF_CONFIGURED'))
    out={'version':3,'as_of':now.date().isoformat(),'comparison_contract':contract,'alternatives':alts,
         'frictions':{'round_trip_friction_pct':1.0,'note':'Conservative public default for risky assets. Browser-local planner can override actual costs/tax/FX.'},
         'public_available_count':sum(x.get('status') in ('AVAILABLE','DERIVED') for x in alts if x['id']!='DEBT_REPAYMENT'),
         'model_version':registry.get('model_version'),
         'guardrail':'All public alternatives expose a native horizon and an annualized comparison field; different native horizons are never compared directly.'}
    save_json('opportunity_inputs.json',out);return out

if __name__=='__main__':print(json.dumps(generate(),ensure_ascii=False,indent=2))
