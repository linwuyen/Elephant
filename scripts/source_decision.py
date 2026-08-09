#!/usr/bin/env python3
from __future__ import annotations
import csv
import re
from common import decode_text, load_json, num, period_key, request_bytes, save_json
from source_moea import decode_resource, month_period, pick

ORDERS_URL='https://service.moea.gov.tw/EE520/opendata/b.csv'
ORDERS_CATALOG='https://data.gov.tw/dataset/6845'
DOMESTIC_URL='https://service.moea.gov.tw/EE520/opendata/ea.csv'
DOMESTIC_CATALOG='https://data.gov.tw/dataset/6842'
LABOR_URL='https://apiservice.mol.gov.tw/OdService/download/A17030000J-000016-wWs'
LABOR_CATALOG='https://data.gov.tw/dataset/13228'
CBC_FIN_CATALOG='https://www.cbc.gov.tw/tw/cp-532-104915-d9972-1.html'
CBC_TABLES={
 'money':'https://www.cbc.gov.tw/public/data/EBOOKXLS/001_EF01_A4L.csv',
 'credit':'https://www.cbc.gov.tw/public/data/EBOOKXLS/003_EF03_A4L.csv',
 'markets':'https://www.cbc.gov.tw/public/data/EBOOKXLS/007_EF07_A4L.csv',
}

def dedup(data):
    return [[p,v] for p,v in sorted(dict(data).items(),key=lambda x:period_key(x[0]))]

def first_value(row, preferred):
    for key in preferred:
        if key in row:
            v=num(row.get(key))
            if v is not None:return v
    for k,v0 in row.items():
        if any(x in str(k) for x in ('統計值','金額','指數')):
            v=num(v0)
            if v is not None:return v
    return None

def parse_long_moea(body,url,kind):
    rows=decode_resource(body,url); grouped={}
    for r in rows:
        rawp=pick(r,'資料期(民國年)','資料期','年月','年月份')
        if not rawp:continue
        try:p=month_period(rawp)
        except Exception:continue
        if kind=='orders':
            value=first_value(r,('統計值(美元)','統計值(金額)','統計值'))
            label=' / '.join(x for x in [str(pick(r,'貨品別') or '').strip(),str(pick(r,'地區別') or '').strip(),str(pick(r,'統計項目','項目') or '').strip()] if x)
        else:
            value=first_value(r,('統計值(金額)','統計值'))
            label=' / '.join(x for x in [str(pick(r,'行業別') or '').strip(),str(pick(r,'統計項目','項目') or '').strip()] if x)
        if value is None or not label:continue
        grouped.setdefault(label,[]).append([p,value])
    return {k:{'name':k,'unit':'million_usd' if kind=='orders' else 'million_ntd','data':dedup(v)} for k,v in grouped.items() if len(v)>=2}

def parse_labor(body):
    rows=decode_resource(body,LABOR_URL); specs={
      'unemployment_rate':('失業率（百分比）','失業率'),
      'avg_monthly_salary':('工業及服務業平均月薪資（元）','工業及服務業平均月薪資'),
      'manufacturing_monthly_salary':('製造業平均月薪資（元）','製造業平均月薪資'),
      'avg_monthly_hours':('工業及服務業平均月工時（小時）','工業及服務業平均月工時'),
      'cpi_yoy':('消費者物價-年增率','消費者物價年增率'),
    }; out={k:[] for k in specs}
    for r in rows:
        rawp=pick(r,'日期（月別）','日期(月別)','日期','資料期')
        if not rawp:continue
        try:p=month_period(rawp)
        except Exception:continue
        for key,aliases in specs.items():
            col=next((c for c in r if any(a in str(c) for a in aliases)),None)
            v=num(r.get(col)) if col else None
            if v is not None:out[key].append([p,v])
    names={'unemployment_rate':'失業率','avg_monthly_salary':'工業及服務業平均月薪資','manufacturing_monthly_salary':'製造業平均月薪資','avg_monthly_hours':'工業及服務業平均月工時','cpi_yoy':'CPI 年增率'}
    units={'unemployment_rate':'percent','avg_monthly_salary':'ntd','manufacturing_monthly_salary':'ntd','avg_monthly_hours':'hours','cpi_yoy':'percent'}
    return {k:{'name':names[k],'unit':units[k],'data':dedup(v)} for k,v in out.items() if v}

