#!/usr/bin/env python3
from __future__ import annotations
import re
from html.parser import HTMLParser
from common import decode_text, load_json, num, period_key, request_bytes, save_json
from source_moea import decode_resource, month_period, pick

ORDERS_URL='https://service.moea.gov.tw/EE520/opendata/b.csv'
ORDERS_CATALOG='https://data.gov.tw/dataset/6845'
DOMESTIC_URL='https://service.moea.gov.tw/EE520/opendata/ea.csv'
DOMESTIC_CATALOG='https://data.gov.tw/dataset/6842'
LABOR_URL='https://apiservice.mol.gov.tw/OdService/download/A17030000J-000016-wWs'
LABOR_CATALOG='https://data.gov.tw/dataset/13228'
CBC_M2_URL='https://www.cbc.gov.tw/tw/np-643-1.html'
CBC_M2_CATALOG='https://www.cbc.gov.tw/tw/lp-1046-1.html'

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows=[]; self.row=None; self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='tr': self.row=[]
        elif tag in ('td','th') and self.row is not None: self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None and self.row is not None:
            self.row.append(re.sub(r'\s+',' ',''.join(self.cell)).strip()); self.cell=None
        elif tag=='tr' and self.row is not None:
            if self.row:self.rows.append(self.row)
            self.row=None

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

def parse_cbc_m2(body):
    hp=TableParser(); hp.feed(decode_text(body)); data=[]
    for row in hp.rows:
        p=None; val=None
        for cell in row:
            m=re.search(r'(20\d{2})[./-](\d{1,2})',cell)
            if m:p=f'{int(m.group(1)):04d}-{int(m.group(2)):02d}'
        nums=[]
        for cell in row:
            if re.fullmatch(r'[+-]?\d+(?:\.\d+)?',cell.replace(',','')):
                try:nums.append(float(cell.replace(',','')))
                except:pass
        if p and nums:val=nums[-1]
        if p and val is not None and -20<val<50:data.append([p,val])
    if not data:
        text=re.sub(r'<[^>]+>',' ',decode_text(body)); text=re.sub(r'\s+',' ',text)
        for y,m,v in re.findall(r'(20\d{2})[./-](\d{1,2})\s+([+-]?\d+(?:\.\d+)?)',text):
            x=float(v)
            if -20<x<50:data.append([f'{int(y):04d}-{int(m):02d}',x])
    vals=dedup(data)
    if not vals:raise ValueError('CBC M2 page parse returned no values')
    return {'m2_yoy':{'name':'貨幣總計數 M2 年增率','unit':'percent','data':vals}}

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
        body,_=request_bytes(LABOR_URL,60,3); parsed=parse_labor(body); rows+=sum(len(x['data']) for x in parsed.values());
        if not parsed:raise ValueError('labor parse empty')
        for k,v in parsed.items():series['labor.'+k]=v
    except Exception as e:warnings.append(f'labor: {type(e).__name__}: {e}')
    try:
        body,_=request_bytes(CBC_M2_URL,60,3); parsed=parse_cbc_m2(body); rows+=sum(len(x['data']) for x in parsed.values());
        for k,v in parsed.items():series['cbc.'+k]=v
    except Exception as e:warnings.append(f'cbc_m2: {type(e).__name__}: {e}')
    latest=max((s['data'][-1][0] for s in series.values() if s.get('data')),key=period_key,default=None)
    obj={'source':'Taiwan official decision inputs','latest_period':latest,'series':series,'catalogs':{'orders':ORDERS_CATALOG,'domestic':DOMESTIC_CATALOG,'labor':LABOR_CATALOG,'cbc_m2':CBC_M2_CATALOG},'warnings':warnings}
    save_json('decision_inputs.json',obj)
    if not series:raise ValueError('no decision input series available')
    return {'latest_period':latest,'rows':rows,'message':'external orders, domestic-demand and financial inputs refreshed'+(('; warnings: '+'; '.join(warnings)) if warnings else ''),'warnings':warnings}
