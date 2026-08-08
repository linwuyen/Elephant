#!/usr/bin/env python3
import datetime as dt
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
TZ = dt.timezone(dt.timedelta(hours=8))


def load(name):
    return json.loads((DATA / name).read_text(encoding='utf-8'))


def save(name, obj):
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')


def latest(series):
    data = (series or {}).get('data', [])
    return data[-1] if data else [None, None]


def prior_year_value(data, period):
    if not period or '-' not in str(period):
        return None
    try:
        y, m = str(period).split('-', 1)
        target = f'{int(y)-1:04d}-{m}'
    except Exception:
        return None
    return dict(data).get(target)


def pct_change(a, b):
    if a is None or b in (None, 0):
        return None
    return (float(a) / float(b) - 1.0) * 100.0


def round2(v):
    return None if v is None or not math.isfinite(v) else round(v, 2)


def metric(series):
    p, v = latest(series)
    return {'period': p, 'value': v, 'unit': (series or {}).get('unit'), 'name': (series or {}).get('name')}


def industry_yoy(dataset):
    out = []
    for key, s in (dataset or {}).get('series', {}).items():
        data = s.get('data', [])
        if not data:
            continue
        p, v = data[-1]
        py = prior_year_value(data, p)
        yoy = pct_change(v, py)
        if yoy is None or not math.isfinite(yoy) or abs(yoy) > 300:
            continue
        out.append({'id': key, 'name': s.get('name', key), 'period': p, 'value': v, 'yoy': round2(yoy)})
    return out


def classify_growth(v):
    if v is None:
        return '資料不足'
    if v >= 5:
        return '高成長'
    if v >= 3:
        return '穩健擴張'
    if v >= 1:
        return '溫和成長'
    if v >= 0:
        return '低成長'
    return '衰退'


def classify_inflation(v):
    if v is None:
        return '物價資料不足'
    if v < 1:
        return '低通膨'
    if v <= 2.5:
        return '通膨溫和'
    if v <= 4:
        return '通膨偏高'
    return '高通膨'


def classify_monthly(yoy):
    if yoy is None:
        return '動能資料不足'
    if yoy >= 10:
        return '強勁擴張'
    if yoy >= 3:
        return '擴張'
    if yoy >= 0:
        return '微幅成長'
    if yoy > -5:
        return '降溫'
    return '明顯收縮'


