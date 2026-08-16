#!/usr/bin/env python3
"""Sync a validated Consultant_System research snapshot into Elephant.

Consultant_System is the ingestion engine. Elephant consumes its published snapshot
only after validating the upstream manifest, artifact hashes, schema and health.
Consultant research is context-only and never alters deterministic economic scores.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "consultant"
BASE = "https://raw.githubusercontent.com/linwuyen/Consultant_System/main/data"
MANIFEST_URL = f"{BASE}/manifest.json"
ARTIFACTS = {
    "reports.json": f"{BASE}/reports.json",
    "reports.csv": f"{BASE}/reports.csv",
    "consultant.db": f"{BASE}/consultant.db",
    "source_health.json": f"{BASE}/source_health.json",
}
UA = "ElephantResearchSync/2.0 (+https://github.com/linwuyen/Elephant)"
REQUIRED_COMPANIES = ("McKinsey", "BCG", "Deloitte", "PwC")
MIN_REPORTS_PER_COMPANY = 3
SUPPORTED_SCHEMA_VERSION = 2
EXPECTED_CONTRACT = "research-context-only"


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=45) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {url}")
        return response.read()


def load_manifest(raw: bytes) -> dict:
    manifest = json.loads(raw.decode("utf-8"))
    if manifest.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        raise RuntimeError(
            f"unsupported Consultant_System schema_version={manifest.get('schema_version')}; "
            f"expected {SUPPORTED_SCHEMA_VERSION}"
        )
    if manifest.get("contract") != EXPECTED_CONTRACT:
        raise RuntimeError(f"unexpected consultant contract: {manifest.get('contract')!r}")
    if manifest.get("score_influence") is not False:
        raise RuntimeError("consultant manifest must explicitly set score_influence=false")

    overall_health = str(manifest.get("overall_health") or "").lower()
    if overall_health not in {"healthy", "degraded", "fail"}:
        raise RuntimeError(f"invalid upstream overall_health={overall_health!r}")
    if overall_health == "fail":
        raise RuntimeError("refusing failed Consultant_System snapshot")

    companies = manifest.get("companies") or {}
    missing = [company for company in REQUIRED_COMPANIES if company not in companies]
    if missing:
        raise RuntimeError(f"manifest missing required companies: {missing}")
    failed = [
        company for company in REQUIRED_COMPANIES
        if str((companies.get(company) or {}).get("ingestion_status") or "").lower() == "fail"
    ]
    if failed:
        raise RuntimeError(f"refusing snapshot with failed company ingestion: {failed}")

    artifacts = manifest.get("artifacts") or {}
    missing_artifacts = [name for name in ARTIFACTS if name not in artifacts]
    if missing_artifacts:
        raise RuntimeError(f"manifest missing artifact metadata: {missing_artifacts}")
    return manifest


def verify_artifact(name: str, raw: bytes, manifest: dict) -> None:
    meta = (manifest.get("artifacts") or {}).get(name) or {}
    expected = str(meta.get("sha256") or "").lower()
    actual = hashlib.sha256(raw).hexdigest()
    if not expected or actual != expected:
        raise RuntimeError(f"{name} SHA-256 mismatch: expected={expected or '<missing>'} actual={actual}")
    declared_bytes = meta.get("bytes")
    if declared_bytes is not None and int(declared_bytes) != len(raw):
        raise RuntimeError(f"{name} byte-size mismatch: expected={declared_bytes} actual={len(raw)}")


def validate_reports(raw: bytes, manifest: dict) -> tuple[dict, Counter]:
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
    incomplete = {
        c: companies.get(c, 0)
        for c in REQUIRED_COMPANIES
        if companies.get(c, 0) < MIN_REPORTS_PER_COMPANY
    }
    if incomplete:
        raise RuntimeError(f"refusing incomplete four-firm research snapshot: {incomplete}")

    manifest_companies = manifest.get("companies") or {}
    mismatched = {
        c: (companies.get(c, 0), int((manifest_companies.get(c) or {}).get("records") or 0))
        for c in REQUIRED_COMPANIES
        if companies.get(c, 0) != int((manifest_companies.get(c) or {}).get("records") or 0)
    }
    if mismatched:
        raise RuntimeError(f"manifest/report company counts disagree: {mismatched}")

    undated = sum(1 for r in reports if not r.get("date"))
    duplicate_urls = len(reports) - len({str(r.get("url", "")) for r in reports})
    if undated or duplicate_urls:
        raise RuntimeError(
            f"research snapshot quality gate failed: undated={undated}, duplicate_urls={duplicate_urls}"
        )
    return payload, companies


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    staged = OUT / ".staging"
    if staged.exists():
        shutil.rmtree(staged)
    staged.mkdir()

    try:
        manifest_raw = fetch(MANIFEST_URL)
        manifest = load_manifest(manifest_raw)
        blobs = {name: fetch(url) for name, url in ARTIFACTS.items()}
        for name, raw in blobs.items():
            verify_artifact(name, raw, manifest)

        payload, companies = validate_reports(blobs["reports.json"], manifest)
        reports = payload["reports"]
        if not blobs["consultant.db"].startswith(b"SQLite format 3\x00"):
            raise RuntimeError("consultant.db is not a valid SQLite file")

        (staged / "manifest.json").write_bytes(manifest_raw)
        for name, content in blobs.items():
            (staged / name).write_bytes(content)

        topics = Counter(topic for r in reports for topic in (r.get("topics") or []))
        latest = max((r.get("date") or "" for r in reports), default="")
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        overall_health = str(manifest["overall_health"]).lower()
        company_health = {
            c: {
                "records": int((manifest["companies"].get(c) or {}).get("records") or 0),
                "latest_publication": (manifest["companies"].get(c) or {}).get("latest_publication"),
                "ingestion_status": (manifest["companies"].get(c) or {}).get("ingestion_status"),
                "observed_count": int((manifest["companies"].get(c) or {}).get("observed_count") or 0),
                "last_success_at": (manifest["companies"].get(c) or {}).get("last_success_at"),
            }
            for c in REQUIRED_COMPANIES
        }

        status = {
            "status": "ok" if overall_health == "healthy" else "degraded",
            "coverage_complete": True,
            "upstream_health": overall_health,
            "upstream_snapshot_id": manifest.get("snapshot_id"),
            "upstream_schema_version": manifest.get("schema_version"),
            "synced_at": now,
            "source_repo": "linwuyen/Consultant_System",
            "source_generated_at": manifest.get("generated_at"),
            "source_updated_at": manifest.get("content_updated_at"),
            "reports": len(reports),
            "latest_date": latest or None,
            "companies": {c: companies.get(c, 0) for c in REQUIRED_COMPANIES},
            "company_health": company_health,
            "minimum_reports_per_company": MIN_REPORTS_PER_COMPANY,
            "topics": dict(sorted(topics.items(), key=lambda x: (-x[1], x[0]))),
            "contract": manifest["contract"],
            "score_influence": manifest["score_influence"],
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