_MONTHS={'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12}
def cbc_row_period(row, roc_year):
    first=str(row[0] or '').strip()
    # CBC sometimes appends footnote/revision marks to the new-year first row.
    both=re.search(r'(?<!\d)(\d{3})\D{1,8}(\d{1,2})(?!\d)',first)
    if both:
        ry,mo=int(both.group(1)),int(both.group(2))
        if 100<=ry<200 and 1<=mo<=12:return f'{ry+1911:04d}-{mo:02d}',ry
    one=re.fullmatch(r'(\d{1,2})',first)
    if one and roc_year is not None:
        mo=int(one.group(1))
        if 1<=mo<=12:return f'{roc_year+1911:04d}-{mo:02d}',roc_year
    # English month column provides an independent year anchor, e.g. Jan. 2026.
    tail=' '.join(str(x or '') for x in row[-5:]).lower()
    em=re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\.?\s*(20\d{2})',tail)
    if em:
        mo=_MONTHS[em.group(1)]; gy=int(em.group(2)); return f'{gy:04d}-{mo:02d}',gy-1911
    return None,roc_year

def cbc_month_rows(body, columns):
    out={k:[] for k in columns}; roc_year=None
    for row in csv.reader(decode_text(body).splitlines()):
        if not row:continue
        period,roc_year=cbc_row_period(row,roc_year)
        if not period:continue
        for key,idx in columns.items():
            if idx>=len(row):continue
            v=num(row[idx])
            if v is not None:out[key].append([period,v])
    return {k:dedup(v) for k,v in out.items() if len(dedup(v))>=12}

def parse_cbc_financial(bodies):
    money=cbc_month_rows(bodies['money'],{'m1b_yoy':16,'m2_yoy':20})
    credit=cbc_month_rows(bodies['credit'],{'credit_yoy':20})
    markets=cbc_month_rows(bodies['markets'],{'interbank_rate':7,'stock_index':10,'exchange_rate':11})
    raw={**money,**credit,**markets}
    names={
      'm1b_yoy':'M1B 年增率','m2_yoy':'M2 年增率','credit_yoy':'金融機構放款與投資年增率',
      'interbank_rate':'金融業隔夜拆款加權平均利率','stock_index':'股價指數','exchange_rate':'銀行間美元收盤匯率',
    }
    units={'m1b_yoy':'percent','m2_yoy':'percent','credit_yoy':'percent','interbank_rate':'percent','stock_index':'index','exchange_rate':'ntd_per_usd'}
    out={k:{'name':names[k],'unit':units[k],'data':v} for k,v in raw.items()}
    for required in ('m1b_yoy','m2_yoy','credit_yoy','interbank_rate'):
        if required not in out:raise ValueError('CBC monthly table missing '+required)
    for key in ('m1b_yoy','m2_yoy','credit_yoy'):
        if not all(-30<float(v)<50 for _,v in out[key]['data'][-24:]):raise ValueError('CBC implausible '+key)
    if not all(0<float(v)<20 for _,v in out['interbank_rate']['data'][-24:]):raise ValueError('CBC implausible interbank_rate')
    return out

def update(_offline=None):
    old=load_json('decision_inputs.json',{'series':{}}); series=dict(old.get('series',{})); warnings=[]; rows=0
    for name,url,catalog,kind in [('orders',ORDERS_URL,ORDERS_CATALOG,'orders'),('domestic',DOMESTIC_URL,DOMESTIC_CATALOG,'domestic')]:
        try:
            body,_=request_bytes(url,75,3); parsed=parse_long_moea(body,url,kind); rows+=sum(len(x['data']) for x in parsed.values())
            if not parsed:raise ValueError(f'{name} parse empty')
            prefix='orders.' if kind=='orders' else 'domestic.'
            for k,v in parsed.items():series[prefix+k]=v
        except Exception as e:warnings.append(f'{name}: {type(e).__name__}: {e}')
    try:
        body,_=request_bytes(LABOR_URL,60,3); parsed=parse_labor(body); rows+=sum(len(x['data']) for x in parsed.values())
        if not parsed:raise ValueError('labor parse empty')
        for k,v in parsed.items():series['labor.'+k]=v
    except Exception as e:warnings.append(f'labor: {type(e).__name__}: {e}')
    try:
        bodies={}
        for key,url in CBC_TABLES.items():bodies[key]=request_bytes(url,60,3)[0]
        parsed=parse_cbc_financial(bodies); rows+=sum(len(x['data']) for x in parsed.values())
        for k,v in parsed.items():series['cbc.'+k]=v
    except Exception as e:warnings.append(f'cbc_financial: {type(e).__name__}: {e}')
    latest=max((s['data'][-1][0] for s in series.values() if s.get('data')),key=period_key,default=None)
    obj={'source':'Taiwan official decision inputs','latest_period':latest,'series':series,'catalogs':{'orders':ORDERS_CATALOG,'domestic':DOMESTIC_CATALOG,'labor':LABOR_CATALOG,'cbc_financial':CBC_FIN_CATALOG},'warnings':warnings}
    save_json('decision_inputs.json',obj)
    if not series:raise ValueError('no decision input series available')
    return {'latest_period':latest,'rows':rows,'message':'external orders, domestic-demand and financial inputs refreshed'+(('; warnings: '+'; '.join(warnings)) if warnings else ''),'warnings':warnings}
