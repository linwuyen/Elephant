(()=>{
  const $=s=>document.querySelector(s);
  const clamp=(v,min,max)=>Math.max(min,Math.min(max,v));
  const latest=s=>s?.data?.length?s.data[s.data.length-1]:[null,null];
  const prev=s=>s?.data?.length>1?s.data[s.data.length-2]:[null,null];
  const pct=(v,d=2)=>v==null?'—':`${Number(v).toFixed(d)}%`;
  const signed=(v,d=2)=>v==null?'—':`${Number(v)>=0?'+':''}${Number(v).toFixed(d)}%`;
  const tone=score=>score>=70?'red':score>=45?'amber':'green';
  const status=score=>score>=70?'高警戒':score>=45?'注意':'正常';
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function newestContaining(series,re){return Object.entries(series||{}).filter(([id,s])=>re.test(`${id} ${s?.name||''}`)).sort((a,b)=>String(latest(a[1])[0]).localeCompare(String(latest(b[1])[0]))).at(-1)?.[1]||null}
  function scoreLinear(v,lo,hi){if(v==null||!Number.isFinite(Number(v)))return 50;return clamp((Number(v)-lo)/(hi-lo)*100,0,100)}
  function momentum(s){const [,a]=latest(s),[,b]=prev(s);if(a==null||b==null)return null;return Number(a)-Number(b)}
  function yoy(s){
    const [p,v]=latest(s); if(p==null||v==null)return null;
    const target=String(p).replace(/^(\d{4})/,y=>String(Number(y)-1));
    const prior=(s?.data||[]).find(([period])=>String(period)===target)?.[1];
    return prior==null||Number(prior)===0?null:(Number(v)/Number(prior)-1)*100;
  }
  async function loadJson(path){const r=await fetch(`${path}?x=${Date.now()}`,{cache:'no-store'});if(!r.ok)throw new Error(`${path} ${r.status}`);return r.json()}
  function compute(macro,official,summary,industry){
    const ms={...(macro?.series||{}),...(official?.series||{})};
    const gdp=ms['dgbas.gdp.growth_rate']||newestContaining(ms,/gdp.*growth|經濟成長率/i);
    const cpi=ms['dgbas.cpi.monthly_yoy']||ms['dgbas.cpi.yoy']||newestContaining(ms,/cpi.*yoy|消費者物價.*年增/i);
    const core=ms['dgbas.cpi.core_yoy']||newestContaining(ms,/core.*cpi|核心.*物價|不含.*蔬果.*能源/i);
    const ppi=ms['dgbas.ppi.yoy']||newestContaining(ms,/ppi|生產者物價/i);
    const m2=ms['cbc.m2.yoy']||newestContaining(ms,/\bm2\b|貨幣總計數.*m2/i);
    const rate=ms['cbc.discount_rate']||newestContaining(ms,/重貼現率|policy.*rate|央行.*利率/i);
    const [,gdpV]=latest(gdp),[,cpiV]=latest(cpi),[,coreV]=latest(core),[,ppiV]=latest(ppi),[,m2V]=latest(m2),[,rateV]=latest(rate);
    const gdpM=momentum(gdp),cpiM=momentum(cpi),coreM=momentum(core),ppiM=momentum(ppi);
    const cycle=summary?.cycle?.score;
    const growthLevel=.7*scoreLinear(gdpV,1,8)+.3*scoreLinear(gdpM,-2,2);
    const growthScore=Math.round(cycle==null?growthLevel:.7*growthLevel+.3*clamp(50+Number(cycle)*.5,0,100));
    const parts=[];
    if(cpiV!=null)parts.push([.35,scoreLinear(cpiV,1.2,3.2)]);
    if(coreV!=null)parts.push([.30,scoreLinear(coreV,1.2,3.0)]);
    if(ppiV!=null)parts.push([.15,scoreLinear(ppiV,0,12)]);
    if(cpiM!=null)parts.push([.10,scoreLinear(cpiM,-.4,.5)]);
    if(coreM!=null)parts.push([.10,scoreLinear(coreM,-.3,.4)]);
    const den=parts.reduce((a,[w])=>a+w,0)||1;
    const inflationScore=Math.round(parts.reduce((a,[w,s])=>a+w*s,0)/den);
    const liquidityScore=Math.round(m2V==null?50:scoreLinear(m2V,3,8));
    const ratesScore=Math.round(rateV==null?.65*inflationScore+.35*growthScore:.6*inflationScore+.25*growthScore+.15*scoreLinear(-rateV,-3,-1));

    const ids=industry?.datasets||{};
    const sales=ids['moea.manufacturing.sales_index_current']?.series?.C||ids['moea.manufacturing.sales_volume']?.series?.C||null;
    const opRevenue=ids['moea.manufacturing.investment']?.series?.['moea.manufacturing.operating_revenue']||null;
    const production=ids['moea.industry.production']?.series?.C||null;
    const salesYoy=yoy(sales), revenueYoy=yoy(opRevenue), productionYoy=yoy(production);
    const earnParts=[];
    if(salesYoy!=null)earnParts.push([.50,scoreLinear(salesYoy,-5,20)]);
    if(revenueYoy!=null)earnParts.push([.30,scoreLinear(revenueYoy,-5,20)]);
    if(productionYoy!=null)earnParts.push([.20,scoreLinear(productionYoy,-5,20)]);
    const earnDen=earnParts.reduce((a,[w])=>a+w,0);
    const earningsScore=Math.round(earnDen?earnParts.reduce((a,[w,s])=>a+w*s,0)/earnDen:50);

    let persistence='待確認';
    if(coreV!=null){if(Number(coreV)>=2&&(coreM==null||coreM>=-.15))persistence='核心通膨黏性升高';else if(Number(coreV)<2&&(cpiM==null||cpiM<0))persistence='較像短期成本衝擊';else persistence='核心通膨仍在轉折確認區'}
    else if(cpiV!=null&&ppiV!=null)persistence=Number(cpiV)>=2&&Number(ppiV)>=8?'成本衝擊正向消費端傳導':'證據不足';
    const hike=Math.round(clamp(.5*inflationScore+.3*growthScore+.2*liquidityScore,0,100));
    const regime=growthScore>=65&&inflationScore>=60?'高成長／高通膨壓力':growthScore>=65?'高成長／溫和通膨':inflationScore>=60?'低成長／通膨壓力':'溫和區間';
    const sourceState=official?.series&&Object.keys(official.series).length?'官方月頻已接入':'官方月頻尚未產生；使用既有資料降級運作';
    return {regime,persistence,hike,sourceState,scores:{growth:growthScore,inflation:inflationScore,liquidity:liquidityScore,rates:ratesScore,earnings:earningsScore},evidence:[['GDP 成長',gdpV==null?'—':signed(gdpV),gdpM==null?'年度序列；無前期比較':`年度動能 ${gdpM>=0?'+':''}${gdpM.toFixed(2)} ppt`],['Headline CPI',cpiV==null?'資料未接入':pct(cpiV),cpiV==null?'待官方月頻資料':'主計總處月頻'],['核心 CPI',coreV==null?'資料未接入':pct(coreV),coreV==null?'待官方月頻資料':(coreM==null?'主計總處月頻':`Δ ${coreM>=0?'+':''}${coreM.toFixed(2)} ppt`)],['PPI',ppiV==null?'資料未接入':pct(ppiV),ppiV==null?'待官方月頻資料':(ppiM==null?'主計總處月頻':`Δ ${ppiM>=0?'+':''}${ppiM.toFixed(2)} ppt`)],['M2',m2V==null?'資料未接入':pct(m2V),m2V==null?'待央行序列':'央行月頻流動性代理'],['政策利率',rateV==null?'資料未接入':pct(rateV),rateV==null?'待央行序列':'央行重貼現率'],['製造業銷售 YoY',salesYoy==null?'資料未接入':signed(salesYoy),salesYoy==null?'MOEA series unavailable':'Earnings 50% 權重'],['製造業營業額 YoY',revenueYoy==null?'資料未接入':signed(revenueYoy),revenueYoy==null?'MOEA quarterly series unavailable':'Earnings 30% 權重'],['製造業生產 YoY',productionYoy==null?'資料未接入':signed(productionYoy),productionYoy==null?'MOEA production unavailable':'Earnings 20% 權重']]};
  }
  function card(name,score,desc){return `<article class="regime-card ${tone(score)}"><div><span>${esc(name)}</span><b>${score}</b></div><strong>${status(score)}</strong><p>${esc(desc)}</p><div class="regime-bar"><i style="width:${score}%"></i></div></article>`}
  function render(r){const root=$('#macroRegimeRoot');if(!root)return;const d={growth:'GDP 成長結合 Elephant Cycle Score；高分代表景氣熱度明顯。',inflation:'月頻 Headline／核心 CPI、PPI 與動能；高分代表持續性通膨風險。',liquidity:'央行 M2 年增率；高分代表流動性仍偏寬鬆。',rates:'綜合通膨、成長與重貼現率的升息壓力。',earnings:'獨立使用 MOEA 製造業銷售、營業額與生產年增率；不再使用 Cycle Score。'};root.innerHTML=`<div class="regime-hero"><div><span class="kicker">MACRO REGIME DETECTOR</span><h2>${esc(r.regime)}</h2><p>${esc(r.persistence)} · ${esc(r.sourceState)}</p></div><div class="hike-gauge"><span>升息壓力指標</span><b>${r.hike}</b><small>/100 · 非政策機率預測</small></div></div><div class="regime-grid">${card('Growth',r.scores.growth,d.growth)}${card('Inflation',r.scores.inflation,d.inflation)}${card('Liquidity',r.scores.liquidity,d.liquidity)}${card('Rates',r.scores.rates,d.rates)}${card('Earnings',r.scores.earnings,d.earnings)}</div><article class="panel regime-evidence"><div class="panel-head"><div><span class="kicker">EVIDENCE</span><h2>目前燈號依據</h2></div><span class="tag">deterministic / transparent</span></div><div class="table-wrap"><table><thead><tr><th>指標</th><th>最新值</th><th>解讀</th></tr></thead><tbody>${r.evidence.map(x=>`<tr><td>${esc(x[0])}</td><td>${esc(x[1])}</td><td>${esc(x[2])}</td></tr>`).join('')}</tbody></table></div></article><article class="notice"><strong>判讀邊界</strong><p>五燈是 regime detector，不是交易指令；升息壓力 0–100 也不是央行決策機率。缺資料時 fail closed 顯示未接入，不以估值補洞。Earnings 是以官方製造業營運動能衡量的總體盈利代理，不宣稱等同上市櫃 EPS revision breadth。</p></article>`}
  async function init(){const root=$('#macroRegimeRoot');if(!root)return;try{const [macro,official,summary,industry]=await Promise.all([loadJson('data/macro.json'),loadJson('data/regime_official.json').catch(()=>({series:{}})),loadJson('data/summary.json').catch(()=>null),loadJson('data/industry.json').catch(()=>({datasets:{}}))]);render(compute(macro,official,summary,industry))}catch(e){root.innerHTML=`<article class="notice"><strong>Macro Regime 載入失敗</strong><p>${esc(e.message)}</p></article>`}}
  init();
})();
