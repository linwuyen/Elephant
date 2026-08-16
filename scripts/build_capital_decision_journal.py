#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt, hashlib, json, subprocess
from common import TZ, load_json, save_json

def digest(obj):return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def gitsha():
    try:return subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    except Exception:return None
def decision_period(as_of):
    try:
        d=dt.date.fromisoformat(as_of);y,w,_=d.isocalendar();return f'{y}-W{w:02d}'
    except Exception:return str(as_of or 'UNKNOWN')

def generate():
    now=dt.datetime.now(TZ).replace(microsecond=0);cap=load_json('capital_allocation.json',{});bundle=load_json('alpha_engine.json',{});alpha=bundle.get('alpha',{});screen=bundle.get('screen',{});reg=load_json('model_registry.json',{})
    out=load_json('capital_decision_journal.json',{'version':1,'decision_snapshots':[],'model_revisions':[],'primary_by_period':{}})
    snaps=list(out.get('decision_snapshots') or []);revs=list(out.get('model_revisions') or []);primary=dict(out.get('primary_by_period') or {})
    period=decision_period((alpha.get('meta') or {}).get('as_of'));code=gitsha()
    core={'decision_period':period,'model_version':reg.get('model_version'),'code_commit':code,'capital_fingerprint':cap.get('fingerprint'),'alpha_as_of':(alpha.get('meta') or {}).get('as_of'),'screen_as_of':(screen.get('meta') or {}).get('as_of'),'hurdle_asset':(cap.get('opportunity_set') or {}).get('hurdle_asset'),'hurdle_annualized_expected_return_pct':(cap.get('opportunity_set') or {}).get('hurdle_annualized_expected_return_pct'),'portfolio_state_status':cap.get('portfolio_state_status'),'lifecycle':[{'ticker':x.get('ticker'),'portfolio_action':x.get('portfolio_action'),'upstream_action':x.get('upstream_action'),'constitution_status':x.get('constitution_status'),'annualized_alpha_pct':x.get('net_alpha_spread_pct')} for x in cap.get('lifecycle',[])],'guardrails':cap.get('guardrails')}
    fp=digest(core);existing=next((x for x in snaps if x.get('snapshot_fingerprint')==fp),None);prior_fp=primary.get(period)
    if existing is None:
        snap=dict(core);snap.update({'recorded_at':now.isoformat(),'snapshot_fingerprint':fp,'snapshot_kind':'SCHEDULED_DECISION','authority':'AUDIT_ONLY','outcomes':{}});snaps.append(snap)
        if prior_fp and prior_fp!=fp:
            rev={'recorded_at':now.isoformat(),'decision_period':period,'from_snapshot_fingerprint':prior_fp,'to_snapshot_fingerprint':fp,'from_model_version':next((x.get('model_version') for x in snaps if x.get('snapshot_fingerprint')==prior_fp),None),'to_model_version':reg.get('model_version'),'reason':'Inputs/model changed inside the same decision period. Only the latest pointer is primary; both immutable snapshots remain for audit.'}
            rev['revision_fingerprint']=digest({k:v for k,v in rev.items() if k!='recorded_at'})
            if not any(x.get('revision_fingerprint')==rev['revision_fingerprint'] for x in revs):revs.append(rev)
        primary[period]=fp
    elif not prior_fp:primary[period]=fp
    primary_set=set(primary.values());summary={'decision_period_count':len(primary),'immutable_snapshot_count':len(snaps),'model_revision_count':len(revs),'primary_snapshot_count':sum(x.get('snapshot_fingerprint') in primary_set for x in snaps)}
    result={'version':2,'updated_at':now.isoformat(),'model_version':reg.get('model_version'),'decision_snapshots':snaps[-1000:],'model_revisions':revs[-1000:],'primary_by_period':primary,'summary':summary,'calibration_contract':'Only snapshot fingerprints selected by primary_by_period enter the primary decision cohort. Same-period reruns are not independent samples.','guardrail':'Snapshots are immutable; only the primary pointer changes when a same-period model/input revision supersedes an earlier run.'}
    save_json('capital_decision_journal.json',result);return result
if __name__=='__main__':print(json.dumps(generate(),ensure_ascii=False,indent=2))
