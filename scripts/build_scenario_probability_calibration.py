#!/usr/bin/env python3
from __future__ import annotations
import json
from common import load_json,save_json
MIN=30

def generate():
 store=load_json('security_fact_store.json',{});cal=load_json('investment_calibration.json',{});resolved=cal.get('resolved_horizon_count',0);rows=[]
 for s in store.get('securities',[]):
  if s.get('stage') not in ('BENCHMARK','RESEARCHED'):continue
  sc=(s.get('valuation') or {}).get('scenarios') or {};prior={k:(v or {}).get('probability') for k,v in sc.items() if k in ('bear','base','bull')}
  rows.append({'ticker':s.get('ticker'),'name':s.get('name'),'prior_probabilities':prior,'posterior_probabilities':prior if prior else None,'calibration_status':'INSUFFICIENT_PROSPECTIVE_SAMPLES' if resolved<MIN else 'READY_FOR_CHALLENGER_FIT','resolved_samples':resolved,'minimum_samples':MIN,'authoritative':False,'note':'Until enough prospective security outcomes exist, scenario weights remain upstream model assumptions; Elephant does not fabricate empirical posterior probabilities.'})
 out={'version':1,'status':'PROSPECTIVE_CALIBRATION','minimum_samples':MIN,'resolved_samples':resolved,'securities':rows,'promotion_rule':'A probability challenger may become authoritative only after prospective calibration and a model-version change; never silently rewrites upstream Buy Gate.'};save_json('scenario_probability_calibration.json',out);return out
if __name__=='__main__':print(json.dumps(generate(),ensure_ascii=False,indent=2))
