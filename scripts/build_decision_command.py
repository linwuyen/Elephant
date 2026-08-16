#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import hashlib
import json

from common import TZ, load_json, save_json
import build_decision_engine_v2 as de2
import build_risk_budget_v2 as rb
import build_risk_budget_v2_availability as rba

DIRECTIONAL = ('cycle', 'growth_persistence', 'domestic_demand', 'financial_conditions')
ALLOWED_ACTIONS = {'BLOCKED', 'REDUCE_RISK', 'HOLD_CASH', 'HOLD_SELECTIVE', 'DEPLOY_SELECTIVELY'}


def clamp(v, lo, hi):
    return max(lo, min(hi, float(v)))


def digest(obj):
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def score_state(validation):
    dims = ((validation.get('data_confidence_v2') or {}).get('dimensions') or {})
    return {k: {'score': (dims.get(k) or {}).get('score'), 'period': (dims.get(k) or {}).get('period')} for k in de2.ALL_DIMS}


def average_directional(scores):
    vals = [float((scores.get(k) or {}).get('score')) for k in DIRECTIONAL if (scores.get(k) or {}).get('score') is not None]
    return None if not vals else sum(vals) / len(vals)


def confidence_label(data_confidence, analog_confidence, structural_status, prospective_resolved, critical_failures):
    reasons = []
    if critical_failures:
        return 'LOW', ['critical source failure is active']
    level = 2
    if data_confidence is None or data_confidence < 75:
        level = 0
        reasons.append('effective data confidence below 75')
    elif data_confidence < 85:
        level = min(level, 1)
        reasons.append('effective data confidence below 85')
    else:
        reasons.append(f'effective data confidence {data_confidence:.1f}')
    if analog_confidence is None or analog_confidence < 60:
        level = min(level, 0)
        reasons.append('risk-budget analog evidence below 60')
    elif analog_confidence < 75:
        level = min(level, 1)
        reasons.append('risk-budget analog evidence below 75')
    else:
        reasons.append(f'risk-budget analog evidence {analog_confidence:.1f}')
    if structural_status == 'HIGH':
        level = min(level, 1)
        reasons.append('structural-break monitor is HIGH')
    elif structural_status == 'WATCH':
        level = min(level, 1)
        reasons.append('structural-break monitor is WATCH')
    if int(prospective_resolved or 0) == 0:
        level = min(level, 1)
        reasons.append('prospective validation has not matured yet')
    return ('LOW', 'MEDIUM', 'HIGH')[level], reasons


def command_policy(v1_target, v2_target, buy_count, structural_status, critical_failures):
    if critical_failures or v1_target is None or v2_target is None:
        return {
            'code': 'BLOCKED',
            'title': '資料未就緒，暫停調整風險',
            'action': '先保留既有部位，不依不完整資料增加或降低曝險。',
            'deployment_policy': 'BLOCK_NEW_DEPLOYMENT',
        }
    low, high = sorted((float(v1_target), float(v2_target)))
    if v2_target <= 55:
        return {
            'code': 'REDUCE_RISK',
            'title': '降低股票風險，先守住資本',
            'action': f'市場感知風險預算降至 {v2_target:.1f}%；高於 {high:.1f}% 的曝險優先往下收。',
            'deployment_policy': 'REDUCE_TO_REVIEW_ZONE',
        }
    if int(buy_count or 0) == 0:
        if v2_target + 3 < v1_target or structural_status == 'HIGH':
            return {
                'code': 'HOLD_CASH',
                'title': '偏多，但新增資金先留現金',
                'action': f'既有股票曝險以 {low:.1f}–{high:.1f}% 為 review zone；目前沒有 BUY，不為了湊滿上限追價。',
                'deployment_policy': 'HOLD_CASH_UNTIL_ALPHA_BUY',
            }
        return {
            'code': 'HOLD_SELECTIVE',
            'title': '維持偏多，沒有合格標的不硬買',
            'action': f'股票曝險維持在 {low:.1f}–{high:.1f}% 區間；新增資金等待 Alpha Buy Gate。',
            'deployment_policy': 'HOLD_CASH_UNTIL_ALPHA_BUY',
        }
    return {
        'code': 'DEPLOY_SELECTIVELY',
        'title': '有風險容量，只部署到通過 BUY Gate 的標的',
        'action': f'在 {low:.1f}–{high:.1f}% review zone 內選擇性增加曝險，不因宏觀偏多越過 Alpha Gate。',
        'deployment_policy': 'BUY_GATE_ONLY',
    }


