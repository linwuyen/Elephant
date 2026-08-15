#!/usr/bin/env python3
from __future__ import annotations

from common import load_json, save_json
import build_decision_engine_v2 as v2

MARKET_KEY = 'twse.taiex_month_end'


def market_series():
    market = load_json('market_inputs.json', {}).get('series', {})
    return v2.series_map(market.get(MARKET_KEY))


def market_outcomes(histories, stock):
    out = {}
    for dim in v2.CORE_DIMS:
        signal = v2.as_map(histories.get(dim, []))
        horizons = {}
        for h in (3, 6, 12):
            rows = []
            for p, score in signal.items():
                q = v2.month_shift(p, h)
                outcome = v2.percent_change(stock, p, q)
                if outcome is not None:
                    rows.append((score, outcome))
            corr = v2.pearson([x[0] for x in rows], [x[1] for x in rows])
            directional = None if not rows else sum((s > 0) == (o > 0) for s, o in rows) / len(rows)
            horizons[f'{h}m'] = {
                'samples': len(rows),
                'pearson': None if corr is None else round(corr, 3),
                'direction_accuracy': None if directional is None else round(directional, 4),
            }
        out[dim] = {
            'kind': 'market',
            'source': 'TWSE',
            'series': MARKET_KEY,
            'horizons': horizons,
        }

    drawdown = {}
    for dim in v2.CORE_DIMS:
        signal = v2.as_map(histories.get(dim, []))
        hs = {}
        for h in (3, 6, 12):
            rows = []
            for p, score in signal.items():
                dd = v2.forward_drawdown(stock, p, h)
                if dd is not None:
                    rows.append((score, dd))
            corr = v2.pearson([x[0] for x in rows], [x[1] for x in rows])
            hs[f'{h}m'] = {
                'samples': len(rows),
                'pearson_score_to_forward_drawdown': None if corr is None else round(corr, 3),
            }
        drawdown[dim] = hs
    return out, drawdown


def risk_backtest(histories, stock):
    states = v2.historical_risk_states(histories)
    monthly_policy, monthly_static, used = [], [], []
    for state in states:
        p, q = state['period'], v2.month_shift(state['period'], 1)
        ret = v2.percent_change(stock, p, q)
        if ret is None:
            continue
        policy_ret = ret * state['equity_pct'] / 100.0
        static_ret = ret * .60
        monthly_policy.append(policy_ret)
        monthly_static.append(static_ret)
        used.append({**state, 'stock_return_1m_pct': ret, 'policy_return_1m_pct': policy_ret})

    if not used:
        return {'status': 'BLOCKED_NO_OVERLAP', 'authority': False, 'observations': 0}

    policy_total, policy_dd = v2.compound(monthly_policy)
    static_total, static_dd = v2.compound(monthly_static)
    horizon_stats = {}
    for h in (3, 6, 12):
        rows = []
        for state in states:
            ret = v2.percent_change(stock, state['period'], v2.month_shift(state['period'], h))
            dd = v2.forward_drawdown(stock, state['period'], h)
            if ret is not None and dd is not None:
                rows.append((state['risk_score'], ret, dd))
        buckets = {}
        for risk, ret, dd in rows:
            lo = int(min(80, (risk // 20) * 20))
            buckets.setdefault(f'{lo}-{lo+20}', []).append((ret, dd))
        rc = v2.pearson([x[0] for x in rows], [x[1] for x in rows]) if rows else None
        dc = v2.pearson([x[0] for x in rows], [x[2] for x in rows]) if rows else None
        horizon_stats[f'{h}m'] = {
            'samples': len(rows),
            'pearson_risk_to_forward_return': None if rc is None else round(rc, 3),
            'pearson_risk_to_forward_drawdown': None if dc is None else round(dc, 3),
            'buckets': {
                key: {
                    'n': len(vals),
                    'mean_forward_return_pct': round(sum(x[0] for x in vals) / len(vals), 2),
                    'mean_forward_drawdown_pct': round(sum(x[1] for x in vals) / len(vals), 2),
                }
                for key, vals in sorted(buckets.items())
            },
        }

    return {
        'status': 'DIAGNOSTIC_ONLY',
        'authority': False,
        'market_source': 'TWSE official MI_5MINS_HIST month-end close',
        'market_series': MARKET_KEY,
        'observations': len(used),
        'policy_vs_static_60_equity': {
            'policy_scaled_equity_return_pct': round(policy_total, 2),
            'static_60_equity_return_pct': round(static_total, 2),
            'policy_max_drawdown_pct': round(policy_dd, 2),
            'static_60_max_drawdown_pct': round(static_dd, 2),
            'cash_return_assumption_pct': 0.0,
            'transaction_costs_included': False,
        },
        'horizons': horizon_stats,
        'warning': 'Reconstructed-score diagnostic only. TWSE is used solely as independent market outcome evidence. This cannot alter v1 Risk Budget.',
    }


def generate():
    obj = load_json('decision_engine_v2.json', {})
    if obj.get('version') != 2:
        raise ValueError('Decision Engine v2 must be built before market validation')
    stock = market_series()
    histories = v2.score_histories()
    if not stock:
        obj['market_evidence'] = {
            'status': 'BLOCKED_NO_TWSE_HISTORY',
            'authority': False,
            'source': 'TWSE',
        }
        obj['risk_budget_backtest'] = {'status': 'BLOCKED_NO_STOCK_INDEX', 'authority': False, 'observations': 0}
    else:
        market, drawdown = market_outcomes(histories, stock)
        ext = obj.setdefault('external_outcome_validation', {})
        for dim, item in market.items():
            ext.setdefault(dim, {})['stock_forward_return'] = item
        ext['_market_drawdown'] = drawdown
        obj['risk_budget_backtest'] = risk_backtest(histories, stock)
        market_obj = load_json('market_inputs.json', {})
        obj['market_evidence'] = {
            'status': 'READY',
            'authority': False,
            'source': 'TWSE',
            'series': MARKET_KEY,
            'latest_period': market_obj.get('latest_period'),
            'months': len(stock),
            'contract': 'official daily TAIEX OHLC → deterministic completed-month last-trading-day close',
        }

    # Recompute promotion gate after market evidence. This still cannot self-promote;
    # prospective outcomes and all other gates remain mandatory.
    obj['promotion_gate'] = v2.promotion_gate(
        obj.get('walk_forward_oos') or {},
        obj.get('external_outcome_validation') or {},
        obj.get('risk_budget_backtest') or {},
        obj.get('journal_scorecard_v2') or {},
    )
    save_json('decision_engine_v2.json', obj)
    return obj


if __name__ == '__main__':
    generate()
