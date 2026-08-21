(()=>{
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[c]));
  const cfg={
    cycle:{name:'Cycle Score',question:'現在景氣強不強？'},
    growth_persistence:{name:'Growth Persistence',question:'這波景氣還能持續嗎？'},
    domestic_demand:{name:'Domestic Demand',question:'內需有沒有跟上？'},
    financial_conditions:{name:'Financial Conditions',question:'金融環境支不支持？'},
    ai_concentration:{name:'AI Concentration',question:'成長有多集中在 AI／電子鏈？',concentration:true}
  };
  const tone=s=>s>=5?'positive':s<=-5?'negative':'neutral';
  const concentrationTone=s=>s>=75?'concentration-high':s>=60?'concentration-elevated':s>=40?'neutral':'positive';
  const signed=v=>v==null?'—':`${Number(v)>=0?'+':''}${Number(v).toFixed(0)}`;
  let charts=[];

  function component(x,key){
    const raw=x.raw==null?'—':Number(x.raw).toLocaleString('zh-TW',{maximumFractionDigits:2});
    const source=x.source||'Elephant';
    const score=key==='ai_concentration'?Number(x.score).toFixed(0):signed(x.score);
    return `<div class="decision-component"><span>${esc(x.name)}</span><b>${score}</b><small>${esc(x.period||'—')} · raw ${raw} · weight ${(Number(x.weight||0)*100).toFixed(0)}% · ${esc(x.note||'')} · ${esc(source)}</small></div>`;
  }

  function scoreAxis(isConcentration){
    return isConcentration
      ? `<div class="bar-axis concentration-axis"><span>0 分散</span><span>60 偏高 · 75 高度</span><span>100 集中</span></div>`
      : `<div class="bar-axis"><span>-100 負向</span><span>0 中性</span><span>+100 正向</span></div>`;
  }

  function card(key,x,idx,hasHistory){
    const isConcentration=!!cfg[key].concentration;
    const width=Math.max(0,Math.min(100,isConcentration?Number(x.score):(Number(x.score)+100)/2));
    const confidence=x.confidence==null?'—':`${Number(x.confidence).toFixed(0)}/100`;
    const confidenceLabel=key==='cycle'?'Data confidence':'Input coverage';
    const history=hasHistory?`<div class="decision-history"><canvas id="decisionChart${idx}"></canvas></div>`:`<div class="decision-history-placeholder">完整 Cycle 歷史請看「情報歷史」</div>`;
    const cls=isConcentration?concentrationTone(Number(x.score)):tone(x.score);
    const score=isConcentration?(x.score==null?'—':Number(x.score).toFixed(0)):signed(x.score);
    const meaning=isConcentration?'<div class="concentration-meaning">0 = 分散；60 起偏高集中；75 起高度集中。高分不是「更好」，而是成長來源更集中。</div>':'<div class="direction-meaning">負值 = 壓制／轉弱；0 = 中性；正值 = 支持／轉強。Bar 的 50% 位置就是 0，不是「得分 50」。</div>';
    const thresholdTicks=isConcentration?'<i class="bar-threshold t60" aria-hidden="true"></i><i class="bar-threshold t75" aria-hidden="true"></i>':'<i class="bar-neutral" aria-hidden="true"></i>';
    return `<article class="decision-card ${cls}"><div class="top"><div><div class="meta">${esc(cfg[key].name)}</div><div class="label">${esc(cfg[key].question)}</div></div><div><div class="score">${score}</div><div class="meta">${confidenceLabel} ${confidence}</div></div></div><div class="bar ${isConcentration?'concentration-bar':'direction-bar'}"><div class="fill" style="width:${width}%"></div>${thresholdTicks}</div>${scoreAxis(isConcentration)}<div class="meta">${esc(x.period||'—')} · ${esc(x.label||'')}</div>${meaning}<details class="decision-components"><summary>查看 Score 元件</summary>${(x.components||[]).map(c=>component(c,key)).join('')}</details>${history}</article>`;
  }

  function cycleView(summary){
    const c=summary?.cycle;
    if(!c)return null;
    return {period:c.as_of,score:c.score,label:c.label,confidence:summary?.confidence?.score,components:c.components||[]};
  }

  function render(d,summary){
    const anchor=document.querySelector('#elephantBrief')||document.querySelector('#headlineCards');
    if(!anchor)return;
    document.querySelector('#decisionSuite')?.remove();
    charts.forEach(c=>c.destroy()); charts=[];

    const current={cycle:cycleView(summary),...(d.current||{})};
    const keys=['cycle','growth_persistence','domestic_demand','financial_conditions','ai_concentration'];
    const node=document.createElement('section');
    node.id='decisionSuite'; node.className='decision-suite';
    node.innerHTML=`<div class="suite-head"><div><span class="kicker">FIVE-LAYER DIAGNOSIS</span><h2>台灣景氣，不只看一個分數</h2><p class="sub">Cycle 看現在強不強；Growth 看能不能持續；Domestic 看內需；Financial 看資金環境；AI Concentration 看成長是否過度集中在 AI／電子鏈。</p></div><div class="decision-sources"><a href="https://data.gov.tw/dataset/6845" target="_blank" rel="noopener">外銷訂單</a><a href="https://data.gov.tw/dataset/8380" target="_blank" rel="noopener">主要貨品出口</a><a href="https://data.gov.tw/dataset/25364" target="_blank" rel="noopener">信用卡消費</a><a href="https://www.cbc.gov.tw/tw/cp-532-104915-d9972-1.html" target="_blank" rel="noopener">央行金融統計</a></div></div><div class="decision-grid">${keys.map((k,i)=>current[k]?card(k,current[k],i,k!=='cycle'):'').join('')}</div><p class="decision-note">Growth / Domestic / Financial 是 -100～+100 的方向分數：0 是中性，不是 50 分。AI Concentration 是 0～100 的集中度指數：電子訂單 → AI 核心出口 → 資訊電子生產 → 非電子 breadth；高分代表更集中，不代表景氣本身更好。Cycle 的 Data confidence 與其餘卡片的 Input coverage 都不是「未來發生機率」；真正 Model / Decision Confidence 另在 Decision Engine 驗證層。缺值只重新正規化可用權重並降低 coverage。</p>`;
    anchor.insertAdjacentElement('afterend',node);

    ['growth_persistence','domestic_demand','financial_conditions','ai_concentration'].forEach((k,j)=>{
      const idx=j+1,rows=d.history?.[k]||[],canvas=document.querySelector(`#decisionChart${idx}`);
      if(!canvas||!rows.length)return;
      const conc=k==='ai_concentration';
      const guide=conc?[{value:60,label:'60 偏高集中'},{value:75,label:'75 高度集中'}]:[{value:0,label:'0 中性'}];
      const c=new Chart(canvas,{type:'line',data:{labels:rows.map(r=>r.period),datasets:[{data:rows.map(r=>r.score),label:cfg[k].name,borderWidth:2,pointRadius:0,tension:0}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},semanticGuide:{lines:guide}},scales:{x:{ticks:{maxTicksLimit:5}},y:conc?{min:0,max:100,title:{display:true,text:'集中度 0…100'},ticks:{maxTicksLimit:5}}:{min:-100,max:100,title:{display:true,text:'方向分數 -100…+100'},ticks:{maxTicksLimit:5}}}}});
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

  if(!document.querySelector('script[data-elephant-intelligence]')){
    const s=document.createElement('script');
    s.src='intelligence.js'; s.defer=true; s.dataset.elephantIntelligence='1';
    document.head.appendChild(s);
  }

  if(!document.querySelector('script[data-elephant-decision-engine]')){
    const s=document.createElement('script');
    s.src='decision_engine.js'; s.defer=true; s.dataset.elephantDecisionEngine='1';
    document.head.appendChild(s);
  }

  if(!document.querySelector('script[data-elephant-validation]')){
    const s=document.createElement('script');
    s.src='decision_validation.js'; s.defer=true; s.dataset.elephantValidation='1';
    document.head.appendChild(s);
  }

  if(!document.querySelector('script[data-elephant-validation-os]')){
    const s=document.createElement('script');
    s.src='validation_os.js'; s.defer=true; s.dataset.elephantValidationOs='1';
    document.head.appendChild(s);
  }

  // Capital v3 is a browser-local private optimizer. It consumes only public model
  // artifacts; personal holdings/debt never enter GitHub or any server workflow.
  if(!document.querySelector('script[data-elephant-personal-capital]')){
    const l=document.createElement('link');l.rel='stylesheet';l.href='personal_capital.css';l.dataset.elephantPersonalCapitalStyle='1';document.head.appendChild(l);
    const s=document.createElement('script');s.src='personal_capital.js';s.defer=true;s.dataset.elephantPersonalCapital='1';document.head.appendChild(s);
  }
})();
