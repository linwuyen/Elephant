#!/usr/bin/env python3
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
