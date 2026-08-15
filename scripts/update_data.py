#!/usr/bin/env python3
import argparse
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path
from common import TZ, URLS, load_json, save_json, request_bytes, decode_text
import build_summary
import build_history
import build_decision_scores
import build_ai_concentration
import build_model_validation
import build_structural_layers
import build_intelligence_layer
import build_investment
import build_vintage
import build_decision_engine
import build_decision_engine_v2
import revision_tracker
import source_macro
import source_moea
import source_moea_dataset
import source_ndc
import source_ris
import source_decision
import source_ai_concentration
import source_supplements
import source_alpha


def segis(offline=False):
    if offline:
        return {'status': 'blocked', 'latest_period': None, 'message': 'SEGIS 未使用測試快照；不產生假資料。', 'source_url': URLS['segis_catalog']}
    msg = 'SEGIS 鄉鎮市區工商家數欄位已註冊；未取得穩定可重現公開直鏈或 APP ID/API Key 前不自動寫入。'
    found = None
    try:
        text = html.unescape(decode_text(request_bytes(URLS['segis_catalog'], 45, 1)[0]))
        m = re.search(r'https?://[^"\'<> ]*reqcontroller\.file\?method=filedown\.downloadproductfile[^"\'<> ]+', text)
        found = m.group(0).replace('&amp;', '&') if m else None
    except Exception as e:
        msg += f' Catalog probe: {type(e).__name__}.'
    return {'status': 'blocked', 'latest_period': None, 'message': msg, 'candidate_download': found, 'source_url': URLS['segis_catalog']}


def coverage(status):
    macro = load_json('macro.json', {})
    pop = load_json('population.json', {})
    ind = load_json('industry.json', {})
    ndc = load_json('ndc.json', {})
    decision = load_json('decision_inputs.json', {})
    ai = load_json('ai_inputs.json', {})
    rows = []
    for iid, s in macro.get('series', {}).items():
        d = s.get('data', [])
        rows.append({'source': 'dgbas', 'dataset': s.get('dataset_id'), 'indicator': iid, 'name': s.get('name'), 'frequency': s.get('frequency', 'annual'), 'points': len(d), 'period': f'{d[0][0]}..{d[-1][0]}' if d else '-'})
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
        'pipeline_version': 15,
        'schedule': '每日 18:17 Asia/Taipei',
        'sources': {},
    }
    bad = []
    refresh_source(status, bad, 'dgbas', source_macro.update, a.offline_dir, True)
    # Critical MOEA sales now comes from data.gov dataset metadata -> official MOEA
    # CSV/ZIP resource. The mutable ASP.NET presentation page is not a data contract.
    source_moea.live_sales_index = source_moea_dataset.sales_index
    refresh_source(status, bad, 'moea', source_moea.update, a.offline_dir, True)
    refresh_source(status, bad, 'ris', source_ris.update, a.offline_dir, True)
    refresh_source(status, bad, 'ndc', source_ndc.update, a.offline_dir, True)
    refresh_source(status, bad, 'decision', source_decision.update, a.offline_dir, False)
    refresh_source(status, bad, 'ai_concentration_inputs', source_ai_concentration.update, a.offline_dir, False)
    refresh_source(status, bad, 'decision_supplements', source_supplements.update, a.offline_dir, False)
    # Inventory total uses data.gov dataset 109753 and resolves the first-party resource
    # dynamically. It never synthesizes a manufacturing total from sub-industries.
    refresh_source(status, bad, 'inventory_manufacturing', source_moea_dataset.update_inventory, a.offline_dir, False)
    refresh_source(status, bad, 'alpha_engine', source_alpha.update, a.offline_dir, False)
    status['sources']['segis'] = segis(bool(a.offline_dir))
    status['critical_failures'] = bad
    if not bad:
        status['last_successful_sync_at'] = now
    save_json('status.json', status)
    coverage(status)
    revision_tracker.record(before, now)

    build_vintage.capture(now)
    build_summary.generate()
    build_history.generate()
    build_decision_scores.generate()
    build_ai_concentration.generate()
    build_model_validation.generate()
    build_structural_layers.generate()
    build_investment.generate()
    build_intelligence_layer.generate()
    # v1 remains authoritative. v2 is generated strictly downstream as a
    # challenger/validation artifact and has no write path back into scores,
    # Risk Budget, Alpha actions, or portfolio policy.
    build_decision_engine.generate(append_journal=True)
    build_decision_engine_v2.generate()
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
