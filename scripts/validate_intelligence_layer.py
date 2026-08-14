#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'data' / 'intelligence_layer.json'
EXPECTED = {'growth_persistence', 'domestic_demand', 'financial_conditions', 'ai_concentration'}
COMPANIES = {'McKinsey', 'BCG', 'Deloitte', 'PwC'}


def main():
    if not PATH.exists():
        raise SystemExit('intelligence_layer.json missing')
    obj = json.loads(PATH.read_text(encoding='utf-8'))
    assert obj.get('version') == 1
    assert obj.get('score_influence') is False
    assert obj.get('contract') == 'official-deterministic-scores-plus-consultant-context'
    dims = obj.get('dimensions') or {}
    assert set(dims) == EXPECTED, set(dims)

    for key, d in dims.items():
        official = d.get('official')
        assert official and official.get('score') is not None, (key, official)
        score = float(official['score'])
        if key == 'ai_concentration':
            assert 0 <= score <= 100, (key, score)
        else:
            assert -100 <= score <= 100, (key, score)
        assert 0 <= float(official.get('confidence', 0)) <= 100
        assert isinstance(d.get('brief'), str) and d['brief']
        assert isinstance(d.get('what_changed'), dict)
        seen = set()
        for bucket in ('evidence', 'contradictions', 'risks'):
            rows = d.get(bucket) or []
            assert len(rows) <= {'evidence': 4, 'contradictions': 2, 'risks': 3}[bucket]
            for row in rows:
                assert row.get('company') in COMPANIES
                assert row.get('id')
                assert row.get('title')
                u = urlparse(str(row.get('url') or ''))
                assert u.scheme == 'https' and u.netloc, row.get('url')
                marker = (bucket, row['id'])
                assert marker not in seen
                seen.add(marker)

    executive = obj.get('executive_brief') or {}
    assert executive.get('headline')
    assert executive.get('interpretation')
    print('Intelligence Layer PASS:', ', '.join(sorted(dims)))


if __name__ == '__main__':
    main()
