#!/usr/bin/env python3
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data'
def load(name):return json.loads((DATA/name).read_text(encoding='utf-8'))

slo=load('data_quality_slo.json')
assert slo['contract']=='data-quality-slo-v1'
assert slo['authority'] is False and slo['score_influence'] is False
assert slo['decision_confidence_influence'] is True
assert set(slo['grade_scores'])=={'A','B','C','D','F'}
for row in slo['sources']:
 assert row['grade'] in slo['grade_scores']
 assert float(row['score'])==float(slo['grade_scores'][row['grade']])

pit=load('point_in_time_validation.json')
assert pit['contract']=='point-in-time-validation-gate-v1'
assert pit['integrity_check']=='ok'
assert pit['lookahead_guardrail_pass'] is True
assert pit['historical_reconstruction_eligible_for_promotion'] is False
assert pit['minimum_months_for_model_promotion']>=36
if pit['prospective_vintages_eligible_for_promotion']:
 assert pit['distinct_snapshot_months']>=pit['minimum_months_for_model_promotion']

val=load('validation_os.json')
assert str(val['product']).startswith('Elephant Validation OS v1.2')
assert val['point_in_time_validation']['contract']=='point-in-time-validation-gate-v1'
assert val['data_quality_slo']['contract']=='data-quality-slo-v1'
for dim in ('growth_persistence','domestic_demand','financial_conditions'):
 row=val['score_challengers']['dimensions'][dim]
 assert row['target']['primary']=='future_same_dimension_composite'
 assert row['automatic_promotion'] is False
 assert row['historical_mode']=='LATEST_REVISED_RECONSTRUCTION'
 for h in ('3m','6m'):
  assert 'primary_improvement' in row['horizons'][h]
  assert 'secondary_cycle_diagnostic' in row['horizons'][h]

attr=load('decision_attribution.json')
assert attr['contract']=='decision-change-attribution-v1'
assert attr['authority'] is False
if attr.get('causal_boundary'):
 assert attr['causal_boundary']['point_estimate_decomposition_available'] is False
 assert 'not invented' in attr['causal_boundary']['reason']

front=load('opportunity_frontier.json')
assert front['contract']=='capital-opportunity-frontier-v1'
assert front['authority'] is False and front['current_hurdle_unchanged'] is True
assert front['status'] in {'COMPLETE','PARTIAL_RISK_DATA'}
assert len(front['non_dominated_ids'])==len(set(front['non_dominated_ids']))

lab=load('statistical_challengers.json')
assert lab['contract']=='non-authoritative-statistical-challenger-lab-v1'
assert lab['authority'] is False and lab['production_promotion_eligible'] is False
assert lab['historical_mode']=='LATEST_REVISED_RECONSTRUCTION'
assert 'DYNAMIC_FACTOR_MODEL' in lab['blocked_models'] and 'MIDAS' in lab['blocked_models']

promo=load('model-promotion-contract-v2.json')
assert promo['contract']=='pre_registered_elephant_model_promotion_v2'
assert promo['automatic_promotion'] is False and promo['immutable_without_version_bump'] is True
assert promo['historical_reconstruction']['may_promote_production_model'] is False
assert promo['point_in_time_gate']['minimum_distinct_snapshot_months']>=36
assert promo['score_weight_challenger']['requires_versioned_human_review'] is True
assert promo['governance']['no_automatic_trading'] is True

print('DECISION SCIENCE V2 PASS')
