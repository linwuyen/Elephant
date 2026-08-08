(()=>{
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const sign=v=>v==null?'—':`${v>=0?'+':''}${Number(v).toFixed(1)}%`;
  const tone=l=>['positive','warning','neutral'].includes(l)?l:'neutral';
  function movers(title,rows,kind){
    if(!rows?.length)return '';
    return `<div class="brief-movers"><div class="brief-mini-title">${esc(title)}</div>${rows.slice(0,4).map(x=>`<div class="mover ${kind}"><span>${esc(x.name)}</span><b>${sign(x.yoy)}</b><small>${esc(x.period)}</small></div>`).join('')}</div>`;
  }
  function render(s){
    const cards=document.querySelector('#headlineCards');
    if(!cards)return;
    document.querySelector('#elephantBrief')?.remove();
    const generated=s.generated_at?new Date(s.generated_at).toLocaleString('zh-TW',{timeZone:'Asia/Taipei'}):'—';
    const takeaways=(s.takeaways||[]).map((x,i)=>`<article class="brief-point ${tone(x.level)}"><div class="brief-index">0${i+1}</div><div><h3>${esc(x.title)}</h3><p>${esc(x.text)}</p>${x.evidence?.length?`<div class="brief-evidence">${x.evidence.map(e=>`<span>${esc(e)}</span>`).join('')}</div>`:''}</div></article>`).join('');
    const breadth=s.industry?.positive_breadth_pct;
    const extra=`<div class="brief-stats"><div><span>產業正成長廣度</span><b>${breadth==null?'—':Number(breadth).toFixed(0)+'%'}</b></div><div><span>人口年變化</span><b>${sign(s.population?.yoy_pct)}</b></div><div><span>65+ 占比</span><b>${s.population?.share_65_plus==null?'—':Number(s.population.share_65_plus).toFixed(2)+'%'}</b></div></div>`;
    const node=document.createElement('section');node.id='elephantBrief';node.className='analysis-brief';
    node.innerHTML=`<div class="brief-head"><div><span class="kicker">ELEPHANT BRIEF</span><h2>目前最值得注意的事</h2><p class="brief-stance">${esc(s.stance||s.headline||'摘要資料準備中')}</p></div><div class="brief-time">根據最新資料自動判讀<br><b>${esc(generated)}</b></div></div>${extra}<div class="brief-grid">${takeaways}</div><div class="brief-bottom">${movers('最新月度最強產業',s.industry?.top_yoy,'up')}${movers('最新月度較弱產業',s.industry?.weak_yoy,'down')}</div>${s.warnings?.length?`<details class="brief-warnings"><summary>資料注意事項 ${s.warnings.length}</summary>${s.warnings.map(w=>`<p>${esc(w)}</p>`).join('')}</details>`:''}<div class="brief-method">${esc(s.methodology||'')}</div>`;
    cards.insertAdjacentElement('afterend',node);
  }
  async function init(){
    try{
      const s=await fetch(`data/summary.json?x=${Date.now()}`,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(`summary ${r.status}`);return r.json()});
      render(s);
    }catch(e){
      console.warn('Elephant summary unavailable',e);
      const cards=document.querySelector('#headlineCards');if(!cards)return;
      const node=document.createElement('section');node.id='elephantBrief';node.className='analysis-brief brief-unavailable';node.innerHTML='<b>經濟摘要正在建立</b><span>圖表與原始資料仍可正常使用。</span>';cards.insertAdjacentElement('afterend',node);
    }
  }
  init();
})();
