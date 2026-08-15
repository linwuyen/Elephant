#!/usr/bin/env python3
import source_opportunity,source_security_facts,build_opportunity_models,build_security_fact_store,build_portfolio_model,build_investment_constitution
from common import load_json

a=source_opportunity.parse_0050('<div>ETF 特性 2026/04/30</div><span>本益比</span><b>30.39</b>')
assert a['pe']==30.39 and a['as_of']=='2026-04-30'
b=source_opportunity.parse_vt('<p>Characteristics as of 05/31/2026</p><div>P/E ratio <b>22.9x</b></div>')
assert b['pe']==22.9 and b['as_of']=='2026-05-31'
c=source_opportunity.parse_cbc('<p>The Board decided to keep the discount rate unchanged at 2%.</p>')
assert c['rate_pct']==2.0
assert round(build_opportunity_models.equity_er(25,4),2)==8.0
routes={(kind,market):url for kind,market,url in source_security_facts.SOURCES}
assert routes[('monthly_revenue','TWSE')].endswith('t187ap05_L')
assert routes[('income_statement','TWSE')].endswith('t187ap06_L_ci')
assert routes[('balance_sheet','TWSE')].endswith('t187ap07_L_ci')
assert routes[('monthly_revenue','TPEX')].endswith('mopsfin_t187ap05_O')
assert routes[('income_statement','TPEX')].endswith('mopsfin_t187ap06_O_ci')
assert routes[('balance_sheet','TPEX')].endswith('mopsfin_t187ap07_O_ci')
assert source_security_facts.TPEX_CSV_FALLBACK['income_statement'].endswith('t187ap06_O_ci.csv')
assert source_security_facts.TPEX_CSV_FALLBACK['balance_sheet'].endswith('t187ap07_O_ci.csv')
assert all('_P' not in u and '_X' not in u for u in routes.values())
assert source_security_facts.code({'\ufeff 公司代號 ':'3081'})=='3081'
q=source_security_facts.compact('income_statement',{' 公司代號 ':'3081','年度':'115','季別':'2','基本每股盈餘（元）':'12.34','營業收入':'1000'},'TPEX')
assert q['eps']==12.34 and q['revenue']==1000 and q['period']=='2026-Q2'
bal=source_security_facts.compact('balance_sheet',{'公司代號':'3081','年度':'115','季別':'2','資產總計':'2000','負債總計':'800','權益總計':'1200'},'TPEX')
assert bal['assets']==2000 and bal['liabilities']==800 and bal['equity']==1200
comp=build_security_fact_store.completeness({'income_statement':{'eps':1},'monthly_revenue':{'revenue_month':1},'balance_sheet':{'assets':1}},{'metrics':[]})
assert 'earnings_basis' in comp['available'] and 'revenue_trend' in comp['available']
assert 'balance_sheet_cash_flow' in comp['missing'] and comp['cash_flow_status']=='MISSING_DEDICATED_CASH_FLOW_EVIDENCE'
comp2=build_security_fact_store.completeness({'balance_sheet':{'assets':1}},{'metrics':['balance_sheet_cash_flow']})
assert 'balance_sheet_cash_flow' in comp2['available'] and comp2['cash_flow_status']=='VERIFIED'
sf=build_security_fact_store.generate();assert any(x['ticker']=='2330' and x['stage']=='BENCHMARK' for x in sf['securities'])
pm=build_portfolio_model.generate();assert pm['alternative_loadings']['CASH']['TAIWAN_MARKET']==0
constitution=load_json('investment_constitution.json',{})
stock={'ticker':'9999','name':'Test','action':'BUY CANDIDATE','reference_price':100}
research={'long_horizon_earnings':{'status':'COMPLETE','metric':'EPS','baseline_period':'2026','baseline_value':10,'target_period':'2029','target_value':20,'target_multiple':2.0,'horizon_months':36,'evidence_and_assumptions':['test']},'long_horizon_valuation':{'status':'COMPLETE','model_type':'PE','current_multiple':10,'bull_multiple':13,'bear_fair_value':65,'evidence_and_assumptions':['test']},'catalysts':[{'name':'capacity','mechanism':'volume','kpi':'utilization','expected_window':'2027','source_quality':'FIRST_PARTY','source_url':'https://example.com'}],'survival':{'status':'PASS','basis':['net cash'],'existential_risk':'NONE'},'quarterly_checks':[{'metric':'revenue','expected':'grow','fail_condition':'yoy<10%','source':'filing'},{'metric':'margin','expected':'>20%','fail_condition':'<15%','source':'filing'},{'metric':'eps','expected':'grow','fail_condition':'decline','source':'filing'}]}
r=build_investment_constitution.evaluate(stock,research,constitution);assert r['constitution_status']=='PASS' and r['capital_eligible'] is True and r['bull_price_multiple']==2.6 and r['bear_return_pct']==-35.0
r2=build_investment_constitution.evaluate(stock,{},constitution);assert r2['constitution_status']=='BLOCKED' and r2['capital_eligible'] is False
print('CAPITAL V3.1 TEST PASS')
