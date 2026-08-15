#!/usr/bin/env python3
import source_moea_dataset as d

meta={'distribution':[{'downloadURL':'https:\/\/service.moea.gov.tw\/EE520\/opendata\/sales.csv'},{'downloadURL':'https://legacy.example/x.csv'}]}
urls=d.resource_candidates(meta,d.SALES_DATASET)
assert urls and urls[0]=='https://service.moea.gov.tw/EE520/opendata/sales.csv',urls

# The exact inventory fallback is an official service.moea CSV published by data.gov.
inv=d.resource_candidates({},d.INVENTORY_DATASET)
assert any('service.moea.gov.tw' in u and u.lower().endswith('.csv') for u in inv),inv

# Use canonical source_moea parsing semantics against a representative official CSV shape.
rows=[]
for month in range(1,7):
    rows.append({'統計項目':'銷售量指數','行業代碼':'C','行業別':'製造業','資料期(民國年)':f'115{month:02d}','統計值(指數)':str(100+month),'計量單位':'民國110年=100'})
    rows.append({'統計項目':'銷售量指數','行業代碼':'I2','行業別':'資訊電子工業','資料期(民國年)':f'115{month:02d}','統計值(指數)':str(110+month),'計量單位':'民國110年=100'})
old=d.dataset_rows
d.dataset_rows=lambda dataset_id:(rows,'https://service.moea.gov.tw/mock.csv')
try:
    sales=d.sales_index()
finally:
    d.dataset_rows=old
assert sales['series']['C']['data'][-1]==['2026-06',106.0]
assert sales['series']['I2']['data'][-1]==['2026-06',116.0]
assert sales['unit']=='index_2021_100'
print('MOEA DATASET TEST PASS')
