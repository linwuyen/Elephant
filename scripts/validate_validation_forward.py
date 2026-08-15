#!/usr/bin/env python3
from __future__ import annotations
import json, math, sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / 'data'
DIMS = {'growth_persistence','domestic_demand','financial_conditions','ai_concentration'}

def fail(msg):
    print('VALIDATION/FORWARD ERROR:', msg, file=sys.stderr)
    raise SystemExit(1)

def main():
    p = DATA / 'validation_forward.json'
    if not p.exists(): fail('missing validation_forward.json')
    obj = json.loads(p.read_text(encoding='utf-8'))
    if obj.get('version') != 1: fail('version')
    if obj.get('contract') != 'deterministic-validation-forward-v1': fail('contract')
    ev = obj.get('evidence_boundary', {})
    if ev.get('historical_reconstruction_is_revised') is not True: fail('revision-bias disclosure')
    if set(obj.get('validation', {})) != DIMS: fail('validation dimensions')
    if set(obj.get('confidence', {})) != DIMS: fail('confidence dimensions')
    for key, q in obj['confidence'].items():
        for field in ('coverage','freshness','agreement','overall'):
            v = q.get(field)
            if v is not None and (not isinstance(v,(int,float)) or not math.isfinite(v) or not 0 <= v <= 100):
                fail(f'{key} invalid {field}')
        r = q.get('reliability')
        if r is not None and not 0 <= r <= 100: fail(f'{key} reliability')
    for h, item in obj.get('forward_regime_probability', {}).items():
        if h not in ('3m','6m'): fail('unexpected horizon '+h)
        probs = item.get('probabilities', {})
        if set(probs) != {'expansion','neutral','contraction'}: fail('probability schema '+h)
        if abs(sum(float(v) for v in probs.values()) - 100) > .2: fail('probability sum '+h)
        if int(item.get('sample_count',0)) < 12: fail('sample count '+h)
    for key, item in obj.get('scenario_engine', {}).items():
        if key not in DIMS: fail('scenario dimension')
        if 'baseline' not in item or 'scenario_score' not in item: fail('scenario payload '+key)
        if item.get('note') != 'Sensitivity scenario only; not a probability forecast.': fail('scenario disclaimer '+key)
    print('VALIDATION/FORWARD PASS')
    for h, item in obj.get('forward_regime_probability', {}).items():
        print(h, item['probabilities'], 'n=', item['sample_count'])

if __name__ == '__main__':
    main()
