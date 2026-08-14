(()=>{
const q=s=>document.querySelector(s);
const esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=v=>v==null?'—':`${Number(v)>=0?'+':''}${Number(v).toFixed(1)}%`;
const num=v=>v==null?'—':Number(v).toLocaleString('zh-TW',{maximumFractionDigits:2});
const cls=v=>v==null?'alpha-neutral':Number(v)>0?'alpha-positive':Number(v)<0?'alpha-negative':'alpha-neutral';
const actionClass=v=>String(v||'').toLowerCase().replaceAll(' ','-');
const contextName={BROADLY_SUPPORTIVE:'廣泛支持',EXPORT_LED_SUPPORTIVE:'出口／科技支持',CONSTRUCTIVE:'偏正向',MIXED:'混合',DEFENSIVE:'防禦',UNKNOWN:'資料不足'};

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
