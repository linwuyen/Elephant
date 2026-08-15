#!/usr/bin/env python3
from __future__ import annotations

import html
import re
import time

from common import decode_text, request_bytes

_BASE_RE = re.compile(r'基期.{0,12}?(\d{2,4})年[=＝]100')


def normalized_visible_text(body: bytes | str) -> str:
    """Compact presentation-only differences while preserving indicator text."""
    text = decode_text(body) if isinstance(body, (bytes, bytearray)) else str(body)
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('\u3000', '').replace('：', ':')
    return re.sub(r'\s+', '', text)


def base_year(body: bytes | str) -> int:
    compact = normalized_visible_text(body)
    match = _BASE_RE.search(compact)
    if not match:
        raise ValueError('MOEA live page missing base-year signature')
    year = int(match.group(1))
    return year if year >= 1911 else year + 1911


def validate_live_page(body: bytes, indicator: str) -> str:
    compact = normalized_visible_text(body)
    required = re.sub(r'\s+', '', indicator)
    if required not in compact:
        raise ValueError(f'MOEA live page missing indicator: {indicator}')
    base_year(body)
    if not re.search(r'\d{1,2}月', compact):
        raise ValueError(f'MOEA live page missing monthly rows: {indicator}')
    return decode_text(body)


def fetch_live_page(url: str, indicator: str, timeout: int = 60, attempts: int = 3) -> bytes:
    """Fetch an official MOEA live table and retry semantic-invalid HTML.

    A 200 response is insufficient: the ASP.NET endpoint can occasionally return
    an alternate/generic body. Every attempt must still contain the requested
    indicator, a published base year, and monthly rows. Wrong pages fail closed.
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
