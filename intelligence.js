(()=>{
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const names={growth_persistence:'Growth Persistence',domestic_demand:'Domestic Demand',financial_conditions:'Financial Conditions',ai_concentration:'AI Concentration'};
  const zh={growth_persistence:'景氣延續性',domestic_demand:'內需',financial_conditions:'金融條件',ai_concentration:'AI／電子集中度'};

  if(!document.querySelector('link[data-intelligence-css]')){
    const l=document.createElement('link');l.rel='stylesheet';l.href='intelligence.css';l.dataset.intelligenceCss='1';document.head.appendChild(l);
  }

  function reportRow(r){
    return `<a class="intel-research-row" href="${esc(r.url)}" target="_blank" rel="noopener"><span class="firm">${esc(r.company)}</span><div><b>${esc(r.title)}</b><small>${esc(r.date||'—')} · relevance ${esc(r.relevance)}</small></div></a>`;
  }

  function bucket(title,rows,cls,empty){
    return `<div class="intel-context-bucket ${cls}"><div class="bucket-title">${esc(title)} <span>${(rows||[]).length}</span></div>${rows?.length?rows.map(reportRow).join(''):`<p class="empty">${esc(empty)}</p>`}</div>`;
  }

  function scoreText(key,o){
    if(!o||o.score==null)return '—';
    return key==='ai_concentration'?Number(o.score).toFixed(0):`${Number(o.score)>=0?'+':''}${Number(o.score).toFixed(0)}`;
  }

  function officialEvidence(o){
    const rows=o?.components||[];
    if(!rows.length)return '<p class="empty">官方元件暫不可用。</p>';
    return `<div class="official-evidence">${rows.slice(0,6).map(x=>`<div><span>${esc(x.name)}</span><b>${x.raw==null?'—':Number(x.raw).toLocaleString('zh-TW',{maximumFractionDigits:2})}</b><small>${esc(x.period||'—')} · ${esc(x.source||'')}</small></div>`).join('')}</div>`;
  }

  function card(key,d){
    const o=d.official||{};
    const highConc=key==='ai_concentration'&&Number(o.score)>=60;
    return `<article class="intel-dimension ${highConc?'concentrated':''}">
      <div class="dimension-head"><div><span class="kicker">${esc(names[key])}</span><h3>${esc(zh[key])}</h3><p>${esc(d.question||'')}</p></div><div class="dimension-score"><b>${scoreText(key,o)}</b><span>${esc(o.label||'—')}</span><small>Confidence ${o.confidence==null?'—':Number(o.confidence).toFixed(0)}/100</small></div></div>
      <p class="dimension-brief">${esc(d.brief||'')}</p>
      <div class="change-strip ${esc(d.what_changed?.state||'stable')}"><b>WHAT CHANGED</b><span>${esc(d.what_changed?.text||'—')}</span></div>
      <details class="official-detail"><summary>官方數據 Evidence</summary>${officialEvidence(o)}</details>
      <div class="context-grid">
        ${bucket('RESEARCH EVIDENCE',d.evidence,'evidence','目前沒有高相關研究 context。')}
        ${bucket('CONTRADICTIONS',d.contradictions,'contradiction','目前沒有明確反例。')}
        ${bucket('RISKS',d.risks,'risk','目前沒有額外風險研究。')}
      </div>
      <div class="dimension-foot"><span>${Number(d.research_count||0).toLocaleString()} related · ${(d.companies||[]).map(esc).join(' / ')||'—'}</span><button class="secondary open-research" data-dimension="${esc(key)}">打開顧問研究</button></div>
    </article>`;
  }

  function render(data){
    document.querySelector('#intelligenceLayer')?.remove();
    const dims=data.dimensions||{};
    const ex=data.executive_brief||{};
    const node=document.createElement('section');node.id='intelligenceLayer';node.className='intelligence-layer';
    node.innerHTML=`<div class="intel-layer-head"><div><span class="kicker">ELEPHANT INTELLIGENCE LAYER v1</span><h2>官方 Evidence × 全球顧問 Research Context</h2><p class="intel-headline">${esc(ex.headline||'')}</p><p>${esc(ex.interpretation||'')}</p><small>${esc(ex.research_context||'')}</small></div><div class="context-contract"><b>CONTEXT ONLY</b><span>顧問研究不改變 Score</span><small>${esc(data.classification||'')}</small></div></div>
      <div class="intel-dimension-grid">${Object.keys(names).map(k=>dims[k]?card(k,dims[k]):'').join('')}</div>
      <div class="global-risk"><div><span class="kicker">CROSS-DIMENSION RISKS</span><h3>目前最值得另外閱讀的外部風險</h3></div><div class="global-risk-list">${(ex.key_risks||[]).length?(ex.key_risks||[]).map(reportRow).join(''):'<p class="empty">目前沒有足夠高相關風險研究。</p>'}</div></div>`;
    const anchor=document.querySelector('#decisionSuite')||document.querySelector('#elephantBrief')||document.querySelector('#headlineCards');
    anchor?.insertAdjacentElement('afterend',node);
    node.querySelectorAll('.open-research').forEach(b=>b.addEventListener('click',()=>{
      document.querySelector('.tabs button[data-tab="research"]')?.click();
      setTimeout(()=>document.querySelector('#research')?.scrollIntoView({behavior:'smooth',block:'start'}),80);
    }));
  }

  async function init(){
    try{
      const data=await fetch(`data/intelligence_layer.json?x=${Date.now()}`,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(`intelligence ${r.status}`);return r.json()});
      // decision.js may still be rendering its asynchronous score suite. Wait briefly
      // so this layer lands immediately after the five-score diagnosis.
      let tries=0;
      const mount=()=>{if(document.querySelector('#decisionSuite')||tries++>20){render(data);return}setTimeout(mount,100)};
      mount();
    }catch(e){console.warn('Intelligence Layer unavailable',e)}
  }
  init();
})();
