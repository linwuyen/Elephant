#!/usr/bin/env python3
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data';p=DATA/'calibration/index.json'
if not p.exists():raise SystemExit('CALIBRATION VALIDATION ERROR: index missing')
d=json.loads(p.read_text(encoding='utf-8'))
if d.get('version')!=1:raise SystemExit('CALIBRATION VALIDATION ERROR: version')
seen=set()
for r in d.get('snapshots',[]):
 fp=r.get('fingerprint');f=r.get('file')
 if not fp or fp in seen:raise SystemExit('CALIBRATION VALIDATION ERROR: duplicate/missing fingerprint')
 seen.add(fp)
 if not f or not (ROOT/f).exists():raise SystemExit('CALIBRATION VALIDATION ERROR: snapshot missing')
print('CALIBRATION VALIDATION PASS',len(seen))