def generate():
    macro = load('macro.json')
    pop = load('population.json')
    industry = load('industry.json')
    status = load('status.json')

    ms = macro.get('series', {})
    ps = pop.get('national', {})
    growth = metric(ms.get('dgbas.gdp.growth_rate'))
    cpi = metric(ms.get('dgbas.cpi.yoy'))
    nominal = metric(ms.get('dgbas.gdp.nominal.production'))

    population = metric(ps.get('ris.pop.year_end_total'))
    pop_data = ps.get('ris.pop.year_end_total', {}).get('data', [])
    prev_pop = pop_data[-2][1] if len(pop_data) >= 2 else None
    pop_change = pct_change(population['value'], prev_pop)
    oldshare = metric(ps.get('ris.pop.share_65_plus'))
    births = metric(ps.get('ris.pop.births'))
    deaths = metric(ps.get('ris.pop.deaths'))
    natural = None
    if births['value'] is not None and deaths['value'] is not None:
        natural = births['value'] - deaths['value']

    datasets = industry.get('datasets', {})
    prod = industry_yoy(datasets.get('moea.industry.production', {}))
    sales = industry_yoy(datasets.get('moea.manufacturing.sales_index_current', {}))
    prod_map = {x['id']: x for x in prod}
    sales_map = {x['id']: x for x in sales}

    mfg = prod_map.get('C') or prod_map.get('Z')
    info = prod_map.get('I2')
    electronics = prod_map.get('26')
    ic = prod_map.get('2611')
    optics = prod_map.get('27')
    current_sales = sales_map.get('C')

    latest_prod_period = max((x['period'] for x in prod), default=None)
    comparable = [x for x in prod if x['period'] == latest_prod_period]
    positive = [x for x in comparable if x['yoy'] > 0]
    breadth = (len(positive) / len(comparable) * 100.0) if comparable else None
    ranked = sorted(comparable, key=lambda x: x['yoy'], reverse=True)
    top = ranked[:5]
    weak = list(reversed(ranked[-5:])) if ranked else []

    g = growth['value']
    inf = cpi['value']
    annual_regime = f"{classify_growth(g)}、{classify_inflation(inf)}"
    monthly_regime = classify_monthly(mfg['yoy'] if mfg else None)

    concentration = '產業擴張廣度尚不足以判斷'
    concentration_level = 'neutral'
    if breadth is not None:
        if breadth >= 70:
            concentration = f'最新月度有 {breadth:.0f}% 的可比產業年增率為正，擴張相對廣泛。'
            concentration_level = 'positive'
        elif breadth <= 40:
            concentration = f'最新月度僅 {breadth:.0f}% 的可比產業年增率為正，景氣動能偏集中。'
            concentration_level = 'warning'
        else:
            concentration = f'最新月度有 {breadth:.0f}% 的可比產業年增率為正，產業表現分化。'
    if info and mfg and info['yoy'] - mfg['yoy'] >= 5:
        concentration += f" 資訊電子年增 {info['yoy']:.1f}%，領先製造業約 {info['yoy']-mfg['yoy']:.1f} 個百分點。"
        concentration_level = 'warning' if breadth is not None and breadth < 60 else concentration_level

    takeaways = []
    if g is not None and inf is not None:
        takeaways.append({
            'level': 'positive' if g >= 3 and inf <= 2.5 else ('warning' if g < 1 or inf > 4 else 'neutral'),
            'title': f'年度總體：{annual_regime}',
            'text': f"{growth['period']} 經濟成長率 {g:.2f}%，CPI 年增率 {inf:.2f}%。年度景氣仍偏強，但月度產業資料期間較新，判讀短期轉折應以產業序列為主。",
            'evidence': [f"GDP growth {growth['period']}: {g:.2f}%", f"CPI YoY {cpi['period']}: {inf:.2f}%"]
        })
    if mfg:
        refs = [x for x in [mfg, info, electronics, ic, optics] if x]
        text = f"{mfg['period']} 製造業生產指數較去年同期 {mfg['yoy']:+.1f}%，屬於{monthly_regime}。"
        if info:
            text += f" 資訊電子 {info['yoy']:+.1f}%。"
        if current_sales:
            text += f" 現行製造業銷售指數 {current_sales['period']} 年增 {current_sales['yoy']:+.1f}%。"
        takeaways.append({
            'level': 'positive' if mfg['yoy'] >= 3 else ('warning' if mfg['yoy'] < 0 else 'neutral'),
            'title': f'最新產業：{monthly_regime}',
            'text': text,
            'evidence': [f"{x['name']} {x['period']}: YoY {x['yoy']:+.1f}%" for x in refs[:4]]
        })
    takeaways.append({
        'level': concentration_level,
        'title': '產業廣度與集中度',
        'text': concentration,
        'evidence': [f"positive breadth: {breadth:.0f}%" if breadth is not None else 'breadth unavailable']
    })
    if population['value'] is not None:
        nat_text = f"自然增加 {natural:,.0f} 人" if natural is not None else '自然增減資料不足'
        text = f"{population['period']} 年底人口 {population['value']:,.0f} 人，較前一年 {pop_change:+.2f}%；65 歲以上占 {oldshare['value']:.2f}%。{nat_text}。"
        takeaways.append({
            'level': 'warning' if (pop_change is not None and pop_change < 0) or (oldshare['value'] or 0) >= 20 else 'neutral',
            'title': '人口：總量下降與高齡化持續',
            'text': text,
            'evidence': [f"Population {population['period']}: {population['value']:,.0f}", f"65+ share: {oldshare['value']:.2f}%", f"Births: {births['value']:,.0f}; deaths: {deaths['value']:,.0f}"]
        })

    warnings = []
    for sid, s in status.get('sources', {}).items():
        if s.get('status') != 'ok':
            warnings.append(f"{sid}: {s.get('status')} — {s.get('message', '')}")
        for w in s.get('warnings', []) or []:
            warnings.append(f'{sid}: {w}')

    headline_parts = [annual_regime]
    if mfg:
        headline_parts.append(f"製造業月度{monthly_regime}")
    if pop_change is not None and pop_change < 0:
        headline_parts.append('人口續減')
    headline = '；'.join(headline_parts)

    out = {
        'version': 1,
        'generated_at': dt.datetime.now(TZ).replace(microsecond=0).isoformat(),
        'data_last_check_at': status.get('last_check_at'),
        'headline': headline,
        'stance': 'Elephant 目前判讀：' + headline + '。',
        'takeaways': takeaways[:5],
        'macro': {'growth': growth, 'cpi_yoy': cpi, 'nominal_gdp': nominal, 'regime': annual_regime},
        'industry': {
            'latest_period': latest_prod_period,
            'manufacturing': mfg,
            'information_electronics': info,
            'electronics_components': electronics,
            'integrated_circuits': ic,
            'computer_optics': optics,
            'manufacturing_sales': current_sales,
            'positive_breadth_pct': round2(breadth),
            'top_yoy': top,
            'weak_yoy': weak
        },
        'population': {
            'period': population['period'], 'population': population['value'], 'yoy_pct': round2(pop_change),
            'share_65_plus': oldshare['value'], 'births': births['value'], 'deaths': deaths['value'], 'natural_increase': natural
        },
        'warnings': warnings,
        'methodology': '規則式摘要：只使用 Elephant 已驗證資料，月度產業以同月年增率比較；不同基期序列不硬接；摘要不使用外部生成式 AI。'
    }
    save('summary.json', out)
    return out


if __name__ == '__main__':
    print(json.dumps(generate(), ensure_ascii=False, indent=2))
