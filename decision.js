(()=>{
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const cfg={
    cycle:{name:'Cycle Score',question:'現在景氣強不強？'},
    growth_persistence:{name:'Growth Persistence',question:'這波景氣還能持續嗎？'},
    domestic_demand:{name:'Domestic Demand',question:'內需有沒有跟上？'},
    financial_conditions:{name:'Financial Conditions',question:'金融環境支不支持？'}
  };
  const tone=s=>s>=5?'positive':s<=-5?'negative':'neutral';
  const signed=v=>v==null?'—':`${Number(v)>=0?'+':''}${Number(v).toFixed(0)}`;
  let charts=[];

  function component(x){
    const raw=x.raw==null?'—':Number(x.raw).toLocaleString('zh-TW',{maximumFractionDigits:2});
    const source=x.source||'Elephant';
    return `<div class="decision-component"><span>${esc(x.name)}</span><b>${signed(x.score)}</b><small>${esc(x.period||'—')} · raw ${raw} · weight ${(Number(x.weight||0)*100).toFixed(0)}% · ${esc(x.note||'')} · ${esc(source)}</small></div>`;
  }

  function card(key,x,idx,hasHistory){
    const width=Math.max(0,Math.min(100,(Number(x.score)+100)/2));
    const confidence=x.confidence==null?'—':`${Number(x.confidence).toFixed(0)}/100`;
    const history=hasHistory?`<div class="decision-history"><canvas id="decisionChart${idx}"></canvas></div>`:`<div class="decision-history-placeholder">完整 Cycle 歷史請看「情報歷史」</div>`;
    return `<article class="decision-card ${tone(x.score)}"><div class="top"><div><div class="meta">${esc(cfg[key].name)}</div><div class="label">${esc(cfg[key].question)}</div></div><div><div class="score">${signed(x.score)}</div><div class="meta">Confidence ${confidence}</div></div></div><div class="bar"><div class="fill" style="width:${width}%"></div></div><div class="meta">${esc(x.period||'—')} · ${esc(x.label||'')}</div><details class="decision-components"><summary>查看 Score 元件</summary>${(x.components||[]).map(component).join('')}</details>${history}</article>`;
  }

  function cycleView(summary){
    const c=summary?.cycle;
    if(!c)return null;
    return {
      period:c.as_of,
      score:c.score,
      label:c.label,
      confidence:summary?.confidence?.score,
      components:c.components||[]
    };
  }

  function render(d,summary){
    const anchor=document.querySelector('#elephantBrief')||document.querySelector('#headlineCards');
    if(!anchor)return;
    document.querySelector('#decisionSuite')?.remove();
    charts.forEach(c=>c.destroy()); charts=[];

    const current={cycle:cycleView(summary),...(d.current||{})};
    const keys=['cycle','growth_persistence','domestic_demand','financial_conditions'];
    const node=document.createElement('section');
    node.id='decisionSuite'; node.className='decision-suite';
    node.innerHTML=`<div class="suite-head"><div><span class="kicker">FOUR-LAYER DIAGNOSIS</span><h2>台灣景氣，不只看一個分數</h2><p class="sub">Cycle 看現在強不強；Growth 看能不能持續；Domestic 看一般人的內需有沒有跟上；Financial 看資金環境是否支援。</p></div><div class="decision-sources"><a href="https://data.gov.tw/dataset/6845" target="_blank" rel="noopener">外銷訂單</a><a href="https://data.gov.tw/dataset/25364" target="_blank" rel="noopener">信用卡消費</a><a href="https://www.cbc.gov.tw/tw/cp-532-104915-d9972-1.html" target="_blank" rel="noopener">央行金融統計</a></div></div><div class="decision-grid">${keys.map((k,i)=>current[k]?card(k,current[k],i,k!=='cycle'):'').join('')}</div><p class="decision-note">Growth：外銷訂單 → 出口 → 生產 → 銷售 → 庫存；Domestic：實質薪資 → 就業 → 零售 → 餐飲 → 信用卡消費；Financial：M1B → M2 → 銀行信用 → 利率 → 匯率。所有 Decision Score 均為 -100～+100 的透明規則式分數，缺值只重新正規化可用權重並降低 Confidence。</p>`;
    anchor.insertAdjacentElement('afterend',node);

    ['growth_persistence','domestic_demand','financial_conditions'].forEach((k,j)=>{
      const idx=j+1,rows=d.history?.[k]||[],canvas=document.querySelector(`#decisionChart${idx}`);
      if(!canvas||!rows.length)return;
      const c=new Chart(canvas,{type:'line',data:{labels:rows.map(r=>r.period),datasets:[{data:rows.map(r=>r.score),label:cfg[k].name,borderWidth:2,pointRadius:0,tension:.15}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{maxTicksLimit:5}},y:{min:-100,max:100,ticks:{maxTicksLimit:5}}}}});
      charts.push(c);
    });
  }

  async function init(){
    try{
      const x=Date.now();
      const [d,summary]=await Promise.all([
        fetch(`data/decision_scores.json?x=${x}`,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(r.status);return r.json()}),
        fetch(`data/summary.json?x=${x}`,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(r.status);return r.json()})
      ]);
      render(d,summary);
    }catch(e){console.warn('decision scores unavailable',e)}
  }
  init();
})();
