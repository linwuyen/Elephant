#!/usr/bin/env python3
from __future__ import annotations
import csv
import re
import xml.etree.ElementTree as ET
from common import decode_text, load_json, num, period_key, request_bytes, save_json
from source_moea import decode_resource, month_period, pick

ORDERS_URL='https://service.moea.gov.tw/EE520/opendata/b.csv'
ORDERS_CATALOG='https://data.gov.tw/dataset/6845'
DOMESTIC_URL='https://service.moea.gov.tw/EE520/opendata/ea.csv'
DOMESTIC_CATALOG='https://data.gov.tw/dataset/6842'
CUSTOMS_URL='https://opendata.customs.gov.tw/data/6053/csv.csv'
CUSTOMS_CATALOG='https://data.gov.tw/dataset/6053'
INVENTORY_URL='https://service.moea.gov.tw/EE520/opendata/%E7%B6%93%E6%BF%9F%E9%83%A8%E7%B5%B1%E8%A8%88%E8%99%95_%E8%A3%BD%E9%80%A0%E6%A5%AD%E5%AD%98%E8%B2%A8%E5%83%B9%E5%80%BC.csv'
INVENTORY_CATALOG='https://data.gov.tw/en/datasets/62446'
LABOR_URL='https://apiservice.mol.gov.tw/OdService/download/A17030000J-000016-wWs'
LABOR_CATALOG='https://data.gov.tw/dataset/13228'
DGBAS_WAGE_URL='https://ws.dgbas.gov.tw/001/Upload/461/relfile/11525/230037/mp05001.xml'
DGBAS_WAGE_CATALOG='https://data.gov.tw/en/datasets/9634'
DGBAS_EMP_URL='https://ws.dgbas.gov.tw/001/Upload/461/relfile/11525/230037/mp05003.xml'
DGBAS_EMP_CATALOG='https://data.gov.tw/dataset/177765'
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
    unit='million_usd' if kind=='orders' else ('thousand_ntd' if kind=='inventory' else 'million_ntd')
    return {k:{'name':k,'unit':unit,'data':dedup(v)} for k,v in grouped.items() if len(v)>=2}

def parse_customs(body):
    rows=decode_resource(body,CUSTOMS_URL); data=[]
    for r in rows:
        y=num(pick(r,'年度','年')); m=num(pick(r,'月份','月'))
        v=num(pick(r,'出口總值(新臺幣千元)','出口總值'))
        if y is None or m is None or v is None:continue
        yy=int(y); mm=int(m)
        if yy<1911:yy+=1911
        if 1<=mm<=12:data.append([f'{yy:04d}-{mm:02d}',v])
    data=dedup(data)
    if len(data)<24:raise ValueError('customs exports parse returned too few rows')
    return {'customs.exports_total':{'name':'海關出口總值','unit':'thousand_ntd','data':data}}

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

def local(tag):return str(tag).split('}')[-1]
def xml_leaf_rows(body):
    root=ET.fromstring(body); rows=[]
    for parent in root.iter():
        children=list(parent)
        if children and all(not list(c) for c in children):
            d={local(c.tag):''.join(c.itertext()).strip() for c in children}
            if len(d)>=2:rows.append(d)
    return rows

def parse_month_any(raw):
    s=str(raw or '').strip()
    try:return month_period(s)
    except Exception:pass
    m=re.search(r'(20\d{2})\D{0,4}(\d{1,2})',s)
    if m and 1<=int(m.group(2))<=12:return f'{int(m.group(1)):04d}-{int(m.group(2)):02d}'
    m=re.search(r'(?<!\d)(\d{2,3})\D{0,4}(\d{1,2})(?!\d)',s)
    if m and int(m.group(1))<1911 and 1<=int(m.group(2))<=12:return f'{int(m.group(1))+1911:04d}-{int(m.group(2)):02d}'
    return None

def parse_dgbas_long(body,name):
    groups={}
    for r in xml_leaf_rows(body):
        pkey=next((k for k in r if 'period' in k.lower() or '年月' in k),None)
        vkey=next((k for k in r if k.lower() in ('val','value','item_value') or '數值' in k),None)
        if not pkey or not vkey:continue
        p=parse_month_any(r.get(pkey)); v=num(r.get(vkey))
        if not p or v is None:continue
        label=' / '.join(str(v0) for k,v0 in r.items() if k not in (pkey,vkey) and ('category' in k.lower() or '項目' in k or '行業' in k))
        groups.setdefault(label or 'total',[]).append([p,v])
    if not groups:raise ValueError('DGBAS long XML parse empty')
    def rank(item):
        label,data=item; x=label.lower(); score=len(data)
        if '工業及服務業' in label or 'industry and services' in x:score+=10000
        if '總計' in label or 'total' in x:score+=3000
        if '製造業' in label:score-=1000
        return score
    label,data=max(groups.items(),key=rank); data=dedup(data)
    if len(data)<24:raise ValueError('DGBAS wage history too short')
    return {'dgbas.total_monthly_salary':{'name':name,'unit':'ntd','data':data,'selection':label}}

def parse_dgbas_employment(body):
    data=[]
    for r in xml_leaf_rows(body):
        pkey=next((k for k in r if '年月' in k or 'year_and_month' in k.lower() or k.lower()=='period'),None)
        if not pkey:continue
        vkey=next((k for k in r if ('工業及服務業' in k or 'industry_and_services' in k.lower()) and ('人數' in k or 'person' in k.lower())),None)
        if not vkey:continue
        p=parse_month_any(r.get(pkey)); v=num(r.get(vkey))
        if p and v is not None:data.append([p,v])
    data=dedup(data)
    if len(data)<24:raise ValueError('DGBAS employment parse too short')
    return {'dgbas.employment_total':{'name':'工業及服務業受僱員工人數','unit':'persons','data':data}}

