#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from common import DATA, TZ, request_bytes, save_json

UPSTREAM_REPO = "https://github.com/linwuyen/stock"
RAW_BASE = "https://raw.githubusercontent.com/linwuyen/stock/main/data"
FILES = {
    "alpha": "alpha.json",
    "screen": "screen.json",
    "performance": "performance.json",
    "scenario_calibration": "scenario-calibration.json",
    "research_voi": "research-voi.json",
    "promotion_contract": "model-promotion-contract.json",
}


def _load_json_bytes(raw: bytes, label: str):
    try:
        value = json.loads(raw.decode("utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"{label}: invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label}: top-level object must be a JSON object")
    return value


def _fetch_json(name: str):
    url = f"{RAW_BASE}/{FILES[name]}"
    raw, _ = request_bytes(url, timeout=60, retries=4)
    return _load_json_bytes(raw, name), url


def _validate(alpha: dict, screen: dict, performance: dict, scenario_calibration: dict,
              research_voi: dict | None = None, promotion_contract: dict | None = None):
    ameta = alpha.get("meta", {})
    if ameta.get("schema_version") != 6:
        raise ValueError("alpha: Elephant requires canonical stock schema_version 6")
    if ameta.get("decision_engine_version") != "security-v6.0.0":
        raise ValueError("alpha: unsupported decision_engine_version")
    policy = alpha.get("decision_policy", {})
    if "min_base_upside_pct" not in policy or "min_margin_of_safety_pct" in policy:
        raise ValueError("alpha: base-upside policy schema contract violated")

    benchmark = alpha.get("benchmark_asset") or {}
    if "base_upside_pct" not in (benchmark.get("valuation_metrics") or {}):
        raise ValueError("alpha: benchmark missing canonical base_upside_pct")

    stocks = alpha.get("stocks") or []
    if not stocks:
        raise ValueError("alpha: no researched stocks")
    tickers = [str(x.get("ticker")) for x in stocks]
    if None in [x.get("ticker") for x in stocks] or len(tickers) != len(set(tickers)):
        raise ValueError("alpha: duplicate/missing tickers")
    for stock in stocks:
        score = stock.get("score")
        confidence = stock.get("confidence_score")
        if score is None or not 0 <= float(score) <= 100:
            raise ValueError(f"alpha: invalid score for {stock.get('ticker')}")
        if confidence is None or not 0 <= float(confidence) <= 100:
            raise ValueError(f"alpha: invalid confidence for {stock.get('ticker')}")
        if stock.get("action") not in {"BUY CANDIDATE", "VERIFY", "WATCH", "AVOID"}:
            raise ValueError(f"alpha: invalid action for {stock.get('ticker')}")
        metrics = stock.get("valuation_metrics") or {}
        if "base_upside_pct" not in metrics or "margin_of_safety_pct" in metrics:
            raise ValueError(f"alpha: canonical base-upside schema missing for {stock.get('ticker')}")
        checks = (stock.get("buy_gate") or {}).get("checks") or {}
        if "base_upside" not in checks or "margin_of_safety" in checks:
            raise ValueError(f"alpha: canonical Buy Gate schema missing for {stock.get('ticker')}")

    smeta = screen.get("meta", {})
    if smeta.get("schema_version", 0) < 5:
        raise ValueError("screen: schema_version < 5")
    if smeta.get("fail_closed") is not True:
        raise ValueError("screen: fail_closed must be true")
    if screen.get("rules", {}).get("screen_is_not_buy_gate") is not True:
        raise ValueError("screen: discovery screen must not be a buy gate")
    candidates = screen.get("candidates") or []
    deep = screen.get("deep_research_queue") or []
    if len(candidates) > 50 or len(deep) > 20:
        raise ValueError("screen: candidate queue exceeds contract")
    for row in candidates:
        if "action" in row:
            raise ValueError("screen: discovery candidates may not carry portfolio actions")
    if smeta.get("status") == "COMPLETE":
        promotion = smeta.get("promotion_enabled_by_market", {})
        if promotion != {"TWSE": True, "TPEX": True}:
            raise ValueError("screen: COMPLETE requires both markets promotion-enabled")

    pmeta = performance.get("meta", {})
    if pmeta.get("schema_version") != 3:
        raise ValueError("performance: Elephant requires total-return schema 3")
    if pmeta.get("primary_cohort") != "BUY_CANDIDATE":
        raise ValueError("performance: primary cohort contract changed")
    if pmeta.get("return_type") != "TOTAL_RETURN_CASH_DISTRIBUTIONS_NO_REINVESTMENT":
        raise ValueError("performance: total-return contract required")
    if pmeta.get("corporate_action_source") != "TWSE_TWT48U_ALL":
        raise ValueError("performance: first-party corporate-action source contract changed")
    if int(performance.get("minimum_samples_for_calibration") or 0) < 30:
        raise ValueError("performance: minimum sample guardrail weakened")

    if scenario_calibration.get("schema_version") != 1:
        raise ValueError("scenario_calibration: unsupported schema")
    if scenario_calibration.get("horizon_weeks") != 52:
        raise ValueError("scenario_calibration: horizon contract changed")
    if int(scenario_calibration.get("minimum_resolved_samples") or 0) < 30:
        raise ValueError("scenario_calibration: minimum sample guardrail weakened")
    if scenario_calibration.get("status") not in {"INSUFFICIENT_HISTORY", "CALIBRATED"}:
        raise ValueError("scenario_calibration: invalid status")

    if research_voi is not None:
        if research_voi.get("schema_version") != 1:
            raise ValueError("research_voi: unsupported schema")
        if research_voi.get("authority") is not False or research_voi.get("score_influence") is not False or research_voi.get("buy_gate_influence") is not False:
            raise ValueError("research_voi: must be non-authoritative and unable to change Buy Gate")
        priorities=[float(x.get("research_priority")) for x in research_voi.get("rows") or []]
        if priorities != sorted(priorities, reverse=True):
            raise ValueError("research_voi: priority ordering is not canonical")

    if promotion_contract is not None:
        if promotion_contract.get("contract") != "pre_registered_security_model_promotion_v1":
            raise ValueError("promotion_contract: unsupported contract")
        if promotion_contract.get("automatic_promotion") is not False or promotion_contract.get("immutable_without_version_bump") is not True:
            raise ValueError("promotion_contract: governance weakened")
        rr=(promotion_contract.get("rules") or {}).get("realized_return_calibration") or {}
        if rr.get("eligible_return_metric") != "EXCESS_TOTAL_RETURN_VS_2330" or int(rr.get("minimum_samples_per_primary_horizon") or 0) < 30:
            raise ValueError("promotion_contract: realized-return gate weakened")


def _offline_existing():
    path = DATA / "alpha_engine.json"
    if not path.exists():
        raise FileNotFoundError("offline mode requires existing data/alpha_engine.json")
    bundle = json.loads(path.read_text(encoding="utf-8"))
    alpha = bundle.get("alpha", {})
    screen = bundle.get("screen", {})
    return {
        "latest_period": screen.get("meta", {}).get("as_of") or alpha.get("meta", {}).get("as_of"),
        "rows": len(alpha.get("stocks", [])),
        "message": "Offline mode: retained checked-in Alpha Engine snapshot.",
        "upstream": UPSTREAM_REPO,
    }


def update(offline_dir: Path | None = None):
    if offline_dir:
        return _offline_existing()

    alpha, alpha_url = _fetch_json("alpha")
    screen, screen_url = _fetch_json("screen")
    performance, performance_url = _fetch_json("performance")
    scenario_calibration, scenario_calibration_url = _fetch_json("scenario_calibration")
    research_voi, research_voi_url = _fetch_json("research_voi")
    promotion_contract, promotion_contract_url = _fetch_json("promotion_contract")
    _validate(alpha, screen, performance, scenario_calibration, research_voi, promotion_contract)

    now = dt.datetime.now(TZ).replace(microsecond=0).isoformat()
    bundle = {
        "version": 3,
        "synced_at": now,
        "upstream": {
            "repository": UPSTREAM_REPO,
            "branch": "main",
            "files": {
                "alpha": alpha_url,
                "screen": screen_url,
                "performance": performance_url,
                "scenario_calibration": scenario_calibration_url,
                "research_voi": research_voi_url,
                "promotion_contract": promotion_contract_url,
            },
        },
        "alpha": alpha,
        "screen": screen,
        "performance": performance,
        "scenario_calibration": scenario_calibration,
        "research_voi": research_voi,
        "model_promotion_contract": promotion_contract,
    }
    save_json("alpha_engine.json", bundle)
    screen_meta = screen.get("meta", {})
    alpha_meta = alpha.get("meta", {})
    return {
        "latest_period": screen_meta.get("as_of") or alpha_meta.get("as_of"),
        "rows": len(screen.get("candidates", [])),
        "message": (
            f"Alpha upstream synced; schema={alpha_meta.get('schema_version')} "
            f"screen={screen_meta.get('status', 'UNKNOWN')} ({screen_meta.get('as_of', '—')}), "
            f"research={alpha_meta.get('as_of', '—')}, total_return={performance.get('meta',{}).get('status','UNKNOWN')}, "
            f"scenario_cal={scenario_calibration.get('status', 'UNKNOWN')}, VOI={len(research_voi.get('rows') or [])}."
        ),
        "upstream": UPSTREAM_REPO,
    }


if __name__ == "__main__":
    print(json.dumps(update(), ensure_ascii=False, indent=2))
