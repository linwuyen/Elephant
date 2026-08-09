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
CBC_FIN_URL='https://www.cbc.gov.tw/public/data/EBOOKXLS/001_EF01_A4L.csv'
CBC_FIN_CATALOG='https://www.cbc.gov.tw/tw/cp-532-104915-d9972-1.html'

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

def cbc_period(cell):
    s=str(cell or '').strip().replace('年','/').replace('月','').replace('.','/').replace('-','/')
    m=re.search(r'(?<!\d)(20\d{2})\s*/\s*(\d{1,2})(?!\d)',s)
    if m:
        y,mo=map(int,m.groups())
        if 1<=mo<=12:return f'{y:04d}-{mo:02d}'
    m=re.search(r'(?<!\d)(\d{2,3})\s*/\s*(\d{1,2})(?!\d)',s)
    if m:
        y,mo=map(int,m.groups())
        if y<1911 and 1<=mo<=12:return f'{y+1911:04d}-{mo:02d}'
    return None

def cbc_metric(label):
    s=re.sub(r'\s+','',str(label or '')).upper()
    yoy='年增' in s or '年成長' in s or 'YOY' in s
    if 'M1B' in s:return 'm1b_yoy' if yoy else 'm1b'
    if re.search(r'(^|[^A-Z0-9])M2([^A-Z0-9]|$)',s):return 'm2_yoy' if yoy else 'm2'
    if '放款與投資' in s:return 'credit_yoy' if yoy else 'credit'
    if '五大銀行' in s and '放款' in s and '利率' in s:return 'loan_rate'
    return None

def parse_cbc_financial(body):
    matrix=[[str(c or '').strip() for c in row] for row in csv.reader(decode_text(body).splitlines())]
    collected={}
    # Orientation A: periods appear across columns; metric names appear down rows.
    for header in matrix:
        pcols={i:cbc_period(c) for i,c in enumerate(header)}
        pcols={i:p for i,p in pcols.items() if p}
        if len(pcols)<3:continue
        for row in matrix:
            label=' '.join(row[:min(pcols)] if pcols else row[:4])
            key=cbc_metric(label)
            if not key:continue
            for i,p in pcols.items():
                if i<len(row):
                    v=num(row[i])
                    if v is not None:collected.setdefault(key,[]).append([p,v])
    # Orientation B: periods appear down rows; metric names appear across header columns.
    for header in matrix:
        mcols={i:cbc_metric(c) for i,c in enumerate(header)}
        mcols={i:k for i,k in mcols.items() if k}
        if not mcols:continue
        for row in matrix:
            p=next((cbc_period(c) for c in row if cbc_period(c)),None)
            if not p:continue
            for i,key in mcols.items():
                if i<len(row):
                    v=num(row[i])
                    if v is not None:collected.setdefault(key,[]).append([p,v])
    names={'m1b':'貨幣總計數 M1B','m1b_yoy':'M1B 年增率','m2':'貨幣總計數 M2','m2_yoy':'M2 年增率','credit':'金融機構放款與投資','credit_yoy':'金融機構放款與投資年增率','loan_rate':'五大銀行新承做放款平均利率'}
    units={'m1b':'value','m1b_yoy':'percent','m2':'value','m2_yoy':'percent','credit':'value','credit_yoy':'percent','loan_rate':'percent'}
    out={k:{'name':names[k],'unit':units[k],'data':dedup(v)} for k,v in collected.items() if len(dedup(v))>=6}
    if not any(k in out for k in ('m1b','m1b_yoy','m2','m2_yoy','credit','credit_yoy')):
        raise ValueError('CBC important-financial-indicators CSV parse returned no core series')
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
        body,_=request_bytes(CBC_FIN_URL,60,3); parsed=parse_cbc_financial(body); rows+=sum(len(x['data']) for x in parsed.values())
        for k,v in parsed.items():series['cbc.'+k]=v
    except Exception as e:warnings.append(f'cbc_financial: {type(e).__name__}: {e}')
    latest=max((s['data'][-1][0] for s in series.values() if s.get('data')),key=period_key,default=None)
    obj={'source':'Taiwan official decision inputs','latest_period':latest,'series':series,'catalogs':{'orders':ORDERS_CATALOG,'domestic':DOMESTIC_CATALOG,'labor':LABOR_CATALOG,'cbc_financial':CBC_FIN_CATALOG},'warnings':warnings}
    save_json('decision_inputs.json',obj)
    if not series:raise ValueError('no decision input series available')
    return {'latest_period':latest,'rows':rows,'message':'external orders, domestic-demand and financial inputs refreshed'+(('; warnings: '+'; '.join(warnings)) if warnings else ''),'warnings':warnings}
