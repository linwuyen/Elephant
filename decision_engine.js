(()=>{
  const $=s=>document.querySelector(s);
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const pct=v=>v==null?'—':`${(Number(v)*100).toFixed(0)}%`;
  const nfmt=v=>v==null||Number.isNaN(Number(v))?'—':Number(v).toLocaleString('zh-TW',{maximumFractionDigits:1});
  const signed=v=>v==null?'—':`${Number(v)>=0?'+':''}${Number(v).toFixed(0)}`;
  const clamp=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));
  const LOCAL_KEY='elephant.portfolio.v1';
  let DATA=null;

  function addStyle(){
    if(document.querySelector('link[data-elephant-engine-style]'))return;
    const l=document.createElement('link');l.rel='stylesheet';l.href='decision_engine.css';l.dataset.elephantEngineStyle='1';document.head.appendChild(l);
  }

  function confidenceCard(label,value,desc){
    const v=Number(value||0),cls=v>=75?'good':v>=55?'warn':'risk';
    return `<div class="engine-card"><span class="engine-badge ${cls}">${esc(label)}</span><div class="big">${v.toFixed(0)}</div><small>${esc(desc)}</small></div>`;
  }

  function forecastRows(forecast){
    const names={cycle:'Cycle',growth_persistence:'Growth Persistence',domestic_demand:'Domestic Demand',financial_conditions:'Financial Conditions',ai_concentration:'AI Concentration'};
    return Object.entries(forecast?.dimensions||{}).map(([k,d])=>{
      const hs=d.horizons||{};
      const target=k==='ai_concentration'?'高集中機率':'維持正值機率';
      return `<tr><td><strong>${esc(names[k]||k)}</strong><small>${esc(d.period||'—')} · ${k==='ai_concentration'?nfmt(d.score):signed(d.score)} · ${esc(target)}</small></td>${['1m','3m','6m','12m'].map(h=>{const x=hs[h]||{};return `<td><span class="engine-prob">${pct(x.probability)}</span><small>n=${x.local_sample_size??0}<br>exp ${nfmt(x.expected_score)}</small></td>`}).join('')}</tr>`;
    }).join('');
  }

  function scenarioCards(rows){
    return (rows||[]).map(x=>`<div class="engine-scenario"><small>${esc(x.name)}</small><b>${nfmt(x.risk_score)}</b><div class="engine-muted">Risk score / 100</div></div>`).join('');
  }

  function claimRows(claims){
    return (claims||[]).slice(0,12).map(c=>`<article class="engine-claim"><div class="engine-claim-meta"><span>${esc(c.company)}</span><span>${esc(c.date||'—')}</span><span>${esc(c.direction)}</span><span>Evidence ${nfmt(c.evidence_strength)}</span></div><h4>${esc(c.title)}</h4><p>${esc(c.claim_candidate)}</p><div class="engine-claim-meta"><span>${esc((c.geography||[]).join(' · '))}</span><span>${esc((c.industries||[]).slice(0,4).join(' · '))}</span><span>${esc(c.horizon)}</span><a href="${esc(c.source_url)}" target="_blank" rel="noopener">原始研究</a></div></article>`).join('');
  }

  function journalRows(journal){
    const entries=[...(journal?.entries||[])].reverse().slice(0,8);
    if(!entries.length)return '<div class="engine-muted">尚未累積 prospective decision snapshot。</div>';
    return entries.map(e=>{
      const score=e.scores?.cycle?.score;
      const outs=Object.values(e.outcomes||{});
      const resolved=outs.length?`${outs.filter(x=>x.correct_direction).length}/${outs.length} 命中`:'等待 outcome';
      return `<div class="engine-journal-row"><div><b>${esc(e.period||'—')}</b><small>${esc((e.recorded_at||'').slice(0,10))}</small></div><div><strong>Cycle ${signed(score)} · ${esc(e.risk_posture||'—')}</strong><small>1M forecast ${pct(e.forecast?.cycle?.['1m'])} · 3M ${pct(e.forecast?.cycle?.['3m'])}</small></div><span class="engine-badge">${esc(resolved)}</span></div>`;
    }).join('');
  }

  function loadPortfolio(){
    try{return JSON.parse(localStorage.getItem(LOCAL_KEY)||'{}')}catch{return {}}
  }
  function savePortfolio(v){localStorage.setItem(LOCAL_KEY,JSON.stringify(v))}
  function val(id){const x=Number($(id)?.value);return Number.isFinite(x)?x:0}

  function calculatePortfolio(){
    const g=DATA.engine?.risk_budget?.allocation_guardrails||DATA.risk?.allocation_guardrails||{};
    let total=val('#engineTotal'),equity=val('#engineEquity'),cash=val('#engineCash'),largest=val('#engineLargest'),maxDd=val('#engineDrawdown')||20;
    if(!total)total=equity+cash;
    const tolerance=clamp(maxDd/25,.45,1.15);
    const systemTarget=Number(g.target_equity_risk_budget_pct||50);
    const targetPct=clamp(systemTarget*tolerance,15,95);
    const cashFloor=Math.max(Number(g.cash_floor_pct||5),100-targetPct);
    const singleCap=Math.min(Number(g.max_single_stock_pct||20),Math.max(8,maxDd*.7));
    const targetEquity=total*targetPct/100;
    const delta=targetEquity-equity;
    const largestAmt=total*singleCap/100;
    const action=delta>total*.03?'有風險預算可增加曝險':delta<-total*.03?'目前曝險高於風險預算':'目前曝險接近風險預算';
    $('#enginePortfolioResult').innerHTML=`<div class="engine-result-grid"><div><small>個人化 Equity ceiling</small><b>${targetPct.toFixed(0)}%</b></div><div><small>最低現金</small><b>${cashFloor.toFixed(0)}%</b></div><div><small>可增減股票曝險</small><b>${delta>=0?'+':''}${Math.round(delta).toLocaleString('zh-TW')}</b></div><div><small>單一股票上限</small><b>${singleCap.toFixed(0)}% · ${Math.round(largestAmt).toLocaleString('zh-TW')}</b></div></div><p>${esc(action)}。這只是 portfolio risk envelope；只有 Alpha Buy Gate 已通過的標的才有資格承接新增資金。</p>`;
    const state={total,equity,cash,largest,maxDd};savePortfolio(state);
  }

  function portfolioForm(){
    const p=loadPortfolio();
    return `<div class="engine-form"><label>可投資資產總額<input id="engineTotal" type="number" min="0" step="1000" value="${esc(p.total??'')}"></label><label>目前股票市值<input id="engineEquity" type="number" min="0" step="1000" value="${esc(p.equity??'')}"></label><label>目前現金<input id="engineCash" type="number" min="0" step="1000" value="${esc(p.cash??'')}"></label><label>最大單一股票市值<input id="engineLargest" type="number" min="0" step="1000" value="${esc(p.largest??'')}"></label><label>可接受最大回撤 %<input id="engineDrawdown" type="number" min="5" max="60" step="1" value="${esc(p.maxDd??20)}"></label></div><div class="engine-actions"><button class="secondary" id="engineCalc">計算風險額度</button><button class="secondary" id="engineClear">清除本機資料</button></div><div id="enginePortfolioResult" class="engine-result"></div><div class="engine-local">🔒 這些數字只存在你的瀏覽器 localStorage，不會上傳 GitHub，也不會寫進 Elephant 公開資料。</div>`;
  }

  function render(){
    const {engine,forecast,claims,journal,vintage}=DATA;
    const c=engine.confidence||{};
    const risk=engine.risk_budget||{};
    const g=risk.allocation_guardrails||{};
    const sc=journal.scorecard||{};
    const claimSummary=claims.summary||{};
    const researchCompanies=Object.entries(claimSummary.companies||{}).map(([k,v])=>`${k} ${v}`).join(' · ');
    const section=$('#decision-engine');
    section.innerHTML=`<div class="engine-shell">
      <article class="engine-hero"><span class="kicker">CLOSED-LOOP DECISION SYSTEM</span><h2>Elephant Decision Engine v1</h2><p>從「資料 → 狀態 → Forecast → Calibration → Risk Budget → Decision Journal → Outcome」形成閉環。研究文章只提供 context；官方 deterministic scores 與 Alpha Buy Gate 的權限邊界保持不變。</p><div class="engine-actions"><a class="secondary" href="data/vintages.db" download>下載 Vintage SQLite</a><a class="secondary" href="data/decision_journal.json" download>下載 Decision Journal</a><a class="secondary" href="data/forecast.json" download>下載 Forecast</a></div></article>
      <div class="engine-grid">${confidenceCard('Data Confidence',c.data_confidence,c.definitions?.data_confidence||'官方輸入完整度')}${confidenceCard('Model Confidence',c.model_confidence,c.definitions?.model_confidence||'歷史 calibration 品質')}${confidenceCard('Decision Confidence',c.decision_confidence,c.definitions?.decision_confidence||'資料 + 模型 + freshness')}</div>
      <article class="panel"><div class="panel-head"><div><span class="kicker">FORECAST / CALIBRATION</span><h2>1M / 3M / 6M / 12M 機率</h2><p class="sub">舊歷史仍是 revised-series reconstruction；真正 point-in-time calibration 從 Vintage DB 建立後開始累積。</p></div><span class="engine-badge">Model ${nfmt(forecast.model_confidence)}</span></div><div class="table-wrap"><table class="engine-table"><thead><tr><th>Dimension</th><th>1M</th><th>3M</th><th>6M</th><th>12M</th></tr></thead><tbody>${forecastRows(forecast)}</tbody></table></div></article>
      <div class="engine-layout"><article class="panel"><div class="panel-head"><div><span class="kicker">RISK BUDGET</span><h2>${esc(risk.posture||'—')}</h2></div><div class="big">${nfmt(risk.risk_score)}</div></div><div class="engine-grid"><div class="engine-card"><small>System equity budget</small><div class="big">${nfmt(g.target_equity_risk_budget_pct)}%</div></div><div class="engine-card"><small>Cash floor</small><div class="big">${nfmt(g.cash_floor_pct)}%</div></div><div class="engine-card"><small>Single-stock ceiling</small><div class="big">${nfmt(g.max_single_stock_pct)}%</div></div></div><p class="engine-muted">AI concentration penalty ${nfmt(g.concentration_penalty_points)} points。Macro 只決定風險 envelope，不會把 WATCH / VERIFY 自動升成 BUY。</p></article><article class="panel"><div class="panel-head"><div><span class="kicker">PRIVATE PORTFOLIO</span><h2>把風險預算換成你的部位</h2></div></div>${portfolioForm()}</article></div>
      <article class="panel"><div class="panel-head"><div><span class="kicker">STRESS ENGINE</span><h2>如果環境突然變差？</h2></div></div><div class="engine-scenarios">${scenarioCards(engine.scenarios)}</div></article>
      <div class="engine-layout"><article class="panel"><div class="panel-head"><div><span class="kicker">DECISION JOURNAL</span><h2>預測之後，必須驗結果</h2><p class="sub">Resolved ${sc.resolved_forecasts??0} · Hit rate ${sc.direction_hit_rate==null?'尚未成熟':pct(sc.direction_hit_rate)} · Brier ${sc.brier_score??'—'}</p></div></div><div class="engine-journal">${journalRows(journal)}</div></article><article class="panel"><div class="panel-head"><div><span class="kicker">POINT-IN-TIME</span><h2>Vintage Database</h2></div><span class="engine-badge good">${esc(vintage.integrity_check||'—')}</span></div><div class="engine-grid"><div class="engine-card"><small>Series</small><div class="big">${nfmt(vintage.series)}</div></div><div class="engine-card"><small>Observations</small><div class="big">${nfmt(vintage.total_observations)}</div></div><div class="engine-card"><small>Revisions</small><div class="big">${nfmt(vintage.revision_observations)}</div></div></div><p class="engine-muted">${esc(vintage.coverage_note||'')}</p></article></div>
      <article class="panel"><div class="panel-head"><div><span class="kicker">RESEARCH CLAIM ENGINE</span><h2>結構化 Claim Candidates</h2><p class="sub">${esc(researchCompanies)} · 共 ${nfmt(claimSummary.claims)} 筆。Metadata-derived，不假裝讀過未取得的全文。</p></div><span class="engine-badge">score influence = false</span></div><div class="engine-claims">${claimRows(claims.claims)}</div></article>
      <div class="engine-contract"><b>權限邊界：</b> Official data → deterministic Scores；Consultant research → context only；Macro → risk budget only；Alpha Buy Gate → 個股 action authority；Portfolio input → browser-local only；沒有自動交易。</div>
    </div>`;
    $('#engineCalc')?.addEventListener('click',calculatePortfolio);
    $('#engineClear')?.addEventListener('click',()=>{localStorage.removeItem(LOCAL_KEY);['#engineTotal','#engineEquity','#engineCash','#engineLargest'].forEach(id=>{if($(id))$(id).value=''});if($('#engineDrawdown'))$('#engineDrawdown').value=20;calculatePortfolio()});
    calculatePortfolio();
  }

  function installTab(){
    const nav=$('.tabs');if(!nav||$('#decision-engine'))return;
    const b=document.createElement('button');b.dataset.tab='decision-engine';b.textContent='Decision Engine';
    const researchBtn=nav.querySelector('[data-tab="research"]');nav.insertBefore(b,researchBtn||null);
    const section=document.createElement('section');section.id='decision-engine';section.className='tab';
    const research=$('#research');if(research)research.insertAdjacentElement('beforebegin',section);else document.querySelector('main.wrap')?.appendChild(section);
    b.addEventListener('click',()=>{
      document.querySelectorAll('.tabs button').forEach(x=>x.classList.toggle('active',x===b));
      document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x===section));
    });
  }

  async function init(){
    try{
      addStyle();installTab();const x=Date.now();
      const files=['decision_engine.json','forecast.json','research_claims.json','decision_journal.json','vintage_manifest.json','risk_budget.json'];
      const rows=await Promise.all(files.map(f=>fetch(`data/${f}?x=${x}`,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(`${f}: ${r.status}`);return r.json()})));
      DATA={engine:rows[0],forecast:rows[1],claims:rows[2],journal:rows[3],vintage:rows[4],risk:rows[5]};render();
    }catch(e){console.warn('Decision Engine unavailable',e);const s=$('#decision-engine');if(s)s.innerHTML=`<article class="notice"><strong>Decision Engine 尚未完成第一次 production build</strong><p>${esc(String(e))}</p></article>`}
  }
  init();
})();
