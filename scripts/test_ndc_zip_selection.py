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


def monthly(n,start_y=2023,start_m=1):
    out=[];y=start_y;m=start_m
    for i in range(n):
        out.append((i,f'{y:04d}-{m:02d}'))
        m+=1
        if m==13:y+=1;m=1
    return out


# Dataset delivery is allowed to split the published semantic fields across
# separate CSV files. The parser must reconstruct one logical monthly table.
composite_headers=[
    'Date','領先指標綜合指數','領先指標不含趨勢指數',
    '同時指標綜合指數','同時指標不含趨勢指數','景氣對策信號綜合分數','景氣對策信號'
]
composite=[]
for i,p in monthly(48,2022,1):
    composite.append({
        'Date':p,'領先指標綜合指數':100+i/10,'領先指標不含趨勢指數':99+i/20,
        '同時指標綜合指數':101+i/10,'同時指標不含趨勢指數':100+i/20,
        '景氣對策信號綜合分數':25+i%5,'景氣對策信號':'綠燈',
    })

macro_headers=['Date','工業生產指數(Index2021=100)','海關出口值(十億元)','貨幣總計數M1B(百萬元)']
macro=[]
for i,p in monthly(36,2023,1):
    macro.append({'Date':p,'工業生產指數(Index2021=100)':100+i,'海關出口值(十億元)':500+i*5,'貨幣總計數M1B(百萬元)':1000+i*2})

stock_headers=['Date','股價指數(Index1966=100)']
stock=[]
for i,p in monthly(36,2023,1):
    stock.append({'Date':p,'股價指數(Index1966=100)':15000+i*100})

credit_headers=['資料期','全體金融機構放款與投資(10億元)','製造業存貨價值(千元)','外銷訂單動向指數(以家數計)']
credit=[]
for i,p in monthly(36,2023,1):
    credit.append({'資料期':p,'全體金融機構放款與投資(10億元)':2000+i*3,'製造業存貨價值(千元)':500+i,'外銷訂單動向指數(以家數計)':55+i/10})

# Unrelated CSVs, including a huge non-semantic file, must not influence output.
noise_headers=['Date','其他欄位']
noise=[{'Date':p,'其他欄位':i} for i,p in monthly(240,2000,1)]

body=make_zip({
    '01_composite.csv':csv_bytes(composite_headers,composite),
    '02_macro_components.csv':csv_bytes(macro_headers,macro),
    '03_market.csv':csv_bytes(stock_headers,stock),
    '04_credit_inventory.csv':csv_bytes(credit_headers,credit),
    '99_noise.csv':csv_bytes(noise_headers,noise),
})
merged=ndc.rows_from_zip(body)
series,signals=ndc.parse_signal_rows(merged)

assert 'stock_index' in series
assert len(series['stock_index']['data'])==36
assert series['stock_index']['data'][0] in (('2023-01',15000.0),['2023-01',15000.0])
assert 'industrial_production' in series
assert 'customs_exports' in series
assert 'm1b' in series
assert 'financial_loans_investments' in series
assert 'manufacturing_inventory' in series
assert 'export_order_diffusion' in series
assert 'leading_no_trend' in series and 'coincident_no_trend' in series
assert signals
assert len(merged)==48, 'month union should follow semantic members, not noise rows'

# Richer/wide and narrow component files may overlap the same field. The richer
# file is merged first and duplicate values from a narrow file must not overwrite it.
wide_headers=['Date','領先指標不含趨勢指數','同時指標不含趨勢指數','股價指數(Index1966=100)']
wide=[{'Date':'2026-01','領先指標不含趨勢指數':101,'同時指標不含趨勢指數':102,'股價指數(Index1966=100)':20000}]
narrow=[{'Date':'2026-01','股價指數(Index1966=100)':99999}]
body2=make_zip({'wide.csv':csv_bytes(wide_headers,wide),'stock.csv':csv_bytes(stock_headers,narrow)})
merged2=ndc.rows_from_zip(body2)
series2,_=ndc.parse_signal_rows(merged2)
assert series2['stock_index']['data'][0] in (('2026-01',20000.0),['2026-01',20000.0])

# If the ZIP has no known semantic fields, fail closed.
body3=make_zip({'noise.csv':csv_bytes(noise_headers,noise)})
try:
    ndc.rows_from_zip(body3)
except ValueError as exc:
    assert 'no parseable semantic' in str(exc)
else:
    raise AssertionError('NDC ZIP without semantic fields must fail closed')

print('NDC ZIP SEMANTIC MERGE TEST PASS')
