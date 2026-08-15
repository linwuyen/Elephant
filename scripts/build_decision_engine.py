#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from common import DATA, TZ, load_json, save_json

HORIZONS = (1, 3, 6, 12)
SIGNED_DIMENSIONS = ('cycle', 'growth_persistence', 'domestic_demand', 'financial_conditions')
ALL_DIMENSIONS = SIGNED_DIMENSIONS + ('ai_concentration',)
SCORE_BINS = (-100, -60, -25, -5, 5, 25, 60, 101)
COMPANIES = ('McKinsey', 'BCG', 'Deloitte', 'PwC')


def clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, float(v)))


def month_shift(period: str, delta: int):
    try:
        y, m = map(int, str(period).split('-'))
    except Exception:
        return None
    idx = y * 12 + m - 1 + delta
    return f'{idx // 12:04d}-{idx % 12 + 1:02d}'


def load(name, default=None):
    return load_json(name, {} if default is None else default)


def score_histories():
    decisions = load('decision_scores.json', {'history': {}})
    intel = load('intelligence_history.json', {'cycle_history': []})
    out = {'cycle': intel.get('cycle_history') or []}
    for key in ('growth_persistence', 'domestic_demand', 'financial_conditions', 'ai_concentration'):
        out[key] = (decisions.get('history') or {}).get(key) or []
    return out


def current_scores():
    decisions = load('decision_scores.json', {'current': {}})
    summary = load('summary.json', {})
    current = dict(decisions.get('current') or {})
    c = summary.get('cycle') or {}
    if c:
        current['cycle'] = {
            'period': c.get('as_of'), 'score': c.get('score'), 'label': c.get('label'),
            'confidence': (summary.get('confidence') or {}).get('score'),
            'components': c.get('components') or [],
        }
    return current


def target_positive(key, score):
    if score is None:
        return None
    return float(score) >= 60 if key == 'ai_concentration' else float(score) > 0


def prior_probability(key, score):
    if score is None:
        return 0.5
    s = float(score)
    if key == 'ai_concentration':
        x = (s - 60.0) / 14.0
    else:
        x = s / 28.0
    return 1.0 / (1.0 + math.exp(-max(-8.0, min(8.0, x))))


def score_bin(score):
    s = float(score)
    for lo, hi in zip(SCORE_BINS[:-1], SCORE_BINS[1:]):
        if lo <= s < hi:
            return lo, hi
    return SCORE_BINS[-2], SCORE_BINS[-1]


def history_pairs(rows, horizon):
    m = {str(r.get('period')): r for r in rows if r.get('period') and r.get('score') is not None}
    pairs = []
    for p, row in sorted(m.items()):
        q = month_shift(p, horizon)
        future = m.get(q)
        if future and future.get('score') is not None:
            pairs.append((p, float(row['score']), q, float(future['score'])))
    return pairs


def empirical_probability(key, pairs, current_score):
    lo, hi = score_bin(current_score)
    local = [(s, f) for _, s, _, f in pairs if lo <= s < hi]
    prior = prior_probability(key, current_score)
    successes = sum(bool(target_positive(key, f)) for _, f in local)
    n = len(local)
    # Bayesian shrinkage to a transparent score-derived prior avoids tiny-bin extremes.
    p_emp = (successes + 1) / (n + 2) if n else prior
    weight = n / (n + 8.0)
    p = weight * p_emp + (1.0 - weight) * prior
    expected = (sum(f for _, f in local) / n) if n else current_score
    return p, expected, n, (lo, hi)


def calibration_for(key, pairs):
    if not pairs:
        return {'samples': 0, 'brier_score': None, 'direction_accuracy': None, 'bins': []}
    bucket = defaultdict(list)
    for _, s, _, f in pairs:
        bucket[score_bin(s)].append((s, f))
    rates = {}
    for b, vals in bucket.items():
        success = sum(bool(target_positive(key, f)) for _, f in vals)
        rates[b] = (success + 1) / (len(vals) + 2)
    preds, actuals = [], []
    for _, s, _, f in pairs:
        b = score_bin(s)
        empirical = rates[b]
        prior = prior_probability(key, s)
        n = len(bucket[b])
        w = n / (n + 8.0)
        p = w * empirical + (1.0 - w) * prior
        y = 1.0 if target_positive(key, f) else 0.0
        preds.append(p); actuals.append(y)
    brier = sum((p-y)**2 for p, y in zip(preds, actuals)) / len(preds)
    acc = sum((p >= .5) == bool(y) for p, y in zip(preds, actuals)) / len(preds)
    bins = []
    for b, vals in sorted(bucket.items()):
        success = sum(bool(target_positive(key, f)) for _, f in vals)
        bins.append({
            'score_bin': [b[0], b[1]], 'samples': len(vals),
            'observed_rate': round(success / len(vals), 4),
        })
    return {
        'samples': len(pairs),
        'brier_score': round(brier, 4),
        'direction_accuracy': round(acc, 4),
        'bins': bins,
    }


