(()=>{
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const names={growth_persistence:'Growth Persistence',domestic_demand:'Domestic Demand',financial_conditions:'Financial Conditions'};
  const zh={growth_persistence:'成長延續性',domestic_demand:'內需強度',financial_conditions:'金融條件'};
  const tone=s=>s>=5?'positive':s<=-5?'negative':'neutral';
  const signed=v=>v==null?'—':`${Number(v)>=0?'+':''}${Number(v).toFixed(0)}`;
  let charts=[];
  function component(x){return `<div class="decision-component"><span>${esc(x.name)}</span><b>${Number(x.score)>=0?'+':''}${Number(x.score).toFixed(0)}</b><small>${esc(x.period)} · raw ${Number(x.raw).toLocaleString('zh-TW',{maximumFractionDigits:2})} · weight ${(Number(x.weight)*100).toFixed(0)}% · ${esc(x.note)} · ${esc(x.source)}</small></div>`}
  function card(key,x,idx){
    const width=Math.max(0,Math.min(100,(Number(x.score)+100)/2));
    return `<article class="decision-card ${tone(x.score)}"><div class="top"><div><div class="meta">${names[key]}</div><div class="label">${zh[key]}</div></div><div><div class="score">${signed(x.score)}</div><div class="meta">Confidence ${x.confidence}/100</div></div></div><div class="bar"><div class="fill" style="width:${width}%"></div></div><div class="meta">${esc(x.period)} · ${esc(x.label)}</div><details class="decision-components"><summary>查看 Score 元件</summary>${(x.components||[]).map(component).join('')}</details><div class="decision-history"><canvas id="decisionChart${idx}"></canvas></div></article>`;
  }
  function render(d){
    const anchor=document.querySelector('#elephantBrief')||document.querySelector('#headlineCards'); if(!anchor)return;
    document.querySelector('#decisionSuite')?.remove(); charts.forEach(c=>c.destroy()); charts=[];
    const current=d.current||{}; const keys=['growth_persistence','domestic_demand','financial_conditions'];
    const node=document.createElement('section'); node.id='decisionSuite'; node.className='decision-suite';
    node.innerHTML=`<div class="suite-head"><div><span class="kicker">DECISION SCORES</span><h2>現在強不強之外，還要看能不能延續</h2><p class="sub">三個 Score 都是透明規則式計算；缺值重新正規化權重並降低 Confidence。</p></div><div class="decision-sources"><a href="https://data.gov.tw/dataset/6845" target="_blank" rel="noopener">外銷訂單</a><a href="https://data.gov.tw/dataset/6842" target="_blank" rel="noopener">批零餐飲</a><a href="https://data.gov.tw/dataset/13228" target="_blank" rel="noopener">薪資／失業</a><a href="https://www.cbc.gov.tw/tw/lp-1046-1.html" target="_blank" rel="noopener">央行 M2</a></div></div><div class="decision-grid">${keys.map((k,i)=>current[k]?card(k,current[k],i):'').join('')}</div><p class="decision-note">Growth Persistence 看訂單→出口→生產→銷售→存貨；Domestic Demand 看零售／餐飲／薪資／就業；Financial Conditions 看 M1B、M2、信用、利率與市場風險偏好。</p>`;
    anchor.insertAdjacentElement('afterend',node);
    keys.forEach((k,i)=>{
      const rows=d.history?.[k]||[], canvas=document.querySelector(`#decisionChart${i}`); if(!canvas||!rows.length)return;
      const c=new Chart(canvas,{type:'line',data:{labels:rows.map(r=>r.period),datasets:[{data:rows.map(r=>r.score),label:zh[k],borderWidth:2,pointRadius:0,tension:.15}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{maxTicksLimit:5}},y:{min:-100,max:100,ticks:{maxTicksLimit:5}}}}}); charts.push(c);
    });
  }
  async function init(){try{const d=await fetch(`data/decision_scores.json?x=${Date.now()}`,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(r.status);return r.json()});render(d)}catch(e){console.warn('decision scores unavailable',e)}}
  init();
})();
