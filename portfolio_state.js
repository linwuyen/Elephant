(()=>{
  const KEY='elephant.portfolio.v2';
  const LEGACY_KEYS=['elephant.portfolio.v1','elephant.personal.capital.v3'];
  const aliases=new Set([KEY,...LEGACY_KEYS]);
  const storage=window.localStorage;
  const proto=Object.getPrototypeOf(storage);
  const rawGet=proto.getItem;
  const rawSet=proto.setItem;
  const rawRemove=proto.removeItem;

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
    const out={...raw,schema_version:2};
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

  function canonicalRaw(){return parseJson(rawGet.call(storage,KEY))}

  function migrate(){
    const existing=canonicalRaw();
    if(Object.keys(existing).length)return normalize(existing);
    const simple=parseJson(rawGet.call(storage,'elephant.portfolio.v1'));
    const detailed=parseJson(rawGet.call(storage,'elephant.personal.capital.v3'));
    if(!Object.keys(simple).length&&!Object.keys(detailed).length)return normalize({});
    // Detailed Personal Capital fields own holdings/debt/liquidity semantics.
    // Simpler v1 fields only fill gaps during one-time migration.
    const seed={...simple,...detailed};
    const next=normalize(seed);
    rawSet.call(storage,KEY,JSON.stringify(next));
    return next;
  }

  function load(){
    const current=canonicalRaw();
    return Object.keys(current).length?normalize(current):migrate();
  }

  function save(patch={}){
    const next=normalize({...load(),...(patch||{})});
    rawSet.call(storage,KEY,JSON.stringify(next));
    return next;
  }

  function clear(){
    rawRemove.call(storage,KEY);
    for(const key of LEGACY_KEYS)rawRemove.call(storage,key);
  }

  // Compatibility shim: existing views can keep their old key names while all
  // reads/writes are routed through one canonical schema. Writes are merged,
  // never wholesale-replaced; detailed holdings derive equity/largest so a
  // simplified calculator cannot silently contradict the detailed portfolio.
  proto.getItem=function(key){
    if(this===storage&&aliases.has(String(key)))return JSON.stringify(load());
    return rawGet.call(this,key);
  };
  proto.setItem=function(key,value){
    if(this===storage&&aliases.has(String(key))){save(parseJson(String(value)));return;}
    return rawSet.call(this,key,value);
  };
  proto.removeItem=function(key){
    if(this===storage&&aliases.has(String(key))){clear();return;}
    return rawRemove.call(this,key);
  };

  migrate();
  window.ElephantPortfolioState={KEY,schemaVersion:2,legacyKeys:[...LEGACY_KEYS],load,save,clear,normalize,parseHoldings};
})();