def build_forecast():
    histories = score_histories()
    current = current_scores()
    dimensions = {}
    metrics = []
    for key in ALL_DIMENSIONS:
        now = current.get(key) or {}
        score = now.get('score')
        if score is None:
            continue
        horizons = {}
        for h in HORIZONS:
            pairs = history_pairs(histories.get(key, []), h)
            p, expected, n, band = empirical_probability(key, pairs, float(score))
            cal = calibration_for(key, pairs)
            if cal.get('brier_score') is not None:
                metrics.append(cal['brier_score'])
            horizons[f'{h}m'] = {
                'horizon_months': h,
                'target': 'high_concentration_60_plus' if key == 'ai_concentration' else 'score_above_zero',
                'probability': round(p, 4),
                'expected_score': round(float(expected), 2),
                'local_sample_size': n,
                'current_score_bin': list(band),
                'calibration': cal,
            }
        dimensions[key] = {
            'period': now.get('period'), 'score': score, 'label': now.get('label'),
            'horizons': horizons,
        }
    avg_brier = sum(metrics) / len(metrics) if metrics else None
    model_conf = 0 if avg_brier is None else clamp((1.0 - avg_brier) * 100.0)
    out = {
        'version': 1,
        'generated_at': dt.datetime.now(TZ).replace(microsecond=0).isoformat(),
        'method': 'empirical-score-bin calibration with Bayesian shrinkage to a transparent logistic prior',
        'basis': 'Historical rows before point-in-time vintage collection are revised-series reconstructions; true vintage calibration accumulates prospectively from vintages.db.',
        'lookahead_warning': True,
        'horizons_months': list(HORIZONS),
        'model_confidence': round(model_conf, 1),
        'dimensions': dimensions,
    }
    save_json('forecast.json', out)
    return out


GEOGRAPHY_RULES = {
    'Taiwan': ('taiwan', 'taiwanese'),
    'China': ('china', 'chinese'),
    'United States': ('united states', 'u.s.', ' us ', 'american'),
    'Europe': ('europe', 'european', 'eu '),
    'Asia': ('asia', 'asian', 'apac'),
    'Global': ('global', 'worldwide', 'world '),
}
INDUSTRY_RULES = {
    'Semiconductor': ('semiconductor', 'chip', 'foundry', 'wafer', 'advanced packaging'),
    'AI Infrastructure': ('data center', 'compute', 'cloud infrastructure', 'ai infrastructure', 'gpu'),
    'Manufacturing': ('manufactur', 'industrial', 'factory'),
    'Consumer': ('consumer', 'retail', 'shopping', 'household'),
    'Financial Services': ('bank', 'financial services', 'capital market', 'insurance'),
    'Energy': ('energy', 'power', 'electricity', 'grid'),
    'Workforce': ('workforce', 'worker', 'talent', 'job', 'skills'),
    'Supply Chain': ('supply chain', 'procurement', 'logistics', 'inventory'),
}
RISK_PATTERNS = ('risk', 'uncertainty', 'shortage', 'pressure', 'slowdown', 'decline', 'constraint', 'threat', 'volatile', 'disruption', 'challenge')
SUPPORT_PATTERNS = ('growth', 'opportunity', 'accelerat', 'advantage', 'value creation', 'expansion', 'productivity', 'strong demand', 'investment boom', 'resilien')


def first_sentence(text):
    text = re.sub(r'\s+', ' ', str(text or '')).strip()
    if not text:
        return ''
    parts = re.split(r'(?<=[.!?。！？])\s+', text)
    return parts[0][:420]


def detect_labels(text, rules):
    low = f' {text.lower()} '
    return [label for label, terms in rules.items() if any(t in low for t in terms)]


def claim_direction(text):
    low = text.lower()
    risk = sum(t in low for t in RISK_PATTERNS)
    support = sum(t in low for t in SUPPORT_PATTERNS)
    if risk >= support + 1:
        return 'risk'
    if support >= risk + 2:
        return 'supportive'
    if risk and support:
        return 'mixed'
    return 'context'


