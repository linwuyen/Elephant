#!/usr/bin/env python3
import datetime as dt

import build_investment


def sample(action="VERIFY"):
    alpha_engine = {
        "synced_at": "2026-08-15T00:00:00+08:00",
        "upstream": {"repository": "https://github.com/linwuyen/stock"},
        "alpha": {
            "meta": {"schema_version": 6, "decision_engine_version": "security-v6.0.0", "as_of": "2026-08-15"},
            "benchmark_asset": {
                "ticker": "2330",
                "name": "台積電",
                "reference_price": 2500,
                "reference_price_date": "2026-08-15",
                "confidence_score": 90,
                "valuation_metrics": {"expected_return_pct": 20, "base_upside_pct": 30},
            },
            "rotation_event": {"trigger_price": 3000},
            "stocks": [{
                "rank": 1,
                "ticker": "9999",
                "name": "測試股",
                "score": 90,
                "grade": "A",
                "confidence_score": 88,
                "action": action,
                "reference_price": 100,
                "reference_price_date": "2026-08-15",
                "alpha_spread_pct": 12,
                "valuation_metrics": {"expected_return_pct": 32, "base_upside_pct": 25},
                "thesis": "test",
                "next_check": "test",
            }],
        },
        "screen": {
            "meta": {"as_of": "2026-08-15", "status": "COMPLETE"},
            "candidates": [{"rank": 1, "ticker": "8888", "name": "Screen only", "screen_priority": 100}],
            "deep_research_queue": [],
        },
        "performance": {"meta": {"schema_version": 2, "primary_cohort": "BUY_CANDIDATE"}},
    }
    summary = {"generated_at": "x", "cycle": {"score": 80, "label": "強勁擴張", "as_of": "2026-06"}}
    decision = {
        "generated_at": "x",
        "current": {
            "growth_persistence": {"score": 90, "label": "非常正向", "period": "2026-06"},
            "domestic_demand": {"score": 70, "label": "非常正向", "period": "2026-06"},
            "financial_conditions": {"score": 80, "label": "非常正向", "period": "2026-06"},
        },
    }
    return alpha_engine, summary, decision


def main():
    now = dt.datetime(2026, 8, 15, 3, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
    alpha, summary, decision = sample("VERIFY")
    result = build_investment.build(alpha, summary, decision, now=now)
    assert result["version"] == 2
    assert result["architecture"]["alpha_schema"] == 6
    assert result["macro_context"]["label"] == "BROADLY_SUPPORTIVE"
    row = result["selection"]["researched"][0]
    assert row["score"] == 90
    assert row["action"] == "VERIFY", "supportive macro must not promote VERIFY to BUY"
    assert row["expected_return_pct"] == 32
    assert row["base_upside_pct"] == 25
    assert "margin_of_safety_pct" not in row
    assert result["benchmark"]["base_upside_pct"] == 30
    assert result["selection"]["buy_candidate_count"] == 0
    assert "action" not in result["selection"]["top_screen"][0]

    alpha, summary, decision = sample("BUY CANDIDATE")
    result = build_investment.build(alpha, summary, decision, now=now)
    assert result["selection"]["buy_candidate_count"] == 1
    assert result["selection"]["researched"][0]["action"] == "BUY CANDIDATE"

    decision["current"]["financial_conditions"]["score"] = -50
    result = build_investment.build(alpha, summary, decision, now=now)
    assert result["macro_context"]["label"] == "DEFENSIVE"
    assert result["selection"]["researched"][0]["action"] == "BUY CANDIDATE", "macro context must remain orthogonal even when defensive"
    print("INVESTMENT INTEGRATION TEST PASS")


if __name__ == "__main__":
    main()
