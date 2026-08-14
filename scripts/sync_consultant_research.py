#!/usr/bin/env python3
"""Sync Consultant_System published research artifacts into Elephant.

Consultant_System remains the ingestion engine. Elephant consumes only its published
artifacts and never lets consultant research alter deterministic economic scores.
"""

from __future__ import annotations

import json
import shutil
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "consultant"
BASE = "https://raw.githubusercontent.com/linwuyen/Consultant_System/main/data"
FILES = {
    "reports.json": f"{BASE}/reports.json",
    "reports.csv": f"{BASE}/reports.csv",
    "consultant.db": f"{BASE}/consultant.db",
}
UA = "ElephantResearchSync/1.1 (+https://github.com/linwuyen/Elephant)"
REQUIRED_COMPANIES = ("McKinsey", "BCG", "Deloitte", "PwC")
MIN_REPORTS_PER_COMPANY = 3


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=45) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {url}")
        return response.read()


def validate_reports(raw: bytes) -> tuple[dict, Counter]:
    payload = json.loads(raw.decode("utf-8"))
    reports = payload.get("reports")
    if not isinstance(reports, list):
        raise RuntimeError("reports.json has no reports array")
    if len(reports) < 10:
        raise RuntimeError(f"refusing suspiciously small research snapshot: {len(reports)} rows")

    required = {"id", "company", "title", "date", "url", "source_name"}
    bad = [i for i, row in enumerate(reports) if not required <= set(row)]
    if bad:
        raise RuntimeError(f"reports.json rows missing required fields: {bad[:5]}")

    companies = Counter(str(r.get("company", "")) for r in reports)
    incomplete = {c: companies.get(c, 0) for c in REQUIRED_COMPANIES if companies.get(c, 0) < MIN_REPORTS_PER_COMPANY}
    if incomplete:
        raise RuntimeError(f"refusing incomplete four-firm research snapshot: {incomplete}")

    undated = sum(1 for r in reports if not r.get("date"))
    duplicate_urls = len(reports) - len({str(r.get("url", "")) for r in reports})
    if undated or duplicate_urls:
        raise RuntimeError(f"research snapshot quality gate failed: undated={undated}, duplicate_urls={duplicate_urls}")

    return payload, companies


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    staged = OUT / ".staging"
    if staged.exists():
        shutil.rmtree(staged)
    staged.mkdir()

    try:
        blobs = {name: fetch(url) for name, url in FILES.items()}
        payload, companies = validate_reports(blobs["reports.json"])
        reports = payload["reports"]

        # SQLite magic header: b"SQLite format 3\x00". A deeper integrity/schema
        # check is performed by the workflow before this staged snapshot is committed.
        if not blobs["consultant.db"].startswith(b"SQLite format 3\x00"):
            raise RuntimeError("consultant.db is not a valid SQLite file")

        for name, content in blobs.items():
            (staged / name).write_bytes(content)

        topics = Counter(topic for r in reports for topic in (r.get("topics") or []))
        latest = max((r.get("date") or "" for r in reports), default="")
        source_updated_at = payload.get("updated_at")
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

        status = {
            "status": "ok",
            "coverage_complete": True,
            "synced_at": now,
            "source_repo": "linwuyen/Consultant_System",
            "source_updated_at": source_updated_at,
            "reports": len(reports),
            "latest_date": latest or None,
            "companies": {c: companies.get(c, 0) for c in REQUIRED_COMPANIES},
            "minimum_reports_per_company": MIN_REPORTS_PER_COMPANY,
            "topics": dict(sorted(topics.items(), key=lambda x: (-x[1], x[0]))),
            "contract": "research-context-only",
            "score_influence": False,
        }
        (staged / "status.json").write_text(
            json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        for path in staged.iterdir():
            path.replace(OUT / path.name)
        staged.rmdir()

        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0
    except Exception:
        shutil.rmtree(staged, ignore_errors=True)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
