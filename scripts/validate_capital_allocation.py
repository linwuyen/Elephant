#!/usr/bin/env python3
import json,math,sys
from pathlib import Path
DATA=Path(__file__).resolve().parents[1]/'data'
def load(n):
    p=DATA/n
    if not p.exists():raise SystemExit('CAPITAL VALIDATION ERROR missing '+n)
    return json.loads(p.read_text(encoding='utf-8'))
def finite(v):return isinstance(v,(int,float)) and math.isfinite(float(v))
def fail(x):print('CAPITAL VALIDATION ERROR:',x,file=sys.stderr);raise SystemExit(1)

policy=load('portfolio_policy.json');state=load('portfolio_state.json');inputs=load('opportunity_inputs.json');capital=load('capital_allocation.json');rq=load('deep_research_queue.json');opp=load('opportunity_set.json');bundle=load('alpha_engine.json');alpha=bundle.get('alpha',{});screen=bundle.get('screen',{});cres=load('investment_constitution_results.json');shadow=load('shadow_book.json');journal=load('capital_decision_journal.json')
if capital.get('version')!=3 or not capital.get('fingerprint'):fail('capital version/fingerprint')
g=capital.get('guardrails',{})
for k in ('portfolio_cannot_upgrade_upstream_action','constitution_required_for_new_capital','constitution_cannot_create_upstream_buy','mixed_horizon_returns_never_compared','expectation_engine_has_no_buy_authority','unavailable_benchmarks_not_fabricated','personalized_sizing_requires_complete_portfolio_state','survival_gate_required_before_sizing','no_automatic_trading'):
    if g.get(k) is not True:fail('guardrail '+k)
if policy.get('fail_closed') is not True:fail('policy must fail closed')
if state.get('status')!='UNCONFIGURED' or state.get('storage_policy')!='BROWSER_LOCAL_ONLY':fail('public portfolio state must remain browser-local sentinel')
for k in ('as_of','investable_assets_twd','cash_twd','debt_twd','debt_effective_rate_pct','human_capital_factor','monthly_required_cashflow_twd','minimum_liquidity_buffer_months','pledged_collateral_twd','broker_maintenance_threshold_pct'):
    if state.get(k) is not None:fail('personal portfolio field committed: '+k)
if state.get('positions') not in ([],None):fail('personal positions must not be committed')
if capital.get('target_sizing',{}).get('status')=='COMPLETE' or capital.get('portfolio_risk',{}).get('personalized') is True:fail('server emitted personalized portfolio output')
if opp.get('comparison_basis')!='ANNUALIZED_NOMINAL_PRE_TAX_AFTER_PUBLIC_FRICTION':fail('opportunity comparison basis')
for a in opp.get('alternatives',[]):
    if a.get('status')=='UNAVAILABLE' and a.get('expected_return_pct') is not None:fail('fabricated alternative '+str(a.get('id')))
    if a.get('status')=='AVAILABLE' and (not finite(a.get('annualized_expected_return_pct')) or not finite(a.get('native_horizon_months'))):fail('unstandardized alternative '+str(a.get('id')))
if opp.get('available_count',0)<1 or not finite(opp.get('hurdle_annualized_expected_return_pct')):fail('annualized hurdle missing')
deep={str(x.get('ticker')) for x in screen.get('deep_research_queue',[])}
for x in rq.get('items',[]):
    if str(x.get('ticker')) not in deep:fail('research provenance')
    if x.get('promotion_authority')!='NONE':fail('research promotion authority')
    if x.get('voi_priority') not in ('HIGH','MEDIUM') or not x.get('unknowns'):fail('research VoI contract')
up={str(x.get('ticker')):x.get('action') for x in alpha.get('stocks',[])};cm={str(x.get('ticker')):x for x in cres.get('securities',[])}
for x in capital.get('lifecycle',[]):
    t=str(x.get('ticker'));pa=x.get('portfolio_action');ua=x.get('upstream_action');cs=cm.get(t,{}).get('constitution_status','BLOCKED')
    if up.get(t)!=ua:fail('upstream action mismatch '+t)
    if x.get('constitution_status')!=cs:fail('constitution mismatch '+t)
    if pa in ('BUY_REVIEW','ADD_REVIEW') and not (ua=='BUY CANDIDATE' and cs=='PASS'):fail('portfolio bypassed upstream/constitution '+t)
    if finite(x.get('native_expected_return_pct')) and not finite(x.get('annualized_expected_return_pct')):fail('security return not standardized '+t)
exp=[x for x in capital.get('expectation_analysis',[]) if x.get('status')=='COMPLETE']
if not exp:fail('expectation analysis empty')
for x in exp:
    if x.get('authority')!='ANALYTIC_ONLY' or not finite(x.get('market_implied_eps')):fail('expectation authority/data')
for x in capital.get('probabilistic_returns',[]):
    d=x.get('distribution',{});p=d.get('probability_provenance',{})
    if p.get('empirical_override') not in (True,False):fail('probability provenance')
    if d.get('status')=='COMPLETE':
        ss=d.get('scenarios',[])
        if len(ss)!=3 or abs(sum(float(s.get('probability',0)) for s in ss)-1)>.02:fail('scenario distribution')
        for s in ss:
            if not finite(s.get('annualized_return_pct')):fail('scenario annualization')
        for k in ('probability_beating_hurdle_pct','probability_loss_gt_20_pct'):
            v=d.get(k)
            if v is not None and not 0<=float(v)<=100:fail(k)
if not finite(inputs.get('frictions',{}).get('round_trip_friction_pct')):fail('friction')
if shadow.get('contracts',{}).get('no_buy_authority') is not True or shadow.get('contracts',{}).get('one_primary_forecast_per_period_ticker') is not True:fail('shadow authority')
primary=journal.get('primary_by_period',{})
if len(set(primary.values()))!=len(primary):fail('journal primary pointer collision')
if journal.get('summary',{}).get('primary_snapshot_count')!=len(primary):fail('journal primary count')
print('CAPITAL ALLOCATION V3.2 VALIDATION PASS');print('research queue:',len(rq.get('items',[])));print('constitution pass:',cres.get('pass_count'));print('annualized hurdle:',opp.get('hurdle_asset'),opp.get('hurdle_annualized_expected_return_pct'));print('shadow forecasts:',shadow.get('summary',{}).get('primary_forecast_count'));print('decision periods:',len(primary))
