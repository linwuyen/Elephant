const fs=require('fs');

const consumers=['command_center.js','decision_engine.js','personal_capital.js'];
const forbidden=['elephant.portfolio.v1','elephant.portfolio.v2','elephant.personal.capital.v3'];
for(const file of consumers){
  const text=fs.readFileSync(file,'utf8');
  for(const token of forbidden){
    if(text.includes(token))throw new Error(`${file} still depends on legacy portfolio key ${token}`);
  }
  if(!text.includes('ElephantPortfolioState'))throw new Error(`${file} does not consume canonical ElephantPortfolioState API`);
}
console.log('PORTFOLIO CONSUMER CONTRACT TEST PASS');
