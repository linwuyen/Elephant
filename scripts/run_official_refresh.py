#!/usr/bin/env python3
from __future__ import annotations
import subprocess,sys

COMMANDS=[
 ['python','-m','py_compile','scripts/common.py','scripts/update_data.py','scripts/source_segis.py','scripts/source_opportunity.py','scripts/source_security_facts.py','scripts/source_moea_dataset.py','scripts/source_twse_market_live.py','scripts/refresh_capital.py','scripts/capital_allocation.py','scripts/build_shadow_book.py','scripts/build_security_calibration.py','scripts/build_capital_decision_journal.py','scripts/build_opportunity_models.py','scripts/build_risk_budget_v2.py','scripts/build_risk_budget_v2_availability.py','scripts/build_validation_os.py','scripts/build_validation_os_v1_1.py','scripts/build_decision_command.py'],
 ['python','scripts/update_data.py'],
 ['python','scripts/source_opportunity.py'],
 ['python','scripts/source_security_facts.py'],
 ['python','scripts/refresh_capital.py'],
 ['python','scripts/validate_data.py'],
 ['python','scripts/validate_decision_scores.py'],
 ['python','scripts/validate_model_validation.py'],
 ['python','scripts/validate_structural_layers.py'],
 ['python','scripts/test_model_validation.py'],
 ['python','scripts/test_source_supplements.py'],
 ['python','scripts/test_moea_dataset.py'],
 ['python','scripts/test_ndc_zip_selection.py'],
 ['python','scripts/test_twse_market_live.py'],
 ['python','scripts/test_source_segis.py'],
 ['python','scripts/test_segis_public.py'],
 ['python','scripts/validate_intelligence_layer.py'],
 ['python','scripts/validate_investment.py'],
 ['python','scripts/test_investment_integration.py'],
 ['python','scripts/build_vintage.py','--validate'],
 ['python','scripts/validate_decision_engine.py'],
 ['python','scripts/validate_decision_engine_v2.py'],
 ['python','scripts/test_decision_engine_v2.py'],
 ['python','scripts/validate_risk_budget_v2.py'],
 ['python','scripts/test_risk_budget_v2.py'],
 ['python','scripts/test_risk_budget_v2_availability.py'],
 ['python','scripts/validate_validation_os.py'],
 ['python','scripts/test_validation_os.py'],
 ['python','scripts/validate_decision_command.py'],
 ['python','scripts/test_decision_command.py'],
 ['python','scripts/validate_capital_allocation.py'],
 ['python','scripts/test_capital_allocation.py'],
 ['python','scripts/validate_calibration.py'],
 ['python','scripts/validate_capital_v3.py'],
 ['python','scripts/test_capital_v3.py'],
]

def main():
 for cmd in COMMANDS:
  print('+',' '.join(cmd),flush=True)
  subprocess.run(cmd,check=True)
 print('OFFICIAL REFRESH PIPELINE PASS')

if __name__=='__main__':
 try:main()
 except subprocess.CalledProcessError as e:sys.exit(e.returncode or 1)
