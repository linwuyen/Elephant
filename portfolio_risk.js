(()=>{
  function n(v,d=0){const x=Number(v);return Number.isFinite(x)?x:d}
  function holdings(text){return String(text||'').split(/\n+/).map(x=>x.trim()).filter(Boolean).map(line=>{const [ticker,value]=line.split(/[,\s]+/);return{ticker:String(ticker||'').trim(),value:n(value,NaN)}}).filter(x=>x.ticker&&Number.isFinite(x.value)&&x.value>=0)}
  function state(){try{return window.ElephantPortfolioState?.load?.()||{}}catch{return {}}}
  function snapshot(raw=state()){
    const rows=holdings(raw.holdings);const equity=rows.length?rows.reduce((a,x)=>a+x.value,0):n(raw.equity);const cash=n(raw.cash);const debt=n(raw.debt);const total=n(raw.total,equity+cash);const largest=rows.length?Math.max(...rows.map(x=>x.value)):n(raw.largest);
    const sorted=[...rows].sort((a,b)=>b.value-a.value);const top3=sorted.slice(0,3).reduce((a,x)=>a+x.value,0);
    return{schema_version:1,total,equity,cash,debt,net_assets:total-debt,largest,holding_count:rows.length,largest_weight_pct:equity>0?largest/equity*100:null,top3_weight_pct:equity>0?top3/equity*100:null,rows};
  }
  function scenario(base,id,label,equityShock){
    const equity=Math.max(0,base.equity*(1+equityShock));const assets=equity+base.cash;const net=assets-base.debt;return{id,label,equity_shock_pct:equityShock*100,post_equity:equity,post_assets:assets,post_net_assets:net,post_debt_to_assets_pct:assets>0?base.debt/assets*100:null,estimated_asset_drawdown_pct:base.total>0?(assets/base.total-1)*100:null};
  }
  function analyze(raw=state()){
    const b=snapshot(raw);const largestShare=b.equity>0?b.largest/b.equity:0;const top3Share=b.equity>0?(b.top3_weight_pct||0)/100:0;
    const scenarios=[scenario(b,'BROAD_EQUITY_MINUS_25','所有股票 -25%',-.25),scenario(b,'LARGEST_NAME_MINUS_30','最大單一持股 -30%',-.30*largestShare),scenario(b,'TOP3_MINUS_20','前三大持股 -20%',-.20*top3Share)];
    const liquidityNeed=n(raw.liquidityNeed??raw.liquidity_need);if(liquidityNeed>0)scenarios.push({...scenario(b,'LIQUIDITY_NEED','立即支付流動性需求',0),cash_outflow:liquidityNeed,post_cash:Math.max(0,b.cash-liquidityNeed),liquidity_shortfall:Math.max(0,liquidityNeed-b.cash)});
    return{version:1,contract:'browser-local-portfolio-stress-v1',authority:false,private_state_persisted_server_side:false,base:b,concentration:{largest_weight_pct:b.largest_weight_pct,top3_weight_pct:b.top3_weight_pct},factor_exposure:{status:'UNAVAILABLE_WITHOUT_VERIFIED_PUBLIC_FACTOR_MAP',note:'Ticker→AI/sector/FX factor labels are not inferred from names or private holdings.'},scenarios,guardrail:'Stress output is sensitivity analysis. It cannot create security BUY authority, place trades, or write private portfolio data to GitHub.'};
  }
  window.ElephantPortfolioRisk={snapshot,analyze};
})();
