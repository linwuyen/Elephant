#!/usr/bin/env python3
import source_opportunity,build_opportunity_models,build_security_fact_store,build_portfolio_model

a=source_opportunity.parse_0050('<div>ETF 特性 2026/04/30</div><span>本益比</span><b>30.39</b>')
assert a['pe']==30.39 and a['as_of']=='2026-04-30'
b=source_opportunity.parse_vt('<p>Characteristics as of 05/31/2026</p><div>P/E ratio <b>22.9x</b></div>')
assert b['pe']==22.9 and b['as_of']=='2026-05-31'
c=source_opportunity.parse_cbc('<p>The Board decided to keep the discount rate unchanged at 2%.</p>')
assert c['rate_pct']==2.0
assert round(build_opportunity_models.equity_er(25,4),2)==8.0
sf=build_security_fact_store.generate();assert any(x['ticker']=='2330' and x['stage']=='BENCHMARK' for x in sf['securities'])
pm=build_portfolio_model.generate();assert pm['alternative_loadings']['CASH']['TAIWAN_MARKET']==0
print('CAPITAL V3 TEST PASS')
