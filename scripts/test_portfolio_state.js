const fs=require('fs');
const vm=require('vm');

class MemoryStorage{
  constructor(seed={}){this.map=new Map(Object.entries(seed));}
  getItem(k){return this.map.has(String(k))?this.map.get(String(k)):null;}
  setItem(k,v){this.map.set(String(k),String(v));}
  removeItem(k){this.map.delete(String(k));}
}
function assert(cond,msg){if(!cond)throw new Error(msg)}
function eq(a,b,msg){if(a!==b)throw new Error(`${msg}: ${a} !== ${b}`)}
function boot(seed={}){
  const localStorage=new MemoryStorage(seed);
  const context={window:{localStorage},console};
  vm.createContext(context);
  vm.runInContext(fs.readFileSync('portfolio_state.js','utf8'),context);
  return {localStorage,api:context.window.ElephantPortfolioState};
}

const simple={total:4000000,equity:3000000,cash:1000000,largest:2500000,maxDd:25};
const detailed={total:4000000,cash:1000000,debt:500000,maxDd:30,holdings:'2330,2500000\n2376,500000'};

// Browser with only legacy keys: migrate once, detailed holdings/debt win, then old keys disappear.
let {localStorage,api}=boot({
  'elephant.portfolio.v1':JSON.stringify(simple),
  'elephant.personal.capital.v3':JSON.stringify(detailed),
});
assert(api,'PortfolioState API missing');
eq(api.KEY,'elephant.portfolio.v3','canonical key');
eq(api.schemaVersion,3,'API schema version');
let s=api.load();
eq(s.schema_version,3,'state schema version');
eq(s.equity,3000000,'holdings-derived equity');
eq(s.largest,2500000,'holdings-derived largest');
eq(s.debt,500000,'detailed debt migrated');
assert(s.holdings_authoritative===true,'holdings should be authoritative');
for(const key of api.migrationKeys)eq(localStorage.getItem(key),null,`migration key removed ${key}`);
assert(localStorage.getItem(api.KEY)!==null,'canonical v3 persisted');

// Stale legacy writes are no longer live aliases and cannot change canonical state.
localStorage.setItem('elephant.portfolio.v1',JSON.stringify({total:1,equity:1,cash:0}));
s=api.load();
eq(s.total,4000000,'legacy write cannot replace total');
eq(s.equity,3000000,'legacy write cannot replace equity');
eq(localStorage.getItem('elephant.portfolio.v1'),null,'load cleans stale legacy write');

// Canonical API partial writes merge and detailed holdings remain authoritative.
s=api.save({cash:1500000,total:4500000,equity:999,largest:999});
eq(s.total,4500000,'canonical patch total');
eq(s.cash,1500000,'canonical patch cash');
eq(s.equity,3000000,'holdings still own equity');
eq(s.largest,2500000,'holdings still own largest');
eq(s.debt,500000,'rich fields preserved');

s=api.save({holdings:'2330,1000000\n2454,750000',cash:250000});
eq(s.equity,1750000,'updated holdings equity');
eq(s.largest,1000000,'updated holdings largest');

// Previous canonical v2 wins over contradictory stale aliases.
({localStorage,api}=boot({
  'elephant.portfolio.v2':JSON.stringify({schema_version:2,total:9000000,cash:1000000,debt:123,holdings:'2330,8000000'}),
  'elephant.portfolio.v1':JSON.stringify({total:2,equity:2}),
  'elephant.personal.capital.v3':JSON.stringify({debt:999,holdings:'9999,1'}),
}));
s=api.load();
eq(s.total,9000000,'v2 canonical total wins');
eq(s.debt,123,'v2 canonical rich field wins');
eq(s.equity,8000000,'v2 holdings derive equity');
eq(s.schema_version,3,'v2 upgraded to v3');
for(const key of api.migrationKeys)eq(localStorage.getItem(key),null,`v2 migration key removed ${key}`);

// Reload semantics: a second page load preserves v3 and does not need aliases.
const persisted=localStorage.getItem(api.KEY);
({localStorage,api}=boot({'elephant.portfolio.v3':persisted}));
s=api.load();
eq(s.total,9000000,'reload preserves canonical total');
eq(s.debt,123,'reload preserves canonical debt');
eq(s.equity,8000000,'reload preserves canonical holdings-derived equity');

api.clear();
eq(localStorage.getItem(api.KEY),null,'clear removes canonical key');
for(const key of api.migrationKeys)eq(localStorage.getItem(key),null,`clear removes migration key ${key}`);
s=api.load();
eq(s.schema_version,3,'clear returns normalized empty v3');
console.log('PORTFOLIO STATE V3 MIGRATION TEST PASS');
