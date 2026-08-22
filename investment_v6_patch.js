(()=>{
  const pct=v=>v==null?'—':`${Number(v)>=0?'+':''}${Number(v).toFixed(1)}%`;
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));

  async function table(){
    for(let i=0;i<80;i++){
      const body=document.querySelector('#alphaRankingRows');
      if(body?.closest('table'))return body;
      await sleep(100);
    }
    return null;
  }

  async function patch(){
    const body=await table();
    if(!body)return;
    try{
      const response=await fetch(`data/investment.json?v=${Date.now()}`,{cache:'no-store'});
      if(!response.ok)throw new Error(`investment.json ${response.status}`);
      const data=await response.json();
      const rows=data.selection?.researched||[];
      const header=body.closest('table')?.querySelector('thead th:last-child');
      if(header){
        header.textContent='Base upside / Next';
        header.title='Base fair value / reference price - 1；不是 classical margin of safety';
      }
      [...body.querySelectorAll('tr')].forEach((tr,i)=>{
        const r=rows[i],cell=tr.cells?.[8];
        if(!r||!cell)return;
        cell.replaceChildren(document.createTextNode(pct(r.base_upside_pct)));
        const next=document.createElement('div');
        next.className='alpha-sub';
        next.textContent=r.next_check||'';
        cell.appendChild(next);
      });
    }catch(e){
      console.warn('investment v6 semantic patch unavailable',e);
    }
  }

  patch();
})();
