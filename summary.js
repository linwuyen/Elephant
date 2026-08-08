(()=>{
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const sign=(v,d=1,suffix='%')=>v==null?'—':`${Number(v)>=0?'+':''}${Number(v).toFixed(d)}${suffix}`;
  const tone=l=>['positive','warning','neutral','major','watch','info'].includes(l)?l:'neutral';

  function jump(t){
    if(!t?.tab)return;
    document.querySelector(`.tabs button[data-tab="${CSS.escape(t.tab)}"]`)?.click();
    setTimeout(()=>{
      if(t.tab==='industry'){
        const ds=document.querySelector('#industryDataset'), ss=document.querySelector('#industrySeries');
        if(ds&&t.dataset&&[...ds.options].some(o=>o.value===t.dataset)){
          ds.value=t.dataset; ds.dispatchEvent(new Event('change'));
          setTimeout(()=>{if(ss&&t.series&&[...ss.options].some(o=>o.value===t.series)){ss.value=t.series;ss.dispatchEvent(new Event('change'))}},30);
        }
      }else if(t.tab==='macro'&&t.series){
        const s=document.querySelector('#macroSelect');if(s&&[...s.options].some(o=>o.value===t.series)){s.value=t.series;s.dispatchEvent(new Event('change'))}
      }else if(t.tab==='population'&&t.series){
        const s=document.querySelector('#popSelect');if(s&&[...s.options].some(o=>o.value===t.series)){s.value=t.series;s.dispatchEvent(new Event('change'))}
      }
      document.querySelector(`#${CSS.escape(t.tab)}`)?.scrollIntoView({behavior:'smooth',block:'start'});
    },60);
  }

  function evidenceChip(e){
    if(typeof e==='string')return `<span>${esc(e)}</span>`;
    const label=`${e.label||''}${e.value?` · ${e.value}`:''}${e.period?` · ${e.period}`:''}`;
    const t=e.target?.tab?` data-target='${esc(JSON.stringify(e.target))}'`:'';
    return `<button class="evidence-chip"${t} title="${esc(e.source||'')}">${esc(label)}</button>`;
  }

  function movers(title,rows,kind){
    if(!rows?.length)return '';
    return `<div class="brief-movers"><div class="brief-mini-title">${esc(title)}</div>${rows.slice(0,5).map(x=>`<div class="mover ${kind}"><span>${esc(x.name)}</span><b>${sign(x.yoy)}</b><small>${esc(x.period)}</small></div>`).join('')}</div>`;
  }

  function changeSummary(s){
    const box={state:'first',items:[]};
    let prev=null;
    try{prev=JSON.parse(localStorage.getItem('elephant.lastSnapshot.v2')||'null')}catch(_){}
    const cur=s.snapshot;
    if(!cur?.fingerprint)return box;
    if(!prev?.fingerprint){
      box.state='first';box.text='首次造訪：已建立這次資料快照，下一次有實質資料變動時會直接告訴你差異。';
    }else if(prev.fingerprint===cur.fingerprint){
      box.state='same';box.text='自上次造訪後沒有實質指標變化；最新官方資料版本與你上次看到的相同。';
    }else{
      const a=prev.metrics||{},b=cur.metrics||{},rows=[];
      for(const [k,n] of Object.entries(b)){
        const o=a[k];if(!o||o.value==null||n.value==null)continue;
        const d=Number(n.value)-Number(o.value);
        const threshold=n.unit==='score'?2:(n.unit==='percent'?0.3:0.3);
        if(Math.abs(d)<threshold)continue;
        const scale=n.unit==='score'?15:(n.unit==='percent'?3:5);
        rows.push({label:n.label,old:o.value,new:n.value,delta:d,unit:n.unit,weight:Math.abs(d)/scale});
      }
      rows.sort((x,y)=>y.weight-x.weight);
      box.state='changed';box.items=rows.slice(0,5);
      box.text=rows.length?'你上次查看後，以下指標出現最明顯變化。':'資料版本已更新，但核心摘要指標變動幅度很小。';
    }
    try{localStorage.setItem('elephant.lastSnapshot.v2',JSON.stringify(cur))}catch(_){}
    return box;
  }

  function renderChanges(c){
    const items=c.items?.map(x=>{
      const suffix=x.unit==='percent'?' 個百分點':x.unit==='score'?' 分':'';
      return `<div class="visit-change"><span>${esc(x.label)}</span><small>${Number(x.old).toFixed(1)} → ${Number(x.new).toFixed(1)}</small><b class="${x.delta>=0?'up':'down'}">${sign(x.delta,1,suffix)}</b></div>`;
    }).join('')||'';
    return `<div class="since-visit ${esc(c.state)}"><div class="brief-mini-title">SINCE YOUR LAST VISIT</div><p>${esc(c.text||'')}</p>${items}</div>`;
  }

  function renderScore(s){
    const c=s.cycle||{}, lead=s.leading||{}, cf=s.confidence||{}, sig=lead.policy_signal||{};
    return `<div class="intel-score-grid">
      <div class="score-main"><span>ELEPHANT CYCLE SCORE</span><b>${c.score==null?'—':`${Number(c.score)>=0?'+':''}${Number(c.score).toFixed(0)}`}</b><strong>${esc(c.label||'—')}</strong><small>自訂透明分數，不等同官方燈號</small></div>
      <div><span>Momentum</span><b>${esc(c.momentum||'—')}</b><small>${c.momentum_score==null?'—':sign(c.momentum_score,0,'')}</small></div>
      <div><span>Breadth</span><b>${c.breadth==null?'—':Number(c.breadth).toFixed(0)+'%'}</b><small>${c.breadth_delta_ppt==null?'前月無比較':`vs 前月 ${sign(c.breadth_delta_ppt,1,' ppt')}`}</small></div>
      <div><span>Leading</span><b>${esc(lead.outlook||'—')}</b><small>${lead.leading_3m_pct==null?'—':`3M ${sign(lead.leading_3m_pct,2)}`}</small></div>
      <div><span>Official signal</span><b>${esc(sig.signal||'—')}</b><small>${sig.score==null?'—':`${sig.period||''} · ${sig.score} 分`}</small></div>
      <div><span>Confidence</span><b>${esc(cf.label||'—')}</b><small>${cf.score==null?'—':`${cf.score}/100`}</small></div>
    </div>`;
  }

  function renderAlerts(rows){
    if(!rows?.length)return '';
    return `<div class="intel-block"><div class="intel-title"><span>WHAT MATTERS NOW</span><b>重大性過濾</b></div><div class="alert-list">${rows.map(x=>`<article class="intel-alert ${tone(x.level)}"><span>${x.level==='major'?'重大':x.level==='watch'?'注意':'資訊'}</span><div><b>${esc(x.title)}</b><p>${esc(x.text)}</p></div><strong>${x.score==null?'':Number(x.score).toFixed(0)}</strong></article>`).join('')}</div></div>`;
  }

  function renderTurning(rows){
    if(!rows?.length)return '';
    const label={recovery_cross:'負轉正',downturn_cross:'正轉負',contraction_easing:'收縮收斂',expansion_fading:'擴張降速',accelerating:'加速',decelerating:'減速'};
    return `<div class="intel-block"><div class="intel-title"><span>TURNING POINTS</span><b>轉折偵測</b></div><div class="turn-grid">${rows.slice(0,6).map(x=>`<div class="turn-card ${x.level}"><small>${esc(x.period)}</small><b>${esc(x.name)}</b><span>${esc(label[x.turn]||x.signal||'動能變化')}</span><p>YoY ${sign(x.yoy)} · Δ ${sign(x.acceleration_ppt,1,' ppt')}</p><em>12M percentile ${x.yoy_percentile_12m==null?'—':Number(x.yoy_percentile_12m).toFixed(0)+'%'}</em></div>`).join('')}</div></div>`;
  }

  function renderDivergences(rows){
    if(!rows?.length)return '';
    return `<div class="intel-block"><div class="intel-title"><span>DIVERGENCES</span><b>值得注意的背離</b></div><div class="div-grid">${rows.map(x=>`<button class="div-card" data-target='${x.target?esc(JSON.stringify(x.target)):''}'><span>${esc(x.direction)}</span><b>${esc(x.title)}</b><p>${esc(x.text)}</p><small>差距 ${sign(x.value,1,' '+(x.unit||''))}</small></button>`).join('')}</div></div>`;
  }

  function renderWatchlist(rows){
    if(!rows?.length)return '';
    return `<div class="intel-block watch-block"><div class="intel-title"><span>NEXT WATCH</span><b>接下來看什麼</b></div><ol>${rows.map(x=>`<li>${esc(x)}</li>`).join('')}</ol></div>`;
  }

  function renderRevisions(r){
    const rows=r?.new||[];
    if(!rows.length)return `<div class="revision-note">本次沒有偵測到官方歷史數值修正；累計已記錄 ${Number(r?.history_count||0).toLocaleString()} 筆 revision。</div>`;
    return `<details class="revision-note"><summary>本次偵測到 ${rows.length} 筆官方歷史修正</summary>${rows.slice(0,10).map(x=>`<p><b>${esc(x.source)} · ${esc(x.series)} · ${esc(x.period)}</b> ${Number(x.old).toLocaleString()} → ${Number(x.new).toLocaleString()}</p>`).join('')}</details>`;
  }

  function render(s){
    const cards=document.querySelector('#headlineCards');if(!cards)return;
    document.querySelector('#elephantBrief')?.remove();
    const generated=s.generated_at?new Date(s.generated_at).toLocaleString('zh-TW',{timeZone:'Asia/Taipei'}):'—';
    const changes=changeSummary(s);
    const takeaways=(s.takeaways||[]).map((x,i)=>`<article class="brief-point ${tone(x.level)}"><div class="brief-index">0${i+1}</div><div><h3>${esc(x.title)}</h3><p>${esc(x.text)}</p>${x.evidence?.length?`<div class="brief-evidence">${x.evidence.map(evidenceChip).join('')}</div>`:''}</div></article>`).join('');
    const node=document.createElement('section');node.id='elephantBrief';node.className='analysis-brief intelligence-v2';
    node.innerHTML=`<div class="brief-head"><div><span class="kicker">ELEPHANT ECONOMIC INTELLIGENCE</span><h2>30 秒掌握台灣經濟</h2><p class="brief-stance">${esc(s.stance||s.headline||'摘要資料準備中')}</p></div><div class="brief-time">資料更新後自動重算<br><b>${esc(generated)}</b></div></div>
      ${renderScore(s)}
      ${renderChanges(changes)}
      ${renderAlerts(s.alerts)}
      <div class="brief-grid">${takeaways}</div>
      ${renderTurning(s.turning_points)}
      ${renderDivergences(s.divergences)}
      ${renderWatchlist(s.watchlist)}
      <div class="brief-bottom">${movers('最新月度最強產業',s.industry?.top_yoy,'up')}${movers('最新月度較弱產業',s.industry?.weak_yoy,'down')}</div>
      ${renderRevisions(s.revisions)}
      ${s.warnings?.length?`<details class="brief-warnings"><summary>資料注意事項 ${s.warnings.length}</summary>${s.warnings.map(w=>`<p>${esc(w)}</p>`).join('')}</details>`:''}
      <details class="brief-method"><summary>方法與 Cycle Score 元件</summary><p>${esc(s.methodology||'')}</p>${(s.cycle?.components||[]).map(x=>`<div class="component"><span>${esc(x.name)}</span><b>${Number(x.score).toFixed(0)}</b><small>weight ${(Number(x.weight)*100).toFixed(0)}% · ${esc(x.note||'')}</small></div>`).join('')}</details>`;
    cards.insertAdjacentElement('afterend',node);
    node.querySelectorAll('[data-target]').forEach(el=>el.addEventListener('click',()=>{
      try{const t=JSON.parse(el.dataset.target);jump(t)}catch(_){}
    }));
  }

  async function init(){
    try{
      const s=await fetch(`data/summary.json?x=${Date.now()}`,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(`summary ${r.status}`);return r.json()});
      render(s);
      setTimeout(()=>document.querySelectorAll('.source .top b').forEach(b=>{if(b.textContent.trim()==='ndc')b.textContent='國發會'}),250);
    }catch(e){
      console.warn('Elephant summary unavailable',e);
      const cards=document.querySelector('#headlineCards');if(!cards)return;
      const node=document.createElement('section');node.id='elephantBrief';node.className='analysis-brief brief-unavailable';node.innerHTML='<b>經濟情報摘要正在建立</b><span>圖表與原始資料仍可正常使用。</span>';cards.insertAdjacentElement('afterend',node);
    }
  }
  init();
})();
