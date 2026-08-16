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
 for name in (
  'security_official_facts.json','security_fact_store.json','opportunity_market_facts.json','opportunity_inputs.json',
  'portfolio_model.json','valuation_routes.json','scenario_probability_calibration.json','investment_constitution.json',
  'constitution_research.json','investment_constitution_results.json','model_validation.json','decision_engine_v2.json',
  'risk_budget_v2.json','validation_os.json','validation_journal.json','decision_command.json','vintage_manifest.json','revisions.json',
  'capital_allocation.json','investment_calibration.json'
 ):
  o=load_json(name,{});items[name]={'fingerprint':digest(o),'as_of':o.get('as_of') or o.get('updated_at') or o.get('generated_at') or o.get('observed_at') or o.get('last_scan_at'),'version':o.get('version')}
 out={'version':1,'model_version':reg.get('model_version'),'code_commit':gitsha(),'artifacts':items,'decision_snapshot_contract':(reg.get('governance') or {}).get('decision_snapshot_requires',[]),'champion_models':{'macro':'deterministic_score+empirical_calibration','risk_budget':'v1_policy_rule','security_valuation':'archetype_router','investment_constitution':'six_rule_asymmetric_growth_hard_gate','scenario_probability':'upstream_prior_until_prospective_calibration','portfolio':'factor_log_growth_approximation'},'challenger_policy':{'status':'ENABLED_CONTRACT','rule':'Challengers, Validation OS and Decision Command Center may report or compile disagreement but cannot change model authority until separately validated and promoted via model_version.'},'reproducibility':'A decision, its validation evidence and its final command artifact are reproducible only when model_version, code_commit, public-artifact fingerprints, constitution status and evidence_hash are present.','automatic_trading':False};save_json('model_governance.json',out);return out
if __name__=='__main__':print(json.dumps(generate(),ensure_ascii=False,indent=2))
