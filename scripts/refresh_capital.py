#!/usr/bin/env python3
import json
import valuation_router
import capital_allocation
import update_calibration

if __name__=='__main__':
 v=valuation_router.generate()
 c=capital_allocation.generate()
 k=update_calibration.generate()
 print(json.dumps({'valuation_routes':len(v.get('routes',[])),'capital_status':c.get('status'),'portfolio_state':c.get('portfolio_state_status'),'research_queue':len(c.get('research_queue',{}).get('items',[])),'hurdle':c.get('opportunity_set',{}).get('hurdle_asset'),'calibration':k},ensure_ascii=False,indent=2))