def current_inputs(histories, risk2):
    current = risk2.get('current') or {}
    if current.get('status') != 'READY':
        return None
    market_period = current.get('period')
    score_period = current.get('score_period')
    maps = rb.score_maps(histories)
    if not market_period or not score_period or not all(score_period in m for m in maps.values()):
        return None
    scores = {k: float(maps[k][score_period]) for k in de2.ALL_DIMS}
    market = current.get('market_state') or {}
    momentum = market.get('momentum_6m_pct')
    trailing_dd = market.get('trailing_drawdown_6m_pct')
    if momentum is None or trailing_dd is None:
        return None
    ndc_stock = de2.series_map((load_json('ndc.json', {}).get('series') or {}).get('stock_index'))
    states = rba.historical_states_lagged(histories, ndc_stock)
    training = rb.usable_training(states, market_period)
    return {
        'market_period': market_period,
        'score_period': score_period,
        'scores': scores,
        'momentum': float(momentum),
        'trailing_dd': float(trailing_dd),
        'training': training,
    }


def predict(training, scores, momentum, trailing_dd):
    return rb.analog_prediction(training, rb.normalized_feature_vector(scores, momentum, trailing_dd))


def counterfactuals(histories, risk2):
    state = current_inputs(histories, risk2)
    if not state or len(state['training']) < rb.MIN_TRAINING_SAMPLES:
        return {'status': 'BLOCKED_INSUFFICIENT_INPUT', 'training_samples': len(state['training']) if state else 0, 'scenarios': []}
    base = predict(state['training'], state['scores'], state['momentum'], state['trailing_dd'])
    if not base:
        return {'status': 'BLOCKED_INSUFFICIENT_INPUT', 'training_samples': len(state['training']), 'scenarios': []}
    base_target = float(base['target_equity_pct'])

    def run(sid, label, description, scores=None, momentum=None, trailing_dd=None):
        pred = predict(
            state['training'],
            scores or dict(state['scores']),
            state['momentum'] if momentum is None else momentum,
            state['trailing_dd'] if trailing_dd is None else trailing_dd,
        )
        if not pred:
            return None
        target = float(pred['target_equity_pct'])
        return {
            'id': sid,
            'label': label,
            'description': description,
            'target_equity_pct': round(target, 1),
            'delta_vs_current_pp': round(target - base_target, 1),
            'expected_forward_return_6m_pct': pred.get('expected_forward_return_6m_pct'),
            'expected_forward_drawdown_6m_pct': pred.get('expected_forward_drawdown_6m_pct'),
            'training_samples': len(state['training']),
            'contract': 'same training set; one declared counterfactual state; diagnostic sensitivity only',
        }

    ai_neutral = dict(state['scores']); ai_neutral['ai_concentration'] = 50.0
    macro_down = dict(state['scores'])
    macro_up = dict(state['scores'])
    for key in DIRECTIONAL:
        macro_down[key] = clamp(macro_down[key] - 15.0, -100.0, 100.0)
        macro_up[key] = clamp(macro_up[key] + 10.0, -100.0, 100.0)
    correction_momentum = clamp(state['momentum'] - 15.0, -30.0, 30.0)
    correction_dd = min(state['trailing_dd'], -15.0)
    scenarios = [
        run('market_heat_removed', '市場熱度歸零', '把 6M market momentum 設為 0，其餘條件不變。', momentum=0.0),
        run('ai_concentration_neutral', 'AI 集中回中性', '把 AI Concentration 設為 50，其餘條件不變。', scores=ai_neutral),
        run('macro_down_15', '景氣四維同步 -15', 'Cycle / Growth / Domestic / Financial 各下降 15 分。', scores=macro_down),
        run('market_correction_15', '市場回檔情境', '6M momentum 下修 15pp，trailing drawdown 至少 -15%，macro 不變。', momentum=correction_momentum, trailing_dd=correction_dd),
        run('macro_up_10', '景氣四維同步 +10', 'Cycle / Growth / Domestic / Financial 各上升 10 分。', scores=macro_up),
    ]
    scenarios = [x for x in scenarios if x]
    return {
        'status': 'READY',
        'base_target_equity_pct': round(base_target, 1),
        'training_samples': len(state['training']),
        'market_period': state['market_period'],
        'score_period': state['score_period'],
        'scenarios': scenarios,
        'note': 'These are model sensitivities, not causal estimates or forecasts. Each scenario uses the exact same historical training set as the current v2.1 review.',
    }


