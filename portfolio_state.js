(()=>{
  const KEY='elephant.portfolio.v3';
  const MIGRATION_KEYS=['elephant.portfolio.v2','elephant.portfolio.v1','elephant.personal.capital.v3'];
  const storage=window.localStorage;

  function parseJson(raw){
    if(!raw)return {};
    try{const x=JSON.parse(raw);return x&&typeof x==='object'&&!Array.isArray(x)?x:{}}catch{return {}}
  }

  function finite(v){return Number.isFinite(Number(v))}

  function parseHoldings(text){
    return String(text||'').split(/\n+/).map(x=>x.trim()).filter(Boolean).map(line=>{
      const [ticker,value]=line.split(/[,\s]+/);
      return {ticker:String(ticker||'').trim(),value:Number(value)};
    }).filter(x=>x.ticker&&Number.isFinite(x.value)&&x.value>=0);
  }

  function normalize(raw={}){
    const out={...raw,schema_version:3};
    const rows=parseHoldings(out.holdings);
    if(rows.length){
      out.equity=rows.reduce((sum,x)=>sum+x.value,0);
      out.largest=rows.reduce((m,x)=>Math.max(m,x.value),0);
      out.holdings_authoritative=true;
    }else{
      if(finite(out.equity))out.equity=Number(out.equity);
      if(finite(out.largest))out.largest=Number(out.largest);
      out.holdings_authoritative=false;
    }
    if(finite(out.cash))out.cash=Number(out.cash);
    if(finite(out.total))out.total=Number(out.total);
    if(!(Number(out.total)>0)){
      const equity=finite(out.equity)?Number(out.equity):0;
      const cash=finite(out.cash)?Number(out.cash):0;
      if(equity+cash>0)out.total=equity+cash;
    }
    return out;
  }

  function canonicalRaw(){return parseJson(storage.getItem(KEY))}

  function cleanupMigrationKeys(){
    for(const key of MIGRATION_KEYS)storage.removeItem(key);
  }

  function persist(next){
    const normalized=normalize(next);
    storage.setItem(KEY,JSON.stringify(normalized));
    const verify=canonicalRaw();
    if(!Object.keys(verify).length||verify.schema_version!==3)throw new Error('PortfolioState v3 persistence verification failed');
    cleanupMigrationKeys();
    return normalize(verify);
  }

  function migrate(){
    const existing=canonicalRaw();
    if(Object.keys(existing).length){
      const current=persist(existing);
      return current;
    }

    // v2 was the previous canonical source and therefore wins over stale legacy
    // aliases if it exists. Only browsers without v2 fall back to the old v1 +
    // Personal Capital v3 pair, where detailed holdings/debt semantics win.
    const previousCanonical=parseJson(storage.getItem('elephant.portfolio.v2'));
    if(Object.keys(previousCanonical).length)return persist(previousCanonical);

    const simple=parseJson(storage.getItem('elephant.portfolio.v1'));
    const detailed=parseJson(storage.getItem('elephant.personal.capital.v3'));
    const seed={...simple,...detailed};
    if(Object.keys(seed).length)return persist(seed);

    cleanupMigrationKeys();
    return normalize({});
  }

  function load(){
    const current=canonicalRaw();
    if(Object.keys(current).length){
      cleanupMigrationKeys();
      return normalize(current);
    }
    return migrate();
  }

  function save(patch={}){
    return persist({...load(),...(patch||{})});
  }

  function clear(){
    storage.removeItem(KEY);
    cleanupMigrationKeys();
  }

  migrate();
  window.ElephantPortfolioState={KEY,schemaVersion:3,migrationKeys:[...MIGRATION_KEYS],load,save,clear,normalize,parseHoldings};
})();