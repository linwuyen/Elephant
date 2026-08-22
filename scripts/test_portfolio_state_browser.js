const {chromium}=require('playwright');

function assert(cond,msg){if(!cond)throw new Error(msg)}
function eq(a,b,msg){if(a!==b)throw new Error(`${msg}: ${a} !== ${b}`)}

(async()=>{
  const browser=await chromium.launch({headless:true});
  try{
    const context=await browser.newContext();
    await context.addInitScript(seed=>{
      localStorage.setItem('elephant.portfolio.v2',JSON.stringify(seed.v2));
      localStorage.setItem('elephant.portfolio.v1',JSON.stringify(seed.staleV1));
      localStorage.setItem('elephant.personal.capital.v3',JSON.stringify(seed.stalePersonal));
    },{
      v2:{schema_version:2,total:4000000,cash:1000000,debt:500000,debtRate:2.4,maxDd:30,holdings:'2330,2500000\n2376,500000'},
      staleV1:{total:1,equity:1,cash:0},
      stalePersonal:{debt:999,holdings:'9999,1'},
    });
    const page=await context.newPage();
    page.on('pageerror',err=>console.warn('pageerror:',err.message));
    await page.goto('http://127.0.0.1:8765/',{waitUntil:'domcontentloaded',timeout:30000});
    await page.waitForFunction(()=>window.ElephantPortfolioState?.schemaVersion===3,null,{timeout:15000});

    let state=await page.evaluate(()=>({
      state:window.ElephantPortfolioState.load(),
      key:window.ElephantPortfolioState.KEY,
      old:window.ElephantPortfolioState.migrationKeys.map(k=>[k,localStorage.getItem(k)]),
    }));
    eq(state.key,'elephant.portfolio.v3','browser canonical key');
    eq(state.state.schema_version,3,'browser schema version');
    eq(state.state.total,4000000,'v2 total migrated');
    eq(state.state.debt,500000,'v2 debt migrated');
    eq(state.state.equity,3000000,'holdings derive equity');
    eq(state.state.largest,2500000,'holdings derive largest');
    assert(state.old.every(([,v])=>v===null),'legacy migration keys removed in browser');

    // Command Center writes through the canonical API.
    await page.waitForSelector('#dccCash',{timeout:20000});
    await page.fill('#dccCash','1200000');
    await page.waitForFunction(()=>window.ElephantPortfolioState.load().cash===1200000,null,{timeout:5000});
    state=await page.evaluate(()=>window.ElephantPortfolioState.load());
    eq(state.debt,500000,'Command Center simple write preserves rich debt');
    eq(state.equity,3000000,'Command Center simple write preserves holdings equity');

    // A stale script writing an old key no longer has alias authority.
    await page.evaluate(()=>localStorage.setItem('elephant.portfolio.v1',JSON.stringify({total:2,equity:2,cash:0})));
    state=await page.evaluate(()=>window.ElephantPortfolioState.load());
    eq(state.total,4000000,'stale v1 write cannot replace canonical total');
    eq(state.cash,1200000,'stale v1 write cannot replace canonical cash');
    eq(await page.evaluate(()=>localStorage.getItem('elephant.portfolio.v1')),null,'canonical load cleans stale v1 write');

    // Decision Engine updates the same state; detailed holdings remain authoritative.
    await page.waitForSelector('#engineCalc',{timeout:20000});
    await page.fill('#engineTotal','4500000');
    await page.fill('#engineCash','1500000');
    await page.click('#engineCalc');
    await page.waitForFunction(()=>{
      const s=window.ElephantPortfolioState.load();return s.total===4500000&&s.cash===1500000;
    },null,{timeout:5000});
    state=await page.evaluate(()=>window.ElephantPortfolioState.load());
    eq(state.equity,3000000,'Decision Engine cannot contradict detailed holdings equity');
    eq(state.debt,500000,'Decision Engine preserves Personal Capital debt');

    // Reload proves all browser views rehydrate from one canonical key.
    await page.reload({waitUntil:'domcontentloaded',timeout:30000});
    await page.waitForFunction(()=>window.ElephantPortfolioState?.schemaVersion===3,null,{timeout:15000});
    await page.waitForSelector('#dccTotal',{timeout:20000});
    await page.waitForSelector('#engineTotal',{timeout:20000});
    await page.waitForSelector('#pcTotal',{timeout:20000});
    eq(await page.inputValue('#dccTotal'),'4500000','Command Center reload total');
    eq(await page.inputValue('#engineTotal'),'4500000','Decision Engine reload total');
    eq(await page.inputValue('#pcTotal'),'4500000','Personal Capital reload total');
    eq(await page.inputValue('#dccCash'),'1500000','Command Center reload cash');
    eq(await page.inputValue('#engineCash'),'1500000','Decision Engine reload cash');
    eq(await page.inputValue('#pcCash'),'1500000','Personal Capital reload cash');
    eq(await page.inputValue('#pcDebt'),'500000','Personal Capital rich field survives simple views');

    state=await page.evaluate(()=>window.ElephantPortfolioState.load());
    assert(state.holdings_authoritative===true,'holdings authority survives browser reload');
    assert((await page.evaluate(()=>window.ElephantPortfolioState.migrationKeys.map(k=>localStorage.getItem(k)))).every(v=>v===null),'legacy keys remain absent after reload');
    console.log('PORTFOLIO STATE BROWSER E2E PASS');
  }finally{
    await browser.close();
  }
})().catch(err=>{console.error(err);process.exit(1)});
