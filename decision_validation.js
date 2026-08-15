(()=>{
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt=v=>v==null?'—':Number(v).toFixed(1);
  const signed=v=>v==null?'—':`${Number(v)>=0?'+':''}${Number(v).toFixed(2)}`;
  const names={growth_persistence:'Growth Persistence',domestic_demand:'Domestic Demand',financial_conditions:'Financial Conditions',ai_concentration:'AI Concentration'};

  function addStyle(){
    if(document.querySelector('link[data-elephant-validation-style]'))return;
    const l=document.createElement('link');l.rel='stylesheet';l.href='decision_validation.css';l.dataset.elephantValidationStyle='1';document.head.appendChild(l);
  }

  function horizonCell(item,h){
    const x=item?.horizons?.[h]||{};
    const corr=x.pearson_to_future_cycle??x.pearson_to_future_same_dimension;
    return `<td><b>${corr==null?'—':Number(corr).toFixed(2)}</b><small>n=${x.samples??0}<br>Reliability ${fmt(x.reliability)}</small></td>`;
  }

  function validationRows(data){
    return Object.entries(data?.cross_dimension_validation||{}).map(([key,item])=>`<tr><td><strong>${esc(names[key]||key)}</strong><small>${esc(item.target||'')}</small></td>${horizonCell(item,'3m')}${horizonCell(item,'6m')}</tr>`).join('');
  }

  function confidenceRows(data){
    return Object.entries(data?.confidence_decomposition||{}).map(([key,x])=>`<tr><td><strong>${esc(names[key]||key)}</strong></td><td>${fmt(x.coverage)}</td><td>${fmt(x.freshness)}</td><td>${fmt(x.signal_agreement)}</td><td>${fmt(x.historical_reliability)}</td><td><b>${fmt(x.provisional_overall)}</b></td></tr>`).join('');
  }

  function analogCards(data){
    return Object.entries(data?.historical_analog_regime_probability||{}).map(([h,x])=>{
      const p=x.probabilities||{};
      return `<div class="validation-analog"><span class="engine-badge">${esc(h.toUpperCase())} historical analog</span><div class="validation-probs"><b>${fmt(p.expansion)}%</b><span>Expansion</span><b>${fmt(p.neutral)}%</b><span>Neutral</span><b>${fmt(p.contraction)}%</b><span>Contraction</span></div><small>n=${x.sample_count??0} · diagnostic only</small></div>`;
    }).join('')||'<div class="engine-muted">歷史相似狀態樣本不足。</div>';
  }

  function stressRows(data){
    return Object.entries(data?.reverse_stress||{}).filter(([k,x])=>k!=='ai_concentration'&&x?.applicable).map(([k,x])=>`<tr><td>${esc(names[k]||k)}</td><td>${signed(x.current_score)}</td><td>${fmt(x.uniform_drop_to_cross_zero)}</td><td>${(x.single_component||[]).slice(0,2).map(v=>`${esc(v.component)} ${fmt(v.required_score_drop)}`).join(' · ')||'—'}</td></tr>`).join('');
  }

  function layerCard(key,x){
    const title={external_demand:'External Demand',business_investment:'Business Investment',regional_vitality:'Regional Vitality'}[key]||key;
    const ready=x.status==='READY';
    return `<article class="validation-layer ${ready?'ready':'blocked'}"><div><span class="engine-badge ${ready?'good':'warn'}">${esc(x.status)}</span><h3>${esc(title)}</h3><p>${esc(x.question||'')}</p></div>${ready?`<div class="validation-layer-score"><b>${signed(x.score)}</b><small>Coverage ${fmt(x.confidence)}</small></div>`:`<p class="engine-muted">${esc(x.reason||'Evidence contract 尚未滿足。')}</p>`}${ready?`<details><summary>Components</summary>${(x.components||[]).map(c=>`<div class="validation-component"><b>${esc(c.name)}</b><span>${signed(c.score)} · raw ${fmt(c.raw)} · ${esc(c.period)}</span></div>`).join('')}</details>`:''}</article>`;
  }

  function render(validation,structural){
    const shell=document.querySelector('#decision-engine .engine-shell');
    if(!shell)return false;
    document.querySelector('#elephantValidationExtension')?.remove();
    const layers=structural?.layers||{};
    const node=document.createElement('section');
    node.id='elephantValidationExtension';
    node.className='validation-extension';
    node.innerHTML=`
      <article class="panel"><div class="panel-head"><div><span class="kicker">MODEL VALIDATION EXTENSION</span><h2>分數真的有未來 information value 嗎？</h2><p class="sub">這裡測的是 Score(t) 與未來狀態的歷史關聯；使用目前修訂後官方序列，因此不是 point-in-time forecast performance。真正 prospective 校準仍由 Vintage DB + Decision Journal 累積。</p></div><span class="engine-badge warn">non-authoritative</span></div><div class="table-wrap"><table class="engine-table"><thead><tr><th>Signal</th><th>→ 3M</th><th>→ 6M</th></tr></thead><tbody>${validationRows(validation)}</tbody></table></div></article>
      <article class="panel"><div class="panel-head"><div><span class="kicker">UNCERTAINTY DECOMPOSITION</span><h2>不要把 Coverage 當 Confidence</h2><p class="sub">Coverage / Freshness / Signal Agreement / Historical Reliability 分開顯示。Provisional Overall 只做診斷，不取代 Decision Engine 三層 Confidence。</p></div></div><div class="table-wrap"><table class="engine-table"><thead><tr><th>Dimension</th><th>Coverage</th><th>Freshness</th><th>Agreement</th><th>Reliability</th><th>Provisional</th></tr></thead><tbody>${confidenceRows(validation)}</tbody></table></div></article>
      <div class="engine-layout"><article class="panel"><div class="panel-head"><div><span class="kicker">HISTORICAL ANALOGS</span><h2>3M / 6M Regime Cross-check</h2></div></div><div class="validation-analogs">${analogCards(validation)}</div></article><article class="panel"><div class="panel-head"><div><span class="kicker">REVERSE STRESS</span><h2>要壞到什麼程度才翻盤？</h2></div></div><div class="table-wrap"><table class="engine-table"><thead><tr><th>Dimension</th><th>Now</th><th>Uniform drop → 0</th><th>Single-component sensitivity</th></tr></thead><tbody>${stressRows(validation)}</tbody></table></div></article></div>
      <article class="panel"><div class="panel-head"><div><span class="kicker">STRUCTURAL LAYERS</span><h2>能算才算；證據不足就 Block</h2><p class="sub">Business Investment 使用既有官方 capex / machinery / credit。External Demand 與 Regional Vitality 在上游或 city-level evidence 不足時不硬湊分數。</p></div></div><div class="validation-layers">${Object.entries(layers).map(([k,x])=>layerCard(k,x)).join('')}</div></article>
      <div class="engine-contract"><b>Evidence boundary：</b> Validation Extension 只能驗證與質疑模型；不能改 deterministic scores、Decision Engine forecast、Risk Budget 或 Alpha Buy Gate。</div>`;
    shell.appendChild(node);
    return true;
  }

  async function init(){
    addStyle();
    try{
      const x=Date.now();
      const [validation,structural]=await Promise.all([
        fetch(`data/model_validation.json?x=${x}`,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(r.status);return r.json()}),
        fetch(`data/structural_layers.json?x=${x}`,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(r.status);return r.json()})
      ]);
      if(render(validation,structural))return;
      const obs=new MutationObserver(()=>{if(render(validation,structural))obs.disconnect()});
      const root=document.querySelector('#decision-engine')||document.body;
      obs.observe(root,{childList:true,subtree:true});
      setTimeout(()=>obs.disconnect(),15000);
    }catch(e){console.warn('validation extension unavailable',e)}
  }
  init();
})();
