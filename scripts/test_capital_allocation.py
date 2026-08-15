#!/usr/bin/env python3
import copy,capital_allocation,valuation_router

def stock(action='VERIFY'):
 return {'ticker':'9999','name':'Test AI Server','rank':1,'action':action,'score':85,'confidence_score':80,'reference_price':100,'thesis_status':'ACTIVE','thesis':'AI server growth','risk_model':{'downside_pct':30},'valuation_model':{'status':'COMPLETE','expected_return_pct':40,'scenarios':{'bear':{'fair_value':80,'probability':.25},'base':{'fair_value':140,'probability':.5},'bull':{'fair_value':180,'probability':.25}}}}
alpha={'benchmark_asset':{'valuation_model':{'expected_return_pct':30}},'stocks':[stock()]};inputs={'alternatives':[{'id':'2330','expected_return_pct':None}]};portfolio={'status':'UNCONFIGURED','positions':[]};policy={'constraints':{'max_single_stock_pct':25,'max_common_factor_pct':60},'lifecycle':{'exit_when_net_alpha_spread_below_pct':-5,'trim_when_net_alpha_spread_below_pct':2}}
opp=capital_allocation.opportunity(alpha,inputs,portfolio);blocked={'9999':{'constitution_status':'BLOCKED','capital_eligible':False}};passed={'9999':{'constitution_status':'PASS','capital_eligible':True}}
r=capital_allocation.lifecycle(alpha,opp,policy,portfolio,1.0,blocked);assert r[0]['portfolio_action']=='RESEARCH'
a2=copy.deepcopy(alpha);a2['stocks'][0]['action']='BUY CANDIDATE';r=capital_allocation.lifecycle(a2,opp,policy,portfolio,1.0,blocked);assert r[0]['portfolio_action']=='CONSTITUTION_BLOCK'
r=capital_allocation.lifecycle(a2,opp,policy,portfolio,1.0,passed);assert r[0]['portfolio_action']=='BUY_REVIEW' and r[0]['constitution_status']=='PASS'
d=capital_allocation.distribution(a2['stocks'][0],30);assert d['status']=='COMPLETE' and d['probability_beating_hurdle_pct']==75.0
q=capital_allocation.research_queue({'meta':{'status':'COMPLETE'},'deep_research_queue':[{'ticker':'2408','name':'南亞科','industry':'24'}]},{'stocks':[]});assert q['items'][0]['promotion_authority']=='NONE' and '24_36m_eps_or_fcf_path' in q['items'][0]['required_evidence']
assert valuation_router.classify({'ticker':'2408','name':'南亞科'})=='CYCLICAL_MEMORY'
print('CAPITAL ALLOCATION TEST PASS')
