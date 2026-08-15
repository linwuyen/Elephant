#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from common import DATA, TZ, save_json

CAL = DATA / "calibration"
CAL.mkdir(exist_ok=True)


def load(name, default=None):
    p = DATA / name
    if not p.exists():
        return {} if default is None else default
    return json.loads(p.read_text(encoding="utf-8"))


def generate():
    now = dt.datetime.now(TZ).replace(microsecond=0)
    capital = load("capital_allocation.json")
    investment = load("investment.json")
    alpha_engine = load("alpha_engine.json")
    alpha = alpha_engine.get("alpha", {})
    screen = alpha_engine.get("screen", {})
    fp = capital.get("fingerprint")
    index = load("calibration/index.json", {"version": 1, "snapshots": []})
    previous = index.get("snapshots", [])[-1] if index.get("snapshots") else None
    if previous and previous.get("fingerprint") == fp:
        return {"created": False, "reason": "UNCHANGED_FINGERPRINT", "snapshot": previous}
    stamp = now.strftime("%Y%m%dT%H%M%S%z")
    filename = f"{stamp}.json"
    buy = [x for x in alpha.get("stocks", []) if x.get("action") == "BUY CANDIDATE"]
    snap = {
        "version": 1,
        "captured_at": now.isoformat(),
        "fingerprint": fp,
        "alpha_as_of": alpha.get("meta", {}).get("as_of"),
        "screen_as_of": screen.get("meta", {}).get("as_of"),
        "macro_context": investment.get("macro_context"),
        "opportunity_set": capital.get("opportunity_set"),
        "buy_entries": [{
            "ticker": x.get("ticker"),
            "name": x.get("name"),
            "reference_price": x.get("reference_price"),
            "expected_return_pct": x.get("valuation_model", {}).get("expected_return_pct"),
            "alpha_spread_pct": x.get("alpha_spread_pct"),
            "score": x.get("score"),
            "confidence_score": x.get("confidence_score"),
        } for x in buy],
        "researched_actions": [{"ticker": x.get("ticker"), "action": x.get("action")} for x in alpha.get("stocks", [])],
        "benchmark": alpha.get("benchmark_asset"),
        "portfolio_state_status": capital.get("portfolio_state_status"),
        "return_measurement_contract": "Future evaluation must use the price/benchmark state available at this captured_at timestamp; never rewrite this snapshot with revised hindsight data.",
    }
    (CAL / filename).write_text(json.dumps(snap, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    entry = {"file": f"data/calibration/{filename}", "captured_at": now.isoformat(), "fingerprint": fp, "buy_entry_count": len(buy)}
    index.setdefault("snapshots", []).append(entry)
    index["snapshots"] = index["snapshots"][-500:]
    index["latest"] = entry
    save_json("calibration/index.json", index)
    return {"created": True, "snapshot": entry}


if __name__ == "__main__":
    print(json.dumps(generate(), ensure_ascii=False, indent=2))
