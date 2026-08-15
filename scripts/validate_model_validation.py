#!/usr/bin/env python3
import json, math, sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / 'data'
DIMS = {'growth_persistence','domestic_demand','financial_conditions','ai_concentration'}

def fail(msg):
    print('MODEL VALIDATION ERROR:', msg, file=sys.stderr)
    raise SystemExit(1)

def in_range(v):
    return isinstance(v,(int,float)) and math.isfinite(v) and 0 <= v <= 100

def main():
    path = DATA / 'model_validation.json'
    if not path.exists(): fail('missing output')
    obj = json.loads(path.read_text(encoding='utf-8'))
    if obj.get('version') != 1: fail('version')
    if obj.get('contract') != 'non_authoritative-model-validation-extension-v1': fail('contract')
    boundary = obj.get('evidence_boundary', {})
    if boundary.get('real_time_vintage_validation') is not False: fail('vintage disclosure')
    if 'revision' not in str(boundary.get('warning','')).lower(): fail('revision warning')

    validation = obj.get('cross_dimension_validation', {})
    if set(validation) != DIMS: fail('dimensions')
    for key,item in validation.items():
        if item.get('mode') != 'revised_historical_reconstruction': fail('mode '+key)
        r = item.get('reliability')
        if r is not None and not in_range(r): fail('reliability '+key)
        if set(item.get('horizons', {})) != {'3m','6m'}: fail('horizons '+key)

    conf = obj.get('confidence_decomposition', {})
    if set(conf) != DIMS: fail('confidence dimensions')
    for key,item in conf.items():
        if item.get('authority') is not False: fail('authority '+key)
        for field in ('coverage','freshness','signal_agreement','historical_reliability','provisional_overall'):
            v=item.get(field)
            if v is not None and not in_range(v): fail(key+'/'+field)

    for horizon,item in obj.get('historical_analog_regime_probability', {}).items():
        if horizon not in ('3m','6m'): fail('analog horizon')
        if item.get('authority') is not False: fail('analog authority')
        if int(item.get('sample_count',0)) < 12: fail('analog samples')
        probs=item.get('probabilities',{})
        if set(probs) != {'expansion','neutral','contraction'}: fail('probability schema')
        if any(not in_range(v) for v in probs.values()): fail('probability range')
        if abs(sum(float(v) for v in probs.values())-100) > .2: fail('probability sum')

    for key,item in obj.get('reverse_stress',{}).items():
        if key != 'ai_concentration' and item and 'not a forecast probability' not in str(item.get('note','')):
            fail('stress disclaimer '+key)
    print('MODEL VALIDATION PASS')

if __name__ == '__main__': main()
