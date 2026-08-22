(()=>{
  const $=s=>document.querySelector(s);
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=(v,d=1)=>v==null||Number.isNaN(Number(v))?'—':Number(v).toLocaleString('zh-TW',{minimumFractionDigits:d,maximumFractionDigits:d});
  const pct=(v,d=1)=>v==null?'—':`${num(v,d)}%`;
  const signed=(v,d=1,suffix='')=>v==null?'—':`${Number(v)>=0?'+':''}${num(v,d)}${suffix}`;
  const money=v=>v==null||!Number.isFinite(Number(v))?'—':`NT$ ${Math.round(Number(v)).toLocaleString('zh-TW')}`;
  let DATA=null;

  function portfolioApi(){return window.ElephantPortfolioState}
  function loadPortfolio(){try{return portfolioApi()?.load?.()||{}}catch{return {}}}
  function savePortfolio(next){try{return portfolioApi()?.save?.(next||{})||loadPortfolio()}catch(_){return loadPortfolio()}}

  function badge(code){
    const cls=code==='REDUCE_RISK'||code==='BLOCKED'?'risk':code==='DEPLOY_SELECTIVELY'?'good':'warn';
    const label={BLOCKED:'BLOCKED',REDUCE_RISK:'REDUCE',HOLD_CASH:'HOLD CASH',HOLD_SELECTIVE:'HOLD',DEPLOY_SELECTIVELY:'DEPLOY'}[code]||code;
    return `<span class="dcc-badge ${cls}">${esc(label)}</span>`;
  }

  function allocationBar(a){
    const zone=a?.operating_zone_equity_pct||[];
    const lo=Number(zone[0]??0),hi=Number(zone[1]??0),v1=Number(a?.v1_authoritative_equity_pct??0),v2=Number(a?.v2_market_aware_review_equity_pct??0);
    return `<div class="dcc-allocation-track"><div class="dcc-zone" style="left:${lo}%;width:${Math.max(0,hi-lo)}%"></div><span class="dcc-marker champion" style="left:${v1}%"><i></i><em>v1 ${pct(v1)}</em></span><span class="dcc-marker challenger" style="left:${v2}%"><i></i><em>v2 ${pct(v2)}</em></span></div><div class="dcc-track-scale"><span>0%</span><span>50%</span><span>100%</span></div>`;
  }

  function deltaPanel(d){
    if(!d)return '';
    const r=d.risk_budget_delta||{};
    const score=d.score_delta||{};
    const rows=[
      ['v1 equity',r.v1_equity_pp,' pp'],['v2 equity',r.v2_equity_pp,' pp'],
      ['Cycle',score.cycle,''],['Growth',score.growth_persistence,''],['Domestic',score.domestic_demand,''],['Financial',score.financial_conditions,'']
    ].filter(x=>x[1]!=null&&Math.abs(Number(x[1]))>=.1);
    return `<article class="dcc-card"><div class="dcc-card-head"><div><span class="kicker">DECISION DELTA</span><h3>跟最近一次基準差在哪？</h3></div><span class="dcc-mini ${d.status==='CHANGED'?'warn':''}">${esc(d.status||'—')}</span></div><p class="dcc-muted">${esc(d.message||'')}</p>${rows.length?`<div class="dcc-deltas">${rows.map(x=>`<div><span>${esc(x[0])}</span><b class="${Number(x[1])>0?'up':Number(x[1])<0?'down':''}">${signed(x[1],1,x[2])}</b></div>`).join('')}</div>`:'<div class="dcc-empty">目前沒有需要改變動作的 material delta。</div>'}</article>`;
  }

  function rationalePanel(rows){
    const labels={support:'支持曝險',market:'市場位置',confidence:'可信度限制',deployment:'資金去處'};
    return `<article class="dcc-card"><div class="dcc-card-head"><div><span class="kicker">WHY NOW</span><h3>為什麼是這個動作？</h3></div></div><div class="dcc-reasons">${(rows||[]).map(x=>`<div class="dcc-reason ${esc(x.type)}"><span>${esc(labels[x.type]||x.type)}</span><div><b>${esc(x.title)}</b><p>${esc(x.text)}</p></div></div>`).join('')}</div></article>`;
  }

  function counterfactualPanel(cf){
    const rows=[...(cf?.scenarios||[])].sort((a,b)=>Math.abs(Number(b.delta_vs_current_pp||0))-Math.abs(Number(a.delta_vs_current_pp||0)));
    return `<article class="dcc-card dcc-wide"><div class="dcc-card-head"><div><span class="kicker">COUNTERFACTUAL ENGINE</span><h3>如果條件改變，股票風險預算會變多少？</h3><p class="dcc-muted">固定同一批 ${cf?.training_samples??'—'} 個 historical training samples，只改 declared condition；這是 sensitivity，不是因果估計。</p></div><span class="dcc-mini">base ${pct(cf?.base_target_equity_pct)}</span></div><div class="dcc-whatif">${rows.map(x=>`<div class="dcc-whatif-card"><small>${esc(x.label)}</small><b>${pct(x.target_equity_pct)}</b><span class="${Number(x.delta_vs_current_pp)>0?'up':Number(x.delta_vs_current_pp)<0?'down':''}">${signed(x.delta_vs_current_pp,1,' pp')}</span><p>${esc(x.description)}</p></div>`).join('')}</div></article>`;
  }

  function triggerPanel(t){
    const group=(title,rows)=>`<div class="dcc-trigger-group"><h4>${esc(title)}</h4>${(rows||[]).map(x=>`<div class="dcc-trigger ${x.met?'met':''}"><span>${x.met?'✓':'○'}</span><div><b>${esc(x.label)}</b><small>現在：${esc(x.current==null?'—':String(x.current))} · 觸發：${esc(x.condition||'—')}</small><p>${esc(x.meaning||'')}</p></div></div>`).join('')}</div>`;
    return `<article class="dcc-card"><div class="dcc-card-head"><div><span class="kicker">WHAT CHANGES MY MIND</span><h3>什麼發生，我才改變動作？</h3></div></div>${group('提高風險／部署資金',t?.increase_risk)}${group('降低風險',t?.decrease_risk)}</article>`;
  }

  function alphaPanel(a){
    const rows=(a?.buy_candidate_count? a.top_buy : a?.top_verify)||[];
    const mode=a?.buy_candidate_count?'BUY candidates':'VERIFY queue';
    return `<article class="dcc-card"><div class="dcc-card-head"><div><span class="kicker">CAPITAL DEPLOYMENT QUEUE</span><h3>${a?.buy_candidate_count??0} BUY · ${a?.verify_count??0} VERIFY</h3></div><span class="dcc-mini">${esc(mode)}</span></div><p class="dcc-muted">${esc(a?.selection_text||'')}</p><div class="dcc-alpha">${rows.length?rows.map(x=>`<div class="dcc-alpha-row"><div><b>${esc(x.name||x.ticker)}</b><small>${esc(x.ticker)} · ${esc(x.action||'')}</small></div><div><strong>${x.alpha_spread_pct==null?'—':signed(x.alpha_spread_pct,1,'%')}</strong><small>Alpha spread</small></div><p>${esc(x.next_check||'已通過 BUY Gate，可依 allocation capacity 評估。')}</p></div>`).join(''):'<div class="dcc-empty">目前沒有可承接新增股票資金的 BUY candidate。</div>'}</div></article>`;
  }

  function personalResult(){
    if(!DATA)return;
    const totalInput=Number($('#dccTotal')?.value||0),equity=Number($('#dccEquity')?.value||0),cash=Number($('#dccCash')?.value||0);
    const total=totalInput>0?totalInput:(equity+cash);
    const zone=DATA.allocation?.operating_zone_equity_pct||[];
    const lo=Number(zone[0]),hi=Number(zone[1]);
    const buy=Number(DATA.alpha?.buy_candidate_count||0);
    const out=$('#dccPersonalResult');if(!out)return;
    savePortfolio({total:totalInput||total,equity,cash});
    if(!total||!Number.isFinite(lo)||!Number.isFinite(hi)){
      out.innerHTML='<div class="dcc-empty">輸入可投資資產與目前股票市值，就會直接換算成應不應動、差多少錢。</div>';
      return;
    }
    const current=equity/total*100;
    let title,text,amount=0,cls='hold';
    if(current>hi+.5){
      amount=Math.max(0,equity-total*hi/100);cls='reduce';title=`股票曝險 ${pct(current)}，高於 review zone`;
      text=`優先降低約 ${money(amount)} 股票曝險，使總股票部位回到 ${pct(hi)} 附近；這是 envelope 調整，不指定賣哪一檔。`;
    }else if(current<lo-.5){
      amount=Math.max(0,total*lo/100-equity);
      if(buy>0){cls='add';title=`股票曝險 ${pct(current)}，低於 review zone`;text=`最多有約 ${money(amount)} 的增加容量，但只允許部署到已通過 BUY Gate 的標的。`;}
      else{cls='hold';title=`有 ${money(amount)} 的風險容量，但現在 0 BUY`;text='不要為了把股票比例補滿而硬買；新增資金先留在現金／低風險資產，等待 Alpha Gate。';}
    }else{
      title=`股票曝險 ${pct(current)}，已在 review zone 內`;text=buy>0?'不用為了配置比例主動大搬風；若有 BUY，只做選擇性部署或換股。':'不需要動。維持既有部位，新增資金等待 BUY candidate。';
    }
    out.innerHTML=`<div class="dcc-personal-call ${cls}"><small>YOUR ACTION</small><b>${esc(title)}</b><p>${esc(text)}</p><div class="dcc-personal-metrics"><span>目前 ${pct(current)}</span><span>Zone ${pct(lo)}–${pct(hi)}</span><span>BUY ${buy}</span></div></div>`;
  }

  function portfolioPanel(){
    const p=loadPortfolio();
    return `<article class="dcc-card dcc-personal"><div class="dcc-card-head"><div><span class="kicker">YOUR MONEY</span><h3>把模型直接換成你的金額</h3></div><span class="dcc-lock">🔒 browser-local</span></div><div class="dcc-inputs"><label>可投資資產總額<input id="dccTotal" type="number" min="0" step="1000" value="${esc(p.total??'')}"></label><label>目前股票市值<input id="dccEquity" type="number" min="0" step="1000" value="${esc(p.equity??'')}"></label><label>目前現金／低風險<input id="dccCash" type="number" min="0" step="1000" value="${esc(p.cash??'')}"></label></div><div id="dccPersonalResult"></div><small class="dcc-privacy">不會上傳 GitHub、不會寫進 Elephant public artifacts；沿用 canonical PortfolioState。</small></article>`;
  }

  function navigateEvidence(target){
    const btn=$('.tabs button[data-tab="decision-engine"]');
    if(btn)btn.click();
    setTimeout(()=>$(target)?.scrollIntoView({behavior:'smooth',block:'start'}),120);
  }

  function render(d){
    DATA=d;
    const cards=$('#headlineCards');if(!cards)return;
    $('#decisionCommandCenter')?.remove();
    const a=d.allocation||{},c=d.command||{},m=d.market||{},v=d.validation||{},alpha=d.alpha||{};
    const zone=a.operating_zone_equity_pct||[];
    const node=document.createElement('section');node.id='decisionCommandCenter';node.className='decision-command-center';
    node.innerHTML=`<article class="dcc-hero"><div class="dcc-hero-copy"><div class="dcc-topline"><span class="kicker">DECISION COMMAND CENTER</span>${badge(c.code)}<span class="dcc-confidence">Confidence ${esc(c.decision_confidence||'—')}</span></div><h2>${esc(c.title||'Decision unavailable')}</h2><p>${esc(c.action||'')}</p><div class="dcc-hero-actions"><button class="secondary" id="dccEvidence">看完整 Decision Engine</button><button class="secondary" id="dccValidation">看 Validation / Evidence</button></div></div><div class="dcc-primary"><div><small>Operating zone</small><b>${zone.length===2?`${pct(zone[0])}–${pct(zone[1])}`:'—'}</b><span>v1 champion ↔ v2.1 market-aware review</span></div><div><small>Alpha gate</small><b>${alpha.buy_candidate_count??0} BUY</b><span>${alpha.verify_count??0} VERIFY · 不強迫部署</span></div></div></article>
      <article class="dcc-allocation"><div class="dcc-kpis"><div><small>v1 authoritative</small><b>${pct(a.v1_authoritative_equity_pct)}</b></div><div><small>v2.1 review</small><b>${pct(a.v2_market_aware_review_equity_pct)}</b></div><div><small>6M momentum</small><b>${signed(m.momentum_6m_pct,1,'%')}</b></div><div><small>Structural break</small><b>${esc(v.structural_break_status||'—')}</b></div><div><small>Data confidence</small><b>${num(v.effective_data_confidence,1)}</b></div></div>${allocationBar(a)}<p class="dcc-allocation-note">${esc(a.note||'')}</p></article>
      <div class="dcc-grid two">${portfolioPanel()}${deltaPanel(d.decision_delta)}</div>
      <div class="dcc-grid two">${rationalePanel(d.rationale)}${triggerPanel(d.what_changes_my_mind)}</div>
      ${counterfactualPanel(d.counterfactuals)}
      ${alphaPanel(alpha)}
      <details class="dcc-contract"><summary>權限與方法邊界</summary><p>Command Center 不建立新模型權限：v1 Risk Budget 仍是 champion；v2.1 仍是 challenger；Validation OS 只能限制 reviewed confidence；個股只有 Alpha Buy Gate 能給 BUY；個人資產只存在瀏覽器；沒有自動交易。</p><code>${esc(d.evidence_hash||'')}</code></details>`;
    const brief=$('#elephantBrief');if(brief)brief.insertAdjacentElement('beforebegin',node);else cards.insertAdjacentElement('afterend',node);
    ['#dccTotal','#dccEquity','#dccCash'].forEach(id=>$(id)?.addEventListener('input',personalResult));
    $('#dccEvidence')?.addEventListener('click',()=>navigateEvidence('#decision-engine'));
    $('#dccValidation')?.addEventListener('click',()=>navigateEvidence('#elephantValidationOS'));
    personalResult();
  }

  async function init(){
    try{
      const d=await fetch(`data/decision_command.json?x=${Date.now()}`,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(r.status);return r.json()});
      render(d);
    }catch(e){
      console.warn('Decision Command Center unavailable',e);
      const cards=$('#headlineCards');if(!cards)return;
      const node=document.createElement('section');node.id='decisionCommandCenter';node.className='decision-command-center dcc-unavailable';node.innerHTML='<article class="dcc-card"><b>Decision Command Center 正在建立</b><p>底層原始資料與既有頁面仍可正常使用。</p></article>';
      const brief=$('#elephantBrief');if(brief)brief.insertAdjacentElement('beforebegin',node);else cards.insertAdjacentElement('afterend',node);
    }
  }
  init();
})();
