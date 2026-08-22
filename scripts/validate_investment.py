#!/usr/bin/env python3
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def load(name):
    path = DATA / name
    if not path.exists():
        raise SystemExit(f"INVESTMENT VALIDATION ERROR: missing data/{name}")
    return json.loads(path.read_text(encoding="utf-8"))


def fail(message):
    print("INVESTMENT VALIDATION ERROR:", message, file=sys.stderr)
    raise SystemExit(1)


def finite_or_none(value):
    return value is None or (isinstance(value, (int, float)) and math.isfinite(value))


def canonical_valuation(asset):
    metrics = asset.get("valuation_metrics") or {}
    model = asset.get("valuation_model") or {}
    expected = metrics.get("expected_return_pct")
    if expected is None:
        expected = model.get("expected_return_pct")
    base_upside = metrics.get("base_upside_pct")
    if base_upside is None:
        base_upside = model.get("base_upside_pct")
    return expected, base_upside


investment = load("investment.json")
upstream = load("alpha_engine.json")
alpha = upstream.get("alpha", {})
screen = upstream.get("screen", {})

if investment.get("version") != 2:
    fail("unsupported investment version")
if investment.get("status") not in {"COMPLETE", "DEGRADED"}:
    fail("invalid investment status")
if investment.get("architecture", {}).get("alpha_schema") != 6:
    fail("investment did not record stock Alpha schema v6")

guards = investment.get("guardrails", {})
required_true = {
    "alpha_score_unchanged_by_macro",
    "macro_context_cannot_create_buy_candidate",
    "screen_is_not_buy_gate",
    "stock_buy_gate_authoritative",
    "stock_base_upside_semantics_preserved",
    "no_automatic_trading",
}
if any(guards.get(key) is not True for key in required_true):
    fail("investment guardrail missing/false")

macro = investment.get("macro_context", {})
if macro.get("label") not in {"UNKNOWN", "DEFENSIVE", "MIXED", "CONSTRUCTIVE", "EXPORT_LED_SUPPORTIVE", "BROADLY_SUPPORTIVE"}:
    fail("invalid macro context label")
for key in ("cycle", "growth_persistence", "domestic_demand", "financial_conditions"):
    value = macro.get(key, {}).get("score")
    if not finite_or_none(value) or (value is not None and not -100 <= value <= 100):
        fail(f"invalid macro score {key}: {value}")

upstream_stocks = {str(x.get("ticker")): x for x in alpha.get("stocks", [])}
researched = investment.get("selection", {}).get("researched", [])
if len(researched) != len(upstream_stocks):
    fail("researched stock count diverged from Alpha Engine")
for row in researched:
    ticker = str(row.get("ticker"))
    source = upstream_stocks.get(ticker)
    if not source:
        fail(f"unknown researched ticker {ticker}")
    if row.get("score") != source.get("score"):
        fail(f"macro layer changed Alpha score for {ticker}")
    if row.get("action") != source.get("action"):
        fail(f"macro layer changed Alpha action for {ticker}")
    if row.get("confidence_score") != source.get("confidence_score"):
        fail(f"macro layer changed confidence for {ticker}")
    expected_return, base_upside = canonical_valuation(source)
    if row.get("expected_return_pct") != expected_return:
        fail(f"expected return diverged from Alpha Engine for {ticker}")
    if row.get("base_upside_pct") != base_upside:
        fail(f"base upside diverged from Alpha Engine for {ticker}")
    if "margin_of_safety_pct" in row:
        fail(f"legacy MOS field republished for {ticker}")
    if row.get("macro_context_changes_alpha_score") is not False:
        fail(f"macro/alpha separation flag invalid for {ticker}")

expected_buy = sorted(str(x.get("ticker")) for x in alpha.get("stocks", []) if x.get("action") == "BUY CANDIDATE")
actual_buy = sorted(str(x.get("ticker")) for x in researched if x.get("action") == "BUY CANDIDATE")
if expected_buy != actual_buy:
    fail("macro layer created/removed BUY CANDIDATE")
if investment.get("selection", {}).get("buy_candidate_count") != len(expected_buy):
    fail("buy candidate count mismatch")

screen_rows = investment.get("selection", {}).get("top_screen", [])
if len(screen_rows) > 10:
    fail("investment top screen exceeds 10")
source_screen = {str(x.get("ticker")): x for x in screen.get("candidates", [])}
for row in screen_rows:
    if str(row.get("ticker")) not in source_screen:
        fail("investment screen contains unknown ticker")
    if "action" in row:
        fail("discovery screen leaked portfolio action")

benchmark = investment.get("benchmark", {})
source_benchmark = alpha.get("benchmark_asset", {})
if benchmark.get("ticker") != source_benchmark.get("ticker"):
    fail("benchmark ticker mismatch")
benchmark_expected, benchmark_base_upside = canonical_valuation(source_benchmark)
if benchmark.get("expected_return_pct") != benchmark_expected:
    fail("benchmark expected return mismatch")
if benchmark.get("base_upside_pct") != benchmark_base_upside:
    fail("benchmark base upside mismatch")
if "margin_of_safety_pct" in benchmark:
    fail("legacy benchmark MOS field republished")

freshness = investment.get("freshness", {})
for key in ("alpha_research_age_days", "screen_age_days"):
    value = freshness.get(key)
    if value is not None and (not isinstance(value, int) or value < 0):
        fail(f"invalid freshness {key}")

print("INVESTMENT VALIDATION PASS")
print("macro context:", macro.get("label"))
print("researched stocks:", len(researched))
print("buy candidates:", len(actual_buy))
print("screen status:", investment.get("sources", {}).get("screen_status"))
