#!/usr/bin/env python3
from __future__ import annotations

import html
import re
import time

from common import decode_text, request_bytes

_BASE_RE = re.compile(r'基期.{0,12}?\d{2,4}年[=＝]100')


def normalized_visible_text(body: bytes | str) -> str:
    """Return compact visible-ish text for resilient semantic checks.

    MOEA's ASP.NET pages may change whitespace, inline tags, dash variants, or the
    published base year without changing the indicator itself.  Strip tags and
    normalize only presentation-level differences; indicator semantics remain
    mandatory.
    """
    text = decode_text(body) if isinstance(body, (bytes, bytearray)) else str(body)
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('\u3000', '').replace('：', ':')
    return re.sub(r'\s+', '', text)


def validate_live_page(body: bytes, indicator: str) -> str:
    compact = normalized_visible_text(body)
    required = re.sub(r'\s+', '', indicator)
    if required not in compact:
        raise ValueError(f'MOEA live page missing indicator: {indicator}')
    if not _BASE_RE.search(compact):
        raise ValueError(f'MOEA live page missing base-year signature: {indicator}')
    if not re.search(r'\d{1,2}月', compact):
        raise ValueError(f'MOEA live page missing monthly rows: {indicator}')
    return decode_text(body)


def fetch_live_page(url: str, indicator: str, timeout: int = 60, attempts: int = 3) -> bytes:
    """Fetch an official MOEA live table with semantic retry.

    Network success is not enough: the ASP.NET endpoint can occasionally return
    an alternate/generic HTML body.  Each attempt must pass the indicator-specific
    semantic contract.  Retries use a harmless cache-busting query parameter and
    never accept another indicator's page as a substitute.
    """
    errors = []
    for attempt in range(attempts):
        suffix = '' if attempt == 0 else f'&_elephant_retry={int(time.time() * 1000)}_{attempt}'
        candidate = url + suffix
        try:
            body = request_bytes(candidate, timeout, 1)[0]
            validate_live_page(body, indicator)
            return body
        except Exception as exc:
            errors.append(f'{type(exc).__name__}: {exc}')
            if attempt + 1 < attempts:
                time.sleep(1 + attempt)
    raise RuntimeError(
        f'MOEA live semantic fetch failed for {indicator} after {attempts} attempts: '
        + ' | '.join(errors)
    )
