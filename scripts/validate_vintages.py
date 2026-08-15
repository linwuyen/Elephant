#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VINTAGES = ROOT / 'data' / 'vintages'


def fail(msg):
    print('VINTAGE VALIDATION ERROR:', msg, file=sys.stderr)
    raise SystemExit(1)


def main():
    if not VINTAGES.exists():
        print('VINTAGE VALIDATION BOOTSTRAP: no vintage directory yet')
        return
    files = sorted(VINTAGES.glob('*.json'))
    if not files:
        print('VINTAGE VALIDATION BOOTSTRAP: no vintage snapshots yet')
        return
    seen = set()
    for path in files:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:-\d+)?\.json', path.name):
            fail('invalid filename ' + path.name)
        obj = json.loads(path.read_text(encoding='utf-8'))
        if obj.get('version') != 1:
            fail('version ' + path.name)
        if obj.get('as_seen_contract') != 'immutable-observed-elephant-vintage':
            fail('contract ' + path.name)
        fp = obj.get('data_fingerprint')
        if not fp or fp in seen:
            fail('duplicate/missing fingerprint ' + path.name)
        seen.add(fp)
        if not obj.get('recorded_at') or not obj.get('decision_scores'):
            fail('missing payload ' + path.name)
    print('VINTAGE VALIDATION PASS', len(files), 'snapshots')


if __name__ == '__main__':
    main()
