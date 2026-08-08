(()=>{
  let ndcChart=null, ndcData=null;
  const $=s=>document.querySelector(s);
  const fmt=v=>v==null?'—':Number(v).toLocaleString('zh-TW',{maximumFractionDigits:4});
  const labels={leading_no_trend:'領先指標（不含趨勢）',coincident_no_trend:'同時指標（不含趨勢）',lagging_no_trend:'落後指標（不含趨勢）',policy_score:'景氣燈號綜合分數',pmi:'PMI',nmi:'NMI',customs_exports:'海關出口值',export_order_diffusion:'外銷訂單動向指數',m1b:'M1B',unemployment_rate:'失業率',manufacturing_inventory:'製造業存貨價值',semiconductor_equipment_imports:'半導體設備進口'};

  function draw(){
    const sel=$('#leadingSelect'); if(!sel||!ndcData)return;
    const s=ndcData.series?.[sel.value]; if(!s)return;
    const canvas=$('#leadingChart');
    if(ndcChart)ndcChart.destroy();
    ndcChart=new Chart(canvas,{type:'line',data:{labels:s.data.map(x=>x[0]),datasets:[{label:s.name||labels[sel.value]||sel.value,data:s.data.map(x=>x[1]),borderWidth:2,pointRadius:s.data.length>48?0:2,tension:.18}]},options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{display:false}},scales:{x:{ticks:{maxTicksLimit:12}},y:{beginAtZero:false}}}});
    const unit=s.unit||'value';
    $('#leadingRows').innerHTML=[...s.data].reverse().slice(0,240).map(([p,v])=>`<tr><td>${p}</td><td>${fmt(v)}</td><td>${unit}</td></tr>`).join('');
  }

  async function loadNDC(){
    try{
      ndcData=await fetch(`data/ndc.json?x=${Date.now()}`,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(r.status);return r.json()});
      const sel=$('#leadingSelect'); if(!sel)return;
      const preferred=['leading_no_trend','coincident_no_trend','lagging_no_trend','policy_score','pmi','nmi','customs_exports','export_order_diffusion','m1b','unemployment_rate','manufacturing_inventory','semiconductor_equipment_imports'];
      const keys=[...preferred.filter(k=>ndcData.series?.[k]),...Object.keys(ndcData.series||{}).filter(k=>!preferred.includes(k))];
      sel.innerHTML=keys.map(k=>`<option value="${k}">${labels[k]||ndcData.series[k]?.name||k}</option>`).join('');
      sel.value=ndcData.series?.leading_no_trend?'leading_no_trend':keys[0];
      sel.onchange=draw;
      const sig=(ndcData.signals||[]).at(-1)||{};
      $('#ndcLatest').textContent=`最新資料 ${ndcData.latest_period||'—'} · 官方燈號 ${sig.signal||'—'} ${sig.score==null?'':sig.score+' 分'}`;
      draw();
    }catch(e){
      console.warn('NDC panel unavailable',e);
      if($('#ndcLatest'))$('#ndcLatest').textContent='國發會資料載入失敗';
    }
  }

  document.addEventListener('click',e=>{
    const chip=e.target.closest('.evidence-chip[title="NDC"]'); if(!chip)return;
    const text=chip.textContent||'';
    document.querySelector('.tabs button[data-tab="leading"]')?.click();
    setTimeout(()=>{
      const sel=$('#leadingSelect'); if(!sel)return;
      let key=text.includes('PMI')?'pmi':text.includes('同時')?'coincident_no_trend':text.includes('燈號')?'policy_score':'leading_no_trend';
      if([...sel.options].some(o=>o.value===key)){sel.value=key;sel.dispatchEvent(new Event('change'))}
      $('#leading')?.scrollIntoView({behavior:'smooth',block:'start'});
    },80);
  });

  loadNDC();
})();
