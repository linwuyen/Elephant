#!/usr/bin/env python3
from __future__ import annotations

import argparse
from common import load_json, save_json
import build_validation_os as core

MIN_COMMON_SAMPLES=36
DIMS=('growth_persistence','domestic_demand','financial_conditions')
ORIGINAL_SOURCE_SCORE=core.source_score


def quality_score(source_id,status):
    slo=load_json('data_quality_slo.json',{})
    rows={x.get('source_id'):x for x in slo.get('sources') or []}
    if source_id in rows:
        return float(rows[source_id].get('score') or 0)
    return ORIGINAL_SOURCE_SCORE(source_id,status)


def target_contract():
    return load_json('validation-target-contract-v1.json',{})


def target_registry():
    contract=target_contract()
    registry={}
    for dim,cfg in (contract.get('targets') or {}).items():
        registry[dim]={
            'primary':cfg.get('id'),
            'meaning':cfg.get('meaning'),
            'secondary':'future_cycle_score' if dim in DIMS else None,
            'independent_of_model_aggregate_weights':True,
        }
    return registry


def target_map(dim):
    artifact=load_json('validation_targets.json',{})
    rows=(artifact.get('history') or {}).get(dim) or []
    return {str(x['period']):float(x['value']) for x in rows if x.get('period') and x.get('value') is not None}


def paired_metrics(champion_rows,challenger_rows,dim,horizon):
    champion=core.de2.as_map(champion_rows)
    challenger=core.de2.as_map(challenger_rows)
    target=target_map(dim)
    cycle=core.cycle_map()
    rows=[]
    for period in sorted(set(champion)&set(challenger)):
        q=core.month_shift(period,horizon)
        if q in target:
            rows.append((champion[period],challenger[period],target[q],cycle.get(q)))
    c=core.pearson([x[0] for x in rows],[x[2] for x in rows])
    e=core.pearson([x[1] for x in rows],[x[2] for x in rows])
    cycle_rows=[x for x in rows if x[3] is not None]
    cc=core.pearson([x[0] for x in cycle_rows],[x[3] for x in cycle_rows])
    ec=core.pearson([x[1] for x in cycle_rows],[x[3] for x in cycle_rows])
    n=len(rows)
    return {
        'samples':n,
        'common_samples':n,
        'champion':{'samples':n,'pearson_to_primary_target':None if c is None else round(c,3)},
        'equal_weight_challenger':{'samples':n,'pearson_to_primary_target':None if e is None else round(e,3)},
        'primary_improvement':None if c is None or e is None else round(e-c,3),
        'secondary_cycle_diagnostic':{
            'samples':len(cycle_rows),
            'champion_pearson':None if cc is None else round(cc,3),
            'challenger_pearson':None if ec is None else round(ec,3),
        },
        'contract':'same score periods + same fixed downstream outcome; target aggregate uses neither champion nor challenger aggregate weights',
    }


def score_challenger_benchmark():
    champion=load_json('decision_scores.json',{'current':{},'history':{}})
    challenger=core.equal_weight_scores()
    pit=load_json('point_in_time_validation.json',{})
    registry=target_registry()
    out={}
    for dim in DIMS:
        improvements=[];enough=True;no_bad=True;horizons={}
        for h in (3,6):
            row=paired_metrics(
                (champion.get('history') or {}).get(dim,[]),
                (challenger.get(dim) or {}).get('history',[]),
                dim,h,
            )
            horizons[f'{h}m']=row
            if row['common_samples']<MIN_COMMON_SAMPLES:
                enough=False
            imp=row['primary_improvement']
            if imp is not None:
                improvements.append(imp)
                if imp < -0.02:
                    no_bad=False
        avg=None if not improvements else sum(improvements)/len(improvements)
        diagnostic_worth=enough and len(improvements)==2 and avg is not None and avg>=0.05 and no_bad
        if not enough:
            status='BLOCKED_INSUFFICIENT_COMMON_SAMPLE'
        elif diagnostic_worth:
            status='CHALLENGER_WORTH_REVIEW'
        else:
            status='CHAMPION_RETAINS'
        out[dim]={
            'target':registry[dim],
            'horizons':horizons,
            'minimum_common_samples':MIN_COMMON_SAMPLES,
            'average_primary_improvement':None if avg is None else round(avg,3),
            'historical_mode':'LATEST_REVISED_RECONSTRUCTION',
            'point_in_time_promotion_eligible':pit.get('prospective_vintages_eligible_for_promotion') is True,
            'status':status,
            'automatic_promotion':False,
        }
    return {
        'version':'1.3',
        'method':'Compare production vs predeclared equal-weight predictors against preregistered downstream outcome targets that exclude both model aggregate weight schemes. Future Cycle remains a secondary diagnostic.',
        'comparison_contract':'paired common-sample comparison on identical predictor periods and identical preregistered downstream future outcomes; minimum 36 common observations at both 3M and 6M before review',
        'target_contract':'independent-economic-validation-targets-v1',
        'target_registry':registry,
        'dimensions':out,
        'promotion_boundary':'Latest-revised history may screen challengers but cannot promote them. Promotion requires sufficient prospective point-in-time vintages plus a versioned governance review.',
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
    obj['product']='Elephant Validation OS v1.3 / Independent-Outcome Point-in-Time-Gated Challenger'
    obj['data_quality_slo']=load_json('data_quality_slo.json',{})
    obj['point_in_time_validation']=load_json('point_in_time_validation.json',{})
    obj['validation_target_contract']=target_contract()
    obj['validation_targets']=load_json('validation_targets.json',{})
    obj['score_challengers']=score_challenger_benchmark()
    save_json('validation_os.json',obj)
    return obj


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--no-journal',action='store_true');args=ap.parse_args()
    generate(append_journal=not args.no_journal)

if __name__=='__main__':main()
