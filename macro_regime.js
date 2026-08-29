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
  async function loadJson(path){const r=await fetch(`${path}?x=${Date.now()}`,{cache:'no-store'});if(!r.ok)throw new Error(`${path} ${r.status}`);return r.json()}
  function compute(macro,summary){
    const ms=macro?.series||{};
    const gdp=ms['dgbas.gdp.growth_rate']||newestContaining(ms,/gdp.*growth|經濟成長率/i);
    const cpi=ms['dgbas.cpi.yoy']||newestContaining(ms,/cpi.*yoy|消費者物價.*年增/i);
    const core=newestContaining(ms,/core.*cpi|核心.*物價|不含.*蔬果.*能源/i);
    const ppi=newestContaining(ms,/ppi|生產者物價/i);
    const m2=newestContaining(ms,/\bm2\b|貨幣總計數.*m2/i);
    const rate=newestContaining(ms,/重貼現率|policy.*rate|央行.*利率/i);
    const [,gdpV]=latest(gdp),[,cpiV]=latest(cpi),[,coreV]=latest(core),[,ppiV]=latest(ppi),[,m2V]=latest(m2),[,rateV]=latest(rate);
    const gdpM=momentum(gdp),cpiM=momentum(cpi),coreM=momentum(core),ppiM=momentum(ppi);
    const growthScore=Math.round(.7*scoreLinear(gdpV,1,8)+.3*scoreLinear(gdpM,-2,2));
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
    const earningsScore=Math.round(summary?.cycle?.score!=null?clamp(50+Number(summary.cycle.score)*.5,0,100):50);
    let persistence='待確認';
    if(coreV!=null){if(Number(coreV)>=2&&(coreM==null||coreM>=-.15))persistence='核心通膨黏性升高';else if(Number(coreV)<2&&(cpiM==null||cpiM<0))persistence='較像短期成本衝擊'}
    else if(cpiV!=null&&ppiV!=null)persistence=Number(cpiV)>=2&&Number(ppiV)>=8?'成本衝擊正向消費端傳導':'證據不足';
    const hike=Math.round(clamp(.5*inflationScore+.3*growthScore+.2*liquidityScore,0,100));
    const regime=growthScore>=65&&inflationScore>=60?'高成長／高通膨壓力':growthScore>=65?'高成長／溫和通膨':inflationScore>=60?'低成長／通膨壓力':'溫和區間';
    return {regime,persistence,hike,scores:{growth:growthScore,inflation:inflationScore,liquidity:liquidityScore,rates:ratesScore,earnings:earningsScore},evidence:[['GDP 成長',gdpV==null?'—':signed(gdpV),gdpM==null?'無前期比較':`動能 ${gdpM>=0?'+':''}${gdpM.toFixed(2)} ppt`],['Headline CPI',cpiV==null?'—':pct(cpiV),cpiM==null?'無前期比較':`Δ ${cpiM>=0?'+':''}${cpiM.toFixed(2)} ppt`],['核心 CPI',coreV==null?'資料未接入':pct(coreV),coreV==null?'待 pipeline 補官方序列':(coreM==null?'無前期比較':`Δ ${coreM>=0?'+':''}${coreM.toFixed(2)} ppt`)],['PPI',ppiV==null?'資料未接入':pct(ppiV),ppiV==null?'待 pipeline 補官方序列':(ppiM==null?'無前期比較':`Δ ${ppiM>=0?'+':''}${ppiM.toFixed(2)} ppt`)],['M2',m2V==null?'資料未接入':pct(m2V),m2V==null?'待 pipeline 補官方序列':'流動性代理'],['政策利率',rateV==null?'資料未接入':pct(rateV),rateV==null?'待 pipeline 補央行序列':'利率條件']]};
  }
  function card(name,score,desc){return `<article class="regime-card ${tone(score)}"><div><span>${esc(name)}</span><b>${score}</b></div><strong>${status(score)}</strong><p>${esc(desc)}</p><div class="regime-bar"><i style="width:${score}%"></i></div></article>`}
  function render(r){const root=$('#macroRegimeRoot');if(!root)return;const d={growth:'實質成長與成長動能；高分代表景氣熱度明顯。',inflation:'Headline／核心／PPI 與動能；高分代表通膨持續性風險。',liquidity:'M2 等流動性代理；高分代表金融條件仍偏寬鬆。',rates:'綜合通膨、成長與政策利率的升息壓力。',earnings:'沿用 Elephant Cycle Score 作為盈利／景氣代理，不改既有模型。'};root.innerHTML=`<div class="regime-hero"><div><span class="kicker">MACRO REGIME DETECTOR</span><h2>${esc(r.regime)}</h2><p>${esc(r.persistence)}</p></div><div class="hike-gauge"><span>升息壓力指標</span><b>${r.hike}</b><small>/100 · 非政策機率預測</small></div></div><div class="regime-grid">${card('Growth',r.scores.growth,d.growth)}${card('Inflation',r.scores.inflation,d.inflation)}${card('Liquidity',r.scores.liquidity,d.liquidity)}${card('Rates',r.scores.rates,d.rates)}${card('Earnings',r.scores.earnings,d.earnings)}</div><article class="panel regime-evidence"><div class="panel-head"><div><span class="kicker">EVIDENCE</span><h2>目前燈號依據</h2></div><span class="tag">deterministic / transparent</span></div><div class="table-wrap"><table><thead><tr><th>指標</th><th>最新值</th><th>解讀</th></tr></thead><tbody>${r.evidence.map(x=>`<tr><td>${esc(x[0])}</td><td>${esc(x[1])}</td><td>${esc(x[2])}</td></tr>`).join('')}</tbody></table></div></article><article class="notice"><strong>判讀邊界</strong><p>這個檢測器不預測央行一定升息，也不直接產生交易指令。若核心 CPI、PPI、M2 或政策利率尚未進入 Elephant 官方資料庫，介面會顯示「資料未接入」，不使用估值補洞。</p></article>`}
  async function init(){const root=$('#macroRegimeRoot');if(!root)return;try{const [macro,summary]=await Promise.all([loadJson('data/macro.json'),loadJson('data/summary.json').catch(()=>null)]);render(compute(macro,summary))}catch(e){root.innerHTML=`<article class="notice"><strong>Macro Regime 載入失敗</strong><p>${esc(e.message)}</p></article>`}}
  init();
})();