def claim_horizon(text):
    low = text.lower()
    if re.search(r'203\d|204\d|long[- ]term|next decade|decade', low):
        return 'long-term'
    if re.search(r'202[6-9]|next (?:two|three|four|five) years|3[-–]5 years', low):
        return 'medium-term'
    if any(x in low for x in ('near-term', 'this year', 'next year', 'quarter', 'months')):
        return 'near-term'
    return 'unspecified'


def build_research_claims():
    research = load('consultant/reports.json', {'reports': []})
    claims = []
    for r in research.get('reports') or []:
        company = r.get('company')
        if company not in COMPANIES:
            continue
        title = str(r.get('title') or '').strip()
        desc = str(r.get('description') or '').strip()
        topics = [str(x) for x in (r.get('topics') or [])]
        text = ' '.join([title, desc, ' '.join(topics)])
        geos = detect_labels(text, GEOGRAPHY_RULES) or ['Global/unspecified']
        industries = sorted(set(detect_labels(text, INDUSTRY_RULES) + topics))[:8]
        basis = first_sentence(desc) or title
        strength = 35 + (25 if desc else 0) + min(20, len(topics) * 5)
        try:
            age = (dt.datetime.now(TZ).date() - dt.date.fromisoformat(str(r.get('date'))[:10])).days
            if age <= 90: strength += 15
            elif age <= 365: strength += 8
        except Exception:
            pass
        claims.append({
            'id': r.get('id'),
            'company': company,
            'date': r.get('date'),
            'title': title,
            'claim_candidate': basis,
            'direction': claim_direction(text),
            'geography': geos,
            'industries': industries,
            'horizon': claim_horizon(text),
            'evidence_strength': round(clamp(strength), 0),
            'source_url': r.get('url'),
            'basis': 'publisher metadata/title/description; not full-text semantic extraction',
            'score_influence': False,
        })
    claims.sort(key=lambda x: (x.get('date') or '', x.get('evidence_strength') or 0), reverse=True)
    by_company = Counter(x['company'] for x in claims)
    by_direction = Counter(x['direction'] for x in claims)
    out = {
        'version': 1,
        'generated_at': dt.datetime.now(TZ).replace(microsecond=0).isoformat(),
        'classification': 'structured-claim-candidates-from-public-metadata',
        'fulltext_claim_extraction': False,
        'score_influence': False,
        'claims': claims,
        'summary': {
            'claims': len(claims),
            'companies': dict(by_company),
            'directions': dict(by_direction),
        },
    }
    save_json('research_claims.json', out)
    return out


def build_risk_budget():
    cur = current_scores()
    def s(k, default=0):
        v = (cur.get(k) or {}).get('score')
        return default if v is None else float(v)
    cycle, growth, domestic, financial, concentration = s('cycle'), s('growth_persistence'), s('domestic_demand'), s('financial_conditions'), s('ai_concentration', 50)
    base = 50 + .14*cycle + .16*growth + .16*financial + .06*domestic
    concentration_penalty = max(0.0, concentration - 55.0) * .55
    risk_score = clamp(base - concentration_penalty)
    if risk_score >= 80:
        posture = 'RISK_ON_WITH_CONCENTRATION_GUARD'
    elif risk_score >= 60:
        posture = 'CONSTRUCTIVE'
    elif risk_score >= 40:
        posture = 'BALANCED'
    elif risk_score >= 20:
        posture = 'DEFENSIVE'
    else:
        posture = 'CAPITAL_PRESERVATION'
    target_equity = round(clamp(25 + .65*risk_score, 20, 90), 0)
    cash_floor = round(clamp(40 - .35*risk_score, 5, 35), 0)
    max_single = round(clamp(22 - max(0, concentration-55)*.12, 10, 22), 0)
    confs = [float((cur.get(k) or {}).get('confidence')) for k in ALL_DIMENSIONS if (cur.get(k) or {}).get('confidence') is not None]
    data_conf = sum(confs)/len(confs) if confs else 0
    out = {
        'version': 1,
        'generated_at': dt.datetime.now(TZ).replace(microsecond=0).isoformat(),
        'risk_score': round(risk_score, 1),
        'posture': posture,
        'data_confidence': round(data_conf, 1),
        'allocation_guardrails': {
            'target_equity_risk_budget_pct': target_equity,
            'cash_floor_pct': cash_floor,
            'max_single_stock_pct': max_single,
            'concentration_penalty_points': round(concentration_penalty, 1),
        },
        'inputs': {
            'cycle': cycle, 'growth_persistence': growth, 'domestic_demand': domestic,
            'financial_conditions': financial, 'ai_concentration': concentration,
        },
        'contract': {
            'does_not_create_buy_candidate': True,
            'does_not_override_alpha_action': True,
            'no_automatic_trading': True,
            'personal_portfolio_not_stored_in_repository': True,
        },
        'position_sizing_rule': 'Browser-local portfolio state may translate this risk budget into add/reduce capacity. Deployment remains gated by the stock Alpha Buy Gate.',
    }
    save_json('risk_budget.json', out)
    return out


