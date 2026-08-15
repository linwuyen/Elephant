#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt,hashlib,json,subprocess
from common import TZ,load_json,save_json

def digest(o):return hashlib.sha256(json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def gitsha():
 try:return subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
 except Exception:return None

def days(a,b):
 try:return (dt.date.fromisoformat(a)-dt.date.fromisoformat(b)).days
 except Exception:return None

def generate():
 now=dt.datetime.now(TZ).replace(microsecond=0);cap=load_json('capital_allocation.json',{});facts=load_json('security_fact_store.json',{});reg=load_json('model_registry.json',{});out=load_json('investment_calibration.json',{'version':1,'decisions':[]});records=list(out.get('decisions') or []);seen={x.get('decision_fingerprint') for x in records};sec={str(x.get('ticker')):x for x in facts.get('securities',[])};bench=sec.get('2330',{})
 for row in cap.get('lifecycle',[]):
  if row.get('portfolio_action') not in ('BUY_REVIEW','ADD_REVIEW','TRIM_REVIEW','EXIT_REVIEW'):continue
  t=str(row.get('ticker'));f=sec.get(t,{})
  rec={'recorded_at':now.isoformat(),'ticker':t,'name':row.get('name'),'decision':row.get('portfolio_action'),'reference_price':f.get('reference_price'),'reference_price_date':f.get('reference_price_date'),'benchmark_ticker':'2330','benchmark_reference_price':bench.get('reference_price'),'benchmark_reference_price_date':bench.get('reference_price_date'),'expected_return_pct':row.get('expected_return_pct'),'hurdle_expected_return_pct':row.get('hurdle_expected_return_pct'),'net_alpha_spread_pct':row.get('net_alpha_spread_pct'),'archetype':f.get('archetype'),'valuation':f.get('valuation'),'evidence_hash':f.get('evidence',{}).get('evidence_hash'),'model_version':reg.get('model_version'),'code_commit':gitsha(),'outcomes':{},'attribution_status':'PENDING_OUTCOME'}
  rec['decision_fingerprint']=digest({k:v for k,v in rec.items() if k not in ('recorded_at','outcomes','attribution_status')})
  if rec['decision_fingerprint'] not in seen:records.append(rec);seen.add(rec['decision_fingerprint'])
 horizons=(reg.get('calibration') or {}).get('horizons_days',{'3m':90,'6m':180,'12m':365,'18m':548})
 for rec in records:
  f=sec.get(str(rec.get('ticker')),{});cur=f.get('reference_price');curd=f.get('reference_price_date');bcur=bench.get('reference_price');bcurd=bench.get('reference_price_date')
  for h,need in horizons.items():
   if h in (rec.get('outcomes') or {}):continue
   elapsed=days(curd,rec.get('reference_price_date'));belapsed=days(bcurd,rec.get('benchmark_reference_price_date'))
   if elapsed is None or belapsed is None or min(elapsed,belapsed)<int(need):continue
   ep=rec.get('reference_price');bp=rec.get('benchmark_reference_price')
   if not all(isinstance(x,(int,float)) and x>0 for x in (ep,bp,cur,bcur)):continue
   rr=(cur/ep-1)*100;br=(bcur/bp-1)*100
   rec.setdefault('outcomes',{})[h]={'observed_at':curd,'security_return_pct':round(rr,2),'benchmark_return_pct':round(br,2),'realized_opportunity_cost_alpha_pct':round(rr-br,2),'evaluation_basis':'first current reference at/after horizon; dividends not yet included'}
  if rec.get('outcomes'):rec['attribution_status']='PARTIAL_RETURN_ATTRIBUTION_ONLY'
 final={'version':1,'updated_at':now.isoformat(),'decisions':records,'resolved_horizon_count':sum(len(x.get('outcomes') or {}) for x in records),'primary_kpi':'realized_opportunity_cost_alpha','attribution_note':'EPS/multiple/timing decomposition remains BLOCKED until point-in-time realized EPS and multiple facts exist; no synthetic attribution is fabricated.','guardrail':'Prospective decision inputs are immutable; only future outcome fields may be appended.'};save_json('investment_calibration.json',final);return final
if __name__=='__main__':print(json.dumps(generate(),ensure_ascii=False,indent=2))
