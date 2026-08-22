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
    performance = {'meta': {'schema_version': 2, 'primary_cohort': 'BUY_CANDIDATE'}}
    scenario = {'schema_version': 1, 'horizon_weeks': 52, 'minimum_resolved_samples': 30, 'status': 'INSUFFICIENT_HISTORY'}
    return alpha, screen, performance, scenario


def must_fail(alpha, screen, performance, scenario):
    try:
        source_alpha._validate(alpha, screen, performance, scenario)
    except ValueError:
        return
    raise AssertionError('expected source_alpha validation failure')


def main():
    alpha, screen, performance, scenario = fixtures()
    source_alpha._validate(alpha, screen, performance, scenario)

    legacy = copy.deepcopy(alpha)
    legacy['meta']['schema_version'] = 5
    must_fail(legacy, screen, performance, scenario)

    wrong = copy.deepcopy(alpha)
    wrong['stocks'][0]['valuation_metrics'] = {'margin_of_safety_pct': 25}
    must_fail(wrong, screen, performance, scenario)

    weak = copy.deepcopy(scenario)
    weak['minimum_resolved_samples'] = 5
    must_fail(alpha, screen, performance, weak)
    print('SOURCE ALPHA V6 CONTRACT TEST PASS')


if __name__ == '__main__':
    main()
