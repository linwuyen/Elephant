#!/usr/bin/env python3
import argparse,json
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data';OUT=DATA/'decision_attribution.json'

def load(name,default=None):
 p=DATA/name;return json.loads(p.read_text(encoding='utf-8')) if p.exists() else ({} if default is None else default)

def iso(v):
 try:return datetime.fromisoformat(str(v).replace('Z','+00:00'))
 except Exception:return None

def build():
 journal=load('decision_journal.json',{'entries':[]});entries=journal.get('entries') or []
 if len(entries)<2:
  return {'version':1,'contract':'decision-change-attribution-v1','status':'INSUFFICIENT_PRIOR_DECISION','authority':False}
 prev,cur=entries[-2],entries[-1]
 score_delta={}
 for dim in sorted(set((prev.get('scores') or {}))|set((cur.get('scores') or {}))):
  a=(prev.get('scores') or {}).get(dim,{}).get('score');b=(cur.get('scores') or {}).get(dim,{}).get('score')
  score_delta[dim]=None if a is None or b is None else round(float(b)-float(a),2)
 alpha_prev=prev.get('alpha_actions') or {};alpha_cur=cur.get('alpha_actions') or {}
 alpha_changes=[{'ticker':t,'from':alpha_prev.get(t),'to':alpha_cur.get(t)} for t in sorted(set(alpha_prev)|set(alpha_cur)) if alpha_prev.get(t)!=alpha_cur.get(t)]
 revisions=load('revisions.json',{}).get('history') or [];pt=iso(prev.get('recorded_at'));ct=iso(cur.get('recorded_at'))
 revision_events=[]
 for x in revisions:
  t=iso(x.get('detected_at'))
  if t and pt and ct and pt<t<=ct:revision_events.append(x)
 slo=load('data_quality_slo.json',{});degraded=[x for x in slo.get('sources') or [] if x.get('grade')!='A']
 changed=any(v not in (None,0,0.0) for v in score_delta.values()) or float(cur.get('risk_budget_pct') or 0)!=float(prev.get('risk_budget_pct') or 0) or bool(alpha_changes)
 return {
  'version':1,'contract':'decision-change-attribution-v1','status':'CHANGED' if changed else 'UNCHANGED','authority':False,
  'from':{'fingerprint':prev.get('fingerprint'),'recorded_at':prev.get('recorded_at')},
  'to':{'fingerprint':cur.get('fingerprint'),'recorded_at':cur.get('recorded_at')},
  'observed_decision_delta':{
   'scores':score_delta,
   'risk_budget_pct':round(float(cur.get('risk_budget_pct') or 0)-float(prev.get('risk_budget_pct') or 0),2),
   'risk_posture':{'from':prev.get('risk_posture'),'to':cur.get('risk_posture')},
   'alpha_action_changes':alpha_changes,
  },
  'evidence_between_snapshots':{
   'official_revision_events':revision_events,
   'non_A_source_quality':degraded,
  },
  'causal_boundary':{
   'point_estimate_decomposition_available':False,
   'reason':'Journal snapshots do not isolate one input at a time. Exact decision deltas and contemporaneous evidence changes are reported, but per-component causal pp attribution is not invented.',
   'future_method':'Use one-factor counterfactual rebuilds from point-in-time vintages once sufficient true vintages exist.'
  },
  'private_portfolio_boundary':'Browser-local PortfolioState changes are intentionally absent from server-side attribution artifacts.'
 }

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();obj=build()
 if a.check:
  assert load('decision_attribution.json',{})==obj,'decision_attribution.json stale';print('DECISION ATTRIBUTION PASS')
 else:OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(OUT)
if __name__=='__main__':main()
