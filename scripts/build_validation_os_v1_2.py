#!/usr/bin/env python3
from __future__ import annotations

import argparse
from common import load_json, save_json
import build_validation_os as core

MIN_COMMON_SAMPLES=36
DIMS=('growth_persistence','domestic_demand','financial_conditions')
TARGETS={
    'growth_persistence':{
        'primary':'future_same_dimension_composite',
        'meaning':'future export orders + exports + manufacturing production/sales + inventory-balance composite',
        'secondary':'future_cycle_score',
    },
    'domestic_demand':{
        'primary':'future_same_dimension_composite',
        'meaning':'future real wage + employment + retail/food/card-spending composite',
        'secondary':'future_cycle_score',
    },
    'financial_conditions':{
        'primary':'future_same_dimension_composite',
        'meaning':'future money/credit/rate financial-conditions composite; FX remains diagnostic weight zero',
        'secondary':'future_cycle_score',
    },
    'ai_concentration':{
        'primary':'future_same_dimension_composite',
        'meaning':'future concentration persistence, not economic-health direction',
        'secondary':None,
    },
    'cycle':{
        'primary':'future_cycle_score',
        'meaning':'future aggregate macro regime',
        'secondary':None,
    },
}


def quality_score(source_id,status):
    slo=load_json('data_quality_slo.json',{})
    rows={x.get('source_id'):x for x in slo.get('sources') or []}
    if source_id in rows:
        return float(rows[source_id].get('score') or 0)
    return ORIGINAL_SOURCE_SCORE(source_id,status)


def target_map(dim):
    return core.de2.as_map(core.histories().get(dim,[]))


def paired_metrics(champion_rows,challenger_rows,dim,horizon):
    champion=core.de2.as_map(champion_rows);challenger=core.de2.as_map(challenger_rows)
    target=target_map(dim);cycle=core.cycle_map();rows=[]
    for period in sorted(set(champion)&set(challenger)):
        q=core.month_shift(period,horizon)
        if q in target:
            rows.append((champion[period],challenger[period],target[q],cycle.get(q)))
    c=core.pearson([x[0] for x in rows],[x[2] for x in rows])
    e=core.pearson([x[1] for x in rows],[x[2] for x in rows])
    cycle_rows=[x for x in rows if x[3] is not None]
    cc=core.pearson([x[0] for x in cycle_rows],[x[3] for x in cycle_rows])
    ec=core.pearson([x[1] for x in cycle_rows],[x[3] for x in cycle_rows])
    return {
        'samples':len(rows),
        'champion':{'pearson_to_primary_target':None if c is None else round(c,3)},
        'equal_weight_challenger':{'pearson_to_primary_target':None if e is None else round(e,3)},
        'primary_improvement':None if c is None or e is None else round(e-c,3),
        'secondary_cycle_diagnostic':{
            'samples':len(cycle_rows),
            'champion_pearson':None if cc is None else round(cc,3),
            'challenger_pearson':None if ec is None else round(ec,3),
        },
        'contract':'same score periods + same future dimension target; future Cycle retained only as secondary diagnostic',
    }


def score_challenger_benchmark():
    champion=load_json('decision_scores.json',{'current':{},'history':{}})
    challenger=core.equal_weight_scores();pit=load_json('point_in_time_validation.json',{})
    out={}
    for dim in DIMS:
        improvements=[];enough=True;no_bad=True;horizons={}
        for h in (3,6):
            row=paired_metrics((champion.get('history') or {}).get(dim,[]),(challenger.get(dim) or {}).get('history',[]),dim,h)
            horizons[f'{h}m']=row
            if row['samples']<MIN_COMMON_SAMPLES:enough=False
            imp=row['primary_improvement']
            if imp is not None:
                improvements.append(imp)
                if imp < -0.02:no_bad=False
        avg=None if not improvements else sum(improvements)/len(improvements)
        diagnostic_worth=enough and len(improvements)==2 and avg is not None and avg>=0.05 and no_bad
        if not enough:status='BLOCKED_INSUFFICIENT_COMMON_SAMPLE'
        elif diagnostic_worth:status='DIAGNOSTIC_CHALLENGER_WORTH_REVIEW'
        else:status='CHAMPION_RETAINS_DIAGNOSTIC'
        out[dim]={
            'target':TARGETS[dim],
            'horizons':horizons,
            'minimum_common_samples':MIN_COMMON_SAMPLES,
            'average_primary_improvement':None if avg is None else round(avg,3),
            'historical_mode':'LATEST_REVISED_RECONSTRUCTION',
            'point_in_time_promotion_eligible':pit.get('prospective_vintages_eligible_for_promotion') is True,
            'status':status,
            'automatic_promotion':False,
        }
    return {
        'version':'1.2',
        'method':'Compare production vs predeclared equal-weight weights on dimension-appropriate future composites; future Cycle is secondary diagnostic rather than a universal target.',
        'target_registry':TARGETS,
        'dimensions':out,
        'promotion_boundary':'Revised historical reconstruction may screen challengers but cannot promote them. Promotion requires sufficient prospective point-in-time vintages plus a versioned governance review.',
        'authority':False,
    }


def generate(append_journal=True):
    original_benchmark=core.score_challenger_benchmark
    original_source=core.source_score
    core.score_challenger_benchmark=score_challenger_benchmark
    core.source_score=quality_score
    try:
        obj=core.generate(append_journal=append_journal)
    finally:
        core.score_challenger_benchmark=original_benchmark
        core.source_score=original_source
    obj['product']='Elephant Validation OS v1.2 / Target-Aware Point-in-Time-Gated Challenger'
    obj['data_quality_slo']=load_json('data_quality_slo.json',{})
    obj['point_in_time_validation']=load_json('point_in_time_validation.json',{})
    obj['validation_targets']=TARGETS
    obj['score_challengers']=score_challenger_benchmark()
    save_json('validation_os.json',obj)
    return obj

ORIGINAL_SOURCE_SCORE=core.source_score

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--no-journal',action='store_true');a=ap.parse_args();generate(append_journal=not a.no_journal)
if __name__=='__main__':main()
