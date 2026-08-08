#!/usr/bin/env python3
import json, sys
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'data/status.json'
s=json.loads(p.read_text(encoding='utf-8'))
bad=[k for k in ('dgbas','moea','ris') if s.get('sources',{}).get(k,{}).get('status')!='ok']
if bad:
    print('Critical source refresh degraded:', ', '.join(bad), file=sys.stderr); raise SystemExit(1)
print('All critical sources healthy; SEGIS is non-critical until credentials/public export are available.')
