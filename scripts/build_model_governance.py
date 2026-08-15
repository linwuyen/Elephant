#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,subprocess
from common import load_json,save_json

def digest(o):return hashlib.sha256(json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def gitsha():
 try:return subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
 except Exception:return None

def generate():
 reg=load_json('model_registry.json',{});items={}
 for name in ('security_official_facts.json','security_fact_store.json','opportunity_market_facts.json','opportunity_inputs.json','portfolio_model.json','valuation_routes.json','scenario_probability_calibration.json','model_validation.json','capital_allocation.json','investment_calibration.json'):
  o=load_json(name,{});items[name]={'fingerprint':digest(o),'as_of':o.get('as_of') or o.get('updated_at') or o.get('generated_at'),'version':o.get('version')}
 out={'version':1,'model_version':reg.get('model_version'),'code_commit':gitsha(),'artifacts':items,'decision_snapshot_contract':(reg.get('governance') or {}).get('decision_snapshot_requires',[]),'champion_models':{'macro':'deterministic_score+empirical_calibration','security_valuation':'archetype_router','scenario_probability':'upstream_prior_until_prospective_calibration','portfolio':'factor_log_growth_approximation'},'challenger_policy':{'status':'ENABLED_CONTRACT','rule':'Challengers may report disagreement but cannot change action until separately validated and promoted via model_version.'},'reproducibility':'A decision is reproducible only when model_version, code_commit, public-artifact fingerprints and evidence_hash are present.','automatic_trading':False};save_json('model_governance.json',out);return out
if __name__=='__main__':print(json.dumps(generate(),ensure_ascii=False,indent=2))
