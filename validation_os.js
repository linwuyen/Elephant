(()=>{
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt=v=>v==null?'—':Number(v).toFixed(1);
  const signed=v=>v==null?'—':`${Number(v)>=0?'+':''}${Number(v).toFixed(1)}`;
  const names={cycle:'Cycle',growth_persistence:'Growth Persistence',domestic_demand:'Domestic Demand',financial_conditions:'Financial Conditions',ai_concentration:'AI Concentration'};

  function loadCommandCenter(){
    if(!document.querySelector('link[data-elephant-command-center-style]')){
      const l=document.createElement('link');l.rel='stylesheet';l.href='command_center.css';l.dataset.elephantCommandCenterStyle='1';document.head.appendChild(l);
    }
    if(!document.querySelector('script[data-elephant-command-center]')){
      const s=document.createElement('script');s.src='command_center.js';s.defer=true;s.dataset.elephantCommandCenter='1';document.head.appendChild(s);
    }
  }
  function addStyle(){
    if(document.querySelector('link[data-elephant-validation-os-style]'))return;
    const l=document.createElement('link');l.rel='stylesheet';l.href='validation_os.css';l.dataset.elephantValidationOsStyle='1';document.head.appendChild(l);
  }
  function confidenceRows(os){
    return Object.entries(os?.data_confidence_v2?.dimensions||{}).map(([k,x])=>`<tr><td><strong>${esc(names[k]||k)}</strong></td><td>${fmt(x.completeness)}</td><td>${fmt(x.freshness)}</td><td>${fmt(x.source_reliability)}</td><td>${fmt(x.revision_evidence_maturity)}</td><td><b>${fmt(x.effective_data_confidence)}</b></td></tr>`).join('');
  }
  function challengerRows(os){
    return Object.entries(os?.score_challengers?.dimensions||{}).map(([k,x])=>{
      const h3=x.horizons?.['3m']||{},h6=x.horizons?.['6m']||{};
      return `<tr><td><strong>${esc(names[k]||k)}</strong><small>${esc(x.status||'')}</small></td><td>${signed(x.champion_current_score)}</td><td>${signed(x.equal_weight_current_score)}</td><td>${fmt(h3.champion?.pearson_to_future_cycle)} → ${fmt(h3.equal_weight_challenger?.pearson_to_future_cycle)}</td><td>${fmt(h6.champion?.pearson_to_future_cycle)} → ${fmt(h6.equal_weight_challenger?.pearson_to_future_cycle)}</td><td>${x.average_correlation_improvement==null?'—':signed(x.average_correlation_improvement)}</td></tr>`;
    }).join('');
  }
  function scorecards(os){
    const p=os?.prospective_scorecards||{},m=p.macro||{},r=p.risk||{},pf=p.portfolio||{},a=p.alpha||{};
    return `<div class="vos-scorecards"><div><small>Macro outcomes</small><b>${m.resolved_total??0}</b></div><div><small>Risk outcomes</small><b>${r.resolved??0}</b></div><div><small>Portfolio envelope</small><b>${pf.resolved??0}</b></div><div><small>Alpha follow-ups</small><b>${a.resolved_total??0}</b></div></div>`;
  }
  function render(os,journal){
    const anchor=document.querySelector('#elephantValidationExtension')||document.querySelector('#decision-engine .engine-shell')||document.querySelector('#decisionSuite');
    if(!anchor)return false;
    document.querySelector('#elephantValidationOS')?.remove();
    const sb=os?.structural_break_monitor||{},rev=os?.data_confidence_v2?.revision_evidence||{},gateClass=sb.status==='HIGH'?'bad':sb.status==='WATCH'?'warn':'good';
    const node=document.createElement('section');node.id='elephantValidationOS';node.className='validation-os';
    node.innerHTML=`
      <article class="panel"><div class="panel-head"><div><span class="kicker">VALIDATION OS / EVIDENCE CONFIDENCE</span><h2>有資料，不等於資料值得 100 分信任</h2><p class="sub">完整度 × 新鮮度 × 來源健康 × prospective revision evidence。Revision evidence 在剛開始收集 Vintage 時刻意從保守值起跑，不會因為「目前尚未觀察到修正」就假裝 100。</p></div><span class="engine-badge warn">non-authoritative</span></div><div class="vos-kpis"><div><small>Effective Data Confidence</small><b>${fmt(os?.data_confidence_v2?.overall)}</b></div><div><small>Revision evidence</small><b>${fmt(rev.score)}</b><span>${fmt(rev.prospective_days)} days</span></div><div><small>Structural break</small><b>${esc(sb.status||'—')}</b><span>regime ${fmt(sb.nearest_regime_similarity)}</span></div></div><div class="table-wrap"><table class="engine-table"><thead><tr><th>Dimension</th><th>Complete</th><th>Fresh</th><th>Source</th><th>Revision evidence</th><th>Effective</th></tr></thead><tbody>${confidenceRows(os)}</tbody></table></div></article>
      <div class="engine-layout"><article class="panel"><div class="panel-head"><div><span class="kicker">STRUCTURAL BREAK MONITOR</span><h2>現在是不是歷史上不太一樣的世界？</h2></div><span class="engine-badge ${gateClass}">${esc(sb.status||'—')}</span></div><div class="vos-kpis"><div><small>Nearest regime</small><b>${fmt(sb.nearest_regime_similarity)}</b></div><div><small>Distribution similarity</small><b>${fmt(sb.distribution_similarity)}</b></div><div><small>Correlation drift</small><b>${fmt(sb.correlation_drift_score)}</b></div></div><ul class="vos-reasons">${(sb.reasons||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul><p class="engine-muted">只做 novelty/drift 警報；不能自行改 Score、Risk Budget 或交易。</p></article><article class="panel"><div class="panel-head"><div><span class="kicker">PROSPECTIVE SCORECARDS</span><h2>只算當時真的不知道的未來</h2></div></div>${scorecards(os)}<p class="engine-muted">Validation snapshots ${journal?.entries?.length??0}；不回填 Validation OS 建立前的假 prospective 成績。</p></article></div>
      <article class="panel"><div class="panel-head"><div><span class="kicker">SCORE CHAMPION / CHALLENGER</span><h2>先拿最簡單的 equal-weight baseline 反駁手調權重</h2><p class="sub">Transforms 與 component 定義完全相同，只把 Growth / Domestic / Financial 權重改成 20% equal-weight 做 challenger。沒有調參、沒有自動升級。</p></div></div><div class="table-wrap"><table class="engine-table"><thead><tr><th>Score</th><th>Champion now</th><th>Equal-weight now</th><th>3M corr champion → challenger</th><th>6M corr champion → challenger</th><th>Avg Δ corr</th></tr></thead><tbody>${challengerRows(os)}</tbody></table></div></article>`;
    anchor.insertAdjacentElement('afterend',node);return true;
  }
  async function init(){
    addStyle();loadCommandCenter();
    try{
      const x=Date.now();
      const [os,journal]=await Promise.all([
        fetch(`data/validation_os.json?x=${x}`,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(r.status);return r.json()}),
        fetch(`data/validation_journal.json?x=${x}`,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(r.status);return r.json()}),
      ]);
      let tries=0;const timer=setInterval(()=>{if(render(os,journal)||++tries>20)clearInterval(timer)},250);
    }catch(e){console.warn('Validation OS unavailable',e)}
  }
  init();
})();
