#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from common import TZ, load_json, save_json
import build_summary
import build_history
import build_decision_scores
import build_ai_concentration
import build_model_validation
import build_structural_layers
import build_intelligence_layer
import build_investment
import build_vintage
import build_data_quality_slo
import build_point_in_time_validation
import build_validation_targets
import build_decision_engine
import build_decision_engine_v2
import build_risk_budget_v2_availability
import build_validation_os_v1_3
import build_decision_attribution
import build_statistical_challengers
import build_decision_command
import revision_tracker
import source_macro
import source_regime_official
import source_moea
import source_moea_live_tables
import source_ndc
import source_ris
import source_decision
import source_ai_concentration
import source_supplements
import source_alpha
import source_twse_market_live
import source_segis


def coverage(status):
    macro = load_json('macro.json', {})
    regime = load_json('regime_official.json', {})
    pop = load_json('population.json', {})
    ind = load_json('industry.json', {})
    ndc = load_json('ndc.json', {})
    decision = load_json('decision_inputs.json', {})
    ai = load_json('ai_inputs.json', {})
    segis = load_json('segis.json', {})
    rows = []
    for iid, s in macro.get('series', {}).items():
        d = s.get('data', [])
        rows.append({'source': 'dgbas', 'dataset': s.get('dataset_id'), 'indicator': iid, 'name': s.get('name'), 'frequency': s.get('frequency', 'annual'), 'points': len(d), 'period': f'{d[0][0]}..{d[-1][0]}' if d else '-'})
    for iid, s in regime.get('series', {}).items():
        d = s.get('data', [])
        rows.append({'source': 'regime_official', 'dataset': s.get('dataset_id'), 'indicator': iid, 'name': s.get('name'), 'frequency': s.get('frequency', 'monthly'), 'points': len(d), 'period': f'{d[0][0]}..{d[-1][0]}' if d else '-'})
    for iid, s in pop.get('national', {}).items():
        d = s.get('data', [])
        rows.append({'source': 'ris', 'dataset': 'ris.history', 'indicator': iid, 'name': s.get('name'), 'frequency': 'annual', 'points': len(d), 'period': f'{d[0][0]}..{d[-1][0]}' if d else '-'})
    for ds, x in ind.get('datasets', {}).items():
        for key, s in x.get('series', {}).items():
            d = s.get('data', [])
            rows.append({'source': 'moea', 'dataset': ds, 'indicator': key, 'name': s.get('name', key), 'frequency': 'monthly/quarterly', 'points': len(d), 'period': f'{d[0][0]}..{d[-1][0]}' if d else '-'})
    for iid, s in ndc.get('series', {}).items():
        d = s.get('data', [])
        rows.append({'source': 'ndc', 'dataset': 'ndc.business_cycle', 'indicator': iid, 'name': s.get('name', iid), 'frequency': 'monthly', 'points': len(d), 'period': f'{d[0][0]}..{d[-1][0]}' if d else '-'})
    for iid, s in decision.get('series', {}).items():
        d=s.get('data',[])
        rows.append({'source':'decision','dataset':'official.decision_inputs','indicator':iid,'name':s.get('name',iid),'frequency':'monthly','points':len(d),'period':f'{d[0][0]}..{d[-1][0]}' if d else '-'})
    for iid, s in ai.get('series', {}).items():
        d=s.get('data',[])
        rows.append({'source':'mof','dataset':'official.ai_concentration_inputs','indicator':iid,'name':s.get('name',iid),'frequency':'monthly','points':len(d),'period':f'{d[0][0]}..{d[-1][0]}' if d else '-'})
    if segis.get('rows'):
        rows.append({'source':'segis','dataset':segis.get('dataset_id','segis.business_count.township'),'indicator':'business_count','name':'行政區工商家數（鄉鎮市區）','frequency':'official snapshot','points':len(segis.get('rows',[])),'period':segis.get('latest_period','-')})
    save_json('coverage.json', {'datasets': rows, 'source_status': status['sources']})


def refresh_source(status, bad, sid, fn, offline_dir, critical=True):
    try:
        status['sources'][sid] = {'status': 'ok', **fn(offline_dir)}
    except Exception as e:
        if critical:
            bad.append(sid)
        prev = load_json('status.json', {'sources': {}}).get('sources', {}).get(sid, {})
        status['sources'][sid] = {
            'status': 'degraded',
            'latest_period': prev.get('latest_period'),
            'rows': prev.get('rows'),
            'message': f'保留上一版資料；本次更新失敗：{type(e).__name__}: {e}',
        }
        print(sid, 'DEGRADED', repr(e), file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--offline-dir', type=Path)
    a = ap.parse_args()
    now = dt.datetime.now(TZ).replace(microsecond=0).isoformat()
    old_status = load_json('status.json', {'sources': {}})
    before = revision_tracker.capture()
    status = {
        'last_check_at': now,
        'last_successful_sync_at': old_status.get('last_successful_sync_at'),
        'pipeline_version': 23,
        'schedule': '每日 18:17 Asia/Taipei',
        'sources': {},
    }
    bad = []
    refresh_source(status, bad, 'dgbas', source_macro.update, a.offline_dir, True)
    refresh_source(status, bad, 'regime_official', source_regime_official.update, a.offline_dir, False)
    source_moea.live_sales_index = source_moea_live_tables.live_sales_index
    refresh_source(status, bad, 'moea', source_moea.update, a.offline_dir, True)
    refresh_source(status, bad, 'ris', source_ris.update, a.offline_dir, True)
    refresh_source(status, bad, 'ndc', source_ndc.update, a.offline_dir, True)
    refresh_source(status, bad, 'market_live', source_twse_market_live.update, a.offline_dir, False)
    refresh_source(status, bad, 'decision', source_decision.update, a.offline_dir, False)
    refresh_source(status, bad, 'ai_concentration_inputs', source_ai_concentration.update, a.offline_dir, False)
    refresh_source(status, bad, 'decision_supplements', source_supplements.update, a.offline_dir, False)
    refresh_source(status, bad, 'inventory_manufacturing', source_moea_live_tables.update_inventory, a.offline_dir, False)
    refresh_source(status, bad, 'alpha_engine', source_alpha.update, a.offline_dir, False)
    refresh_source(status, bad, 'segis', source_segis.update, a.offline_dir, False)
    status['critical_failures'] = bad
    if not bad:
        status['last_successful_sync_at'] = now
    save_json('status.json', status)
    coverage(status)
    revision_tracker.record(before, now)
    save_json('data_quality_slo.json', build_data_quality_slo.build())

    build_vintage.capture(now)
    save_json('point_in_time_validation.json', build_point_in_time_validation.build())
    build_summary.generate()
    build_history.generate()
    build_decision_scores.generate()
    save_json('validation_targets.json', build_validation_targets.build())
    build_ai_concentration.generate()
    build_model_validation.generate()
    build_structural_layers.generate()
    build_investment.generate()
    build_intelligence_layer.generate()
    build_decision_engine.generate(append_journal=True)
    build_decision_engine_v2.generate()
    build_risk_budget_v2_availability.generate()
    save_json('decision_attribution.json', build_decision_attribution.build())
    save_json('statistical_challengers.json', build_statistical_challengers.build())
    build_validation_os_v1_3.generate(append_journal=True)
    build_decision_command.generate()
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