def history_map(histories, key):
    return {str(r.get('period')): r for r in histories.get(key, []) if r.get('period')}


def forecast_probability(forecast, key, h):
    return ((((forecast.get('dimensions') or {}).get(key) or {}).get('horizons') or {}).get(f'{h}m') or {}).get('probability')


def journal_fingerprint(period, scores, risk, investment):
    buy = sorted(str(x.get('ticker')) for x in ((investment.get('selection') or {}).get('researched') or []) if x.get('action') == 'BUY CANDIDATE')
    obj = {
        'period': period,
        'scores': {k: round(float((scores.get(k) or {}).get('score')), 1) if (scores.get(k) or {}).get('score') is not None else None for k in ALL_DIMENSIONS},
        'risk': risk.get('posture'), 'buy': buy,
    }
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:16]


def evaluate_journal(journal, histories):
    resolved = []
    current_periods = [r.get('period') for r in histories.get('cycle', []) if r.get('period')]
    latest = max(current_periods) if current_periods else None
    for entry in journal.get('entries') or []:
        outcomes = entry.setdefault('outcomes', {})
        base = entry.get('period')
        for h in HORIZONS:
            key = f'{h}m'
            if key in outcomes or not base or not latest:
                continue
            target_p = month_shift(base, h)
            if target_p > latest:
                continue
            actual = (history_map(histories, 'cycle').get(target_p) or {}).get('score')
            prob = ((entry.get('forecast') or {}).get('cycle') or {}).get(key)
            if actual is None or prob is None:
                continue
            y = 1 if float(actual) > 0 else 0
            prediction = 1 if float(prob) >= .5 else 0
            result = {
                'target_period': target_p,
                'actual_cycle_score': actual,
                'actual_positive': bool(y),
                'forecast_probability': prob,
                'correct_direction': prediction == y,
                'brier': round((float(prob)-y)**2, 4),
            }
            outcomes[key] = result
            resolved.append(result)
    all_outcomes = [o for e in journal.get('entries') or [] for o in (e.get('outcomes') or {}).values()]
    if all_outcomes:
        hit = sum(bool(x.get('correct_direction')) for x in all_outcomes) / len(all_outcomes)
        brier = sum(float(x.get('brier', 0)) for x in all_outcomes) / len(all_outcomes)
    else:
        hit = brier = None
    journal['scorecard'] = {
        'resolved_forecasts': len(all_outcomes),
        'direction_hit_rate': None if hit is None else round(hit, 4),
        'brier_score': None if brier is None else round(brier, 4),
        'note': 'Scorecard becomes point-in-time meaningful only for decisions recorded after vintage collection began.',
    }
    return journal


