#!/usr/bin/env python3
import build_decision_scores as bds
import source_inventory as si
import source_supplements as ss


def monthly_rows(header, row_fn, months=30):
    lines = [header]
    y, m = 113, 1
    for i in range(months):
        lines.append(row_fn(y, m, i))
        m += 1
        if m == 13:
            y += 1
            m = 1
    return ('\n'.join(lines) + '\n').encode('utf-8-sig')


def roc_months(months=30):
    out = []
    y, m = 113, 1
    for _ in range(months):
        out.append((y, m))
        m += 1
        if m == 13:
            y += 1
            m = 1
    return out


# Canonical long MOEA open-data layout.
inventory = monthly_rows(
    '資料期(民國年),行業代碼,行業別,統計項目,統計值(指數)',
    lambda y, m, i: f'{y}{m:02d},C,製造業,存貨量指數,{100 + i * .5}'
)
parsed = ss.parse_inventory_index(inventory)
series = parsed['inventory.manufacturing_index']
assert len(series['data']) == 30
assert series['data'][0][0] == '2024-01'
assert series['data'][-1][0] == '2026-06'
assert series['layout'] == 'long'

# Defensive wide export: date per row, industries in columns.
wide_inventory = monthly_rows(
    '資料期(民國年),製造業,金屬機電工業,資訊電子工業,化學工業,民生工業',
    lambda y, m, i: f'{y}{m:02d},{101 + i * .4},{98 + i * .3},{110 + i * .8},{95 + i * .2},{99 + i * .1}'
)
wide = ss.parse_inventory_index(wide_inventory)['inventory.manufacturing_index']
assert len(wide['data']) == 30
assert wide['layout'] == 'wide'
assert wide['selection'] == '製造業'

# Defensive transposed export: industry per row, months in columns.
months = roc_months()
transposed_header = '行業別,' + ','.join(f'{y}年{m}月' for y, m in months)
transposed_values = '製造業,' + ','.join(str(100 + i * .25) for i in range(len(months)))
transposed = (transposed_header + '\n' + transposed_values + '\n').encode('utf-8-sig')
trans = ss.parse_inventory_index(transposed)['inventory.manufacturing_index']
assert len(trans['data']) == 30
assert trans['layout'] == 'transposed'
assert trans['data'][-1][0] == '2026-06'

# Current MOEA statistics page contract: the first published numeric series after
# each month is the explicit 製造業 total. Partial-year rows such as 1-5月 must
# never be mistaken for monthly observations.
live_rows = ['<table>', '<tr><th></th><th></th><th>製造業</th><th>金屬機電工業</th></tr>']
for i in range(13):
    year = 114 if i < 8 else 115
    month = i + 5 if i < 8 else i - 7
    if i in (0, 8):
        live_rows.append(f'<tr><td>{year}年</td><td>{"" if i == 0 else "1-5月"}</td><td>999.0</td><td>888.0</td></tr>')
    live_rows.append(
        f'<tr><td></td><td>{month}月</td><td>{120.0 + i:.2f}</td><td>{100.0 + i:.2f}</td></tr>'
    )
live_rows.extend(['</table>', '<div>製造業存貨指數－按四大行業及中分類分 基期：110年=100</div>'])
live_body = ''.join(live_rows).encode('utf-8')
live = si.parse_live_inventory_page(live_body)
assert len(live['data']) == 13
assert live['data'][0] == ['2025-05', 120.0]
assert live['data'][-1] == ['2026-05', 132.0]
assert live['layout'] == 'official_live_table'
assert '製造業 total' in live['selection']

# Score-consumption contract: once the canonical official manufacturing total
# exists, a longer legacy inventory series must never outrank it.  This is the
# exact production regression that previously left Growth Confidence at 85%.
canonical_inventory = {
    'name': '製造業 / 存貨指數',
    'data': [['2025-05', 100.0], ['2026-05', 105.0]],
}
legacy_inventory = {
    'name': '製造業 / 存貨價值（歷史候選）',
    'data': [[f'{2020 + i // 12:04d}-{i % 12 + 1:02d}', 80.0 + i] for i in range(60)],
}
selector_inputs = {
    'inventory.manufacturing_index': canonical_inventory,
    'inventory.legacy_value': legacy_inventory,
}
assert bds.find_inventory(selector_inputs) is canonical_inventory

score_inputs = {
    'series': {
        'orders.total': {
            'name': '外銷訂單總額',
            'data': [['2025-06', 100.0], ['2026-06', 120.0]],
        },
        'customs.exports_total': {
            'name': '出口總值',
            'data': [['2025-06', 100.0], ['2026-06', 115.0]],
        },
        **selector_inputs,
    }
}
prod = {'data': [['2025-06', 100.0], ['2026-06', 110.0]]}
sales = {'data': [['2025-05', 100.0], ['2026-05', 108.0]]}
growth = bds.growth_score('2026-06', prod, sales, {}, score_inputs)
assert growth is not None
assert growth['confidence'] == 100
assert {x['key'] for x in growth['components']} == {
    'orders', 'exports', 'production', 'sales', 'inventory_balance'
}
assert next(x for x in growth['components'] if x['key'] == 'inventory_balance')['period'] == '2026-05'

orders = monthly_rows(
    '資料期(民國年),貨品別,統計項目,統計值(美元)',
    lambda y, m, i: f'{y}{m:02d},電子產品,外銷訂單金額,{1000 + i * 25}'
)
family = ss.parse_order_family(
    orders,
    ss.ELECTRONIC_ORDERS_URL,
    '電子產品',
    'orders_supplement.electronic',
    ss.ELECTRONIC_ORDERS_CATALOG,
)
assert family
key = next(iter(family))
assert key.startswith('orders_supplement.electronic.')
assert family[key]['level_comparability'] == 'not_assumed_across_resources'

# DGBAS fallback preserves the exact monthly total-salary and industry/services
# employee-count semantics; it does not substitute unemployment or another proxy.
news = []
for i, (y, m) in enumerate(months):
    if i == len(months) - 1:
        people, salary = '858萬4千', '60,267'
    else:
        people, salary = f'{850 + i // 12}萬{i % 10}千', f'{52000 + i * 173:,}'
    average_word = '平均數' if i % 2 else '平均'
    news.append(
        f'<tr><td>{y}年{m}月底工業及服務業受僱員工人數為{people}人，'
        f'本月總薪資{average_word}為{salary}元</td></tr>'
    )
news_body = ('<html><body><table>' + ''.join(news) + '</table></body></html>').encode('utf-8')
dgbas = ss.parse_dgbas_news_pages([news_body])
assert len(dgbas['dgbas.total_monthly_salary']['data']) == 30
assert len(dgbas['dgbas.employment_total']['data']) == 30
assert dgbas['dgbas.total_monthly_salary']['data'][-1] == ['2026-06', 60267.0]
assert dgbas['dgbas.employment_total']['data'][-1] == ['2026-06', 8584000.0]
assert 'official salary/productivity' in dgbas['dgbas.employment_total']['selection']
assert ss._parse_people('850萬') == 8500000.0
assert ss._parse_people('858萬4千') == 8584000.0

print('SOURCE SUPPLEMENTS TEST PASS')