def decision_delta(journal, current_scores, v1_target, v2_target, market_period):
    entries = list(journal.get('entries') or [])
    if not entries:
        return {'status': 'NO_BASELINE', 'message': '尚無 prospective baseline；下一個 snapshot 起顯示真正 decision delta。'}
    previous = entries[-1]
    prev_risk = previous.get('risk') or {}
    deltas = {
        'v1_equity_pp': None if prev_risk.get('v1_equity_pct') is None or v1_target is None else round(float(v1_target) - float(prev_risk['v1_equity_pct']), 1),
        'v2_equity_pp': None if prev_risk.get('v2_equity_pct') is None or v2_target is None else round(float(v2_target) - float(prev_risk['v2_equity_pct']), 1),
    }
    score_deltas = {}
    for key in de2.ALL_DIMS:
        old = ((previous.get('scores') or {}).get(key) or {}).get('score')
        new = (current_scores.get(key) or {}).get('score')
        score_deltas[key] = None if old is None or new is None else round(float(new) - float(old), 1)
    meaningful = [abs(x) for x in list(deltas.values()) + list(score_deltas.values()) if x is not None]
    changed = any(x >= 1.0 for x in meaningful)
    return {
        'status': 'CHANGED' if changed else 'NO_MATERIAL_CHANGE',
        'baseline_recorded_at': previous.get('recorded_at'),
        'baseline_market_period': (previous.get('market') or {}).get('period'),
        'current_market_period': market_period,
        'risk_budget_delta': deltas,
        'score_delta': score_deltas,
        'message': '決策條件有實質變化。' if changed else '和最近 prospective baseline 相比，核心決策條件沒有實質變化。',
    }


def triggers(v2_target, v1_target, structural_status, data_confidence, buy_count, macro_avg):
    return {
        'increase_risk': [
            {
                'id': 'alpha_buy_unlock',
                'label': '出現真正 BUY candidate',
                'current': int(buy_count or 0),
                'condition': 'BUY candidate >= 1',
                'met': int(buy_count or 0) >= 1,
                'meaning': '只有這個條件滿足，新增股票資金才有 security-level 去處。',
            },
            {
                'id': 'risk_budget_converges',
                'label': '市場感知 Risk Budget 回到 champion 附近',
                'current': v2_target,
                'condition': None if v1_target is None else f'v2 review >= {max(60.0, float(v1_target)-2.0):.1f}%',
                'met': False if v1_target is None or v2_target is None else float(v2_target) >= max(60.0, float(v1_target)-2.0),
                'meaning': '代表 market-aware challenger 不再明顯要求比 v1 更保守。',
            },
            {
                'id': 'regime_normalizes',
                'label': 'Structural Break 降回 WATCH / NORMAL',
                'current': structural_status,
                'condition': 'status != HIGH',
                'met': structural_status not in ('HIGH', None),
                'meaning': '歷史類比更可信時，才值得提高對模型 sizing 的信心。',
            },
        ],
        'decrease_risk': [
            {
                'id': 'risk_budget_breaks_60',
                'label': 'Market-aware equity budget 跌破 60%',
                'current': v2_target,
                'condition': 'v2 review <= 60%',
                'met': False if v2_target is None else float(v2_target) <= 60.0,
                'meaning': '代表歷史 outcome evidence 已不再支持偏多風險配置。',
            },
            {
                'id': 'macro_breadth_breaks',
                'label': '景氣四維平均跌破 40',
                'current': None if macro_avg is None else round(macro_avg, 1),
                'condition': 'Cycle/Growth/Domestic/Financial average < 40',
                'met': False if macro_avg is None else macro_avg < 40.0,
                'meaning': '不是單一數據轉弱，而是廣泛 macro support 明顯失速。',
            },
            {
                'id': 'data_confidence_breaks',
                'label': 'Effective Data Confidence 跌破 75',
                'current': data_confidence,
                'condition': 'confidence < 75',
                'met': False if data_confidence is None else float(data_confidence) < 75.0,
                'meaning': '資料本身不夠可靠時，先縮小動作而不是強行輸出精確 allocation。',
            },
        ],
    }


