#!/usr/bin/env python3
from __future__ import annotations

import json
from common import load_json, save_json

MIN = 30


def generate():
    store = load_json('security_fact_store.json', {})
    bundle = load_json('alpha_engine.json', {})
    upstream = bundle.get('scenario_calibration') or {}
    forecasts = upstream.get('forecasts') or []
    resolved_total = int(upstream.get('resolved_samples') or 0)
    pending_total = int(upstream.get('pending_samples') or 0)
    upstream_status = upstream.get('status', 'UNAVAILABLE')
    rows = []

    for s in store.get('securities', []):
        if s.get('stage') not in ('BENCHMARK', 'RESEARCHED'):
            continue
        ticker = str(s.get('ticker'))
        sc = (s.get('valuation') or {}).get('scenarios') or {}
        prior = {k: (v or {}).get('probability') for k, v in sc.items() if k in ('bear', 'base', 'bull')}
        own = [x for x in forecasts if str(x.get('ticker')) == ticker]
        own_resolved = [x for x in own if x.get('status') == 'RESOLVED']
        own_pending = [x for x in own if x.get('status') == 'PENDING']
        rows.append({
            'ticker': s.get('ticker'),
            'name': s.get('name'),
            'prior_probabilities': prior,
            'posterior_probabilities': prior if prior else None,
            'calibration_status': 'READY_FOR_CHALLENGER_FIT' if upstream_status == 'CALIBRATED' else 'INSUFFICIENT_PROSPECTIVE_SAMPLES',
            'resolved_samples': len(own_resolved),
            'pending_samples': len(own_pending),
            'minimum_samples': MIN,
            'authoritative': False,
            'note': 'stock owns prospective Bear/Base/Bull forecast capture and outcome scoring. Elephant consumes that evidence but never silently rewrites upstream scenario priors or Buy Gate authority.',
        })

    out = {
        'version': 2,
        'status': 'PROSPECTIVE_CALIBRATION',
        'minimum_samples': max(MIN, int(upstream.get('minimum_resolved_samples') or 0)),
        'resolved_samples': resolved_total,
        'pending_samples': pending_total,
        'upstream_status': upstream_status,
        'upstream_method': upstream.get('method'),
        'upstream_horizon_weeks': upstream.get('horizon_weeks'),
        'upstream_multiclass_brier_score': upstream.get('multiclass_brier_score'),
        'securities': rows,
        'promotion_rule': 'Prospective probability evidence may justify a separately versioned challenger only after minimum samples; it never automatically mutates upstream priors, Buy Gate, or portfolio sizing.',
        'authority': 'CALIBRATION_EVIDENCE_ONLY',
    }
    save_json('scenario_probability_calibration.json', out)
    return out


if __name__ == '__main__':
    print(json.dumps(generate(), ensure_ascii=False, indent=2))
