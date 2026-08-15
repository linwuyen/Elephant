#!/usr/bin/env python3
from __future__ import annotations
import json, math
from common import load_json, save_json


def finite(v):
    return isinstance(v, (int, float)) and math.isfinite(float(v))


def gate(status, value=None, threshold=None, reason=None, evidence=None):
    return {"status": status, "value": value, "threshold": threshold, "reason": reason, "evidence": evidence or []}


def required_fields(obj, fields):
    return all(obj.get(k) not in (None, "", []) for k in fields)


def evaluate(stock, research, constitution):
    rules = constitution["rules"]
    vm = stock.get("valuation_model") or {}
    scenarios = vm.get("scenarios") or {}
    price = stock.get("reference_price")
    long = research.get("long_horizon_earnings") or {}
    catalysts = research.get("catalysts") or []
    survival = research.get("survival") or {}
    quarterly = research.get("quarterly_checks") or []
    gates = {}

    ep = rules["earnings_power"]
    ep_fields = ["metric", "baseline_period", "baseline_value", "target_period", "target_value", "target_multiple", "horizon_months", "evidence_and_assumptions"]
    if long.get("status") != "COMPLETE" or not required_fields(long, ep_fields) or not finite(long.get("target_multiple")) or not finite(long.get("horizon_months")):
        gates["earnings_power"] = gate("BLOCKED", reason="Missing structured 24-36m EPS/FCF model.")
    else:
        mult = float(long["target_multiple"]); months = float(long["horizon_months"])
        ok = mult >= float(ep["minimum_eps_or_fcf_multiple"]) and float(ep["horizon_months_min"]) <= months <= float(ep["horizon_months_max"])
        gates["earnings_power"] = gate("PASS" if ok else "FAIL", round(mult, 2), f">={ep['minimum_eps_or_fcf_multiple']}x within {ep['horizon_months_min']}-{ep['horizon_months_max']}m", "Earnings power meets constitution." if ok else "EPS/FCF path is not close enough to 2x inside 2-3 years.", long.get("evidence_and_assumptions"))

    bull = scenarios.get("bull") or {}; bear = scenarios.get("bear") or {}
    bull_fv = bull.get("fair_value"); bear_fv = bear.get("fair_value")
    bull_price_multiple = float(bull_fv) / float(price) if finite(bull_fv) and finite(price) and float(price) > 0 else None
    bear_return = (float(bear_fv) / float(price) - 1) * 100 if finite(bear_fv) and finite(price) and float(price) > 0 else None

    fd = rules["fundamental_driven_return"]
    current_mult = stock.get("pe_ttm")
    if not finite(current_mult) and finite(long.get("baseline_value")) and long.get("metric") == "EPS" and finite(price) and float(long["baseline_value"]) > 0:
        current_mult = float(price) / float(long["baseline_value"])
    bull_mult = bull.get("multiple")
    earnings_mult = long.get("target_multiple") if long.get("status") == "COMPLETE" else None
    contribution = None
    expansion = None
    if finite(earnings_mult) and bull_price_multiple and bull_price_multiple > 1 and float(earnings_mult) > 0:
        contribution = math.log(float(earnings_mult)) / math.log(float(bull_price_multiple)) * 100
    if finite(current_mult) and finite(bull_mult) and float(current_mult) > 0:
        expansion = float(bull_mult) / float(current_mult)
    if contribution is None or expansion is None:
        gates["fundamental_driven_return"] = gate("BLOCKED", reason="Cannot decompose Bull upside into earnings vs valuation contribution without structured long-horizon earnings and comparable valuation multiples.")
    else:
        ok = contribution >= float(fd["minimum_fundamental_upside_contribution_pct"]) and expansion <= float(fd["maximum_valuation_multiple_expansion_ratio"])
        gates["fundamental_driven_return"] = gate("PASS" if ok else "FAIL", {"fundamental_contribution_pct": round(contribution, 1), "valuation_expansion_ratio": round(expansion, 2)}, {"fundamental_contribution_pct": f">={fd['minimum_fundamental_upside_contribution_pct']}", "valuation_expansion_ratio": f"<={fd['maximum_valuation_multiple_expansion_ratio']}"}, "Bull return is fundamentally driven." if ok else "Bull case relies too much on valuation expansion.")

    cr = rules["catalyst"]
    valid_cat = [c for c in catalysts if required_fields(c, ["name", "mechanism", "kpi", "expected_window", "source_quality", "source_url"]) and c.get("source_quality") == cr["required_source_quality"]]
    gates["catalyst"] = gate("PASS" if len(valid_cat) >= int(cr["minimum_count"]) else "BLOCKED", len(valid_cat), f">={cr['minimum_count']} structured FIRST_PARTY catalyst", "Catalyst is measurable and sourced." if valid_cat else "No structured first-party catalyst with mechanism/KPI/window.", valid_cat)

    cv = rules["convexity"]
    if bull_price_multiple is None:
        gates["convexity"] = gate("BLOCKED", reason="Bull fair value/reference price unavailable.")
    else:
        ok = bull_price_multiple >= float(cv["minimum_bull_price_multiple"])
        gates["convexity"] = gate("PASS" if ok else "FAIL", round(bull_price_multiple, 2), f">={cv['minimum_bull_price_multiple']}x", "Bull convexity clears the hard gate." if ok else "Bull case is not at least 2.5x.")

    sd = rules["survival_downside"]
    if bear_return is None:
        downside_status = "BLOCKED"
    else:
        downside_status = "PASS" if bear_return >= float(sd["minimum_bear_return_pct"]) else "FAIL"
    if survival.get("status") != sd["require_survival_status"] or survival.get("existential_risk") not in ("NONE",):
        survival_status = "BLOCKED" if survival.get("status") in (None, "INCOMPLETE") or survival.get("existential_risk") in (None, "UNKNOWN") else "FAIL"
    else:
        survival_status = "PASS"
    combined = "FAIL" if "FAIL" in (downside_status, survival_status) else ("BLOCKED" if "BLOCKED" in (downside_status, survival_status) else "PASS")
    gates["survival_downside"] = gate(combined, None if bear_return is None else round(bear_return, 1), f">={sd['minimum_bear_return_pct']}% + survival PASS", "Bear case must be survivable without rescue financing.", survival.get("basis") or [])

    qf = rules["quarterly_falsifiability"]
    valid_q = [q for q in quarterly if required_fields(q, ["metric", "expected", "fail_condition", "source"])]
    gates["quarterly_falsifiability"] = gate("PASS" if len(valid_q) >= int(qf["minimum_metrics"]) else "BLOCKED", len(valid_q), f">={qf['minimum_metrics']} structured quarterly checks", "Thesis can be falsified every quarter." if len(valid_q) >= int(qf["minimum_metrics"]) else "Need explicit quarterly metrics and pre-committed fail conditions.", valid_q)

    statuses = [x["status"] for x in gates.values()]
    overall = "FAIL" if "FAIL" in statuses else ("BLOCKED" if "BLOCKED" in statuses else "PASS")
    upstream = stock.get("action")
    return {
        "ticker": str(stock.get("ticker")), "name": stock.get("name"), "upstream_action": upstream,
        "constitution_status": overall,
        "capital_eligible": overall == "PASS" and upstream == "BUY CANDIDATE",
        "gates": gates,
        "bull_price_multiple": None if bull_price_multiple is None else round(bull_price_multiple, 2),
        "bear_return_pct": None if bear_return is None else round(bear_return, 1),
        "next_required_evidence": [k for k, v in gates.items() if v["status"] == "BLOCKED"],
        "failed_rules": [k for k, v in gates.items() if v["status"] == "FAIL"]
    }


def generate():
    constitution = load_json("investment_constitution.json", {})
    research_bundle = load_json("constitution_research.json", {})
    research = research_bundle.get("securities") or {}
    alpha = (load_json("alpha_engine.json", {}).get("alpha") or {})
    rows = [evaluate(s, research.get(str(s.get("ticker")), {}), constitution) for s in alpha.get("stocks", [])]
    out = {
        "version": 1,
        "constitution_name": constitution.get("name"),
        "authority": constitution.get("authority"),
        "as_of": alpha.get("meta", {}).get("as_of"),
        "status": "COMPLETE",
        "securities": rows,
        "pass_count": sum(r["constitution_status"] == "PASS" for r in rows),
        "capital_eligible_count": sum(r["capital_eligible"] for r in rows),
        "guardrail": "Constitution cannot create upstream BUY. It can only block capital deployment; missing structured evidence fails closed."
    }
    save_json("investment_constitution_results.json", out)
    return out


if __name__ == "__main__":
    print(json.dumps(generate(), ensure_ascii=False, indent=2))
