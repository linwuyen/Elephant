#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import sqlite3
from pathlib import Path

from common import DATA, TZ, load_json, save_json

DB_PATH = DATA / 'vintages.db'
MANIFEST = 'vintage_manifest.json'
PERIOD_RE = re.compile(r'^\d{4}-(?:0[1-9]|1[0-2])$|^\d{4}$')


def _finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def _series_rows(series: dict, source_file: str, prefix: str = ''):
    for key, s in (series or {}).items():
        if not isinstance(s, dict):
            continue
        sid = f'{prefix}{key}' if prefix else str(key)
        name = str(s.get('name') or sid)
        unit = str(s.get('unit') or '')
        for row in s.get('data') or []:
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                continue
            period, value = str(row[0]), row[1]
            if not PERIOD_RE.match(period) or not _finite(value):
                continue
            yield sid, name, unit, period, float(value), source_file


def iter_observations():
    # Decision-critical high-frequency inputs.
    decision = load_json('decision_inputs.json', {'series': {}})
    yield from _series_rows(decision.get('series', {}), 'decision_inputs.json')

    ai = load_json('ai_inputs.json', {'series': {}})
    yield from _series_rows(ai.get('series', {}), 'ai_inputs.json')

    ndc = load_json('ndc.json', {'series': {}})
    yield from _series_rows(ndc.get('series', {}), 'ndc.json', 'ndc.')

    # Cycle Score breadth depends on the full industrial-production cross-section.
    # Preserve that dataset, but do not duplicate every unrelated MOEA table.
    industry = load_json('industry.json', {'datasets': {}})
    prod = (industry.get('datasets') or {}).get('moea.industry.production', {})
    yield from _series_rows(prod.get('series', {}), 'industry.json', 'industry.production.')

    sales = (industry.get('datasets') or {}).get('moea.manufacturing.sales_index_current', {})
    yield from _series_rows(sales.get('series', {}), 'industry.json', 'industry.sales.')

    # Annual macro series are inexpensive and useful for future long-horizon models.
    macro = load_json('macro.json', {'series': {}})
    yield from _series_rows(macro.get('series', {}), 'macro.json')


def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute('PRAGMA journal_mode=DELETE')
    con.execute('PRAGMA foreign_keys=ON')
    con.executescript('''
    CREATE TABLE IF NOT EXISTS series (
      series_id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      unit TEXT,
      source_file TEXT NOT NULL,
      first_seen_at TEXT NOT NULL,
      last_seen_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS observations (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      series_id TEXT NOT NULL REFERENCES series(series_id),
      period TEXT NOT NULL,
      value REAL NOT NULL,
      observed_at TEXT NOT NULL,
      previous_value REAL,
      revision_delta REAL,
      UNIQUE(series_id, period, observed_at)
    );
    CREATE INDEX IF NOT EXISTS idx_obs_lookup
      ON observations(series_id, period, observed_at DESC);
    CREATE INDEX IF NOT EXISTS idx_obs_observed
      ON observations(observed_at DESC);
    CREATE TABLE IF NOT EXISTS snapshots (
      observed_at TEXT PRIMARY KEY,
      inserted_observations INTEGER NOT NULL,
      unchanged_observations INTEGER NOT NULL,
      series_seen INTEGER NOT NULL
    );
    ''')
    return con


def capture(observed_at: str | None = None):
    observed_at = observed_at or dt.datetime.now(TZ).replace(microsecond=0).isoformat()
    con = connect()
    inserted = unchanged = 0
    seen_series = set()

    latest_sql = '''
      SELECT value FROM observations
      WHERE series_id=? AND period=?
      ORDER BY observed_at DESC, id DESC LIMIT 1
    '''
    for sid, name, unit, period, value, source_file in iter_observations():
        seen_series.add(sid)
        con.execute('''
          INSERT INTO series(series_id,name,unit,source_file,first_seen_at,last_seen_at)
          VALUES(?,?,?,?,?,?)
          ON CONFLICT(series_id) DO UPDATE SET
            name=excluded.name,
            unit=excluded.unit,
            source_file=excluded.source_file,
            last_seen_at=excluded.last_seen_at
        ''', (sid, name, unit, source_file, observed_at, observed_at))
        row = con.execute(latest_sql, (sid, period)).fetchone()
        previous = None if row is None else float(row[0])
        if previous is not None and math.isclose(previous, value, rel_tol=0.0, abs_tol=1e-12):
            unchanged += 1
            continue
        delta = None if previous is None else value - previous
        con.execute('''
          INSERT OR IGNORE INTO observations
            (series_id,period,value,observed_at,previous_value,revision_delta)
          VALUES(?,?,?,?,?,?)
        ''', (sid, period, value, observed_at, previous, delta))
        inserted += 1

    con.execute('''
      INSERT OR REPLACE INTO snapshots(observed_at,inserted_observations,unchanged_observations,series_seen)
      VALUES(?,?,?,?)
    ''', (observed_at, inserted, unchanged, len(seen_series)))
    con.commit()

    integrity = con.execute('PRAGMA integrity_check').fetchone()[0]
    total_obs = con.execute('SELECT COUNT(*) FROM observations').fetchone()[0]
    revisions = con.execute('SELECT COUNT(*) FROM observations WHERE previous_value IS NOT NULL').fetchone()[0]
    first_seen = con.execute('SELECT MIN(observed_at) FROM observations').fetchone()[0]
    last_seen = con.execute('SELECT MAX(observed_at) FROM observations').fetchone()[0]
    con.close()

    manifest = {
        'version': 1,
        'database': 'vintages.db',
        'contract': 'point-in-time-observation-store',
        'observed_at': observed_at,
        'series': len(seen_series),
        'inserted_this_run': inserted,
        'unchanged_this_run': unchanged,
        'total_observations': total_obs,
        'revision_observations': revisions,
        'first_observed_at': first_seen,
        'last_observed_at': last_seen,
        'integrity_check': integrity,
        'coverage_note': 'Decision-critical official series plus industrial-production breadth and annual macro series. Historical rows before this database existed are not retroactively treated as real-time vintages.',
        'lookahead_guardrail': True,
    }
    save_json(MANIFEST, manifest)
    return manifest


def validate():
    if not DB_PATH.exists():
        raise SystemExit('VINTAGE VALIDATION ERROR: data/vintages.db missing')
    con = sqlite3.connect(DB_PATH)
    if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
        raise SystemExit('VINTAGE VALIDATION ERROR: SQLite integrity_check failed')
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required = {'series', 'observations', 'snapshots'}
    if not required <= tables:
        raise SystemExit(f'VINTAGE VALIDATION ERROR: tables missing {required - tables}')
    bad = con.execute("SELECT COUNT(*) FROM observations WHERE period NOT GLOB '[0-9][0-9][0-9][0-9]*'").fetchone()[0]
    if bad:
        raise SystemExit(f'VINTAGE VALIDATION ERROR: malformed periods={bad}')
    con.close()
    manifest = load_json(MANIFEST, {})
    if manifest.get('integrity_check') != 'ok' or manifest.get('lookahead_guardrail') is not True:
        raise SystemExit('VINTAGE VALIDATION ERROR: manifest contract invalid')
    print('VINTAGE VALIDATION PASS', manifest.get('total_observations'), 'observations')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--validate', action='store_true')
    ap.add_argument('--observed-at')
    args = ap.parse_args()
    if args.validate:
        validate()
    else:
        print(json.dumps(capture(args.observed_at), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
