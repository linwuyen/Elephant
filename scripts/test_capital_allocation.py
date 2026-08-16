#!/usr/bin/env python3
import copy,capital_allocation,valuation_router

def stock(action='VERIFY'):
    return {'ticker':'9999','name':'Test AI Server','rank':1,'action':action,'score':85,'confidence_score':80,'reference_price':100,'thesis_status':'ACTIVE','thesis':'AI server growth','risk_model':{'downside_pct':30},'valuation_model':{'status':'COMPLETE','expected_return_pct':40,'normalized_eps':10,'scenarios':{'bear':{'eps':8,'multiple':10,'fair_value':80,'probability':.25},'base':{'eps':14,'multiple':10,'fair_value':140,'probability':.5},'bull':{'eps':18,'multiple':10,'fair_value':180,'probability':.25}}}}
registry={'return_comparison':{'comparison_basis':'ANNUALIZED_NOMINAL_PRE_TAX_AFTER_PUBLIC_FRICTION','upstream_security_native_horizon_months':15}}
alpha={'benchmark_asset':{'valuation_model':{'expected_return_pct':30}},'stocks':[stock()]};inputs={'alternatives':[{'id':'2330','expected_return_pct':None,'native_horizon_months':15}],'frictions':{'round_trip_friction_pct':1.0}};portfolio={'status':'UNCONFIGURED','positions':[]};policy={'constraints':{'max_single_stock_pct':25,'max_common_factor_pct':60},'lifecycle':{'exit_when_net_alpha_spread_below_pct':-5,'trim_when_net_alpha_spread_below_pct':2}};scenario_cal={'minimum_samples':30,'resolved_samples':0,'securities':[]}
opp=capital_allocation.opportunity(alpha,inputs,portfolio,registry);assert opp['comparison_basis']=='ANNUALIZED_NOMINAL_PRE_TAX_AFTER_PUBLIC_FRICTION' and opp['hurdle_annualized_expected_return_pct'] is not None
blocked={'9999':{'constitution_status':'BLOCKED','capital_eligible':False}};passed={'9999':{'constitution_status':'PASS','capital_eligible':True}}
r=capital_allocation.lifecycle(alpha,opp,policy,portfolio,registry,1.0,blocked);assert r[0]['portfolio_action']=='RESEARCH'
a2=copy.deepcopy(alpha);a2['stocks'][0]['action']='BUY CANDIDATE';r=capital_allocation.lifecycle(a2,opp,policy,portfolio,registry,1.0,blocked);assert r[0]['portfolio_action']=='CONSTITUTION_BLOCK'
r=capital_allocation.lifecycle(a2,opp,policy,portfolio,registry,1.0,passed);assert r[0]['portfolio_action']=='BUY_REVIEW' and r[0]['constitution_status']=='PASS'
d=capital_allocation.distribution(a2['stocks'][0],opp['hurdle_annualized_expected_return_pct'],registry,1.0,scenario_cal);assert d['status']=='COMPLETE' and d['probability_provenance']['empirical_override'] is False
q=capital_allocation.research_queue({'meta':{'status':'COMPLETE'},'deep_research_queue':[{'ticker':'2408','name':'南亞科','industry':'24','rank':1,'flags':['CYCLE_EXTREME_GROWTH_LOW_PE']}]},{'stocks':[]});assert q['items'][0]['promotion_authority']=='NONE' and q['items'][0]['voi_priority']=='HIGH' and q['items'][0]['unknowns']
assert valuation_router.classify({'ticker':'2408','name':'南亞科'})=='CYCLICAL_MEMORY'
e=capital_allocation.expectation(a2['stocks'][0]);assert e['status']=='COMPLETE' and e['market_implied_eps']==10.0 and e['base_eps_expectation_gap_pct']==40.0
print('CAPITAL ALLOCATION V3.2 TEST PASS')
