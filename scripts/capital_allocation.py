#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from pathlib import Path

from common import DATA, TZ, save_json


def load(name, default=None):
    p = DATA / name
    if not p.exists():
        return {} if default is None else default
    return json.loads(p.read_text(encoding="utf-8"))


def finite(v):
    return isinstance(v, (int, float)) and math.isfinite(float(v))


def pct_return(fv, price):
    if not finite(fv) or not finite(price) or float(price) <= 0:
        return None
    return (float(fv) / float(price) - 1.0) * 100.0


def business_archetype(row):
    text = " ".join(str(row.get(k, "")) for k in ("name", "industry", "thesis")).lower()
    flags = " ".join(row.get("flags", [])).lower()
    joined = text + " " + flags
    memory = ("記憶體", "memory", "dram", "nand", "flash")
    property_words = ("建設", "營造", "property", "construction")
    utility_words = ("電力", "汽電", "utility", "power generation")
    secular = ("ai", "server", "cloud", "光通訊", "hpc", "datacenter", "data center")
    asset = ("控股", "資產", "holding", "asset")
    if any(x in joined for x in memory):
        return "CYCLICAL_MEMORY"
    if any(x in joined for x in property_words):
        return "PROPERTY"
    if any(x in joined for x in utility_words):
        return "UTILITY"
    if any(x in joined for x in asset):
        return "ASSET_NAV"
    if any(x in joined for x in secular):
        return "SECULAR_GROWTH"
    return "GENERAL_INDUSTRIAL"


def scenario_distribution(stock, hurdle_pct):
    vm = stock.get("valuation_model", {})
    price = stock.get("reference_price")
    scenarios = vm.get("scenarios") or {}
    rows = []
    prob_sum = 0.0
    weighted = 0.0
    beat_prob = 0.0
    loss20_prob = 0.0
    downside_returns = []
    for key in ("bear", "base", "bull"):
        s = scenarios.get(key) or {}
        p = s.get("probability")
        fv = s.get("fair_value")
        er = pct_return(fv, price)
        if not finite(p) or er is None:
            continue
        p = float(p)
        prob_sum += p
        weighted += p * er
        if hurdle_pct is not None and er > hurdle_pct:
            beat_prob += p
        if er <= -20:
            loss20_prob += p
        if er < 0:
            downside_returns.append((p, er))
        rows.append({"scenario": key, "probability": p, "return_pct": round(er, 2), "fair_value": fv})
    if prob_sum <= 0:
        return {
            "status": "INCOMPLETE",
            "scenarios": rows,
            "expected_return_pct": vm.get("expected_return_pct"),
            "probability_beating_hurdle_pct": None,
            "probability_loss_gt_20_pct": None,
            "expected_shortfall_pct": None,
        }
    weighted /= prob_sum
    beat = beat_prob / prob_sum * 100 if hurdle_pct is not None else None
    loss20 = loss20_prob / prob_sum * 100
    neg_p = sum(p for p, _ in downside_returns)
    exp_shortfall = sum(p * r for p, r in downside_returns) / neg_p if neg_p else 0.0
    return {
        "status": "COMPLETE" if len(rows) >= 3 and abs(prob_sum - 1.0) <= 0.02 else "PARTIAL",
        "scenarios": rows,
        "expected_return_pct": round(weighted, 2),
        "probability_beating_hurdle_pct": None if beat is None else round(beat, 1),
        "probability_loss_gt_20_pct": round(loss20, 1),
        "expected_shortfall_pct": round(exp_shortfall, 2),
    }


