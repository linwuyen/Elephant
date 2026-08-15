(()=>{
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt=v=>v==null?'—':Number(v).toFixed(1);
  const pct=v=>v==null?'—':`${(Number(v)*100).toFixed(0)}%`;
  const signed=v=>v==null?'—':`${Number(v)>=0?'+':''}${Number(v).toFixed(2)}`;
  const names={cycle:'Cycle',growth_persistence:'Growth Persistence',domestic_demand:'Domestic Demand',financial_conditions:'Financial Conditions',ai_concentration:'AI Concentration'};

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

  function v2HorizonCell(dim,h){
    const x=dim?.horizons?.[h]||{},cur=x.current||{};
    const skill=x.brier_skill_vs_climatology;
    return `<td><b>${pct(cur.probability)}</b><small>OOS n=${x.oos_predictions??0} · local n=${cur.local_sample_size??0}<br>Confidence ${fmt(cur.model_confidence)} · Brier skill ${skill==null?'—':fmt(Number(skill)*100)+'%'}</small></td>`;
  }

  function v2Rows(v2){
    return ['cycle','growth_persistence','domestic_demand','financial_conditions'].map(key=>{
      const dim=v2?.walk_forward_oos?.[key]||{};
      return `<tr><td><strong>${esc(names[key]||key)}</strong><small>strict expanding-window</small></td>${v2HorizonCell(dim,'3m')}${v2HorizonCell(dim,'6m')}</tr>`;
    }).join('');
  }

  function outcomeRows(v2){
    const out=v2?.external_outcome_validation||{};
    return ['cycle','growth_persistence','domestic_demand','financial_conditions'].map(key=>{
      const ip=out?.[key]?.industrial_production_yoy?.horizons?.['6m']||{};
      const market=out?.[key]?.stock_forward_return?.horizons?.['6m']||{};
      return `<tr><td><strong>${esc(names[key])}</strong></td><td>${ip.pearson==null?'—':Number(ip.pearson).toFixed(2)}<small>n=${ip.samples??0} · direction ${ip.direction_accuracy==null?'—':pct(ip.direction_accuracy)}</small></td><td>${market.pearson==null?'—':Number(market.pearson).toFixed(2)}<small>n=${market.samples??0} · direction ${market.direction_accuracy==null?'—':pct(market.direction_accuracy)}</small></td></tr>`;
    }).join('');
  }

  function v2Panel(v2){
    const c=v2?.confidence||{},gate=v2?.promotion_gate||{},risk=v2?.risk_budget_backtest||{},pv=risk.policy_vs_static_60_equity||{};
    const status=gate.status||'CHALLENGER_ONLY';
    const statusClass=gate.promotion_eligible?'good':'warn';
    return `<article class="panel"><div class="panel-head"><div><span class="kicker">DECISION ENGINE V2 / CHALLENGER</span><h2>真正 Walk-forward OOS，而不是拿同一批歷史驗自己</h2><p class="sub">每個歷史預測只能使用當時已成熟的 outcome；pre-vintage 歷史仍承認 revision bias。v2 永遠不能自動覆蓋 v1。</p></div><span class="engine-badge ${statusClass}">${esc(status)}</span></div><div class="engine-grid"><div class="engine-card"><small>Effective Data Confidence</small><div class="big">${fmt(c.effective_data_confidence)}</div></div><div class="engine-card"><small>Sample-aware Model Confidence</small><div class="big">${fmt(c.sample_aware_model_confidence)}</div></div><div class="engine-card"><small>Regime similarity</small><div class="big">${fmt(c.regime_similarity)}</div></div><div class="engine-card"><small>Prospective outcomes</small><div class="big">${c.prospective_outcomes??0}</div></div></div><div class="table-wrap"><table class="engine-table"><thead><tr><th>Signal</th><th>Strict OOS 3M</th><th>Strict OOS 6M</th></tr></thead><tbody>${v2Rows(v2)}</tbody></table></div></article>
      <div class="engine-layout"><article class="panel"><div class="panel-head"><div><span class="kicker">REAL-WORLD OUTCOME TARGETS</span><h2>不要只預測自己的 Score</h2><p class="sub">6M 對官方工業生產 YoY 與 NDC 股價指數 forward return 的歷史關聯；僅作 evidence，不等於報酬保證。</p></div></div><div class="table-wrap"><table class="engine-table"><thead><tr><th>Signal</th><th>Industrial Production</th><th>Stock Index Return</th></tr></thead><tbody>${outcomeRows(v2)}</tbody></table></div></article><article class="panel"><div class="panel-head"><div><span class="kicker">RISK BUDGET V1 DIAGNOSTIC</span><h2>先證明舊 position-sizing 規則有沒有價值</h2></div></div><div class="engine-grid"><div class="engine-card"><small>Observations</small><div class="big">${risk.observations??0}</div></div><div class="engine-card"><small>Policy scaled return</small><div class="big">${fmt(pv.policy_scaled_equity_return_pct)}%</div></div><div class="engine-card"><small>Static 60% return</small><div class="big">${fmt(pv.static_60_equity_return_pct)}%</div></div><div class="engine-card"><small>Policy max DD</small><div class="big">${fmt(pv.policy_max_drawdown_pct)}%</div></div></div><p class="engine-muted">Cash return 固定 0%、未含交易成本；這是 reconstructed diagnostic，不是可交易績效宣稱。</p></article></div>`;
  }

  function riskBudgetV2Panel(rb){
    const cur=rb?.current||{},env=cur.allocation_envelope||{},bt=rb?.walk_forward_backtest||{},gate=rb?.promotion_gate||{};
    const zero=bt?.cost_sensitivity?.['0']||{},cost25=bt?.cost_sensitivity?.['25']||{};
    const c=zero.challenger||{},v1=zero.v1_champion||{},st=zero.static_60||{},c25=cost25.challenger||{};
    const ready=cur.status==='READY';
    const gateClass=gate.promotion_eligible?'good':'warn';
    return `<article class="panel"><div class="panel-head"><div><span class="kicker">RISK BUDGET V2 / ALLOCATION CHALLENGER</span><h2>景氣強，不代表現在應該加股票</h2><p class="sub">宏觀五維 + 市場 6M momentum / trailing drawdown → strict walk-forward historical analogs → 未來 6M return / drawdown evidence。證據弱時往 60% 中性曝險收縮。</p></div><span class="engine-badge ${gateClass}">${esc(gate.status||'CHALLENGER_ONLY')}</span></div>
      <div class="engine-grid"><div class="engine-card"><small>Challenger equity review</small><div class="big">${ready?fmt(env.equity_risk_budget_review_pct)+'%':'—'}</div><small>v1 champion ${fmt(env.v1_champion_target_equity_pct)}%</small></div><div class="engine-card"><small>Cash / low-risk reserve</small><div class="big">${ready?fmt(env.cash_or_low_risk_reserve_review_pct)+'%':'—'}</div><small>neutral anchor ${fmt(env.neutral_anchor_equity_pct)}%</small></div><div class="engine-card"><small>Expected 6M return</small><div class="big">${ready?fmt(cur.expected_forward_return_6m_pct)+'%':'—'}</div><small>return pctile ${fmt(cur.return_percentile)}</small></div><div class="engine-card"><small>Expected 6M drawdown</small><div class="big">${ready?fmt(cur.expected_forward_drawdown_6m_pct)+'%':'—'}</div><small>DD quality pctile ${fmt(cur.drawdown_quality_percentile)}</small></div><div class="engine-card"><small>Allocation score</small><div class="big">${fmt(cur.allocation_score)}</div></div><div class="engine-card"><small>Evidence confidence</small><div class="big">${fmt(cur.evidence_confidence)}</div></div></div>
      <div class="table-wrap"><table class="engine-table"><thead><tr><th>Strict-OOS comparator</th><th>Return</th><th>Max DD</th><th>Return / |DD|</th><th>Avg equity</th></tr></thead><tbody><tr><td><strong>Risk Budget v2</strong><small>n=${bt.months??0}</small></td><td>${fmt(c.total_return_pct)}%</td><td>${fmt(c.max_drawdown_pct)}%</td><td>${fmt(c.return_to_abs_max_drawdown)}</td><td>${fmt(c.average_equity_pct)}%</td></tr><tr><td>v1 champion</td><td>${fmt(v1.total_return_pct)}%</td><td>${fmt(v1.max_drawdown_pct)}%</td><td>${fmt(v1.return_to_abs_max_drawdown)}</td><td>${fmt(v1.average_equity_pct)}%</td></tr><tr><td>Static 60</td><td>${fmt(st.total_return_pct)}%</td><td>${fmt(st.max_drawdown_pct)}%</td><td>${fmt(st.return_to_abs_max_drawdown)}</td><td>${fmt(st.average_equity_pct)}%</td></tr></tbody></table></div>
      <p class="engine-muted">25 bps / 100% turnover sensitivity：challenger return ${fmt(c25.total_return_pct)}%。單月 equity budget 最多變動 ${fmt(env.max_monthly_equity_change_pct_points)} 個百分點。這只是 aggregate risk envelope；個股與地區配置仍由 Capital OS / Alpha / Investment Constitution 決定。</p></article>`;
  }

  function render(validation,structural,v2,riskBudgetV2){
    const shell=document.querySelector('#decision-engine .engine-shell');
    if(!shell)return false;
    document.querySelector('#elephantValidationExtension')?.remove();
    const layers=structural?.layers||{};
    const node=document.createElement('section');
    node.id='elephantValidationExtension';
    node.className='validation-extension';
    node.innerHTML=`
      ${v2Panel(v2)}
      ${riskBudgetV2Panel(riskBudgetV2)}
      <article class="panel"><div class="panel-head"><div><span class="kicker">MODEL VALIDATION EXTENSION</span><h2>分數真的有未來 information value 嗎？</h2><p class="sub">這裡測的是 Score(t) 與未來狀態的歷史關聯；使用目前修訂後官方序列，因此不是 point-in-time forecast performance。真正 prospective 校準仍由 Vintage DB + Decision Journal 累積。</p></div><span class="engine-badge warn">non-authoritative</span></div><div class="table-wrap"><table class="engine-table"><thead><tr><th>Signal</th><th>→ 3M</th><th>→ 6M</th></tr></thead><tbody>${validationRows(validation)}</tbody></table></div></article>
      <article class="panel"><div class="panel-head"><div><span class="kicker">UNCERTAINTY DECOMPOSITION</span><h2>不要把 Coverage 當 Confidence</h2><p class="sub">Coverage / Freshness / Signal Agreement / Historical Reliability 分開顯示。Provisional Overall 只做診斷，不取代 Decision Engine 三層 Confidence。</p></div></div><div class="table-wrap"><table class="engine-table"><thead><tr><th>Dimension</th><th>Coverage</th><th>Freshness</th><th>Agreement</th><th>Reliability</th><th>Provisional</th></tr></thead><tbody>${confidenceRows(validation)}</tbody></table></div></article>
      <div class="engine-layout"><article class="panel"><div class="panel-head"><div><span class="kicker">HISTORICAL ANALOGS</span><h2>3M / 6M Regime Cross-check</h2></div></div><div class="validation-analogs">${analogCards(validation)}</div></article><article class="panel"><div class="panel-head"><div><span class="kicker">REVERSE STRESS</span><h2>要壞到什麼程度才翻盤？</h2></div></div><div class="table-wrap"><table class="engine-table"><thead><tr><th>Dimension</th><th>Now</th><th>Uniform drop → 0</th><th>Single-component sensitivity</th></tr></thead><tbody>${stressRows(validation)}</tbody></table></div></article></div>
      <article class="panel"><div class="panel-head"><div><span class="kicker">STRUCTURAL LAYERS</span><h2>能算才算；證據不足就 Block</h2><p class="sub">Business Investment 使用既有官方 capex / machinery / credit。External Demand 與 Regional Vitality 在上游或 city-level evidence 不足時不硬湊分數。</p></div></div><div class="validation-layers">${Object.entries(layers).map(([k,x])=>layerCard(k,x)).join('')}</div></article>
      <div class="engine-contract"><b>Evidence boundary：</b> Decision v2 / Risk Budget v2 / Validation Extension 只能驗證、質疑與提出 promotion evidence；不能改 deterministic scores、v1 forecast、v1 Risk Budget、Capital OS、Alpha 或 Investment Constitution。</div>`;
    shell.appendChild(node);
    return true;
  }

  async function init(){
    addStyle();
    try{
      const x=Date.now();
      const [validation,structural,v2,riskBudgetV2]=await Promise.all([
        fetch(`data/model_validation.json?x=${x}`,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(r.status);return r.json()}),
        fetch(`data/structural_layers.json?x=${x}`,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(r.status);return r.json()}),
        fetch(`data/decision_engine_v2.json?x=${x}`,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(r.status);return r.json()}),
        fetch(`data/risk_budget_v2.json?x=${x}`,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(r.status);return r.json()})
      ]);
      if(render(validation,structural,v2,riskBudgetV2))return;
      const obs=new MutationObserver(()=>{if(render(validation,structural,v2,riskBudgetV2))obs.disconnect()});
      const root=document.querySelector('#decision-engine')||document.body;
      obs.observe(root,{childList:true,subtree:true});
      setTimeout(()=>obs.disconnect(),15000);
    }catch(e){console.warn('validation extension unavailable',e)}
  }
  init();
})();
