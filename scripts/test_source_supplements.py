#!/usr/bin/env python3
import source_supplements as ss


def monthly_rows(header, row_fn, months=30):
    lines=[header]
    y,m=113,1
    for i in range(months):
        lines.append(row_fn(y,m,i))
        m+=1
        if m==13: y+=1; m=1
    return ('\n'.join(lines)+'\n').encode('utf-8-sig')

inventory=monthly_rows(
    '資料期(民國年),行業代碼,行業別,統計項目,統計值(指數)',
    lambda y,m,i:f'{y}{m:02d},C,製造業,存貨量指數,{100+i*.5}'
)
parsed=ss.parse_inventory_index(inventory)
series=parsed['inventory.manufacturing_index']
assert len(series['data']) == 30
assert series['data'][0][0] == '2024-01'
assert series['data'][-1][0] == '2026-06'

orders=monthly_rows(
    '資料期(民國年),貨品別,統計項目,統計值(美元)',
    lambda y,m,i:f'{y}{m:02d},電子產品,外銷訂單金額,{1000+i*25}'
)
family=ss.parse_order_family(orders, ss.ELECTRONIC_ORDERS_URL, '電子產品', 'orders_supplement.electronic', ss.ELECTRONIC_ORDERS_CATALOG)
assert family
key=next(iter(family))
assert key.startswith('orders_supplement.electronic.')
assert family[key]['level_comparability'] == 'not_assumed_across_resources'
print('SOURCE SUPPLEMENTS TEST PASS')
