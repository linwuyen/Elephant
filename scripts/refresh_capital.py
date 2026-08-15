#!/usr/bin/env python3
import json
import valuation_router,build_security_fact_store,build_portfolio_model,build_opportunity_models
import capital_allocation,update_calibration,build_investment_calibration,build_scenario_probability_calibration,build_model_governance

if __name__=='__main__':
 v=valuation_router.generate();sf=build_security_fact_store.generate();pm=build_portfolio_model.generate();om=build_opportunity_models.generate();c=capital_allocation.generate();k=update_calibration.generate();ic=build_investment_calibration.generate();sp=build_scenario_probability_calibration.generate();mg=build_model_governance.generate()
 print(json.dumps({'valuation_routes':len(v.get('routes',[])),'security_facts':len(sf.get('securities',[])),'portfolio_model':pm.get('status'),'public_opportunity_count':om.get('public_available_count'),'capital_status':c.get('status'),'portfolio_state':c.get('portfolio_state_status'),'research_queue':len(c.get('research_queue',{}).get('items',[])),'hurdle':c.get('opportunity_set',{}).get('hurdle_asset'),'calibration_snapshots':k.get('count'),'investment_decisions':len(ic.get('decisions',[])),'scenario_calibration':sp.get('status'),'model_version':mg.get('model_version')},ensure_ascii=False,indent=2))
