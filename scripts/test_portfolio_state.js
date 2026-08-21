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

const simple={total:4000000,equity:3000000,cash:1000000,largest:2500000,maxDd:25};
const detailed={total:4000000,cash:1000000,debt:500000,maxDd:30,holdings:'2330,2500000\n2376,500000'};
const localStorage=new MemoryStorage({
  'elephant.portfolio.v1':JSON.stringify(simple),
  'elephant.personal.capital.v3':JSON.stringify(detailed),
});
const context={window:{localStorage},console};
vm.createContext(context);
vm.runInContext(fs.readFileSync('portfolio_state.js','utf8'),context);

const api=context.window.ElephantPortfolioState;
assert(api,'PortfolioState API missing');
let s=api.load();
eq(s.schema_version,2,'schema version');
eq(s.equity,3000000,'holdings-derived equity');
eq(s.largest,2500000,'holdings-derived largest');
eq(s.debt,500000,'detailed debt migrated');
assert(s.holdings_authoritative===true,'holdings should be authoritative');

// Legacy aliases must read the same canonical object.
const viaV1=JSON.parse(localStorage.getItem('elephant.portfolio.v1'));
const viaV3=JSON.parse(localStorage.getItem('elephant.personal.capital.v3'));
eq(viaV1.equity,s.equity,'v1 alias equity');
eq(viaV3.debt,s.debt,'v3 alias debt');

// A simplified view may patch cash/total, but cannot contradict detailed holdings.
localStorage.setItem('elephant.portfolio.v1',JSON.stringify({total:4500000,equity:999,largest:999,cash:1500000,maxDd:22}));
s=api.load();
eq(s.total,4500000,'simple patch total');
eq(s.cash,1500000,'simple patch cash');
eq(s.equity,3000000,'holdings still own equity');
eq(s.largest,2500000,'holdings still own largest');
eq(s.debt,500000,'rich fields preserved');

// Detailed holdings update must propagate derived values to all views.
localStorage.setItem('elephant.personal.capital.v3',JSON.stringify({holdings:'2330,1000000\n2454,750000',cash:250000}));
s=api.load();
eq(s.equity,1750000,'updated holdings equity');
eq(s.largest,1000000,'updated holdings largest');
eq(JSON.parse(localStorage.getItem('elephant.portfolio.v1')).equity,1750000,'alias sees updated equity');

localStorage.removeItem('elephant.portfolio.v1');
assert(localStorage.getItem(api.KEY)!==null,'aliased get after clear should expose empty normalized state');
s=api.load();
assert(!s.holdings,'clear removes holdings');
eq(s.schema_version,2,'clear returns normalized empty schema');

console.log('PORTFOLIO STATE TEST PASS');
