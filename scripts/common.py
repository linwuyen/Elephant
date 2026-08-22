from __future__ import annotations
import csv, datetime as dt, json, re, time, urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'; DATA.mkdir(exist_ok=True)
TZ=ZoneInfo('Asia/Taipei')
UA='Elephant-Taiwan-Economic-Dashboard/3.0 (+https://github.com/linwuyen/Elephant)'
URLS={
 'mol_macro':'https://apiservice.mol.gov.tw/OdService/download/A17000000J-030243-zbf',
 'ndc_dataset':'https://data.gov.tw/dataset/43372',
 'ndc_meta':'https://data.gov.tw/api/v2/rest/dataset/43372',
 'moea_indprod':'https://service.moea.gov.tw/EE520/opendata/d.csv',
 'moea_sales_volume':'https://service.moea.gov.tw/EE520/opendata/e.csv',
 'moea_sales_value':'https://service.moea.gov.tw/EE520/opendata/f.csv',
 'moea_investment':'https://service.moea.gov.tw/EE520/opendata/ec.csv',
 'ris_base':'https://www.ris.gov.tw/documents/data/en/3',
 # Canonical SEGIS target is the nationwide township/district business-count
 # product, not the county-only variant. 114Y12 is the latest public product
 # verified on 2026-08-22; source discovery must fail closed if SEGIS rotates
 # the opaque COL/MCOL identifiers before a reproducible machine endpoint is found.
 'segis_business_township':'https://segis.moi.gov.tw/STATCloud/QueryInterfaceView?COL=8%252fnKF8Qu3MIbJoiTa%252f3Gng%253d%253d&MCOL=fACyEf%252f7IGprAbIDY0oUgQ%253d%253d',
 'segis_catalog':'https://segis.moi.gov.tw/STATCloud/Catalog',
}

def load_json(name,default):
 p=DATA/name
 return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default

def save_json(name,obj):
 (DATA/name).write_text(json.dumps(obj,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')

def num(v):
 if v is None:return None
 s=str(v).strip().replace(',','').replace('%','')
 if s in {'','-','—','…','...','NA','N/A','null','None'}:return None
 try:return float(s)
 except ValueError:return None

def roc_year(v):return str(int(str(v).strip())+1911)
def roc_month(v):
 s=str(v).strip().zfill(5); return f'{int(s[:-2])+1911:04d}-{int(s[-2:]):02d}'

def request_bytes(url,timeout=90,retries=3):
 last=None
 for attempt in range(retries):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'*/*'})
   with urllib.request.urlopen(req,timeout=timeout) as r:
    b=r.read()
    if len(b)<20:raise ValueError(f'body too small: {len(b)} bytes')
    return b,r.headers.get_content_type()
  except Exception as e:
   last=e; time.sleep(2**attempt)
 raise RuntimeError(f'fetch failed {url}: {last}')

def decode_text(b):
 for enc in ('utf-8-sig','utf-8','cp950','big5'):
  try:return b.decode(enc)
  except UnicodeDecodeError:pass
 return b.decode('utf-8',errors='replace')

def csv_rows_bytes(b):return list(csv.DictReader(decode_text(b).splitlines()))
def offline_bytes(offline,filename):
 p=Path(offline)/filename
 if not p.exists():raise FileNotFoundError(p)
 return p.read_bytes()
def fetch_or_offline(offline,filename,url):return (offline_bytes(offline,filename),'application/octet-stream') if offline else request_bytes(url)

def period_key(p):
 s=str(p); m=re.fullmatch(r'(\d{4})-Q([1-4])',s)
 if m:return int(m.group(1)),int(m.group(2))*3,0
 m=re.fullmatch(r'(\d{4})-(\d{2})',s)
 if m:return int(m.group(1)),int(m.group(2)),1
 m=re.fullmatch(r'(\d{4})',s)
 return (int(m.group(1)),12,-1) if m else (0,0,0)

def max_period(obj):
 vals=[]
 def walk(x):
  if isinstance(x,dict):
   if isinstance(x.get('data'),list):
    for r in x['data']:
     if isinstance(r,list) and r:vals.append(str(r[0]))
     elif isinstance(r,dict) and 'period' in r:vals.append(str(r['period']))
   for v in x.values():walk(v)
  elif isinstance(x,list):
   for v in x:walk(v)
 walk(obj); return max(vals,key=period_key) if vals else None
