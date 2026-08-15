#!/usr/bin/env python3
import source_opportunity,source_security_facts,build_opportunity_models,build_security_fact_store,build_portfolio_model

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
sf=build_security_fact_store.generate();assert any(x['ticker']=='2330' and x['stage']=='BENCHMARK' for x in sf['securities'])
pm=build_portfolio_model.generate();assert pm['alternative_loadings']['CASH']['TAIWAN_MARKET']==0
print('CAPITAL V3 TEST PASS')
