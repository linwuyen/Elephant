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


def _validate(alpha: dict, screen: dict, performance: dict):
    if alpha.get("meta", {}).get("schema_version", 0) < 3:
        raise ValueError("alpha: schema_version < 3")
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

    meta = screen.get("meta", {})
    if meta.get("schema_version", 0) < 2:
        raise ValueError("screen: schema_version < 2")
    if meta.get("fail_closed") is not True:
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
    if meta.get("status") == "COMPLETE":
        promotion = meta.get("promotion_enabled_by_market", {})
        if promotion != {"TWSE": True, "TPEX": True}:
            raise ValueError("screen: COMPLETE requires both markets promotion-enabled")

    pmeta = performance.get("meta", {})
    if pmeta.get("schema_version", 0) < 2:
        raise ValueError("performance: schema_version < 2")
    if pmeta.get("primary_cohort") != "BUY_CANDIDATE":
        raise ValueError("performance: primary cohort contract changed")


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
    _validate(alpha, screen, performance)

    now = dt.datetime.now(TZ).replace(microsecond=0).isoformat()
    bundle = {
        "version": 1,
        "synced_at": now,
        "upstream": {
            "repository": UPSTREAM_REPO,
            "branch": "main",
            "files": {
                "alpha": alpha_url,
                "screen": screen_url,
                "performance": performance_url,
            },
        },
        "alpha": alpha,
        "screen": screen,
        "performance": performance,
    }
    save_json("alpha_engine.json", bundle)
    screen_meta = screen.get("meta", {})
    alpha_meta = alpha.get("meta", {})
    return {
        "latest_period": screen_meta.get("as_of") or alpha_meta.get("as_of"),
        "rows": len(screen.get("candidates", [])),
        "message": (
            f"Alpha upstream synced; screen={screen_meta.get('status', 'UNKNOWN')} "
            f"({screen_meta.get('as_of', '—')}), research={alpha_meta.get('as_of', '—')}."
        ),
        "upstream": UPSTREAM_REPO,
    }


if __name__ == "__main__":
    print(json.dumps(update(), ensure_ascii=False, indent=2))
