#!/usr/bin/env python3
import argparse
import json
import sqlite3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
OUT=DATA/'point_in_time_validation.json'
DB=DATA/'vintages.db'


def load(name,default=None):
    p=DATA/name
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else ({} if default is None else default)


def as_of_value(con,series_id,period,as_of):
    row=con.execute('''SELECT value,observed_at FROM observations
      WHERE series_id=? AND period=? AND observed_at<=?
      ORDER BY observed_at DESC,id DESC LIMIT 1''',(series_id,period,as_of)).fetchone()
    return None if not row else {'value':row[0],'observed_at':row[1]}


def build():
    if not DB.exists():
        return {'version':1,'contract':'point-in-time-validation-gate-v1','status':'BLOCKED_NO_VINTAGE_DB','authority':False}
    con=sqlite3.connect(DB)
    integrity=con.execute('PRAGMA integrity_check').fetchone()[0]
    snapshots=con.execute('SELECT observed_at,inserted_observations,unchanged_observations,series_seen FROM snapshots ORDER BY observed_at').fetchall()
    obs=con.execute('SELECT COUNT(*) FROM observations').fetchone()[0]
    revisions=con.execute('SELECT COUNT(*) FROM observations WHERE previous_value IS NOT NULL').fetchone()[0]
    distinct_months=con.execute("SELECT COUNT(DISTINCT substr(observed_at,1,7)) FROM snapshots").fetchone()[0]
    first=con.execute('SELECT MIN(observed_at) FROM snapshots').fetchone()[0]
    last=con.execute('SELECT MAX(observed_at) FROM snapshots').fetchone()[0]
    # Prove the lookup guardrail with one real row when available: querying before
    # first observation must never return a future value.
    probe=con.execute('SELECT series_id,period,observed_at FROM observations ORDER BY observed_at,id LIMIT 1').fetchone()
    guard=True
    if probe:
        sid,period,observed_at=probe
        before='0001-01-01T00:00:00+00:00'
        guard=as_of_value(con,sid,period,before) is None and as_of_value(con,sid,period,observed_at) is not None
    con.close()
    minimum_months=36
    status='ELIGIBLE_FOR_PIT_CHALLENGER' if distinct_months>=minimum_months else 'BLOCKED_INSUFFICIENT_POINT_IN_TIME_HISTORY'
    manifest=load('vintage_manifest.json',{})
    return {
        'version':1,'contract':'point-in-time-validation-gate-v1','status':status,'authority':False,
        'database':'vintages.db','integrity_check':integrity,'lookahead_guardrail_pass':guard,
        'first_snapshot_at':first,'last_snapshot_at':last,'snapshot_count':len(snapshots),
        'distinct_snapshot_months':distinct_months,'minimum_months_for_model_promotion':minimum_months,
        'observation_count':obs,'revision_observation_count':revisions,
        'manifest_first_observed_at':manifest.get('first_observed_at'),
        'historical_reconstruction_eligible_for_promotion':False,
        'prospective_vintages_eligible_for_promotion':distinct_months>=minimum_months and guard and integrity=='ok',
        'query_contract':'For any simulated as_of, select the latest observation with observed_at <= as_of; never select a later revision.',
        'history_boundary':'Rows predating the first true vintage remain revised-series reconstructions and cannot be relabeled point-in-time.',
    }


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();obj=build()
    if a.check:
        cur=load('point_in_time_validation.json',{});assert cur==obj,'point_in_time_validation.json stale';print('POINT IN TIME VALIDATION PASS')
    else:
        OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(OUT)
if __name__=='__main__':main()