def opportunity_set(alpha, inputs, portfolio):
    benchmark = alpha.get("benchmark_asset", {})
    bvm = benchmark.get("valuation_model", {})
    out = []
    for alt in inputs.get("alternatives", []):
        row = dict(alt)
        if row.get("id") == "2330":
            er = bvm.get("expected_return_pct")
            row["expected_return_pct"] = er
            row["status"] = "AVAILABLE" if finite(er) else "UNAVAILABLE"
            row["source"] = "ALPHA_ENGINE"
        elif row.get("id") == "DEBT_REPAYMENT":
            rate = portfolio.get("debt_effective_rate_pct") if portfolio.get("status") == "COMPLETE" else None
            row["expected_return_pct"] = rate if finite(rate) else None
            row["status"] = "AVAILABLE" if finite(rate) else "UNAVAILABLE"
            row["source"] = "PORTFOLIO_STATE"
        elif finite(row.get("expected_return_pct")):
            row["status"] = "AVAILABLE"
        else:
            row["status"] = "UNAVAILABLE"
        out.append(row)
    available = [x for x in out if x.get("status") == "AVAILABLE" and finite(x.get("expected_return_pct"))]
    hurdle = max((float(x["expected_return_pct"]) for x in available), default=None)
    leader = next((x for x in available if hurdle is not None and float(x["expected_return_pct"]) == hurdle), None)
    return {
        "status": "COMPLETE" if len(available) >= 3 else "PARTIAL",
        "alternatives": out,
        "available_count": len(available),
        "hurdle_expected_return_pct": hurdle,
        "hurdle_asset": leader.get("id") if leader else None,
        "note": "Hurdle uses only AVAILABLE alternatives; unavailable benchmarks never receive fabricated returns.",
    }


def build_research_queue(screen, alpha):
    researched = {str(x.get("ticker")) for x in alpha.get("stocks", [])}
    rows = []
    queue = screen.get("deep_research_queue") or []
    for row in queue:
        x = {
            "ticker": str(row.get("ticker")),
            "name": row.get("name"),
            "market": row.get("market"),
            "rank": row.get("rank"),
            "screen_priority": row.get("screen_priority"),
            "reference_price": row.get("reference_price"),
            "archetype": business_archetype(row),
            "already_researched": str(row.get("ticker")) in researched,
            "status": "REFRESH" if str(row.get("ticker")) in researched else "NEW_RESEARCH",
            "required_evidence": ["reference_price", "earnings_basis", "revenue_trend", "balance_sheet_cash_flow", "material_events", "valuation_basis"],
            "promotion_authority": "NONE",
            "next_action": "collect first-party evidence → classify valuation route → build scenarios → upstream Alpha Buy Gate",
        }
        rows.append(x)
    return {
        "status": "COMPLETE" if screen.get("meta", {}).get("status") == "COMPLETE" else "DEGRADED",
        "as_of": screen.get("meta", {}).get("as_of"),
        "items": rows,
        "new_research_count": sum(1 for x in rows if x["status"] == "NEW_RESEARCH"),
        "guardrail": "Research queue cannot create BUY CANDIDATE.",
    }


def portfolio_weights(portfolio):
    if portfolio.get("status") != "COMPLETE" or not finite(portfolio.get("investable_assets_twd")) or float(portfolio["investable_assets_twd"]) <= 0:
        return {}
    total = float(portfolio["investable_assets_twd"])
    weights = {}
    for p in portfolio.get("positions", []):
        ticker = str(p.get("ticker"))
        mv = p.get("market_value_twd")
        if ticker and finite(mv):
            weights[ticker] = float(mv) / total * 100
    cash = portfolio.get("cash_twd")
    if finite(cash):
        weights["CASH"] = float(cash) / total * 100
    return weights


def lifecycle_actions(alpha, opportunity, policy, portfolio):
    hurdle = opportunity.get("hurdle_expected_return_pct")
    friction = load("opportunity_inputs.json", {}).get("frictions", {}).get("round_trip_friction_pct", 0)
    weights = portfolio_weights(portfolio)
    lc = policy.get("lifecycle", {})
    out = []
    for s in alpha.get("stocks", []):
        vm = s.get("valuation_model", {})
        er = vm.get("expected_return_pct")
        net_alpha = None
        if finite(er) and finite(hurdle):
            net_alpha = float(er) - float(hurdle) - (float(friction) if finite(friction) else 0)
        upstream = s.get("action")
        thesis = s.get("thesis_status")
        current_weight = weights.get(str(s.get("ticker")))
        action = "RESEARCH"
        reason = "Upstream action is not BUY; portfolio layer cannot upgrade it."
        if thesis == "INVALIDATED":
            action, reason = "EXIT_REVIEW", "Thesis invalidated."
        elif upstream == "BUY CANDIDATE":
            if net_alpha is None:
                action, reason = "HOLD_REVIEW", "Opportunity hurdle incomplete."
            elif net_alpha <= float(lc.get("exit_when_net_alpha_spread_below_pct", -5)):
                action, reason = "EXIT_REVIEW", "Net alpha spread materially below opportunity hurdle."
            elif net_alpha <= float(lc.get("trim_when_net_alpha_spread_below_pct", 2)):
                action, reason = "TRIM_REVIEW", "Net alpha edge has compressed."
            elif current_weight is None:
                action, reason = "BUY_REVIEW", "Upstream BUY plus positive opportunity-set edge; sizing needs portfolio state."
            else:
                action, reason = "ADD_REVIEW", "Upstream BUY remains valid and position exists."
        elif current_weight is not None:
            action, reason = "HOLD_REVIEW", "Held position is no longer a BUY candidate; review thesis and opportunity cost."
        out.append({
            "ticker": s.get("ticker"),
            "name": s.get("name"),
            "upstream_action": upstream,
            "portfolio_action": action,
            "expected_return_pct": er,
            "hurdle_expected_return_pct": hurdle,
            "net_alpha_spread_pct": None if net_alpha is None else round(net_alpha, 2),
            "current_weight_pct": None if current_weight is None else round(current_weight, 2),
            "reason": reason,
        })
    return out


