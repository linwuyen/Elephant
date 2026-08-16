#!/usr/bin/env python3
import source_moea_dataset as d

meta={'distribution':[{'downloadURL':'https://service.moea.gov.tw/EE520/opendata/sales.csv'},{'downloadURL':'https://legacy.example/x.csv'}]}
urls=d.resource_candidates(meta,d.SALES_DATASET)
assert urls and urls[0]=='https://service.moea.gov.tw/EE520/opendata/sales.csv',urls

# The inventory fallback is an official service.moea CSV published by data.gov.
inv=d.resource_candidates({},d.INVENTORY_DATASET)
assert any('service.moea.gov.tw' in u and u.lower().endswith('.csv') for u in inv),inv

# Datasets 95141/109753 are explicitly scoped to four major industries.
# Validate the publisher-provided I1-I4 series and never fabricate a C total.
rows=[]
names={
    'I1':'金屬機電工業',
    'I2':'資訊電子工業',
    'I3':'化學工業',
    'I4':'民生工業',
}
for code_offset,(code,name) in enumerate(names.items(),start=1):
    for month in range(1,7):
        rows.append({
            '統計項目':'銷售量指數',
            '行業代碼':code,
            '行業別':name,
            '資料期(民國年)':f'115{month:02d}',
            '統計值(指數)':str(100+10*code_offset+month),
            '計量單位':'民國110年=100',
        })
old=d.dataset_rows
d.dataset_rows=lambda dataset_id:(rows,'https://service.moea.gov.tw/mock.csv')
try:
    sales=d.sales_index()
finally:
    d.dataset_rows=old
assert set(d.MAJOR_INDUSTRIES) <= set(sales['series'])
assert 'C' not in sales['series']
assert sales['series']['I1']['data'][-1]==['2026-06',116.0]
assert sales['series']['I4']['data'][-1]==['2026-06',146.0]
assert sales['unit']=='index_2021_100'
assert sales['scope']=='official four-major-industry series; no synthetic manufacturing total'

# Missing one publisher series must fail closed instead of silently passing or synthesizing it.
missing_i4=[r for r in rows if r['行業代碼']!='I4']
d.dataset_rows=lambda dataset_id:(missing_i4,'https://service.moea.gov.tw/mock.csv')
try:
    try:
        d.sales_index()
        raise AssertionError('missing I4 should fail closed')
    except ValueError as exc:
        assert 'I4' in str(exc),exc
finally:
    d.dataset_rows=old

print('MOEA DATASET TEST PASS')
