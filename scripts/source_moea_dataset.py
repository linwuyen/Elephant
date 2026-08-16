#!/usr/bin/env python3
from __future__ import annotations
import html, io, json, re, urllib.parse, zipfile
from common import csv_rows_bytes, decode_text, load_json, period_key, request_bytes, save_json

DATA_GOV_META='https://data.gov.tw/api/v2/rest/dataset/{dataset_id}'
SALES_DATASET=95141
INVENTORY_DATASET=109753
CATALOGS={SALES_DATASET:'https://data.gov.tw/dataset/95141',INVENTORY_DATASET:'https://data.gov.tw/dataset/109753'}
MAJOR_INDUSTRIES=('I1','I2','I3','I4')
FALLBACKS={
 INVENTORY_DATASET:'https://service.moea.gov.tw/EE520/opendata/%E7%B6%93%E6%BF%9F%E9%83%A8%E7%B5%B1%E8%A8%88%E8%99%95_%E8%A3%BD%E9%80%A0%E6%A5%AD%E5%AD%98%E8%B2%A8%E9%87%8F%E6%8C%87%E6%95%B8%EF%BC%8D%E6%8C%89%E5%9B%9B%E5%A4%A7%E8%A1%8C%E6%A5%AD%E5%88%A5%E5%88%86.csv',
}

def strings(x):
 if isinstance(x,str):yield x
 elif isinstance(x,dict):
  for v in x.values():yield from strings(v)
 elif isinstance(x,list):
  for v in x:yield from strings(v)

def normalize_url(s):
 s=html.unescape(str(s or '')).replace('\\/','/').strip().strip('"\'')
 try:s=urllib.parse.unquote(s)
 except Exception:pass
 if not re.match(r'^https?://',s,re.I):return None
 parts=urllib.parse.urlsplit(s);path=urllib.parse.quote(urllib.parse.unquote(parts.path),safe='/%:@');query=urllib.parse.quote(urllib.parse.unquote(parts.query),safe='=&%:@/?')
 return urllib.parse.urlunsplit((parts.scheme,parts.netloc,path,query,parts.fragment))

def resource_candidates(meta,dataset_id):
 out=[]
 for s in strings(meta):
  u=normalize_url(s)
  if not u:continue
  low=u.lower()
  if ('moea.gov.tw' in low or 'data.gov.tw' in low or 'data.nat.gov.tw' in low) and ('.csv' in low or '.zip' in low):out.append(u)
 if dataset_id in FALLBACKS:out.append(FALLBACKS[dataset_id])
 return sorted(dict.fromkeys(out),key=lambda u:(0 if 'service.moea.gov.tw' in u.lower() else 1,0 if '.csv' in u.lower() else 1,len(u)))

def decode_rows(body,url):
 if body[:2]==b'PK':
  with zipfile.ZipFile(io.BytesIO(body)) as zf:
   names=[n for n in zf.namelist() if n.lower().endswith(('.csv','.txt')) and not n.endswith('/')]
   if not names:raise ValueError('ZIP has no CSV/TXT')
   body=zf.read(names[0])
 prefix=decode_text(body[:500]).lstrip().lower()
 if prefix.startswith('<!doctype') or prefix.startswith('<html'):raise ValueError('resource returned HTML')
 rows=csv_rows_bytes(body)
 if len(rows)<10:raise ValueError(f'CSV rows implausibly low: {len(rows)}')
 return rows

def dataset_rows(dataset_id):
 meta_url=DATA_GOV_META.format(dataset_id=dataset_id);errors=[];meta={}
 try:
  body,_=request_bytes(meta_url,timeout=30,retries=3);meta=json.loads(decode_text(body))
 except Exception as e:errors.append(f'metadata:{type(e).__name__}:{e}')
 candidates=resource_candidates(meta,dataset_id)
 if not candidates:raise RuntimeError(f'no MOEA CSV/ZIP resource in data.gov metadata dataset={dataset_id}; errors={errors}')
 for url in candidates[:12]:
  try:
   body,_=request_bytes(url,timeout=45,retries=3);return decode_rows(body,url),url
  except Exception as e:errors.append(f'{url}:{type(e).__name__}:{e}')
 raise RuntimeError(f'all MOEA dataset resources failed dataset={dataset_id}; '+' | '.join(errors[-8:]))

