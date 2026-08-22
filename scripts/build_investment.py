#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from common import DATA, TZ, save_json


def _load(name: str, default=None):
    path = DATA / name
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def _score(value):
    return None if value is None else round(float(value), 2)


def _macro_context(cycle, growth, domestic, financial):
    required = [cycle, growth, financial]
    if any(v is None for v in required):
        return "UNKNOWN", "總經關鍵分數不足，不調整個股 Buy Gate。"
    if any(float(v) <= -25 for v in required):
        return "DEFENSIVE", "景氣、成長延續或金融條件至少一項明顯轉弱；降低風險背景評價，但不直接改寫 Alpha action。"
    if float(cycle) >= 50 and float(growth) >= 50 and float(financial) >= 25:
        if domestic is not None and float(domestic) >= 25:
            return "BROADLY_SUPPORTIVE", "景氣、成長延續、金融條件與內需同向偏強；屬廣泛支持的風險背景。"
        return "EXPORT_LED_SUPPORTIVE", "景氣、成長延續與金融條件偏強，但內需未必同步；屬出口／科技主導的支持背景。"
    if float(cycle) >= 20 and float(growth) >= 20 and float(financial) >= 0:
        return "CONSTRUCTIVE", "總經背景偏正向但不是全面強勢；個股仍必須靠自身 Alpha / valuation / evidence 過關。"
    return "MIXED", "總經訊號混合；維持選股優先，不以 macro context 取代個股 Buy Gate。"


def _age_days(as_of: str | None, now_date: dt.date):
    if not as_of:
        return None
    try:
        return (now_date - dt.date.fromisoformat(as_of)).days
    except ValueError:
        return None


def _canonical_valuation(asset: dict):
    """Consume stock schema v6 while retaining read-only support for the last v5 snapshot.

    `base_upside_pct` is the canonical quantity. A legacy MOS-named field is read only
    as migration fallback and is never republished by Elephant.
    """
    metrics = asset.get("valuation_metrics") or {}
    model = asset.get("valuation_model") or {}
    expected = metrics.get("expected_return_pct")
    if expected is None:
        expected = model.get("expected_return_pct")
    base_upside = metrics.get("base_upside_pct")
    if base_upside is None:
        base_upside = model.get("base_upside_pct")
    if base_upside is None:
        base_upside = metrics.get("margin_of_safety_pct")
    if base_upside is None:
        base_upside = model.get("margin_of_safety_pct")
    return expected, base_upside


