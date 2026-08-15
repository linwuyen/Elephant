#!/usr/bin/env python3
from __future__ import annotations
import math
from common import load_json

ALL_DIMS={'cycle','growth_persistence','domestic_demand','financial_conditions','ai_concentration'}
DIRECTIONAL={'growth_persistence','domestic_demand','financial_conditions'}

def finite(v):
    try:return math.isfinite(float(v))
    except Exception:return False

def main():
    obj=load_json('validation_os.json',{})
    assert obj.get('version')==1
    assert obj.get('authority') is False
    contract=obj.get('contract') or {}
    for key in ('production_scores_unchanged','v1_decision_engine_remains_authoritative','risk_budget_v2_remains_challenger','cannot_change_capital_os','cannot_change_alpha_or_constitution','no_automatic_promotion','no_automatic_trading'):
        assert contract.get(key) is True,key

    dc=obj.get('data_confidence_v2') or {}
    assert dc.get('authority') is False
    assert finite(dc.get('overall'))
    dims=dc.get('dimensions') or {}
    assert set(dims)==ALL_DIMS
    for key,row in dims.items():
        for field in ('completeness','freshness','source_reliability','revision_evidence_maturity','effective_data_confidence'):
            assert finite(row.get(field)),(key,field)
            assert 0<=float(row[field])<=100,(key,field,row[field])
    rev=dc.get('revision_evidence') or {}
    assert finite(rev.get('score'))
    if float(rev.get('prospective_days') or 0)<180:
        assert float(rev['score'])<100

    sb=obj.get('structural_break_monitor') or {}
    assert sb.get('authority') is False
    assert sb.get('status') in ('NORMAL','WATCH','HIGH','BLOCKED_INSUFFICIENT_HISTORY')
    if sb.get('status')!='BLOCKED_INSUFFICIENT_HISTORY':
        for field in ('nearest_regime_similarity','distribution_similarity','mean_abs_robust_z'):
            assert finite(sb.get(field)),field
        drift=sb.get('correlation_drift_score')
        assert drift is None or (finite(drift) and 0<=float(drift)<=100)

    sc=obj.get('score_challengers') or {}
    assert sc.get('authority') is False
    assert 'paired common-sample' in str(sc.get('comparison_contract'))
    cd=sc.get('dimensions') or {}
    assert set(cd)==DIRECTIONAL
    for key,row in cd.items():
        assert row.get('automatic_promotion') is False
        assert row.get('status') in ('CHAMPION_RETAINS','CHALLENGER_WORTH_REVIEW','BLOCKED_INSUFFICIENT_COMMON_SAMPLE')
        assert set(row.get('horizons') or {})=={'3m','6m'}
        enough=True
        for h,hrow in (row.get('horizons') or {}).items():
            c=(hrow.get('champion') or {}).get('samples')
            e=(hrow.get('equal_weight_challenger') or {}).get('samples')
            common=hrow.get('common_samples')
            assert int(c)==int(e)==int(common),(key,h,c,e,common)
            enough=enough and int(common)>=int(row.get('minimum_common_samples') or 36)
        if row.get('status')=='BLOCKED_INSUFFICIENT_COMMON_SAMPLE':
            assert not enough
        else:
            assert enough

    ps=obj.get('prospective_scorecards') or {}
    assert set(('macro','risk','portfolio','alpha')).issubset(ps)
    assert int(ps.get('resolved_total') or 0)>=0
    journal=load_json('validation_journal.json',{})
    assert journal.get('version')==1
    assert 'prospective-only' in str(journal.get('contract'))
    assert (journal.get('scorecards') or {}).get('resolved_total')==ps.get('resolved_total')

    print('VALIDATION OS VALIDATION PASS')
    print('effective data confidence:',dc.get('overall'))
    print('structural break:',sb.get('status'))
    print('prospective resolved:',ps.get('resolved_total'))

if __name__=='__main__':
    main()
