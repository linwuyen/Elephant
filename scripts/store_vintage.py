#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

from common import TZ, load_json

ROOT = Path(__file__).resolve().parents[1]
VINTAGES = ROOT / 'data' / 'vintages'


def stable_fingerprint(obj):
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()[:20]


def compact_components(scores):
    out = {}
    for key, cur in scores.get('current', {}).items():
        if not cur:
            continue
        out[key] = {
            'period': cur.get('period'),
            'score': cur.get('score'),
            'label': cur.get('label'),
            'coverage_confidence': cur.get('confidence'),
            'components': [
                {
                    'key': x.get('key'), 'raw': x.get('raw'), 'score': x.get('score'),
                    'weight': x.get('weight'), 'period': x.get('period'), 'source': x.get('source'),
                }
                for x in cur.get('components', [])
            ],
        }
    return out


def generate():
    scores = load_json('decision_scores.json', {})
    summary = load_json('summary.json', {})
    validation = load_json('validation_forward.json', {})
    now = dt.datetime.now(TZ).replace(microsecond=0)
    payload = {
        'version': 1,
        'recorded_at': now.isoformat(),
        'as_seen_contract': 'immutable-observed-elephant-vintage',
        'cycle': {k: summary.get('cycle', {}).get(k) for k in ('as_of', 'score', 'label', 'momentum_score', 'momentum', 'breadth')},
        'decision_scores': compact_components(scores),
        'formula_fingerprint': validation.get('score_formula_fingerprint'),
        'source_last_check_at': summary.get('data_last_check_at'),
        'note': 'This file records what Elephant actually saw at this refresh. It is not retroactively revised.',
    }
    payload['data_fingerprint'] = stable_fingerprint({
        'cycle': payload['cycle'],
        'decision_scores': payload['decision_scores'],
        'formula_fingerprint': payload['formula_fingerprint'],
    })
    VINTAGES.mkdir(parents=True, exist_ok=True)
    date_prefix = now.strftime('%Y-%m-%d')
    existing = sorted(VINTAGES.glob(date_prefix + '*.json'))
    for path in existing:
        try:
            old = json.loads(path.read_text(encoding='utf-8'))
            if old.get('data_fingerprint') == payload['data_fingerprint']:
                return {'created': False, 'path': str(path.relative_to(ROOT)), 'fingerprint': payload['data_fingerprint']}
        except Exception:
            continue
    suffix = '' if not existing else f'-{len(existing)+1}'
    path = VINTAGES / f'{date_prefix}{suffix}.json'
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    return {'created': True, 'path': str(path.relative_to(ROOT)), 'fingerprint': payload['data_fingerprint']}


if __name__ == '__main__':
    print(json.dumps(generate(), ensure_ascii=False, indent=2))
