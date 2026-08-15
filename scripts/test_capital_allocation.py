#!/usr/bin/env python3
import copy
import capital_allocation


def stock(action="VERIFY"):
    return {
        "ticker":"9999","name":"Test AI Server","rank":1,"action":action,"score":85,"confidence_score":80,
        "reference_price":100,"thesis_status":"ACTIVE","thesis":"AI server growth",
        "risk_model":{"downside_pct":30},
        "valuation_model":{"status":"COMPLETE","expected_return_pct":40,"scenarios":{
            "bear":{"fair_value":80,"probability":0.25},
            "base":{"fair_value":140,"probability":0.5},
            "bull":{"fair_value":180,"probability":0.25}
        }}
    }

alpha={"benchmark_asset":{"valuation_model":{"expected_return_pct":30}},"stocks":[stock("VERIFY")]}
inputs={"alternatives":[{"id":"2330","status":"DERIVED","expected_return_pct":None}]}
portfolio={"status":"UNCONFIGURED","positions":[]}
policy={"constraints":{"max_single_stock_pct":25,"max_common_factor_pct":60},"lifecycle":{"exit_when_net_alpha_spread_below_pct":-5,"trim_when_net_alpha_spread_below_pct":2}}
opp=capital_allocation.opportunity_set(alpha,inputs,portfolio)
rows=capital_allocation.lifecycle_actions(alpha,opp,policy,portfolio)
assert rows[0]["portfolio_action"]=="RESEARCH", rows

alpha2=copy.deepcopy(alpha);alpha2["stocks"][0]["action"]="BUY CANDIDATE"
rows2=capital_allocation.lifecycle_actions(alpha2,opp,policy,portfolio)
assert rows2[0]["portfolio_action"]=="BUY_REVIEW", rows2

d=capital_allocation.scenario_distribution(alpha2["stocks"][0],30)
assert d["status"]=="COMPLETE"
assert d["probability_beating_hurdle_pct"]==75.0, d
assert d["probability_loss_gt_20_pct"]==0.0, d

q=capital_allocation.build_research_queue({"meta":{"status":"COMPLETE","as_of":"2026-08-15"},"deep_research_queue":[{"ticker":"2408","name":"南亞科","industry":"24"}]},{"stocks":[]})
assert q["items"][0]["archetype"]=="CYCLICAL_MEMORY",q
assert q["items"][0]["promotion_authority"]=="NONE"

print("CAPITAL ALLOCATION TEST PASS")
