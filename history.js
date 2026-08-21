(()=>{
  let hist=null, chart=null;
  const $=s=>document.querySelector(s);
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt=v=>v==null?'—':Number(v).toLocaleString('zh-TW',{maximumFractionDigits:2});
  const sign=(v,s='')=>v==null?'—':`${Number(v)>=0?'+':''}${Number(v).toFixed(1)}${s}`;

  function setMeaning(){const canvas=$('#cycleHistoryChart'),wrap=canvas?.closest('.chart');if(!wrap)return;let p=wrap.nextElementSibling;if(!p||!p.classList.contains('chart-meaning')){p=document.createElement('p');p.className='chart-meaning';wrap.insertAdjacentElement('afterend',p)}p.textContent='Cycle Score 與 Momentum 都在 -100～+100 的同一標準化方向尺度；0 是中性基準。這是用目前修訂後官方序列重建的歷史比較，不是當時可取得資料的 real-time backtest。';}
  function draw(){
    if(!hist)return;
    const rows=hist.cycle_history||[];
    const ctx=$('#cycleHistoryChart'); if(!ctx)return;
    if(chart)chart.destroy();
    chart=new Chart(ctx,{type:'line',data:{labels:rows.map(x=>x.period),datasets:[
      {label:'Cycle Score',data:rows.map(x=>x.score),borderWidth:2,pointRadius:0,tension:0,yAxisID:'y'},
      {label:'Momentum',data:rows.map(x=>x.momentum_score),borderWidth:1.5,pointRadius:0,tension:0,yAxisID:'y'}
    ]},options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{position:'bottom'},semanticGuide:{lines:[{value:0,label:'0 = 中性'}]}},scales:{y:{min:-100,max:100,title:{display:true,text:'標準化方向分數 (-100…+100)'}},x:{ticks:{maxTicksLimit:14}}}}});
    setMeaning();
    const last=rows.at(-1);
    $('#cycleHistoryMeta').textContent=last?`重建 ${rows.length} 個月 · 最新 ${last.period} · ${last.label} ${sign(last.score)}`:'—';
    $('#cycleHistoryRows').innerHTML=[...rows].reverse().slice(0,120).map(x=>`<tr><td>${esc(x.period)}</td><td>${sign(x.score)}</td><td>${esc(x.label)}</td><td>${sign(x.momentum_score)}</td><td>${x.breadth==null?'—':fmt(x.breadth)+'%'}</td><td>${x.pmi==null?'—':fmt(x.pmi)}</td><td>${x.policy_score==null?'—':fmt(x.policy_score)}</td></tr>`).join('');
    $('#regimeRows').innerHTML=[...(hist.regime_changes||[])].reverse().map(x=>`<tr><td>${esc(x.period)}</td><td>${esc(x.from)}</td><td>→</td><td>${esc(x.to)}</td><td>${sign(x.score)}</td></tr>`).join('')||'<tr><td colspan="5">尚無 regime change</td></tr>';
    const snaps=hist.snapshots||[];
    $('#snapshotRows').innerHTML=[...snaps].reverse().slice(0,80).map(x=>`<tr><td>${x.recorded_at?new Date(x.recorded_at).toLocaleString('zh-TW',{timeZone:'Asia/Taipei'}):'—'}</td><td>${sign(x.cycle_score)}</td><td>${esc(x.cycle_label||'—')}</td><td>${sign(x.manufacturing_yoy,'%')}</td><td>${sign(x.leading_3m,'%')}</td><td>${x.pmi==null?'—':fmt(x.pmi)}</td><td>${esc(x.headline||'')}</td></tr>`).join('')||'<tr><td colspan="7">首次建立快照後，後續資料版本變化會累積在這裡。</td></tr>';
  }

  function download(){
    const rows=hist?.cycle_history||[]; if(!rows.length)return;
    const headers=['period','score','label','momentum_score','momentum','breadth','manufacturing_yoy','sales_yoy','leading_3m','pmi','policy_score'];
    const escCsv=v=>`"${String(v??'').replaceAll('"','""')}"`;
    const csv='\ufeff'+[headers.join(','),...rows.map(r=>headers.map(k=>escCsv(r[k])).join(','))].join('\n');
    const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));a.download='elephant-cycle-history.csv';a.click();URL.revokeObjectURL(a.href);
  }

  async function load(){
    try{
      const [h,r]=await Promise.all([
        fetch(`data/intelligence_history.json?x=${Date.now()}`,{cache:'no-store'}).then(x=>x.json()),
        fetch(`data/revisions.json?x=${Date.now()}`,{cache:'no-store'}).then(x=>x.json())
      ]);
      hist=h; draw();
      const rev=r.history||[];
      $('#revisionHistoryMeta').textContent=`累計 ${rev.length} 筆官方修正 · 最後掃描 ${r.last_scan_at?new Date(r.last_scan_at).toLocaleString('zh-TW',{timeZone:'Asia/Taipei'}):'—'}`;
      $('#revisionHistoryRows').innerHTML=[...rev].reverse().slice(0,150).map(x=>`<tr><td>${x.detected_at?new Date(x.detected_at).toLocaleString('zh-TW',{timeZone:'Asia/Taipei'}):'—'}</td><td>${esc(x.source)}</td><td>${esc(x.series)}</td><td>${esc(x.period)}</td><td>${fmt(x.old)}</td><td>${fmt(x.new)}</td><td>${sign(Number(x.new)-Number(x.old))}</td></tr>`).join('')||'<tr><td colspan="7">目前尚未偵測到官方歷史值修正。</td></tr>';
      $('#cycleCsv')?.addEventListener('click',download);
    }catch(e){console.warn('history panel unavailable',e);if($('#cycleHistoryMeta'))$('#cycleHistoryMeta').textContent='情報歷史載入失敗';}
  }
  load();
})();
