#!/usr/bin/env python3
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def load(name):
    p = DATA / name
    if not p.exists():
        print(f"CAPITAL VALIDATION ERROR: missing {name}", file=sys.stderr)
        raise SystemExit(1)
    return json.loads(p.read_text(encoding="utf-8"))


def fail(msg):
    print("CAPITAL VALIDATION ERROR:", msg, file=sys.stderr)
    raise SystemExit(1)


def finite(v):
    return isinstance(v, (int, float)) and math.isfinite(float(v))

policy = load("portfolio_policy.json")
state = load("portfolio_state.json")
opp_inputs = load("opportunity_inputs.json")
capital = load("capital_allocation.json")
research = load("deep_research_queue.json")
opportunity = load("opportunity_set.json")
alpha_bundle = load("alpha_engine.json")
alpha = alpha_bundle.get("alpha", {})
screen = alpha_bundle.get("screen", {})

if capital.get("version") != 1:
    fail("capital_allocation version")
if not capital.get("fingerprint") or len(capital["fingerprint"]) < 32:
    fail("capital allocation fingerprint missing")
if capital.get("guardrails", {}).get("portfolio_cannot_upgrade_upstream_action") is not True:
    fail("portfolio upgrade guardrail missing")
if capital.get("guardrails", {}).get("unavailable_benchmarks_not_fabricated") is not True:
    fail("benchmark fabrication guardrail missing")
if capital.get("guardrails", {}).get("personalized_sizing_requires_complete_portfolio_state") is not True:
    fail("personal sizing guardrail missing")

if policy.get("fail_closed") is not True:
    fail("portfolio policy must fail closed")
constraints = policy.get("constraints", {})
for key in ("max_single_stock_pct", "max_sector_pct", "max_common_factor_pct", "cash_floor_pct", "max_gross_exposure_pct"):
    v = constraints.get(key)
    if not finite(v) or not 0 <= float(v) <= 100:
        fail(f"invalid policy {key}")

if state.get("status") not in {"UNCONFIGURED", "COMPLETE"}:
    fail("portfolio_state status")
if state.get("status") != "COMPLETE" and capital.get("target_sizing", {}).get("status") == "COMPLETE":
    fail("personalized sizing emitted without complete portfolio state")

alts = opportunity.get("alternatives", [])
if not alts:
    fail("opportunity set empty")
for a in alts:
    if a.get("status") == "UNAVAILABLE" and a.get("expected_return_pct") is not None:
        fail(f"unavailable alternative fabricated return: {a.get('id')}")
if opportunity.get("available_count", 0) < 1:
    fail("no opportunity benchmark available")
if opportunity.get("hurdle_asset") is None or not finite(opportunity.get("hurdle_expected_return_pct")):
    fail("hurdle missing")

screen_tickers = {str(x.get("ticker")) for x in screen.get("deep_research_queue", [])}
for item in research.get("items", []):
    if str(item.get("ticker")) not in screen_tickers:
        fail("research queue item not sourced from deep research queue")
    if item.get("promotion_authority") != "NONE":
        fail("research queue illegally has promotion authority")
    if item.get("archetype") not in {"SECULAR_GROWTH", "CYCLICAL_MEMORY", "PROPERTY", "UTILITY", "FINANCIAL", "ASSET_NAV", "GENERAL_INDUSTRIAL"}:
        fail("invalid archetype")

upstream = {str(x.get("ticker")): x.get("action") for x in alpha.get("stocks", [])}
for row in capital.get("lifecycle", []):
    t = str(row.get("ticker"))
    ua = row.get("upstream_action")
    if upstream.get(t) != ua:
        fail(f"lifecycle upstream action mismatch {t}")
    pa = row.get("portfolio_action")
    if ua != "BUY CANDIDATE" and pa in {"BUY_REVIEW", "ADD_REVIEW"}:
        fail(f"portfolio upgraded non-BUY upstream {t}")

for row in capital.get("probabilistic_returns", []):
    d = row.get("distribution", {})
    if d.get("status") == "COMPLETE":
        ss = d.get("scenarios", [])
        if len(ss) != 3:
            fail("complete probability distribution without three scenarios")
        p = sum(float(x.get("probability", 0)) for x in ss)
        if abs(p - 1.0) > 0.02:
            fail("scenario probabilities do not sum to one")
        b = d.get("probability_beating_hurdle_pct")
        l = d.get("probability_loss_gt_20_pct")
        if b is not None and not 0 <= float(b) <= 100:
            fail("invalid beat probability")
        if l is not None and not 0 <= float(l) <= 100:
            fail("invalid loss probability")

risk = capital.get("portfolio_risk", {})
if state.get("status") != "COMPLETE" and risk.get("personalized") is True:
    fail("personalized risk emitted without state")
if state.get("status") == "COMPLETE" and risk.get("status") not in {"PASS", "REVIEW"}:
    fail("complete portfolio missing risk status")

friction = opp_inputs.get("frictions", {}).get("round_trip_friction_pct")
if not finite(friction) or friction < 0:
    fail("invalid friction assumption")

print("CAPITAL ALLOCATION VALIDATION PASS")
print("research queue:", len(research.get("items", [])))
print("opportunity alternatives:", len(alts), "available:", opportunity.get("available_count"))
print("hurdle:", opportunity.get("hurdle_asset"), opportunity.get("hurdle_expected_return_pct"))
print("portfolio state:", state.get("status"))
print("risk:", risk.get("status"))
print("sizing:", capital.get("target_sizing", {}).get("status"))