def risk_engine(alpha, portfolio, policy):
    weights = portfolio_weights(portfolio)
    if portfolio.get("status") != "COMPLETE":
        return {
            "status": "UNCONFIGURED",
            "personalized": False,
            "violations": [],
            "stress_tests": [],
            "note": "Portfolio state is not COMPLETE; no personalized risk or leverage recommendation emitted.",
        }
    stocks = {str(x.get("ticker")): x for x in alpha.get("stocks", [])}
    max_single = policy.get("constraints", {}).get("max_single_stock_pct", 25)
    violations = []
    factor = {}
    for ticker, w in weights.items():
        if ticker == "CASH":
            continue
        if w > max_single:
            violations.append({"type": "SINGLE_STOCK", "ticker": ticker, "weight_pct": round(w, 2), "limit_pct": max_single})
        s = stocks.get(ticker, {})
        a = business_archetype(s)
        factor[a] = factor.get(a, 0.0) + w
    max_factor = policy.get("constraints", {}).get("max_common_factor_pct", 60)
    for name, w in factor.items():
        if w > max_factor:
            violations.append({"type": "COMMON_FACTOR", "factor": name, "weight_pct": round(w, 2), "limit_pct": max_factor})
    debt = float(portfolio.get("debt_twd") or 0)
    assets = float(portfolio.get("investable_assets_twd") or 0)
    debt_ratio = debt / assets * 100 if assets > 0 else None
    max_debt = policy.get("constraints", {}).get("max_net_debt_to_investable_assets_pct", 25)
    if debt_ratio is not None and debt_ratio > max_debt:
        violations.append({"type": "LEVERAGE", "value_pct": round(debt_ratio, 2), "limit_pct": max_debt})
    equity_weight = sum(w for t, w in weights.items() if t != "CASH")
    stress = []
    for shock in (-20, -35, -50):
        loss_pct = equity_weight / 100 * shock
        post_assets = assets * (1 + loss_pct / 100)
        post_debt_ratio = debt / post_assets * 100 if post_assets > 0 else None
        stress.append({"market_shock_pct": shock, "portfolio_impact_pct": round(loss_pct, 2), "post_shock_debt_ratio_pct": None if post_debt_ratio is None else round(post_debt_ratio, 2)})
    return {
        "status": "REVIEW" if violations else "PASS",
        "personalized": True,
        "weights_pct": {k: round(v, 2) for k, v in weights.items()},
        "common_factor_exposure_pct": {k: round(v, 2) for k, v in factor.items()},
        "debt_to_investable_assets_pct": None if debt_ratio is None else round(debt_ratio, 2),
        "violations": violations,
        "stress_tests": stress,
    }


