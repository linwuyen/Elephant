#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import zipfile

import source_ndc as ndc


def csv_bytes(headers, rows):
    buf=io.StringIO()
    w=csv.DictWriter(buf,fieldnames=headers)
    w.writeheader();w.writerows(rows)
    return buf.getvalue().encode('utf-8-sig')


def make_zip(entries):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as zf:
        for name,body in entries.items():
            zf.writestr(name,body)
    return out.getvalue()


# A longer composite-only file must NOT outrank a shorter field-rich business-
# cycle table. This reproduces the production failure that silently dropped the
# official 股價指數 even though dataset 6099 publishes it.
sparse_headers=[
    'Date','領先指標綜合指數','領先指標不含趨勢指數',
    '同時指標綜合指數','同時指標不含趨勢指數','景氣對策信號綜合分數'
]
sparse=[]
for i in range(120):
    y=2010+i//12;m=i%12+1
    sparse.append({
        'Date':f'{y:04d}-{m:02d}','領先指標綜合指數':100+i/10,
        '領先指標不含趨勢指數':99+i/20,'同時指標綜合指數':101+i/10,
        '同時指標不含趨勢指數':100+i/20,'景氣對策信號綜合分數':25,
    })

full_headers=[
    'Date','工業生產指數','製造業銷售量指數','海關出口值',
    '領先指標綜合指數','領先指標不含趨勢指數',
    '同時指標綜合指數','同時指標不含趨勢指數',
    '落後指標綜合指數','落後指標不含趨勢指數',
    '景氣對策信號綜合分數','貨幣總計數M1B','股價指數(Index1966=100)',
    '全體金融機構放款與投資','製造業存貨價值','外銷訂單動向指數'
]
full=[]
for i in range(36):
    y=2023+i//12;m=i%12+1
    full.append({
        'Date':f'{y:04d}-{m:02d}',
        '工業生產指數':100+i,'製造業銷售量指數':95+i,
        '海關出口值':500+i*5,'領先指標綜合指數':100+i/10,
        '領先指標不含趨勢指數':99+i/20,'同時指標綜合指數':101+i/10,
        '同時指標不含趨勢指數':100+i/20,'落後指標綜合指數':98+i/20,
        '落後指標不含趨勢指數':97+i/20,'景氣對策信號綜合分數':30,
        '貨幣總計數M1B':1000+i*2,'股價指數(Index1966=100)':15000+i*100,
        '全體金融機構放款與投資':2000+i*3,'製造業存貨價值':500+i,
        '外銷訂單動向指數':55+i/10,
    })

body=make_zip({
    '01_composite_long.csv':csv_bytes(sparse_headers,sparse),
    '02_business_cycle_full.csv':csv_bytes(full_headers,full),
})
selected=ndc.rows_from_zip(body)
assert len(selected)==36, 'field-rich candidate must beat longer sparse candidate'
assert ndc.candidate_field_coverage(selected[0].keys())>ndc.candidate_field_coverage(sparse_headers)
series,signals=ndc.parse_signal_rows(selected)
assert 'stock_index' in series
assert len(series['stock_index']['data'])==36
assert series['stock_index']['data'][0]==('2023-01',15000.0) or series['stock_index']['data'][0]==['2023-01',15000.0]
assert 'industrial_production' in series
assert 'customs_exports' in series
assert 'm1b' in series

# A misleading very-long CSV without the required leading/coincident contract is
# ineligible regardless of size.
noise_headers=['Date','股價指數','其他欄位']
noise=[{'Date':f'2020-{i%12+1:02d}','股價指數':100+i,'其他欄位':1} for i in range(300)]
body2=make_zip({
    'noise.csv':csv_bytes(noise_headers,noise),
    'full.csv':csv_bytes(full_headers,full),
})
selected2=ndc.rows_from_zip(body2)
series2,_=ndc.parse_signal_rows(selected2)
assert 'stock_index' in series2
assert len(series2['stock_index']['data'])==36

print('NDC ZIP SELECTION TEST PASS')
