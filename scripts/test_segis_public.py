#!/usr/bin/env python3
from __future__ import annotations

import html
import re
from urllib.parse import urljoin

from common import URLS, decode_text, request_bytes

EXPECTED_TITLE = "114年12月行政區工商家數_鄉鎮市區"
REQUIRED_FIELDS = ("工商業總家數", "鄉鎮市區代碼", "鄉鎮市區名稱", "縣市代碼", "縣市名稱")


def visible_text(raw: str) -> str:
    raw = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<style\b[^>]*>.*?</style>", " ", raw, flags=re.I | re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()


def candidate_links(raw: str):
    links = []
    decoded = html.unescape(raw)
    for href in re.findall(r'''href\s*=\s*["']([^"']+)["']''', decoded, flags=re.I):
        value = urljoin(URLS["segis_catalog"], href.replace("&amp;", "&"))
        low = value.lower()
        if any(token in low for token in ("json", "filedown", "download", "reqcontroller", "service", "openapi")):
            links.append(value)
    return sorted(set(links))


def service_metadata(raw: str):
    decoded = html.unescape(raw)
    rows = []
    patterns = (
        r'''(?:onclick|data-[\w-]+)\s*=\s*["']([^"']*(?:json|csv|service|download|filedown|reqcontroller)[^"']*)["']''',
        r'''["']([^"']*(?:QueryInterface|Service|download|filedown|reqcontroller)[^"']*)["']''',
        r'''\b([A-Za-z_$][\w$]*\([^\n;]{0,300}(?:JSON|CSV|json|csv|download|service)[^\n;]{0,300}\))''',
    )
    for pattern in patterns:
        for value in re.findall(pattern, decoded, flags=re.I):
            value = re.sub(r"\s+", " ", value).strip()
            if value and value not in rows:
                rows.append(value)
    return rows[:80]


def context_snippets(raw: str):
    decoded = html.unescape(raw)
    snippets = []
    for token in ("JSON", "CSV下載", "GeoJSON", "filedown", "reqcontroller", "Service"):
        for match in re.finditer(re.escape(token), decoded, flags=re.I):
            start = max(0, match.start() - 350)
            end = min(len(decoded), match.end() + 500)
            value = re.sub(r"\s+", " ", decoded[start:end]).strip()
            if value not in snippets:
                snippets.append(value)
            if len(snippets) >= 30:
                return snippets
    return snippets


def main():
    raw = decode_text(request_bytes(URLS["segis_catalog"], 60, 2)[0])
    text = visible_text(raw)
    assert EXPECTED_TITLE in text, f"SEGIS target drifted: expected {EXPECTED_TITLE}"
    assert "是否對外公開" in text and "公開" in text, "SEGIS product is no longer explicitly public"
    assert "是否需申請" in text and "不需申請" in text, "SEGIS product unexpectedly requires application"
    assert "開放服務連結" in text and "JSON" in text, "SEGIS product no longer advertises JSON service"
    for field in REQUIRED_FIELDS:
        assert field in text, f"SEGIS field missing: {field}"
    links = candidate_links(raw)
    print("SEGIS PUBLIC METADATA PASS")
    print("target:", EXPECTED_TITLE)
    print("source:", URLS["segis_catalog"])
    print("machine-link candidates:", len(links))
    for link in links[:20]:
        print("candidate:", link)
    meta = service_metadata(raw)
    print("service metadata:", len(meta))
    for row in meta:
        print("service-meta:", row)
    snippets = context_snippets(raw)
    print("service context snippets:", len(snippets))
    for row in snippets:
        print("service-context:", row)


if __name__ == "__main__":
    main()
