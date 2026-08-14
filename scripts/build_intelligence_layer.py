#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
from pathlib import Path

from common import TZ, load_json, save_json

DIMENSIONS = {
    'growth_persistence': {
        'name': 'Growth Persistence',
        'question': '這波景氣還能持續嗎？',
        'topics': {'Manufacturing', 'Supply Chain', 'Semiconductor', 'Data Center', 'Economics', 'Strategy'},
        'keywords': ('manufactur', 'supply chain', 'semiconductor', 'chip', 'export', 'trade', 'inventory', 'capex', 'capital spending', 'industrial', 'procurement', 'resilience', 'data center', 'demand'),
    },
    'domestic_demand': {
        'name': 'Domestic Demand',
        'question': '台灣一般人的經濟真的有變好嗎？',
        'topics': {'Economics', 'Workforce', 'Strategy'},
        'keywords': ('consumer', 'retail', 'spending', 'household', 'inflation', 'wage', 'employment', 'jobs', 'shopping', 'sentiment', 'food', 'health'),
    },
    'financial_conditions': {
        'name': 'Financial Conditions',
        'question': '資金環境是在支持還是壓制景氣？',
        'topics': {'Economics', 'Strategy'},
        'keywords': ('capital', 'funding', 'interest rate', 'liquidity', 'credit', 'investment', 'cfo', 'cost of capital', 'financing', 'currency', 'valuation', 'portfolio'),
    },
    'ai_concentration': {
        'name': 'AI Concentration',
        'question': '台灣成長有多集中在 AI／電子鏈？',
        'topics': {'AI', 'Semiconductor', 'Data Center', 'Manufacturing', 'Supply Chain'},
        'keywords': ('artificial intelligence', 'generative ai', 'agentic', ' ai ', 'semiconductor', 'chip', 'wafer', 'foundry', 'data center', 'compute', 'cloud infrastructure', 'advanced packaging', 'technology infrastructure'),
    },
}

SUPPORT_WORDS = (
    'opportunity', 'accelerat', 'strong demand', 'competitive advantage', 'value creation',
    'resilien', 'boost', 'expansion', 'grow', 'productivity', 'investment', 'scale', 'thrive',
)
RISK_WORDS = (
    'risk', 'uncertainty', 'pessim', 'pressure', 'slowdown', 'shortage', 'cost uncertainty',
    'volatil', 'decline', 'weak', 'disruption', 'constraint', 'concern', 'tighten', 'threat',
)
COMPANIES = {'McKinsey', 'BCG', 'Deloitte', 'PwC'}


def parse_date(value):
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def report_text(r):
    return f" {r.get('title', '')} {r.get('description', '')} {' '.join(r.get('topics') or [])} ".lower()


def relevance(r, cfg, today):
    text = report_text(r)
    title = f" {r.get('title', '')} ".lower()
    topics = set(r.get('topics') or [])
    score = 0.0
    for topic in cfg['topics']:
        if topic in topics:
            score += 7
    for kw in cfg['keywords']:
        k = kw.lower()
        if k in title:
            score += 6
        elif k in text:
            score += 2.5
    d = parse_date(r.get('date'))
    if d:
        age = max(0, (today - d).days)
        if age <= 30:
            score += 4
        elif age <= 90:
            score += 2
        elif age > 365:
            score -= 2
    return score


def stance(r):
    text = report_text(r)
    pos = sum(1 for x in SUPPORT_WORDS if x in text)
    neg = sum(1 for x in RISK_WORDS if x in text)
    if neg >= pos + 1:
        return 'risk'
    if pos >= neg + 2:
        return 'supportive'
    return 'context'


def compact_report(r, rel):
    return {
        'id': r.get('id'),
        'company': r.get('company'),
        'date': r.get('date'),
        'title': r.get('title'),
        'url': r.get('url'),
        'topics': r.get('topics') or [],
        'stance': stance(r),
        'relevance': round(float(rel), 1),
    }


def diverse_top(rows, n):
    rows = sorted(rows, key=lambda x: (x['relevance'], x.get('date') or ''), reverse=True)
    out, seen_ids, used_firms = [], set(), set()
    for row in rows:
        if row['company'] in used_firms:
            continue
        out.append(row); seen_ids.add(row['id']); used_firms.add(row['company'])
        if len(out) >= n:
            return out
    for row in rows:
        if row['id'] in seen_ids:
            continue
        out.append(row); seen_ids.add(row['id'])
        if len(out) >= n:
            break
    return out


def map_dimension(reports, cfg, today):
    mapped = []
    for r in reports:
        if r.get('company') not in COMPANIES:
            continue
        rel = relevance(r, cfg, today)
        if rel < 4:
            continue
        mapped.append(compact_report(r, rel))
    return sorted(mapped, key=lambda x: (x['relevance'], x.get('date') or ''), reverse=True)


def official_block(score):
    if not score:
        return None
    return {
        'period': score.get('period'),
        'score': score.get('score'),
        'label': score.get('label'),
        'confidence': score.get('confidence'),
        'components': [
            {
                'key': x.get('key'), 'name': x.get('name'), 'raw': x.get('raw'),
                'score': x.get('score'), 'period': x.get('period'), 'source': x.get('source'),
            }
            for x in score.get('components', [])
        ],
    }


