#!/usr/bin/env python3
import json,sys
from pathlib import Path
DATA=Path(__file__).resolve().parents[1]/'data'
p=DATA/'calibration/index.json'
if not p.exists():
    print('CALIBRATION VALIDATION ERROR: index missing',file=sys.stderr);raise SystemExit(1)
d=json.loads(p.read_text(encoding='utf-8'))
if d.get('version')!=1: raise SystemExit('calibration index version')
seen=set()
for row in d.get('snapshots',[]):
    fp=row.get('fingerprint');f=row.get('file')
    if not fp or fp in seen: raise SystemExit('duplicate/missing calibration fingerprint')
    seen.add(fp)
    if not f or not (Path(__file__).resolve().parents[1]/f).exists(): raise SystemExit('calibration snapshot file missing')
print('CALIBRATION VALIDATION PASS',len(seen))
