#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'


def load(name):
    p = DATA / name
    if not p.exists():
        raise SystemExit(f'DECISION ENGINE VALIDATION ERROR: missing data/{name}')
    return json.loads(p.read_text(encoding='utf-8'))


def fail(msg):
    print('DECISION ENGINE VALIDATION ERROR:', msg, file=sys.stderr)
    raise SystemExit(1)


def num(v, lo=None, hi=None):
    if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(float(v)):
        return False
    if lo is not None and float(v) < lo: return False
    if hi is not None and float(v) > hi: return False
    return True


engine = load('decision_engine.json')
forecast = load('forecast.json')
claims = load('research_claims.json')
risk = load('risk_budget.json')
journal = load('decision_journal.json')
manifest = load('vintage_manifest.json')

contract = engine.get('contract') or {}
required_true = (
    'official_scores_are_deterministic', 'alpha_buy_gate_authoritative',
    'no_automatic_trading', 'no_fabricated_missing_values',
)
if any(contract.get(k) is not True for k in required_true):
    fail('core guardrail missing/false')
if contract.get('research_score_influence') is not False:
    fail('research may not influence scores')
if contract.get('personal_portfolio_storage') != 'browser-local-only':
    fail('personal portfolio must remain browser-local')

conf = engine.get('confidence') or {}
for key in ('data_confidence', 'model_confidence', 'decision_confidence'):
    if not num(conf.get(key), 0, 100):
        fail(f'invalid {key}: {conf.get(key)}')

for key, dim in (forecast.get('dimensions') or {}).items():
    for h in ('1m','3m','6m','12m'):
        row = (dim.get('horizons') or {}).get(h)
        if not row:
            fail(f'missing forecast horizon {key}.{h}')
        if not num(row.get('probability'), 0, 1):
            fail(f'invalid probability {key}.{h}')
        cal = row.get('calibration') or {}
        if cal.get('brier_score') is not None and not num(cal.get('brier_score'), 0, 1):
            fail(f'invalid brier {key}.{h}')
        if cal.get('direction_accuracy') is not None and not num(cal.get('direction_accuracy'), 0, 1):
            fail(f'invalid accuracy {key}.{h}')

if claims.get('score_influence') is not False or claims.get('fulltext_claim_extraction') is not False:
    fail('research claim contract invalid')
for row in claims.get('claims') or []:
    if row.get('company') not in {'McKinsey','BCG','Deloitte','PwC'}:
        fail('unknown research company')
    if row.get('score_influence') is not False:
        fail('claim leaked into score path')
    if row.get('direction') not in {'supportive','risk','mixed','context'}:
        fail('invalid claim direction')

rb_contract = risk.get('contract') or {}
if any(rb_contract.get(k) is not True for k in (
    'does_not_create_buy_candidate','does_not_override_alpha_action',
    'no_automatic_trading','personal_portfolio_not_stored_in_repository')):
    fail('risk budget guardrail invalid')
if not num(risk.get('risk_score'), 0, 100):
    fail('invalid risk_score')
for key in ('target_equity_risk_budget_pct','cash_floor_pct','max_single_stock_pct'):
    if not num((risk.get('allocation_guardrails') or {}).get(key), 0, 100):
        fail(f'invalid allocation guardrail {key}')

if journal.get('version') != 1 or not isinstance(journal.get('entries'), list):
    fail('decision journal schema invalid')
sc = journal.get('scorecard') or {}
if sc.get('direction_hit_rate') is not None and not num(sc.get('direction_hit_rate'), 0, 1):
    fail('journal hit rate invalid')
if sc.get('brier_score') is not None and not num(sc.get('brier_score'), 0, 1):
    fail('journal brier invalid')

vdb = DATA / 'vintages.db'
if not vdb.exists():
    fail('vintages.db missing')
con = sqlite3.connect(vdb)
if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
    fail('vintage SQLite integrity failure')
tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
if not {'series','observations','snapshots'} <= tables:
    fail('vintage tables missing')
con.close()
if manifest.get('lookahead_guardrail') is not True or manifest.get('integrity_check') != 'ok':
    fail('vintage manifest invalid')

print('DECISION ENGINE VALIDATION PASS')
print('data confidence:', conf.get('data_confidence'))
print('model confidence:', conf.get('model_confidence'))
print('decision confidence:', conf.get('decision_confidence'))
print('research claims:', len(claims.get('claims') or []))
print('journal entries:', len(journal.get('entries') or []))
print('vintage observations:', manifest.get('total_observations'))
