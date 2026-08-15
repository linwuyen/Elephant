#!/usr/bin/env python3
from __future__ import annotations

import argparse

from common import load_json, save_json
import build_validation_os as core

MIN_COMMON_SAMPLES = 36


def paired_future_cycle_metrics(champion_rows, challenger_rows, horizon):
    champion=core.de2.as_map(champion_rows)
    challenger=core.de2.as_map(challenger_rows)
    cycle=core.cycle_map()
    rows=[]
    for period in sorted(set(champion)&set(challenger)):
        outcome_period=core.month_shift(period,horizon)
        if outcome_period in cycle:
            rows.append((champion[period],challenger[period],cycle[outcome_period]))
    c=core.pearson([x[0] for x in rows],[x[2] for x in rows])
    e=core.pearson([x[1] for x in rows],[x[2] for x in rows])
    return {
        'samples':len(rows),
        'champion':{'samples':len(rows),'pearson_to_future_cycle':None if c is None else round(c,3)},
        'equal_weight_challenger':{'samples':len(rows),'pearson_to_future_cycle':None if e is None else round(e,3)},
        'correlation_improvement':None if c is None or e is None else round(e-c,3),
        'contract':'same score periods + same future Cycle outcomes for champion and challenger',
    }


def paired_score_challenger_benchmark():
    champion=load_json('decision_scores.json', {'current':{},'history':{}})
    challenger=core.equal_weight_scores()
    out={}
    for dim in core.DIRECTIONAL:
        ch_cur=(champion.get('current') or {}).get(dim) or {}
        eq_cur=(challenger.get(dim) or {}).get('current') or {}
        horizons={}
        improvements=[]
        no_bad=True
        enough=True
        for h in (3,6):
            row=paired_future_cycle_metrics(
                (champion.get('history') or {}).get(dim,[]),
                (challenger.get(dim) or {}).get('history',[]),
                h,
            )
            horizons[f'{h}m']={
                'champion':row['champion'],
                'equal_weight_challenger':row['equal_weight_challenger'],
                'correlation_improvement':row['correlation_improvement'],
                'common_samples':row['samples'],
                'contract':row['contract'],
            }
            if row['samples']<MIN_COMMON_SAMPLES:
                enough=False
            imp=row['correlation_improvement']
            if imp is not None:
                improvements.append(imp)
                if imp < -0.02:
                    no_bad=False
        avg=None if not improvements else sum(improvements)/len(improvements)
        worth=enough and avg is not None and avg>=0.05 and no_bad and len(improvements)==2
        status='BLOCKED_INSUFFICIENT_COMMON_SAMPLE' if not enough else 'CHALLENGER_WORTH_REVIEW' if worth else 'CHAMPION_RETAINS'
        out[dim]={
            'champion_current_score':ch_cur.get('score'),
            'equal_weight_current_score':eq_cur.get('score'),
            'current_score_delta':None if ch_cur.get('score') is None or eq_cur.get('score') is None else round(float(eq_cur['score'])-float(ch_cur['score']),2),
            'horizons':horizons,
            'minimum_common_samples':MIN_COMMON_SAMPLES,
            'average_correlation_improvement':None if avg is None else round(avg,3),
            'status':status,
            'automatic_promotion':False,
        }
    return {
        'version':'1.1',
        'method':'Production transforms/components held fixed; compare hand-set production weights with a predeclared equal-weight baseline on identical common periods and identical future Cycle outcomes.',
        'comparison_contract':'paired common-sample comparison; minimum 36 common observations at both 3M and 6M before a winner may be declared',
        'dimensions':out,
        'excluded':{
            'cycle':'Cycle has a different production construction; no like-for-like equal-weight challenger is declared here.',
            'ai_concentration':'Concentration semantics differ from directional health Scores; no automatic equal-weight benchmark.',
        },
        'authority':False,
    }


def generate(append_journal=True):
    original=core.score_challenger_benchmark
    core.score_challenger_benchmark=paired_score_challenger_benchmark
    try:
        obj=core.generate(append_journal=append_journal)
    finally:
        core.score_challenger_benchmark=original
    obj['product']='Elephant Validation OS v1.1 / Paired-Sample Score Challenger'
    obj['score_challengers']=paired_score_challenger_benchmark()
    save_json('validation_os.json',obj)
    return obj


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--no-journal',action='store_true')
    a=ap.parse_args()
    generate(append_journal=not a.no_journal)


if __name__=='__main__':
    main()
