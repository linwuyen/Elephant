const fs=require('fs'),vm=require('vm');
const state={schema_version:3,total:4000000,cash:1000000,debt:500000,liquidityNeed:1200000,holdings:'2330,2000000\n2376,700000\n2382,300000'};
const sandbox={window:{ElephantPortfolioState:{load:()=>({...state})}},console};vm.createContext(sandbox);vm.runInContext(fs.readFileSync('portfolio_risk.js','utf8'),sandbox);
const out=sandbox.window.ElephantPortfolioRisk.analyze();
function assert(x,m){if(!x)throw new Error(m)}
assert(out.contract==='browser-local-portfolio-stress-v1','contract');
assert(out.private_state_persisted_server_side===false,'privacy');
assert(out.base.equity===3000000,'holdings equity');
assert(Math.abs(out.concentration.largest_weight_pct-66.6666666667)<1e-6,'largest weight');
assert(out.scenarios.find(x=>x.id==='BROAD_EQUITY_MINUS_25').post_assets===3250000,'broad stress');
assert(out.scenarios.find(x=>x.id==='LARGEST_NAME_MINUS_30').post_assets===3400000,'largest stress');
const liq=out.scenarios.find(x=>x.id==='LIQUIDITY_NEED');assert(liq.liquidity_shortfall===200000,'liquidity shortfall');
assert(out.factor_exposure.status==='UNAVAILABLE_WITHOUT_VERIFIED_PUBLIC_FACTOR_MAP','no invented factors');
assert(!JSON.stringify(out).includes('github.com'),'no server write path');
console.log('PORTFOLIO RISK PASS');
