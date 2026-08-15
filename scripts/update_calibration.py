#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt,json
from common import DATA,TZ,save_json
CAL=DATA/'calibration';CAL.mkdir(exist_ok=True)
def load(name,default=None):
 p=DATA/name;return json.loads(p.read_text(encoding='utf-8')) if p.exists() else ({} if default is None else default)
def generate():
 now=dt.datetime.now(TZ).replace(microsecond=0);capital=load('capital_allocation.json');investment=load('investment.json');bundle=load('alpha_engine.json');alpha=bundle.get('alpha',{});screen=bundle.get('screen',{});fp=capital.get('fingerprint');idx=load('calibration/index.json',{'version':1,'snapshots':[]});prev=idx.get('snapshots',[])[-1] if idx.get('snapshots') else None
 if prev and prev.get('fingerprint')==fp:return {'created':False,'reason':'UNCHANGED_FINGERPRINT','snapshot':prev}
 fn=now.strftime('%Y%m%dT%H%M%S%z')+'.json';buy=[x for x in alpha.get('stocks',[]) if x.get('action')=='BUY CANDIDATE'];snap={'version':1,'captured_at':now.isoformat(),'fingerprint':fp,'alpha_as_of':alpha.get('meta',{}).get('as_of'),'screen_as_of':screen.get('meta',{}).get('as_of'),'macro_context':investment.get('macro_context'),'opportunity_set':capital.get('opportunity_set'),'buy_entries':[{'ticker':x.get('ticker'),'name':x.get('name'),'reference_price':x.get('reference_price'),'expected_return_pct':x.get('valuation_model',{}).get('expected_return_pct'),'alpha_spread_pct':x.get('alpha_spread_pct'),'score':x.get('score'),'confidence_score':x.get('confidence_score')} for x in buy],'researched_actions':[{'ticker':x.get('ticker'),'action':x.get('action')} for x in alpha.get('stocks',[])],'benchmark':alpha.get('benchmark_asset'),'portfolio_state_status':capital.get('portfolio_state_status'),'return_measurement_contract':'Evaluate only from data observable at captured_at; never rewrite with revised hindsight data.'}
 (CAL/fn).write_text(json.dumps(snap,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8');entry={'file':'data/calibration/'+fn,'captured_at':now.isoformat(),'fingerprint':fp,'buy_entry_count':len(buy)};idx.setdefault('snapshots',[]).append(entry);idx['snapshots']=idx['snapshots'][-500:];idx['latest']=entry;save_json('calibration/index.json',idx);return {'created':True,'snapshot':entry}
if __name__=='__main__':print(json.dumps(generate(),ensure_ascii=False,indent=2))