def build(alpha_engine: dict, summary: dict, decision_scores: dict, now: dt.datetime | None = None):
    now = now or dt.datetime.now(TZ).replace(microsecond=0)
    alpha = alpha_engine.get("alpha", {})
    screen = alpha_engine.get("screen", {})
    performance = alpha_engine.get("performance", {})
    current = decision_scores.get("current", {})

    cycle = summary.get("cycle", {})
    growth = current.get("growth_persistence", {})
    domestic = current.get("domestic_demand", {})
    financial = current.get("financial_conditions", {})
    context, context_text = _macro_context(
        cycle.get("score"), growth.get("score"), domestic.get("score"), financial.get("score")
    )

    benchmark = alpha.get("benchmark_asset", {})
    researched = []
    for stock in sorted(alpha.get("stocks", []), key=lambda x: x.get("rank", 9999)):
        expected_return, base_upside = _canonical_valuation(stock)
        researched.append({
            "rank": stock.get("rank"),
            "ticker": stock.get("ticker"),
            "name": stock.get("name"),
            "score": stock.get("score"),
            "grade": stock.get("grade"),
            "confidence_score": stock.get("confidence_score"),
            "action": stock.get("action"),
            "reference_price": stock.get("reference_price"),
            "reference_price_date": stock.get("reference_price_date"),
            "expected_return_pct": expected_return,
            "base_upside_pct": base_upside,
            "alpha_spread_pct": stock.get("alpha_spread_pct"),
            "thesis": stock.get("thesis"),
            "next_check": stock.get("next_check"),
            "macro_context": context,
            "macro_context_changes_alpha_score": False,
        })

    buy_candidates = [x for x in researched if x.get("action") == "BUY CANDIDATE"]
    verify = [x for x in researched if x.get("action") == "VERIFY"]
    top_screen = []
    for row in sorted(screen.get("candidates", []), key=lambda x: x.get("rank", 9999))[:10]:
        top_screen.append({
            "rank": row.get("rank"),
            "ticker": row.get("ticker"),
            "name": row.get("name"),
            "market": row.get("market"),
            "industry": row.get("industry"),
            "reference_price": row.get("reference_price"),
            "screen_priority": row.get("screen_priority"),
            "screen_score": row.get("screen_score"),
            "revenue_yoy_pct": row.get("revenue_yoy_pct"),
            "pe_ttm": row.get("pe_ttm"),
            "deep_research_selected": bool(row.get("deep_research_selected")),
            "status": row.get("status"),
        })

    alpha_meta = alpha.get("meta", {})
    screen_meta = screen.get("meta", {})
    alpha_age = _age_days(alpha_meta.get("as_of"), now.date())
    screen_age = _age_days(screen_meta.get("as_of"), now.date())
    research_stale = alpha_age is None or alpha_age > 10
    screen_stale = screen_age is None or screen_age > 3

    if buy_candidates:
        selection_text = f"目前有 {len(buy_candidates)} 檔通過 Alpha Buy Gate；macro context 只作背景，不新增或取消 BUY。"
    elif verify:
        selection_text = f"目前沒有 BUY CANDIDATE；有 {len(verify)} 檔處於 VERIFY，需等待 freshness / evidence / valuation gate 完整通過。"
    else:
        selection_text = "目前沒有 BUY CANDIDATE；保持研究與等待，不因總經偏強自動升級個股。"

    benchmark_expected, benchmark_base_upside = _canonical_valuation(benchmark)
    return {
        "version": 2,
        "generated_at": now.isoformat(),
        "status": "DEGRADED" if research_stale or screen_stale or screen_meta.get("status") != "COMPLETE" else "COMPLETE",
        "architecture": {
            "product": "Elephant",
            "macro_engine": "Elephant deterministic economic diagnosis",
            "alpha_engine": "linwuyen/stock",
            "alpha_schema": alpha_meta.get("schema_version"),
            "contract": "Macro context is orthogonal to Alpha Score. Stock Buy Gate remains authoritative.",
        },
        "sources": {
            "elephant_summary_generated_at": summary.get("generated_at"),
            "elephant_decision_generated_at": decision_scores.get("generated_at"),
            "alpha_synced_at": alpha_engine.get("synced_at"),
            "alpha_research_as_of": alpha_meta.get("as_of"),
            "screen_as_of": screen_meta.get("as_of"),
            "screen_status": screen_meta.get("status"),
            "upstream_repository": alpha_engine.get("upstream", {}).get("repository"),
        },
        "freshness": {
            "alpha_research_age_days": alpha_age,
            "screen_age_days": screen_age,
            "alpha_research_stale": research_stale,
            "screen_stale": screen_stale,
        },
        "macro_context": {
            "label": context,
            "text": context_text,
            "cycle": {"score": _score(cycle.get("score")), "label": cycle.get("label"), "period": cycle.get("as_of")},
            "growth_persistence": {"score": _score(growth.get("score")), "label": growth.get("label"), "period": growth.get("period")},
            "domestic_demand": {"score": _score(domestic.get("score")), "label": domestic.get("label"), "period": domestic.get("period")},
            "financial_conditions": {"score": _score(financial.get("score")), "label": financial.get("label"), "period": financial.get("period")},
        },
        "benchmark": {
            "ticker": benchmark.get("ticker"),
            "name": benchmark.get("name"),
            "reference_price": benchmark.get("reference_price"),
            "reference_price_date": benchmark.get("reference_price_date"),
            "expected_return_pct": benchmark_expected,
            "base_upside_pct": benchmark_base_upside,
            "confidence_score": benchmark.get("confidence_score"),
            "rotation_event": alpha.get("rotation_event", {}),
        },
        "selection": {
            "text": selection_text,
            "buy_candidate_count": len(buy_candidates),
            "verify_count": len(verify),
            "researched": researched,
            "top_screen": top_screen,
            "deep_research_queue": screen.get("deep_research_queue", []),
        },
        "calibration": performance,
        "guardrails": {
            "alpha_score_unchanged_by_macro": True,
            "macro_context_cannot_create_buy_candidate": True,
            "screen_is_not_buy_gate": True,
            "stock_buy_gate_authoritative": True,
            "stock_base_upside_semantics_preserved": True,
            "no_automatic_trading": True,
        },
    }


def generate():
    alpha_engine = _load("alpha_engine.json", {})
    summary = _load("summary.json", {})
    decision_scores = _load("decision_scores.json", {})
    result = build(alpha_engine, summary, decision_scores)
    save_json("investment.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(generate(), ensure_ascii=False, indent=2))
