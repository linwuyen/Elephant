#!/usr/bin/env python3
from __future__ import annotations
import math
from common import load_json, save_json

TRACK_FILES = ('macro.json', 'population.json', 'industry.json', 'ndc.json')

def capture():
    return {name: load_json(name, {}) for name in TRACK_FILES}

def _series_map(obj_by_file):
    out = {}
    macro = obj_by_file.get('macro.json', {})
    for sid, s in macro.get('series', {}).items():
        for p, v in s.get('data', []):
            if isinstance(v, (int, float)):
                out[('dgbas', s.get('dataset_id') or 'macro', sid, str(p))] = float(v)

    pop = obj_by_file.get('population.json', {})
    for sid, s in pop.get('national', {}).items():
        for p, v in s.get('data', []):
            if isinstance(v, (int, float)):
                out[('ris', 'ris.history', sid, str(p))] = float(v)

    ind = obj_by_file.get('industry.json', {})
    for dataset, ds in ind.get('datasets', {}).items():
        for sid, s in ds.get('series', {}).items():
            for p, v in s.get('data', []):
                if isinstance(v, (int, float)):
                    out[('moea', dataset, sid, str(p))] = float(v)

    ndc = obj_by_file.get('ndc.json', {})
    for sid, s in ndc.get('series', {}).items():
        for p, v in s.get('data', []):
            if isinstance(v, (int, float)):
                out[('ndc', 'ndc.business_cycle', sid, str(p))] = float(v)
    return out

def record(before, detected_at):
    after = capture()
    old_map = _series_map(before)
    new_map = _series_map(after)
    log = load_json('revisions.json', {'version': 1, 'history': []})
    found = []
    for key in sorted(set(old_map).intersection(new_map)):
        old, new = old_map[key], new_map[key]
        tol = max(1e-9, abs(old) * 1e-10)
        if math.isfinite(old) and math.isfinite(new) and abs(new - old) > tol:
            source, dataset, series, period = key
            found.append({
                'detected_at': detected_at,
                'source': source,
                'dataset': dataset,
                'series': series,
                'period': period,
                'old': old,
                'new': new,
                'delta': new - old,
            })
    history = (log.get('history') or []) + found
    history = history[-1500:]
    save_json('revisions.json', {
        'version': 1,
        'last_scan_at': detected_at,
        'new_revisions': found[-50:],
        'history': history,
    })
    return found

if __name__ == '__main__':
    print('Use revision_tracker.capture() before refresh and record() after refresh.')
