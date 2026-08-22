#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import load_json, period_key, save_json
import build_decision_scores as ds

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'validation_targets.json'
CONTRACT=ROOT/'data'/'validation-target-contract-v1.json'


def component_map(result):
    return {x.get('key'):x for x in (result or {}).get('components') or [] if x.get('key')}


def aggregate_target(result, keys, minimum):
    parts=component_map(result)
    selected=[]
    for key in keys:
        row=parts.get(key)
        if row is not None and row.get('score') is not None:
            selected.append({
                'key':key,
                'score':float(row['score']),
                'raw':row.get('raw'),
                'source_period':row.get('period'),
                'source':row.get('source'),
            })
    if len(selected)<minimum:
        return None
    value=sum(x['score'] for x in selected)/len(selected)
    return {'value':round(value,2),'components':selected,'coverage':len(selected)}


def build():
    contract=json.loads(CONTRACT.read_text(encoding='utf-8'))
    industry=load_json('industry.json',{})
    ndcobj=load_json('ndc.json',{})
    inputs=load_json('decision_inputs.json',{'series':{}})
    ndc=ndcobj.get('series',{})
    prod=industry.get('datasets',{}).get('moea.industry.production',{}).get('series',{}).get('C',{})
    sales=industry.get('datasets',{}).get('moea.manufacturing.sales_index_current',{}).get('series',{}).get('C',{})
    current_period=ds.latest_period(prod) or ndcobj.get('latest_period')
    allseries=[prod,sales,*ndc.values(),*inputs.get('series',{}).values()]
    periods=[p for p in ds.history_periods(allseries,120) if not current_period or p<=current_period]
    histories={k:[] for k in ('growth_persistence','domestic_demand','financial_conditions')}
    definitions=contract['targets']

    for p in periods:
        growth=ds.growth_score(p,prod,sales,ndc,inputs)
        domestic=ds.domestic_score(p,ndc,inputs)
        financial=ds.financial_score(p,ndc,inputs)
        for dim,result in (
            ('growth_persistence',growth),
            ('domestic_demand',domestic),
            ('financial_conditions',financial),
        ):
            cfg=definitions[dim]
            target=aggregate_target(result,cfg['components'],int(cfg['minimum_components']))
            if target:
                histories[dim].append({
                    'period':p,
                    'target_id':cfg['id'],
                    **target,
                })

    return {
        'version':1,
        'contract':'independent-economic-validation-targets-v1',
        'target_contract_version':contract['version'],
        'as_of':current_period,
        'historical_mode':'LATEST_REVISED_RECONSTRUCTION',
        'promotion_authority':False,
        'definitions':definitions,
        'history':histories,
        'guardrail':'Outcome targets are downstream fixed subsets and never aggregate with champion/challenger weights. Revised-history targets remain diagnostic only until point-in-time evidence matures.'
    }


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args()
    obj=build()
    if args.check:
        current=load_json('validation_targets.json',{})
        assert current==obj,'validation_targets.json stale'
        print('INDEPENDENT VALIDATION TARGETS PASS')
    else:
        save_json('validation_targets.json',obj)
        print(OUT)

if __name__=='__main__':main()