def generate():
    now = dt.datetime.now(TZ).replace(microsecond=0).isoformat()
    risk1 = load_json('risk_budget.json', {})
    risk2 = load_json('risk_budget_v2.json', {})
    validation = load_json('validation_os.json', {})
    investment = load_json('investment.json', {})
    journal = load_json('validation_journal.json', {})
    status = load_json('status.json', {})
    histories = de2.score_histories()

    current2 = risk2.get('current') or {}
    envelope = current2.get('allocation_envelope') or {}
    v1_target = (risk1.get('allocation_guardrails') or {}).get('target_equity_risk_budget_pct')
    v2_target = envelope.get('equity_risk_budget_review_pct') or current2.get('target_equity_pct')
    zone = None if v1_target is None or v2_target is None else [round(min(float(v1_target), float(v2_target)), 1), round(max(float(v1_target), float(v2_target)), 1)]

    selection = investment.get('selection') or {}
    buy_count = int(selection.get('buy_candidate_count') or 0)
    verify_count = int(selection.get('verify_count') or 0)
    researched = list(selection.get('researched') or [])
    buy_rows = [x for x in researched if x.get('action') == 'BUY']
    verify_rows = sorted((x for x in researched if x.get('action') == 'VERIFY'), key=lambda x: (-(float(x.get('alpha_spread_pct') or -999)), int(x.get('rank') or 999)))

    sb = validation.get('structural_break_monitor') or {}
    data_conf = (validation.get('data_confidence_v2') or {}).get('overall')
    prospective = (validation.get('prospective_scorecards') or {}).get('resolved_total') or 0
    structural_status = sb.get('status')
    analog_conf = current2.get('evidence_confidence')
    critical = status.get('critical_failures') or []
    confidence, confidence_reasons = confidence_label(data_conf, analog_conf, structural_status, prospective, critical)
    policy = command_policy(v1_target, v2_target, buy_count, structural_status, critical)
    assert policy['code'] in ALLOWED_ACTIONS

    scores = score_state(validation)
    macro_avg = average_directional(scores)
    market = current2.get('market_state') or {}
    cf = counterfactuals(histories, risk2)
    delta = decision_delta(journal, scores, v1_target, v2_target, current2.get('period'))

    top_verify = [
        {
            'ticker': str(x.get('ticker')),
            'name': x.get('name'),
            'action': x.get('action'),
            'alpha_spread_pct': x.get('alpha_spread_pct'),
            'expected_return_pct': x.get('expected_return_pct'),
            'confidence_score': x.get('confidence_score'),
            'next_check': x.get('next_check'),
            'reference_price': x.get('reference_price'),
            'reference_price_date': x.get('reference_price_date'),
        }
        for x in verify_rows[:3]
    ]
    top_buy = [
        {
            'ticker': str(x.get('ticker')),
            'name': x.get('name'),
            'action': x.get('action'),
            'alpha_spread_pct': x.get('alpha_spread_pct'),
            'expected_return_pct': x.get('expected_return_pct'),
            'confidence_score': x.get('confidence_score'),
            'reference_price': x.get('reference_price'),
            'reference_price_date': x.get('reference_price_date'),
        }
        for x in buy_rows[:3]
    ]

    rationale = [
        {
            'type': 'support',
            'title': 'Macro environment',
            'text': (investment.get('macro_context') or {}).get('text') or 'Macro context unavailable.',
        },
        {
            'type': 'market',
            'title': 'Market already moved',
            'text': f"6M momentum {float(market.get('momentum_6m_pct') or 0):+.1f}% · trailing drawdown {float(market.get('trailing_drawdown_6m_pct') or 0):+.1f}% · v2 review {float(v2_target or 0):.1f}%.",
        },
        {
            'type': 'confidence',
            'title': 'Model uncertainty',
            'text': f"Effective data confidence {float(data_conf or 0):.1f}; Structural Break {structural_status or '—'}; prospective resolved {int(prospective)}.",
        },
        {
            'type': 'deployment',
            'title': 'Alpha deployment gate',
            'text': f'{buy_count} BUY · {verify_count} VERIFY. Risk capacity does not force security selection.',
        },
    ]

    trigger_set = triggers(v2_target, v1_target, structural_status, data_conf, buy_count, macro_avg)
    source_evidence = {
        'risk_budget_v1': risk1,
        'risk_budget_v2_current': current2,
        'validation_summary': {
            'data_confidence': data_conf,
            'structural_break': sb,
            'prospective_resolved': prospective,
        },
        'investment_selection': {
            'generated_at': investment.get('generated_at'),
            'macro_context': investment.get('macro_context'),
            'buy_count': buy_count,
            'verify_count': verify_count,
            'researched': researched,
        },
        'latest_validation_snapshot': (journal.get('entries') or [])[-1:] if journal.get('entries') else [],
    }

    obj = {
        'version': 1,
        'generated_at': now,
        'product': 'Elephant Decision Command Center v1',
        'authority': False,
        'contract': {
            'presentation_and_policy_compiler_only': True,
            'v1_risk_budget_remains_authoritative': True,
            'v2_risk_budget_remains_challenger': True,
            'alpha_buy_gate_remains_security_action_authority': True,
            'validation_os_can_only_reduce_reviewed_confidence': True,
            'does_not_create_buy_candidates': True,
            'does_not_store_private_portfolio': True,
            'no_automatic_trading': True,
        },
        'command': {
            **policy,
            'decision_confidence': confidence,
            'decision_confidence_reasons': confidence_reasons,
            'urgency': 'ACT' if policy['code'] == 'REDUCE_RISK' else 'WAIT_FOR_TRIGGER' if policy['code'] in ('HOLD_CASH', 'HOLD_SELECTIVE') else 'REVIEW',
        },
        'allocation': {
            'v1_authoritative_equity_pct': v1_target,
            'v2_market_aware_review_equity_pct': v2_target,
            'operating_zone_equity_pct': zone,
            'v2_cash_or_low_risk_pct': envelope.get('cash_or_low_risk_reserve_review_pct'),
            'disagreement_pct_points': None if v1_target is None or v2_target is None else round(float(v1_target) - float(v2_target), 1),
            'market_period': current2.get('period'),
            'score_period': current2.get('score_period'),
            'note': 'The zone is not a new model target: lower/upper bounds are the existing v2.1 challenger review and v1 champion outputs.',
        },
        'market': {
            'momentum_6m_pct': market.get('momentum_6m_pct'),
            'trailing_drawdown_6m_pct': market.get('trailing_drawdown_6m_pct'),
            'expected_forward_return_6m_pct': current2.get('expected_forward_return_6m_pct'),
            'expected_forward_drawdown_6m_pct': current2.get('expected_forward_drawdown_6m_pct'),
            'analog_evidence_confidence': analog_conf,
        },
        'macro': {
            'context': investment.get('macro_context'),
            'directional_average_score': None if macro_avg is None else round(macro_avg, 1),
            'scores': scores,
        },
        'validation': {
            'effective_data_confidence': data_conf,
            'structural_break_status': structural_status,
            'structural_break_reason': sb.get('reasons'),
            'correlation_drift_score': sb.get('correlation_drift_score'),
            'prospective_resolved_outcomes': prospective,
        },
        'alpha': {
            'buy_candidate_count': buy_count,
            'verify_count': verify_count,
            'top_buy': top_buy,
            'top_verify': top_verify,
            'selection_text': selection.get('text'),
        },
        'decision_delta': delta,
        'rationale': rationale,
        'counterfactuals': cf,
        'what_changes_my_mind': trigger_set,
        'private_portfolio_policy': {
            'storage': 'browser-local only',
            'rule': 'Above zone: reduce toward upper bound. Inside zone: hold unless a BUY candidate justifies selective deployment. Below zone with no BUY: preserve cash rather than force exposure. Below zone with BUY: deployment capacity is capped by the lower review bound.',
        },
        'source_generated_at': {
            'risk_budget_v1': risk1.get('generated_at'),
            'risk_budget_v2': risk2.get('generated_at'),
            'validation_os': validation.get('generated_at'),
            'investment': investment.get('generated_at'),
            'validation_journal': journal.get('updated_at'),
            'status': status.get('last_check_at'),
        },
        'evidence_hash': digest(source_evidence),
    }
    save_json('decision_command.json', obj)
    return obj


if __name__ == '__main__':
    print(json.dumps(generate(), ensure_ascii=False, indent=2))
