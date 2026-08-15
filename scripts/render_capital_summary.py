#!/usr/bin/env python3
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'

if __name__=='__main__':
    p=DATA/'capital_allocation.json'
    if not p.exists():
        raise SystemExit('capital_allocation.json missing')
    d=json.loads(p.read_text(encoding='utf-8'))
    print('status:',d.get('status'))
    print('research queue:',len(d.get('research_queue',{}).get('items',[])))
    print('hurdle:',d.get('opportunity_set',{}).get('hurdle_asset'),d.get('opportunity_set',{}).get('hurdle_expected_return_pct'))
    print('portfolio:',d.get('portfolio_state_status'))
    print('sizing:',d.get('target_sizing',{}).get('status'))