def merge_recent(base,recent):
    d=dict((base or {}).get('data',[])); d.update(dict((recent or {}).get('data',[])))
    out=dict(base or recent or {}); out['data']=dedup(d.items()); return out

_MONTHS={'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12}
def cbc_row_period(row, roc_year):
    first=str(row[0] or '').strip(); both=re.search(r'(?<!\d)(\d{3})\D{1,8}(\d{1,2})(?!\d)',first)
    if both:
        ry,mo=int(both.group(1)),int(both.group(2))
        if 100<=ry<200 and 1<=mo<=12:return f'{ry+1911:04d}-{mo:02d}',ry
    one=re.fullmatch(r'(\d{1,2})',first)
    if one and roc_year is not None:
        mo=int(one.group(1))
        if 1<=mo<=12:return f'{roc_year+1911:04d}-{mo:02d}',roc_year
    tail=' '.join(str(x or '') for x in row[-5:]).lower(); em=re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\.?\s*(20\d{2})',tail)
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
            if idx<len(row):
                v=num(row[idx])
                if v is not None:out[key].append([period,v])
    return {k:dedup(v) for k,v in out.items() if len(dedup(v))>=12}

def parse_cbc_financial(bodies):
    raw={**cbc_month_rows(bodies['money'],{'m1b_yoy':16,'m2_yoy':20}),**cbc_month_rows(bodies['credit'],{'credit_yoy':20}),**cbc_month_rows(bodies['markets'],{'interbank_rate':7,'stock_index':10,'exchange_rate':11})}
    names={'m1b_yoy':'M1B 年增率','m2_yoy':'M2 年增率','credit_yoy':'金融機構放款與投資年增率','interbank_rate':'金融業隔夜拆款加權平均利率','stock_index':'股價指數','exchange_rate':'銀行間美元收盤匯率'}
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
    for name,url,kind,prefix in [('orders',ORDERS_URL,'orders','orders.'),('domestic',DOMESTIC_URL,'domestic','domestic.'),('inventory',INVENTORY_URL,'inventory','inventory.')]:
        try:
            body,_=request_bytes(url,75,3); parsed=parse_long_moea(body,url,kind); rows+=sum(len(x['data']) for x in parsed.values())
            if not parsed:raise ValueError(f'{name} parse empty')
            for k,v in parsed.items():series[prefix+k]=v
        except Exception as e:warnings.append(f'{name}: {type(e).__name__}: {e}')
    try:
        body,_=request_bytes(CUSTOMS_URL,60,3); parsed=parse_customs(body); rows+=sum(len(x['data']) for x in parsed.values()); series.update(parsed)
    except Exception as e:warnings.append(f'customs: {type(e).__name__}: {e}')
    labor={}
    try:
        body,_=request_bytes(LABOR_URL,60,3); labor=parse_labor(body); rows+=sum(len(x['data']) for x in labor.values())
        if not labor:raise ValueError('labor parse empty')
        for k,v in labor.items():series['labor.'+k]=v
    except Exception as e:warnings.append(f'labor: {type(e).__name__}: {e}')
    try:
        body,_=request_bytes(DGBAS_WAGE_URL,75,2); parsed=parse_dgbas_long(body,'工業及服務業平均每月總薪資'); rows+=sum(len(x['data']) for x in parsed.values()); series.update(parsed)
        if labor.get('avg_monthly_salary'):series['dgbas.total_monthly_salary']=merge_recent(series['dgbas.total_monthly_salary'],labor['avg_monthly_salary'])
    except Exception as e:warnings.append(f'dgbas_wage: {type(e).__name__}: {e}')
    try:
        body,_=request_bytes(DGBAS_EMP_URL,75,2); parsed=parse_dgbas_employment(body); rows+=sum(len(x['data']) for x in parsed.values()); series.update(parsed)
    except Exception as e:warnings.append(f'dgbas_employment: {type(e).__name__}: {e}')
    try:
        bodies={key:request_bytes(url,60,3)[0] for key,url in CBC_TABLES.items()}; parsed=parse_cbc_financial(bodies); rows+=sum(len(x['data']) for x in parsed.values())
        for k,v in parsed.items():series['cbc.'+k]=v
    except Exception as e:warnings.append(f'cbc_financial: {type(e).__name__}: {e}')
    latest=max((s['data'][-1][0] for s in series.values() if s.get('data')),key=period_key,default=None)
    catalogs={'orders':ORDERS_CATALOG,'domestic':DOMESTIC_CATALOG,'customs':CUSTOMS_CATALOG,'inventory':INVENTORY_CATALOG,'labor':LABOR_CATALOG,'dgbas_wage':DGBAS_WAGE_CATALOG,'dgbas_employment':DGBAS_EMP_CATALOG,'cbc_financial':CBC_FIN_CATALOG}
    obj={'source':'Taiwan official decision inputs','latest_period':latest,'series':series,'catalogs':catalogs,'warnings':warnings}; save_json('decision_inputs.json',obj)
    if not series:raise ValueError('no decision input series available')
    return {'latest_period':latest,'rows':rows,'message':'official decision inputs refreshed'+(('; warnings: '+'; '.join(warnings)) if warnings else ''),'warnings':warnings}