def change_block(old, current, mapped):
    if not old:
        return {'state': 'baseline', 'text': '建立 Intelligence Layer v1 baseline。', 'new_research': len(mapped)}
    old_score = (old.get('official') or {}).get('score')
    new_score = (current or {}).get('score')
    delta = None if old_score is None or new_score is None else round(float(new_score) - float(old_score), 2)
    old_ids = {x.get('id') for key in ('evidence', 'contradictions', 'risks') for x in old.get(key, [])}
    new_items = [x for x in mapped if x.get('id') not in old_ids]
    if delta is not None and abs(delta) >= 2:
        text = f"官方分數較上一版變動 {delta:+.1f}；新增 {len(new_items)} 篇相關顧問研究。"
        state = 'changed'
    elif new_items:
        text = f"官方核心分數大致穩定；新增 {len(new_items)} 篇相關顧問研究。"
        state = 'research-updated'
    else:
        text = '官方核心分數與主要研究 context 沒有顯著變化。'
        state = 'stable'
    return {
        'state': state,
        'text': text,
        'score_delta': delta,
        'new_research': len(new_items),
        'new_titles': [x.get('title') for x in new_items[:3]],
    }


def dimension_brief(key, official, mapped, risks):
    cfg = DIMENSIONS[key]
    if not official:
        return f"{cfg['name']} 官方分數暫不可用；顧問研究僅保留為外部 context。"
    score, label = official.get('score'), official.get('label')
    firms = len({x['company'] for x in mapped})
    if key == 'ai_concentration':
        lead = f"AI Concentration {float(score):.0f}/100（{label}）"
        interpretation = '；分數越高代表成長越集中於 AI／電子鏈，不代表景氣更好。'
    else:
        lead = f"{cfg['name']} {float(score):+.0f}/100（{label}）"
        interpretation = '。'
    return f"{lead}{interpretation} 目前映射 {len(mapped)} 篇、{firms} 家顧問公司的全球研究 context，其中 {len(risks)} 篇帶有風險語意；這些研究不進入分數。"


def generate():
    scores = load_json('decision_scores.json', {'current': {}})
    research = load_json('consultant/reports.json', {'reports': []})
    old = load_json('intelligence_layer.json', {})
    reports = research.get('reports') or []
    today = dt.datetime.now(TZ).date()
    dimensions = {}

    for key, cfg in DIMENSIONS.items():
        mapped = map_dimension(reports, cfg, today)
        supportive = [x for x in mapped if x['stance'] == 'supportive']
        contextual = [x for x in mapped if x['stance'] == 'context']
        risk_rows = [x for x in mapped if x['stance'] == 'risk']
        current = (scores.get('current') or {}).get(key)
        official = official_block(current)

        evidence = diverse_top(supportive + contextual, 4)
        risks = diverse_top(risk_rows, 3)
        contradictions = []
        if current and key != 'ai_concentration':
            s = float(current.get('score') or 0)
            if s >= 25:
                contradictions = diverse_top(risk_rows, 2)
            elif s <= -25:
                contradictions = diverse_top(supportive, 2)
        elif current and key == 'ai_concentration' and float(current.get('score') or 0) >= 60:
            # A high concentration reading is challenged only by research explicitly
            # framed around diversification/broadening, not by generic AI risks.
            contradictions = diverse_top([
                x for x in mapped
                if any(w in report_text(next((r for r in reports if r.get('id') == x['id']), {})) for w in ('diversif', 'broad-based', 'broadening'))
            ], 2)

        old_dim = (old.get('dimensions') or {}).get(key)
        dimensions[key] = {
            'name': cfg['name'],
            'question': cfg['question'],
            'official': official,
            'research_count': len(mapped),
            'companies': sorted({x['company'] for x in mapped}),
            'latest_research_date': max((x.get('date') or '' for x in mapped), default=None),
            'evidence': evidence,
            'contradictions': contradictions,
            'risks': risks,
            'what_changed': change_block(old_dim, current, mapped),
            'brief': dimension_brief(key, official, mapped, risks),
            'mapped_report_ids': [x['id'] for x in mapped[:100]],
        }

    ds = scores.get('current') or {}
    def fmt(k, signed=True):
        x = ds.get(k)
        if not x:
            return f"{DIMENSIONS[k]['name']} 暫缺"
        v = float(x['score'])
        return f"{DIMENSIONS[k]['name']} {v:+.0f}" if signed else f"{DIMENSIONS[k]['name']} {v:.0f}"

    all_risks = []
    for key in DIMENSIONS:
        all_risks.extend(dimensions[key]['risks'])
    all_risks = diverse_top(all_risks, 5)
    mapped_ids = {rid for d in dimensions.values() for rid in d['mapped_report_ids']}
    firms = sorted({r.get('company') for r in reports if r.get('id') in mapped_ids and r.get('company') in COMPANIES})
    latest = max((r.get('date') or '' for r in reports), default=None)

    executive = {
        'headline': f"{fmt('growth_persistence')}；{fmt('domestic_demand')}；{fmt('financial_conditions')}；{fmt('ai_concentration', False)}。",
        'interpretation': '官方分數回答台灣景氣與集中度；全球顧問研究只用來補充策略 context、反例與風險，不作為台灣因果證據，也不改變任何 deterministic score。',
        'research_context': f"目前 {len(reports)} 篇顧問研究中，有 {len(mapped_ids)} 篇映射到至少一個決策維度，涵蓋 {len(firms)} 家公司。",
        'key_risks': all_risks,
    }

    out = {
        'version': 1,
        'generated_at': dt.datetime.now(TZ).replace(microsecond=0).isoformat(),
        'contract': 'official-deterministic-scores-plus-consultant-context',
        'score_influence': False,
        'classification': 'deterministic-keyword-and-metadata-context',
        'research_latest_date': latest,
        'executive_brief': executive,
        'dimensions': dimensions,
    }
    save_json('intelligence_layer.json', out)
    return out


if __name__ == '__main__':
    generate()
