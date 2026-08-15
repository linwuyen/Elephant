#!/usr/bin/env python3
import json, math, sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / 'data'
EXPECTED = {'external_demand','business_investment','regional_vitality'}

def fail(msg):
    print('STRUCTURAL LAYER ERROR:', msg, file=sys.stderr)
    raise SystemExit(1)

def main():
    p=DATA/'structural_layers.json'
    if not p.exists(): fail('missing output')
    obj=json.loads(p.read_text(encoding='utf-8'))
    if obj.get('version') != 1: fail('version')
    if obj.get('contract') != 'evidence-gated-structural-layers-v1': fail('contract')
    layers=obj.get('layers',{})
    if set(layers) != EXPECTED: fail('layers')

    external=layers['external_demand']
    if external.get('status') != 'BLOCKED_UPSTREAM' or external.get('score') is not None:
        fail('external demand must stay blocked without upstream evidence')

    regional=layers['regional_vitality']
    if regional.get('status') != 'BLOCKED_EVIDENCE' or regional.get('score') is not None:
        fail('regional vitality must stay evidence-gated')
    if '4/6' not in str(regional.get('minimum_publish_rule','')):
        fail('regional publish rule')

    business=layers['business_investment']
    if business.get('status') not in ('READY','BLOCKED_EVIDENCE'): fail('business status')
    if business.get('status') == 'READY':
        score=business.get('score')
        if not isinstance(score,(int,float)) or not math.isfinite(score) or not -100 <= score <= 100:
            fail('business score')
        if not 50 <= business.get('confidence',0) <= 100: fail('business coverage')
        if len(business.get('components',[])) < 1: fail('business components')
    elif business.get('score') is not None:
        fail('blocked business score must be null')
    print('STRUCTURAL LAYERS PASS')

if __name__ == '__main__': main()
