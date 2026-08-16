#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt, hashlib, json, math
from common import TZ, load_json, save_json

def finite(v):return isinstance(v,(int,float)) and math.isfinite(float(v))
def digest(obj):return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def days(a,b):
    try:return (dt.date.fromisoformat(a)-dt.date.fromisoformat(b)).days
    except Exception:return None
def period_key(as_of):
    try:
        d=dt.date.fromisoformat(as_of);y,w,_=d.isocalendar();return f'{y}-W{w:02d}'
    except Exception:return str(as_of or 'UNKNOWN')

def generate():
    now=dt.datetime.now(TZ).replace(microsecond=0);bundle=load_json('alpha_engine.json',{});alpha=bundle.get('alpha',{})
    facts=load_json('security_fact_store.json',{});sec={str(x.get('ticker')):x for x in facts.get('securities',[])}
    cap=load_json('capital_allocation.json',{});reg=load_json('model_registry.json',{})
    store=load_json('shadow_book.json',{'version':2,'forecasts':[],'forecast_revisions':[],'primary_by_period_ticker':{},'discovery_observations':[]})
    forecasts=list(store.get('forecasts') or []);revs=list(store.get('forecast_revisions') or []);primary=dict(store.get('primary_by_period_ticker') or {})
    disc=list(store.get('discovery_observations') or []);life={str(x.get('ticker')):x for x in cap.get('lifecycle',[])}
    probs={str(x.get('ticker')):x.get('distribution',{}) for x in cap.get('probabilistic_returns',[])}
    exp={str(x.get('ticker')):x for x in cap.get('expectation_analysis',[]) if x.get('ticker')}
    period=period_key((alpha.get('meta') or {}).get('as_of'));hurdle=(cap.get('opportunity_set') or {}).get('hurdle_annualized_expected_return_pct');bench=sec.get('2330',{})
    seen={x.get('forecast_fingerprint') for x in forecasts}
    for s in alpha.get('stocks',[]):
        t=str(s.get('ticker'));f=sec.get(t,{});l=life.get(t,{});d=probs.get(t,{})
        rec={'decision_period':period,'captured_at':now.isoformat(),'ticker':t,'name':s.get('name'),'action':s.get('action'),'score':s.get('score'),'confidence_score':s.get('confidence_score'),'archetype':f.get('archetype'),'reference_price':s.get('reference_price'),'reference_price_date':s.get('reference_price_date'),'benchmark_reference_price':bench.get('reference_price'),'benchmark_reference_price_date':bench.get('reference_price_date'),'native_expected_return_pct':l.get('native_expected_return_pct'),'native_horizon_months':l.get('native_horizon_months'),'annualized_expected_return_pct':l.get('annualized_expected_return_pct'),'hurdle_annualized_expected_return_pct':hurdle,'annualized_alpha_pct':l.get('net_alpha_spread_pct'),'probability_beating_hurdle_pct':d.get('probability_beating_hurdle_pct'),'expectation_analysis':exp.get(t),'model_version':reg.get('model_version'),'evidence_hash':(f.get('evidence') or {}).get('evidence_hash'),'authority':'CALIBRATION_ONLY','outcomes':{}}
        fp=digest({k:v for k,v in rec.items() if k not in ('captured_at','outcomes')});rec['forecast_fingerprint']=fp;key=f'{period}:{t}';prior=primary.get(key)
        if fp not in seen:
            forecasts.append(rec);seen.add(fp)
            if prior and prior!=fp:
                rev={'recorded_at':now.isoformat(),'period_ticker':key,'from_forecast_fingerprint':prior,'to_forecast_fingerprint':fp,'reason':'Same decision period forecast changed. The new pointer supersedes the old forecast for primary calibration; both remain immutable.'}
                rev['revision_fingerprint']=digest({k:v for k,v in rev.items() if k!='recorded_at'})
                if not any(x.get('revision_fingerprint')==rev['revision_fingerprint'] for x in revs):revs.append(rev)
            primary[key]=fp
        elif not prior:primary[key]=fp
    screen=bundle.get('screen',{});dseen={x.get('observation_fingerprint') for x in disc}
    for r in (screen.get('deep_research_queue') or []):
        rec={'decision_period':period,'captured_at':now.isoformat(),'ticker':str(r.get('ticker')),'name':r.get('name'),'rank':r.get('rank'),'screen_priority':r.get('screen_priority'),'reference_price':r.get('reference_price'),'flags':r.get('flags') or [],'authority':'DISCOVERY_ONLY_NO_RETURN_FORECAST'}
        rec['observation_fingerprint']=digest({k:v for k,v in rec.items() if k!='captured_at'})
        if rec['observation_fingerprint'] not in dseen:disc.append(rec);dseen.add(rec['observation_fingerprint'])
    horizons=(reg.get('shadow_book') or {}).get('horizons_days',{'3m':90,'6m':180,'12m':365});primary_fps=set(primary.values());errors=[];resolved_primary=0
    for rec in forecasts:
        f=sec.get(str(rec.get('ticker')),{});cur=f.get('reference_price');curd=f.get('reference_price_date');bcur=bench.get('reference_price');bcurd=bench.get('reference_price_date')
        for h,need in horizons.items():
            if h in rec.get('outcomes',{}):continue
            elapsed=days(curd,rec.get('reference_price_date'));belapsed=days(bcurd,rec.get('benchmark_reference_price_date'))
            if elapsed is None or belapsed is None or min(elapsed,belapsed)<int(need):continue
            ep=rec.get('reference_price');bp=rec.get('benchmark_reference_price')
            if not all(finite(x) and float(x)>0 for x in (ep,bp,cur,bcur)):continue
            sr=(float(cur)/float(ep)-1)*100;br=(float(bcur)/float(bp)-1)*100;alpha_r=sr-br
            rec.setdefault('outcomes',{})[h]={'observed_at':curd,'security_return_pct':round(sr,2),'tsmc_return_pct':round(br,2),'realized_opportunity_cost_alpha_pct':round(alpha_r,2),'regret_vs_tsmc_pct':round(max(0.0,br-sr),2),'return_type':'PRICE_RETURN_EX_DIVIDENDS'}
        if rec.get('forecast_fingerprint') in primary_fps and rec.get('outcomes'):
            resolved_primary+=1;pred=rec.get('annualized_alpha_pct')
            for o in rec.get('outcomes',{}).values():
                if finite(pred) and finite(o.get('realized_opportunity_cost_alpha_pct')):errors.append(float(o['realized_opportunity_cost_alpha_pct'])-float(pred))
    result={'version':2,'updated_at':now.isoformat(),'model_version':reg.get('model_version'),'forecasts':forecasts[-5000:],'forecast_revisions':revs[-5000:],'primary_by_period_ticker':primary,'discovery_observations':disc[-5000:],'summary':{'immutable_forecast_count':len(forecasts),'primary_forecast_count':len(primary),'forecast_revision_count':len(revs),'resolved_primary_forecast_count':resolved_primary,'resolved_primary_horizon_count':sum(len(x.get('outcomes',{})) for x in forecasts if x.get('forecast_fingerprint') in primary_fps),'mean_alpha_forecast_error_pct':round(sum(errors)/len(errors),2) if errors else None},'contracts':{'primary_kpi':'realized_opportunity_cost_alpha_vs_tsmc','regret_scope':'TSMC_ONLY','one_primary_forecast_per_period_ticker':True,'no_buy_authority':True,'no_backfill_before_point_in_time_capture':True},'guardrail':'Shadow Book records all upstream researched securities, but only the primary pointer per period/ticker enters calibration. Discovery-only rows never receive fabricated return forecasts.'}
    save_json('shadow_book.json',result);return result
if __name__=='__main__':print(json.dumps(generate(),ensure_ascii=False,indent=2))
