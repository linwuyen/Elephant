#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
from urllib.parse import urljoin

from common import URLS, decode_text, request_bytes

EXPECTED_TITLE = "114年12月行政區工商家數_鄉鎮市區"
REQUIRED_FIELDS = ("工商業總家數", "鄉鎮市區代碼", "鄉鎮市區名稱", "縣市代碼", "縣市名稱")


def visible_text(raw: str) -> str:
    raw = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<style\b[^>]*>.*?</style>", " ", raw, flags=re.I | re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()


def json_service_url(raw: str) -> str:
    decoded = html.unescape(raw)
    m = re.search(r'''data-url=["']([^"']+GetAdminSTDataForOpenCode\?oCode=[^"']+)["'][^>]*>\s*JSON\b''', decoded, flags=re.I | re.S)
    if not m:
        raise AssertionError("SEGIS JSON service URL not found in canonical product page")
    return urljoin(URLS["segis_catalog"], m.group(1).replace("&amp;", "&"))


def inspect_payload(value, depth=0):
    if depth > 3:
        return type(value).__name__
    if isinstance(value, dict):
        return {str(k): inspect_payload(v, depth + 1) for k, v in list(value.items())[:12]}
    if isinstance(value, list):
        return {"type": "list", "length": len(value), "sample": inspect_payload(value[0], depth + 1) if value else None}
    if isinstance(value, str):
        return value[:180]
    return value


def main():
    raw = decode_text(request_bytes(URLS["segis_catalog"], 60, 2)[0])
    text = visible_text(raw)
    assert EXPECTED_TITLE in text, f"SEGIS target drifted: expected {EXPECTED_TITLE}"
    assert "是否對外公開" in text and "公開" in text, "SEGIS product is no longer explicitly public"
    assert "是否需申請" in text and "不需申請" in text, "SEGIS product unexpectedly requires application"
    assert "開放服務連結" in text and "JSON" in text, "SEGIS product no longer advertises JSON service"
    for field in REQUIRED_FIELDS:
        assert field in text, f"SEGIS field missing: {field}"

    service_url = json_service_url(raw)
    payload_bytes, content_type = request_bytes(service_url, 90, 2)
    payload_text = decode_text(payload_bytes)
    print("SEGIS PUBLIC METADATA PASS")
    print("target:", EXPECTED_TITLE)
    print("source:", URLS["segis_catalog"])
    print("json-service:", service_url)
    print("json-content-type:", content_type)
    print("json-bytes:", len(payload_bytes))
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        print("json-prefix:", payload_text[:1000].replace("\n", " "))
        raise AssertionError(f"SEGIS advertised JSON service is not JSON: {exc}")
    print("json-shape:", json.dumps(inspect_payload(payload), ensure_ascii=False)[:5000])


if __name__ == "__main__":
    main()