def major_industry_index(dataset_id,aliases,indicator_id,name,min_points):
 from source_moea import infer_unit, parse
 rows,url=dataset_rows(dataset_id)
 series=parse(rows,('統計值(指數)','統計值'),aliases)
 missing=[code for code in MAJOR_INDUSTRIES if code not in series or len(series[code].get('data',[]))<min_points]
 if missing:raise ValueError(f'data.gov MOEA four-industry series missing/short: {missing}')
 for code in MAJOR_INDUSTRIES:
  data=series[code]['data']
  if not all(0<float(v)<1000 for _,v in data[-24:]):raise ValueError(f'data.gov MOEA {code} values outside plausible range')
 return {'indicator_id':indicator_id,'name':name,'unit':infer_unit(rows,'index_2021_100'),'series':series,'source_url':url,'catalog':CATALOGS[dataset_id],'transport':'data.gov metadata → MOEA CSV/ZIP','scope':'official four-major-industry series; no synthetic manufacturing total'}

def sales_index():
 return major_industry_index(SALES_DATASET,('銷售量指數','銷售指數'),'moea.manufacturing.sales_volume_index_major_industries','製造業銷售量指數－按四大行業別',5)

def inventory_index():
 return major_industry_index(INVENTORY_DATASET,('存貨量指數','存貨指數'),'moea.manufacturing.inventory_index_major_industries','製造業存貨量指數－按四大行業別',13)

def update_inventory(offline=None):
 if offline:return {'latest_period':load_json('decision_inputs.json',{}).get('latest_period'),'rows':0,'message':'inventory data.gov source skipped in offline mode'}
 from source_moea import infer_unit, parse
 rows,url=dataset_rows(INVENTORY_DATASET);series=parse(rows,('統計值(指數)','統計值'),('存貨量指數','存貨指數'))
 total=series.get('C') or next((x for x in series.values() if str(x.get('name','')).replace(' ','')=='製造業'),None)
 if not total or len(total.get('data',[]))<13:raise ValueError('data.gov MOEA inventory manufacturing-total series missing/short')
 if not all(0<float(v)<1000 for _,v in total['data'][-24:]):raise ValueError('data.gov MOEA inventory values outside plausible range')
 incoming={'name':'製造業 / 存貨指數','unit':infer_unit(rows,'index_2021_100'),'data':total['data'],'selection':'official dataset / 製造業 total','layout':'data_gov_official_resource','catalog':CATALOGS[INVENTORY_DATASET],'source_url':url}
 obj=load_json('decision_inputs.json',{'series':{},'catalogs':{}});s=dict(obj.get('series',{}));s['inventory.manufacturing_index']=incoming;obj['series']=s;cats=dict(obj.get('catalogs',{}));cats['inventory_manufacturing_data_gov']=CATALOGS[INVENTORY_DATASET];obj['catalogs']=cats;obj['latest_period']=max((x['data'][-1][0] for x in s.values() if x.get('data')),key=period_key,default=obj.get('latest_period'));notes=list(obj.get('supplement_notes',[]));note='MOEA manufacturing inventory uses the official data.gov dataset resource resolved from dataset metadata; sub-industries are never composited into a synthetic total.'
 if note not in notes:notes.append(note)
 obj['supplement_notes']=notes[-20:];save_json('decision_inputs.json',obj)
 return {'latest_period':incoming['data'][-1][0],'rows':len(incoming['data']),'message':f'MOEA inventory refreshed from official data.gov resource ({url})'}

if __name__=='__main__':
 s=sales_index();print('sales',{k:len(s['series'][k]['data']) for k in MAJOR_INDUSTRIES},s['source_url']);i=inventory_index();print('inventory',{k:len(i['series'][k]['data']) for k in MAJOR_INDUSTRIES},i['source_url'])