def build_journal(forecast, risk, append=True):
    journal = load('decision_journal.json', {'version': 1, 'entries': [], 'scorecard': {}})
    histories = score_histories()
    current = current_scores()
    investment = load('investment.json', {})
    period = (current.get('cycle') or {}).get('period') or (current.get('growth_persistence') or {}).get('period')
    fp = journal_fingerprint(period, current, risk, investment)
    entries = journal.setdefault('entries', [])
    if append and (not entries or entries[-1].get('fingerprint') != fp):
        alpha_rows = (investment.get('selection') or {}).get('researched') or []
        entry = {
            'id': fp,
            'fingerprint': fp,
            'recorded_at': dt.datetime.now(TZ).replace(microsecond=0).isoformat(),
            'period': period,
            'scores': {k: {
                'score': (current.get(k) or {}).get('score'),
                'label': (current.get(k) or {}).get('label'),
                'confidence': (current.get(k) or {}).get('confidence'),
            } for k in ALL_DIMENSIONS},
            'forecast': {
                k: {f'{h}m': forecast_probability(forecast, k, h) for h in HORIZONS}
                for k in ALL_DIMENSIONS if k in (forecast.get('dimensions') or {})
            },
            'risk_posture': risk.get('posture'),
            'risk_budget_pct': (risk.get('allocation_guardrails') or {}).get('target_equity_risk_budget_pct'),
            'alpha_actions': {str(x.get('ticker')): x.get('action') for x in alpha_rows},
            'expectation': 'Prospective machine decision snapshot. Future outcomes are evaluated against later observed Cycle Score without rewriting this entry.',
            'invalidation': {
                'cycle_below': 0,
                'growth_persistence_below': 0,
                'financial_conditions_below': 0,
                'note': 'Thresholds are risk-regime invalidation guards, not automatic trade orders.',
            },
            'outcomes': {},
        }
        entries.append(entry)
        journal['entries'] = entries[-300:]
    journal = evaluate_journal(journal, histories)
    journal['updated_at'] = dt.datetime.now(TZ).replace(microsecond=0).isoformat()
    save_json('decision_journal.json', journal)
    return journal


def confidence_layers(forecast, risk, investment):
    data = float(risk.get('data_confidence') or 0)
    model = float(forecast.get('model_confidence') or 0)
    freshness = investment.get('freshness') or {}
    freshness_penalty = 0
    if freshness.get('alpha_research_stale'): freshness_penalty += 15
    if freshness.get('screen_stale'): freshness_penalty += 10
    decision = clamp(.45*data + .40*model + .15*100 - freshness_penalty)
    return {
        'data_confidence': round(data, 1),
        'model_confidence': round(model, 1),
        'decision_confidence': round(decision, 1),
        'definitions': {
            'data_confidence': 'How complete the currently required official score inputs are.',
            'model_confidence': 'Historical forecast calibration quality and sample support.',
            'decision_confidence': 'Combined data/model confidence adjusted for investment-layer freshness; not a guarantee of return.',
        },
    }


def build_scenarios(risk):
    base = risk.get('inputs') or {}
    def calc(shocks):
        x = dict(base)
        for k, d in shocks.items():
            x[k] = float(x.get(k, 0)) + d
        raw = 50 + .14*x['cycle'] + .16*x['growth_persistence'] + .16*x['financial_conditions'] + .06*x['domestic_demand']
        penalty = max(0, x['ai_concentration'] - 55) * .55
        return round(clamp(raw-penalty), 1)
    return [
        {'name': 'Base', 'shocks': {}, 'risk_score': calc({})},
        {'name': 'Growth shock', 'shocks': {'growth_persistence': -50, 'cycle': -25}, 'risk_score': calc({'growth_persistence': -50, 'cycle': -25})},
        {'name': 'Liquidity shock', 'shocks': {'financial_conditions': -60}, 'risk_score': calc({'financial_conditions': -60})},
        {'name': 'AI concentration shock', 'shocks': {'ai_concentration': 20}, 'risk_score': calc({'ai_concentration': 20})},
    ]


def generate(append_journal=True):
    forecast = build_forecast()
    claims = build_research_claims()
    risk = build_risk_budget()
    journal = build_journal(forecast, risk, append=append_journal)
    investment = load('investment.json', {})
    confidence = confidence_layers(forecast, risk, investment)
    out = {
        'version': 1,
        'generated_at': dt.datetime.now(TZ).replace(microsecond=0).isoformat(),
        'product': 'Elephant Decision Engine v1',
        'contract': {
            'official_scores_are_deterministic': True,
            'research_score_influence': False,
            'alpha_buy_gate_authoritative': True,
            'no_automatic_trading': True,
            'no_fabricated_missing_values': True,
            'personal_portfolio_storage': 'browser-local-only',
        },
        'confidence': confidence,
        'forecast': {
            'model_confidence': forecast.get('model_confidence'),
            'basis': forecast.get('basis'),
            'dimensions': forecast.get('dimensions'),
        },
        'risk_budget': risk,
        'scenarios': build_scenarios(risk),
        'research_claims': {
            'summary': claims.get('summary'),
            'classification': claims.get('classification'),
            'fulltext_claim_extraction': False,
        },
        'journal_scorecard': journal.get('scorecard'),
    }
    save_json('decision_engine.json', out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-journal', action='store_true')
    args = ap.parse_args()
    print(json.dumps(generate(append_journal=not args.no_journal), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
