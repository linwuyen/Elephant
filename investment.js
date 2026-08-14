(()=>{
const q=s=>document.querySelector(s);
const esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=v=>v==null?'—':`${Number(v)>=0?'+':''}${Number(v).toFixed(1)}%`;
const num=v=>v==null?'—':Number(v).toLocaleString('zh-TW',{maximumFractionDigits:2});
const cls=v=>v==null?'alpha-neutral':Number(v)>0?'alpha-positive':Number(v)<0?'alpha-negative':'alpha-neutral';
const actionClass=v=>String(v||'').toLowerCase().replaceAll(' ','-');
const contextName={BROADLY_SUPPORTIVE:'廣泛支持',EXPORT_LED_SUPPORTIVE:'出口／科技支持',CONSTRUCTIVE:'偏正向',MIXED:'混合',DEFENSIVE:'防禦',UNKNOWN:'資料不足'};

function ensureShell(){
 if(!q('link[href="investment.css"]')){const link=document.createElement('link');link.rel='stylesheet';link.href='investment.css';document.head.appendChild(link)}
 const tabs=q('.tabs');
 if(tabs&&!q('[data-tab="investment"]')){const b=document.createElement('button');b.dataset.tab='investment';b.textContent='投資／Alpha';const health=q('[data-tab="health"]');tabs.insertBefore(b,health||null)}
 if(!q('#investment')){
  const section=document.createElement('section');section.id='investment';section.className='tab';section.innerHTML=`
    <div class="investment-hero">
      <article class="panel"><div class="panel-head"><div><span class="kicker">MACRO × ALPHA</span><h2>Investment Context</h2><p class="sub">Elephant 只提供總經背景；Alpha Score / Buy Gate 仍完全由個股引擎決定。</p></div><span id="investmentStatus" class="investment-status">—</span></div><h3 id="investmentContextLabel">—</h3><p id="investmentContextText" class="sub">載入投資決策層…</p><div id="investmentMetrics" class="investment-context"></div></article>
      <article class="panel"><div class="panel-head"><div><span class="kicker">BENCHMARK</span><h2>TSMC Opportunity Cost</h2></div></div><div id="investmentBenchmark">—</div><div class="investment-rule"><strong>核心規則</strong><p>TSMC 3000 只觸發重新評估。候選股必須在預期報酬、估值、安全邊際、證據與 freshness 上真正勝過 benchmark，才可能升級。</p></div></article>
    </div>
    <article class="panel"><div class="panel-head controls-head"><div><span class="kicker">ALPHA ENGINE</span><h2>已研究個股與 Buy Gate</h2><p id="investmentSelectionText" class="sub">載入 Alpha research…</p></div><div class="alpha-upstream"><span id="investmentFreshness" class="alpha-sub"></span><a class="secondary" href="https://github.com/linwuyen/stock" target="_blank" rel="noopener">Upstream Engine</a></div></div><div class="table-wrap"><table class="alpha-table"><thead><tr><th>#</th><th>個股</th><th>Alpha</th><th>Confidence</th><th>Action</th><th>參考價</th><th>預期報酬</th><th>vs TSMC</th><th>MOS / Next</th></tr></thead><tbody id="alphaRankingRows"></tbody></table></div></article>
    <article class="panel"><div class="panel-head"><div><span class="kicker">FULL MARKET SCREEN</span><h2>全市場 Top 10 Discovery</h2><p class="sub">Screen 只能產生研究候選，永遠不能直接產生 BUY。</p></div></div><div class="table-wrap"><table><thead><tr><th>#</th><th>公司</th><th>市場</th><th>價格</th><th>營收 YoY</th><th>TTM PE</th><th>Priority</th><th>研究狀態</th></tr></thead><tbody id="alphaScreenRows"></tbody></table></div></article>
    <article class="panel"><div class="panel-head"><div><span class="kicker">DEEP RESEARCH</span><h2>下一輪研究佇列</h2></div></div><div id="deepResearchGrid" class="deep-grid"></div></article>
    <article class="panel"><div class="panel-head"><div><span class="kicker">CLOSED LOOP</span><h2>Alpha Calibration</h2></div></div><div id="alphaCalibration">—</div></article>
    <article class="notice"><strong>架構邊界</strong><p>Macro context ≠ Alpha。Elephant 不會因景氣強就替任何股票加 Alpha 分，也不會因景氣弱就自動取消 upstream BUY。這一層只把「總經 regime」與「個股 mispricing」放在同一個決策畫面中。</p></article>`;
  const health=q('#health');(health?.parentNode||q('main')).insertBefore(section,health||null)
 }
}

function metric(label,x){return `<div class="investment-metric"><div class="label">${esc(label)}</div><div class="value">${x?.score==null?'—':Number(x.score).toFixed(0)}</div><div class="period">${esc(x?.label||'—')} · ${esc(x?.period||'—')}</div></div>`}

function render(data){
 const status=q('#investmentStatus'); if(status){status.textContent=data.status;status.className=`investment-status ${String(data.status||'').toLowerCase()}`}
 const macro=data.macro_context||{};
 q('#investmentContextLabel').textContent=contextName[macro.label]||macro.label||'—';
 q('#investmentContextText').textContent=macro.text||'—';
 q('#investmentMetrics').innerHTML=[['Cycle',macro.cycle],['Growth Persistence',macro.growth_persistence],['Domestic Demand',macro.domestic_demand],['Financial Conditions',macro.financial_conditions]].map(([a,b])=>metric(a,b)).join('');

 const b=data.benchmark||{};
 q('#investmentBenchmark').innerHTML=`<div class="value">${esc(b.ticker)} ${esc(b.name)}</div><div class="alpha-sub">參考價 ${num(b.reference_price)} · ${esc(b.reference_price_date)}<br>模型預期報酬 <b class="${cls(b.expected_return_pct)}">${pct(b.expected_return_pct)}</b> · Confidence ${num(b.confidence_score)}<br>TSMC 3000 僅是重新評估事件，不是自動賣出訊號。</div>`;

 const src=data.sources||{},fresh=data.freshness||{};
 q('#investmentFreshness').innerHTML=`研究資料 ${esc(src.alpha_research_as_of)}（${fresh.alpha_research_age_days??'—'} 天）<br>全市場 Screen ${esc(src.screen_as_of)}（${fresh.screen_age_days??'—'} 天）<br>Screen status：<b>${esc(src.screen_status)}</b>`;
 q('#investmentSelectionText').textContent=data.selection?.text||'—';

 const rows=data.selection?.researched||[];
 q('#alphaRankingRows').innerHTML=rows.map(r=>`<tr><td>${esc(r.rank)}</td><td><b>${esc(r.ticker)} ${esc(r.name)}</b><div class="alpha-sub">${esc(r.thesis||'')}</div></td><td><span class="alpha-score">${num(r.score)}</span> / ${esc(r.grade)}</td><td>${num(r.confidence_score)}</td><td><span class="alpha-action ${actionClass(r.action)}">${esc(r.action)}</span></td><td>${num(r.reference_price)}<div class="alpha-sub">${esc(r.reference_price_date)}</div></td><td class="${cls(r.expected_return_pct)}">${pct(r.expected_return_pct)}</td><td class="${cls(r.alpha_spread_pct)}">${pct(r.alpha_spread_pct)}</td><td>${r.margin_of_safety_pct==null?'—':pct(r.margin_of_safety_pct)}<div class="alpha-sub">${esc(r.next_check||'')}</div></td></tr>`).join('')||'<tr><td colspan="9">尚無 Alpha research 資料</td></tr>';

 const screen=data.selection?.top_screen||[];
 q('#alphaScreenRows').innerHTML=screen.map(r=>`<tr><td>${esc(r.rank)}</td><td><b>${esc(r.ticker)} ${esc(r.name)}</b></td><td>${esc(r.market)}</td><td>${num(r.reference_price)}</td><td>${pct(r.revenue_yoy_pct)}</td><td>${num(r.pe_ttm)}</td><td>${num(r.screen_priority)}</td><td>${r.deep_research_selected?'Deep Research':'Screen'}</td></tr>`).join('')||'<tr><td colspan="8">尚無 Screen 資料</td></tr>';

 const deep=data.selection?.deep_research_queue||[];
 q('#deepResearchGrid').innerHTML=deep.slice(0,12).map((r,i)=>`<div class="deep-card"><b>#${esc(r.rank??i+1)} ${esc(r.ticker)} ${esc(r.name||'')}</b><span>${esc(r.market||'')} ${r.screen_priority!=null?`· priority ${num(r.screen_priority)}`:''}</span></div>`).join('')||'<div class="alpha-sub">目前沒有 Deep Research queue。</div>';

 const cal=data.calibration||{},cm=cal.meta||{};
 q('#alphaCalibration').innerHTML=`狀態：<b>${esc(cm.status||'—')}</b> · BUY entry samples ${num(cm.primary_entry_count)} / 最低校準門檻 ${num(cal.minimum_samples_for_calibration)}。<br><span class="alpha-sub">績效回饋仍以 stock engine 的 BUY_CANDIDATE entry transitions 對 TSMC 超額報酬為準；樣本不足時不宣稱模型已被驗證。</span>`;
}

async function init(){
 ensureShell();
 try{
  const r=await fetch(`data/investment.json?x=${Date.now()}`,{cache:'no-store'});
  if(!r.ok)throw new Error(`HTTP ${r.status}`);
  render(await r.json());
 }catch(e){
  console.error('investment layer',e);
  const el=q('#investmentSelectionText');if(el)el.textContent=`Investment layer 載入失敗：${String(e)}`;
 }
}
init();
})();
