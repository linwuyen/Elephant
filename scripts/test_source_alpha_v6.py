#!/usr/bin/env python3
import copy

import source_alpha


def fixtures():
    alpha = {
        'meta': {'schema_version': 6, 'decision_engine_version': 'security-v6.0.0'},
        'decision_policy': {'min_base_upside_pct': 20},
        'benchmark_asset': {'valuation_metrics': {'base_upside_pct': 30}},
        'stocks': [{
            'ticker': '9999', 'score': 80, 'confidence_score': 75, 'action': 'VERIFY',
            'valuation_metrics': {'base_upside_pct': 25},
            'buy_gate': {'checks': {'base_upside': True}},
        }],
    }
    screen = {
        'meta': {'schema_version': 5, 'fail_closed': True, 'status': 'COMPLETE', 'promotion_enabled_by_market': {'TWSE': True, 'TPEX': True}},
        'rules': {'screen_is_not_buy_gate': True},
        'candidates': [], 'deep_research_queue': [],
    }
    performance = {
        'meta': {
            'schema_version': 3,
            'primary_cohort': 'BUY_CANDIDATE',
            'return_type': 'TOTAL_RETURN_CASH_DISTRIBUTIONS_NO_REINVESTMENT',
            'corporate_action_source': 'TWSE_TWT48U_ALL',
        },
        'minimum_samples_for_calibration': 30,
    }
    scenario = {'schema_version': 1, 'horizon_weeks': 52, 'minimum_resolved_samples': 30, 'status': 'INSUFFICIENT_HISTORY'}
    voi = {
        'schema_version': 1, 'authority': False, 'score_influence': False, 'buy_gate_influence': False,
        'rows': [{'ticker':'9999','research_priority':80,'rank':1}],
    }
    promotion = {
        'contract':'pre_registered_security_model_promotion_v1','automatic_promotion':False,'immutable_without_version_bump':True,
        'rules':{'realized_return_calibration':{'eligible_return_metric':'EXCESS_TOTAL_RETURN_VS_2330','minimum_samples_per_primary_horizon':30}}
    }
    return alpha, screen, performance, scenario, voi, promotion


def must_fail(alpha, screen, performance, scenario, voi, promotion):
    try:
        source_alpha._validate(alpha, screen, performance, scenario, voi, promotion)
    except ValueError:
        return
    raise AssertionError('expected source_alpha validation failure')


def main():
    alpha, screen, performance, scenario, voi, promotion = fixtures()
    source_alpha._validate(alpha, screen, performance, scenario, voi, promotion)

    legacy = copy.deepcopy(alpha);legacy['meta']['schema_version'] = 5
    must_fail(legacy, screen, performance, scenario, voi, promotion)

    wrong = copy.deepcopy(alpha);wrong['stocks'][0]['valuation_metrics'] = {'margin_of_safety_pct': 25}
    must_fail(wrong, screen, performance, scenario, voi, promotion)

    price_only=copy.deepcopy(performance);price_only['meta']['return_type']='PRICE_RETURN_EX_DIVIDENDS'
    must_fail(alpha,screen,price_only,scenario,voi,promotion)

    weak = copy.deepcopy(scenario);weak['minimum_resolved_samples'] = 5
    must_fail(alpha, screen, performance, weak, voi, promotion)

    authoritative=copy.deepcopy(voi);authoritative['buy_gate_influence']=True
    must_fail(alpha,screen,performance,scenario,authoritative,promotion)

    auto=copy.deepcopy(promotion);auto['automatic_promotion']=True
    must_fail(alpha,screen,performance,scenario,voi,auto)
    print('SOURCE ALPHA V6 + DECISION SCIENCE CONTRACT TEST PASS')


if __name__ == '__main__':
    main()
