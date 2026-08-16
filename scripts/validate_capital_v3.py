#!/usr/bin/env python3
import json,math,sys
from pathlib import Path
DATA=Path(__file__).resolve().parents[1]/'data'
def load(n):
    p=DATA/n
    if not p.exists():raise SystemExit('CAPITAL V3 VALIDATION ERROR missing '+n)
    return json.loads(p.read_text(encoding='utf-8'))
def fail(x):print('CAPITAL V3 VALIDATION ERROR:',x,file=sys.stderr);raise SystemExit(1)
def finite(v):return isinstance(v,(int,float)) and math.isfinite(float(v))

reg=load('model_registry.json');oppin=load('opportunity_inputs.json');store=load('security_fact_store.json');pm=load('portfolio_model.json');cap=load('capital_allocation.json');gov=load('model_governance.json');cal=load('investment_calibration.json');state=load('portfolio_state.json');constitution=load('investment_constitution.json');cres=load('investment_constitution_results.json');research=load('constitution_research.json');shadow=load('shadow_book.json');journal=load('capital_decision_journal.json')
if reg.get('model_version')!='capital-v3.2.0':fail('model_version')
rc=reg.get('return_comparison',{})
if rc.get('comparison_basis')!='ANNUALIZED_NOMINAL_PRE_TAX_AFTER_PUBLIC_FRICTION' or not finite(rc.get('upstream_security_native_horizon_months')):fail('return comparison contract')
if reg.get('investment_constitution',{}).get('required_before_new_capital') is not True:fail('constitution registry authority')
public={x.get('id'):x for x in oppin.get('alternatives',[]) if x.get('id')!='DEBT_REPAYMENT'}
for k in ('2330','TAIWAN_BROAD','GLOBAL_EQUITY','CASH'):
    if k not in public:fail('missing public alternative '+k)
for k in ('TAIWAN_BROAD','GLOBAL_EQUITY','CASH'):
    if public[k].get('status')!='AVAILABLE' or not finite(public[k].get('expected_return_pct')) or not finite(public[k].get('native_horizon_months')):fail('public alternative unavailable/unstandardized '+k)
if state.get('status')!='UNCONFIGURED' or state.get('storage_policy')!='BROWSER_LOCAL_ONLY':fail('portfolio privacy sentinel')
if not store.get('fingerprint') or len(store.get('securities',[]))<7:fail('security fact store')
for s in store.get('securities',[]):
    if s.get('stage')=='DISCOVERY' and s.get('action')=='BUY_CANDIDATE':fail('discovery buy authority')
if pm.get('status')!='MODEL_ASSUMPTION' or len(pm.get('factors',[]))<8:fail('portfolio model')
if cap.get('version')!=3:fail('capital allocation version')
for k in ('no_automatic_trading','constitution_required_for_new_capital','constitution_cannot_create_upstream_buy','mixed_horizon_returns_never_compared','survival_gate_required_before_sizing'):
    if cap.get('guardrails',{}).get(k) is not True:fail('capital guardrail '+k)
if constitution.get('authority')!='FINAL_CAPITAL_ELIGIBILITY_GATE':fail('constitution authority')
required_gates={'earnings_power','fundamental_driven_return','catalyst','convexity','survival_downside','quarterly_falsifiability'}
if set(constitution.get('rules',{}))!=required_gates:fail('constitution rule set')
if research.get('version')!=2 or not {'2301','2376','2451'}<=set((research.get('securities') or {}).keys()):fail('three-stock constitution research seed')
for t in ('2301','2376','2451'):
    r=research['securities'][t]
    if r.get('long_horizon_earnings',{}).get('status')!='COMPLETE':fail('seed earnings '+t)
    if r.get('survival',{}).get('status')=='PASS' and not r.get('survival',{}).get('basis'):fail('unsupported survival pass '+t)
if cres.get('version')!=2:fail('constitution results version')
for r in cres.get('securities',[]):
    gates=r.get('gates',{})
    if set(gates)!=required_gates:fail('constitution gates '+str(r.get('ticker')))
    statuses={g.get('status') for g in gates.values()}
    if not statuses <= {'PASS','FAIL','BLOCKED'}:fail('constitution status domain')
    if r.get('constitution_status')=='PASS' and statuses!={'PASS'}:fail('false constitution pass '+str(r.get('ticker')))
    if r.get('capital_eligible') and not (r.get('constitution_status')=='PASS' and r.get('upstream_action')=='BUY_CANDIDATE'):fail('false capital eligibility '+str(r.get('ticker')))
cmap={str(r.get('ticker')):r for r in cres.get('securities',[])}
for r in cap.get('lifecycle',[]):
    t=str(r.get('ticker'));cs=cmap.get(t,{}).get('constitution_status','BLOCKED')
    if r.get('constitution_status')!=cs:fail('lifecycle constitution mismatch '+t)
    if r.get('portfolio_action') in ('BUY_REVIEW','ADD_REVIEW') and not (r.get('upstream_action')=='BUY CANDIDATE' and cs=='PASS'):fail('capital bypassed constitution '+t)
    if finite(r.get('native_expected_return_pct')) and not finite(r.get('annualized_expected_return_pct')):fail('annualized return missing '+t)
for r in cap.get('target_sizing',{}).get('targets',[]):
    if cmap.get(str(r.get('ticker')),{}).get('constitution_status')!='PASS':fail('sizing bypassed constitution '+str(r.get('ticker')))
if not any(x.get('status')=='COMPLETE' for x in cap.get('expectation_analysis',[])):fail('market-implied expectation missing')
for p in cap.get('probabilistic_returns',[]):
    prov=(p.get('distribution') or {}).get('probability_provenance') or {}
    if 'calibration_status' not in prov or prov.get('empirical_override') not in (True,False):fail('scenario probability provenance')
if shadow.get('version')!=2 or shadow.get('contracts',{}).get('no_buy_authority') is not True or shadow.get('contracts',{}).get('one_primary_forecast_per_period_ticker') is not True:fail('shadow book contract')
if shadow.get('summary',{}).get('primary_forecast_count',0)<len((load('alpha_engine.json').get('alpha') or {}).get('stocks',[])):fail('shadow researched coverage')
if journal.get('version')!=2 or journal.get('calibration_contract') is None:fail('capital journal contract')
primary=journal.get('primary_by_period',{})
if journal.get('summary',{}).get('primary_snapshot_count')!=len(primary):fail('capital journal primary cohort')
if gov.get('model_version')!=reg.get('model_version') or not gov.get('artifacts'):fail('model governance')
for r in cal.get('decisions',[]):
    for k in ('decision_fingerprint','model_version','code_commit','evidence_hash'):
        if r.get(k) in (None,''):fail('decision provenance '+k)
    if r.get('decision') in ('BUY_REVIEW','ADD_REVIEW') and r.get('model_version')=='capital-v3.2.0' and r.get('constitution_status')!='PASS':fail('v3.2 buy decision without constitution pass')
print('CAPITAL V3.2 VALIDATION PASS');print('constitution pass:',cres.get('pass_count'),'capital eligible:',cres.get('capital_eligible_count'));print('model version:',reg.get('model_version'));print('shadow forecasts:',shadow.get('summary',{}).get('primary_forecast_count'));print('journal periods:',len(primary))
