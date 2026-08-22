#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = DATA / 'data_quality_slo.json'
GRADE_SCORE = {'A':100.0,'B':90.0,'C':70.0,'D':40.0,'F':0.0}


def load(name, default=None):
    p=DATA/name
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else ({} if default is None else default)


def grade_source(source_id,row):
    status=str(row.get('status') or 'unknown').lower()
    text=' '.join([str(row.get('message') or ''),*(str(x) for x in row.get('warnings') or []),*(str(x) for x in row.get('recoveries') or [])]).lower()
    if status in {'blocked','fail','failed','error'}:
        grade='F'; reason='source blocked or failed'
    elif status in {'degraded','stale'}:
        grade='C'; reason='explicit degraded/stale source state'
    elif 'retained last-good' in text or 'retained last good' in text:
        # When the package still refreshed its current official core and only one
        # legacy transport is on last-good, keep it B. Otherwise it is C.
        current_core=('refreshed' in text and status=='ok')
        grade='B' if current_core else 'C'
        reason='mixed direct official refresh with explicit last-good component' if current_core else 'last-good retention'
    elif row.get('recoveries'):
        grade='B'; reason='equivalent first-party recovery/fallback semantics'
    elif row.get('warnings'):
        grade='B'; reason='first-party source available with warning'
    elif status=='ok':
        grade='A'; reason='direct verified production source with no degradation signal'
    else:
        grade='D'; reason='unknown or unclassified integrity state'
    return {
        'source_id':source_id,'grade':grade,'score':GRADE_SCORE[grade],
        'status':status,'reason':reason,'latest_period':row.get('latest_period'),
        'warnings':row.get('warnings') or [],'recoveries':row.get('recoveries') or [],
    }


def build():
    status=load('status.json',{})
    rows=[grade_source(k,v or {}) for k,v in sorted((status.get('sources') or {}).items())]
    counts={g:sum(1 for x in rows if x['grade']==g) for g in GRADE_SCORE}
    return {
        'version':1,
        'contract':'data-quality-slo-v1',
        'generated_from_status_at':status.get('last_check_at'),
        'authority':False,
        'score_influence':False,
        'decision_confidence_influence':True,
        'grades':{
            'A':'direct verified production source; no active degradation signal',
            'B':'first-party equivalent fallback/recovery or mixed direct+last-good package',
            'C':'last-good/degraded but still within explicit integrity handling',
            'D':'unknown/stale quality requiring review',
            'F':'blocked, failed, or semantic mismatch',
        },
        'grade_scores':GRADE_SCORE,
        'counts':counts,
        'sources':rows,
        'guardrail':'SLO grade may reduce evidence/data confidence; it never changes deterministic macro/security Scores directly.'
    }


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args()
    obj=build()
    if a.check:
        cur=load('data_quality_slo.json',{})
        assert cur==obj,'data_quality_slo.json stale'
        print('DATA QUALITY SLO PASS')
    else:
        OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(OUT)

if __name__=='__main__':main()
