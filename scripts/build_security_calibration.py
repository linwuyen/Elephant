#!/usr/bin/env python3
from __future__ import annotations
import json,math
from common import load_json,save_json

def finite(v):return isinstance(v,(int,float)) and math.isfinite(float(v))
def mean(xs):return round(sum(xs)/len(xs),2) if xs else None
def bucket(v,edges):
    if not finite(v):return 'UNKNOWN'
    x=float(v)
    for lo,hi,label in edges:
        if lo<=x<hi:return label
    return edges[-1][2]
def aggregate(rows):
    realized=[float(x['realized_alpha_pct']) for x in rows if finite(x.get('realized_alpha_pct'))]
    errors=[float(x['forecast_error_pct']) for x in rows if finite(x.get('forecast_error_pct'))]
    regrets=[float(x['regret_pct']) for x in rows if finite(x.get('regret_pct'))]
    hits=[1.0 if x.get('direction_hit') else 0.0 for x in rows if x.get('direction_hit') is not None]
    return {'sample_size':len(rows),'mean_realized_alpha_pct':mean(realized),'mean_forecast_error_pct':mean(errors),'mean_regret_vs_tsmc_pct':mean(regrets),'direction_hit_rate_pct':round(sum(hits)/len(hits)*100,1) if hits else None}

def generate():
    book=load_json('shadow_book.json',{});reg=load_json('model_registry.json',{});primary=set((book.get('primary_by_period_ticker') or {}).values());obs=[]
    for rec in book.get('forecasts',[]):
        if rec.get('forecast_fingerprint') not in primary:continue
        predicted=rec.get('annualized_alpha_pct');score=rec.get('score')
        for horizon,out in (rec.get('outcomes') or {}).items():
            realized=out.get('realized_opportunity_cost_alpha_pct');err=float(realized)-float(predicted) if finite(realized) and finite(predicted) else None
            obs.append({'forecast_fingerprint':rec.get('forecast_fingerprint'),'decision_period':rec.get('decision_period'),'ticker':rec.get('ticker'),'horizon':horizon,'score':score,'predicted_annualized_alpha_pct':predicted,'realized_alpha_pct':realized,'forecast_error_pct':None if err is None else round(err,2),'regret_pct':out.get('regret_vs_tsmc_pct'),'direction_hit':None if not finite(realized) or not finite(predicted) else ((float(realized)>=0)==(float(predicted)>=0))})
    horizons={}
    for h in ('3m','6m','12m'):
        rows=[x for x in obs if x['horizon']==h];horizons[h]=aggregate(rows)
    score_edges=[(-1e9,65,'<65'),(65,75,'65-74'),(75,85,'75-84'),(85,1e9,'85+')]
    alpha_edges=[(-1e9,0,'<0'),(0,5,'0-4.9'),(5,15,'5-14.9'),(15,1e9,'15+')]
    sb={};ab={}
    for x in obs:
        sb.setdefault(bucket(x.get('score'),score_edges),[]).append(x);ab.setdefault(bucket(x.get('predicted_annualized_alpha_pct'),alpha_edges),[]).append(x)
    minimum=int((reg.get('shadow_book') or {}).get('minimum_samples_for_model_change',30))
    total=len(obs);out={'version':1,'model_version':reg.get('model_version'),'status':'CALIBRATED' if total>=minimum else 'INSUFFICIENT_HISTORY','minimum_samples_for_model_change':minimum,'resolved_primary_observations':total,'horizons':horizons,'score_buckets':{k:aggregate(v) for k,v in sorted(sb.items())},'predicted_alpha_buckets':{k:aggregate(v) for k,v in sorted(ab.items())},'observations':obs[-5000:],'authority':'CALIBRATION_ONLY','model_change_allowed':total>=minimum,'guardrail':'Only primary point-in-time Shadow Book forecasts enter security calibration. Insufficient history cannot change model weights, BUY authority or scenario probabilities.'}
    save_json('security_calibration.json',out);return out
if __name__=='__main__':print(json.dumps(generate(),ensure_ascii=False,indent=2))