def target_sizing(alpha, opportunity, policy, portfolio):
    if portfolio.get("status") != "COMPLETE":
        return {"status": "UNCONFIGURED", "targets": [], "note": "Configure portfolio_state before personalized sizing."}
    hurdle = opportunity.get("hurdle_expected_return_pct")
    if hurdle is None:
        return {"status": "BLOCKED", "targets": [], "note": "Opportunity hurdle unavailable."}
    candidates = []
    for s in alpha.get("stocks", []):
        if s.get("action") != "BUY CANDIDATE":
            continue
        vm = s.get("valuation_model", {})
        er = vm.get("expected_return_pct")
        conf = s.get("confidence_score")
        down = s.get("risk_model", {}).get("downside_pct")
        dist = scenario_distribution(s, hurdle)
        beat = dist.get("probability_beating_hurdle_pct")
        if not all(finite(x) for x in (er, conf, down, beat)):
            continue
        spread = max(0.0, float(er) - float(hurdle))
        raw = spread * (float(conf) / 100) * (float(beat) / 100) / max(10.0, float(down))
        if raw > 0:
            candidates.append((s, raw, dist))
    if not candidates:
        return {"status": "NO_BUY", "targets": [], "note": "No fully qualified BUY candidate with complete probabilistic sizing inputs."}
    investable_target = policy.get("sizing", {}).get("normalize_to_investable_pct", 85)
    max_single = policy.get("constraints", {}).get("max_single_stock_pct", 25)
    max_new = policy.get("constraints", {}).get("max_new_position_pct", 12)
    total = sum(x[1] for x in candidates)
    weights = portfolio_weights(portfolio)
    targets = []
    for s, raw, dist in candidates:
        unconstrained = raw / total * investable_target
        current = weights.get(str(s.get("ticker")), 0.0)
        cap = max_single if current > 0 else min(max_single, max_new)
        target = min(cap, unconstrained)
        targets.append({
            "ticker": s.get("ticker"), "name": s.get("name"), "target_weight_pct": round(target, 2),
            "current_weight_pct": round(current, 2), "raw_score": round(raw, 4),
            "probability_beating_hurdle_pct": dist.get("probability_beating_hurdle_pct"),
        })
    return {"status": "COMPLETE", "targets": targets, "cash_floor_pct": policy.get("constraints", {}).get("cash_floor_pct")}


def fingerprint(obj):
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def generate():
    now = dt.datetime.now(TZ).replace(microsecond=0)
    alpha_engine = load("alpha_engine.json")
    alpha = alpha_engine.get("alpha", {})
    screen = alpha_engine.get("screen", {})
    policy = load("portfolio_policy.json")
    portfolio = load("portfolio_state.json")
    opp_inputs = load("opportunity_inputs.json")
    opportunity = opportunity_set(alpha, opp_inputs, portfolio)
    research_queue = build_research_queue(screen, alpha)
    lifecycle = lifecycle_actions(alpha, opportunity, policy, portfolio)
    risk = risk_engine(alpha, portfolio, policy)
    sizing = target_sizing(alpha, opportunity, policy, portfolio)
    distributions = []
    hurdle = opportunity.get("hurdle_expected_return_pct")
    for s in alpha.get("stocks", []):
        distributions.append({
            "ticker": s.get("ticker"),
            "name": s.get("name"),
            "archetype": business_archetype(s),
            "valuation_model": s.get("valuation_model", {}).get("model_type"),
            "distribution": scenario_distribution(s, hurdle),
        })
    result = {
        "version": 1,
        "generated_at": now.isoformat(),
        "status": "COMPLETE" if alpha and screen else "DEGRADED",
        "objective": policy.get("objective"),
        "research_queue": research_queue,
        "opportunity_set": opportunity,
        "probabilistic_returns": distributions,
        "lifecycle": lifecycle,
        "portfolio_risk": risk,
        "target_sizing": sizing,
        "portfolio_state_status": portfolio.get("status"),
        "guardrails": {
            "portfolio_cannot_upgrade_upstream_action": True,
            "unavailable_benchmarks_not_fabricated": True,
            "personalized_sizing_requires_complete_portfolio_state": True,
            "no_automatic_trading": True,
        },
    }
    result["fingerprint"] = fingerprint({k: result[k] for k in ("research_queue", "opportunity_set", "lifecycle", "portfolio_risk", "target_sizing")})
    save_json("capital_allocation.json", result)
    save_json("deep_research_queue.json", research_queue)
    save_json("opportunity_set.json", opportunity)
    return result


if __name__ == "__main__":
    print(json.dumps(generate(), ensure_ascii=False, indent=2))
