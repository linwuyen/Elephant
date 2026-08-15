#!/usr/bin/env python3
from __future__ import annotations
import subprocess,sys

COMMANDS=[
 ['python','-m','py_compile','scripts/common.py','scripts/update_data.py','scripts/source_opportunity.py','scripts/source_security_facts.py','scripts/source_moea_dataset.py','scripts/refresh_capital.py'],
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
 ['python','scripts/validate_intelligence_layer.py'],
 ['python','scripts/validate_investment.py'],
 ['python','scripts/test_investment_integration.py'],
 ['python','scripts/build_vintage.py','--validate'],
 ['python','scripts/validate_decision_engine.py'],
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
