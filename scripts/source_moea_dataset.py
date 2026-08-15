#!/usr/bin/env python3
from __future__ import annotations
import html, io, json, re, urllib.parse, zipfile
from common import csv_rows_bytes, decode_text, request_bytes

DATA_GOV_META='https://data.gov.tw/api/v2/rest/dataset/{dataset_id}'
FALLBACKS={
 109753:'https://service.moea.gov.tw/EE520/opendata/%E7%B6%93%E6%BF%9F%E9%83%A8%E7%B5%B1%E8%A8%88%E8%99%95_%E8%A3%BD%E9%80%A0%E6%A5%AD%E5%AD%98%E8%B2%A8%E9%87%8F%E6%8C%87%E6%95%B8%EF%BC%8D%E6%8C%89%E5%9B%9B%E5%A4%A7%E8%A1%8C%E6%A5%AD%E5%88%A5%E5%88%86.csv',
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
 # urllib requires non-ASCII URL paths to be quoted while preserving URL separators.
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
 # Prefer current service.moea over legacy dmz and de-duplicate in order.
 out=sorted(dict.fromkeys(out),key=lambda u:(0 if 'service.moea.gov.tw' in u.lower() else 1,0 if '.csv' in u.lower() else 1,len(u)))
 return out

def decode_rows(body,url):
 if body[:2]==b'PK':
  with zipfile.ZipFile(io.BytesIO(body)) as zf:
   names=[n for n in zf.namelist() if n.lower().endswith(('.csv','.txt')) and not n.endswith('/')]
   if not names:raise ValueError('ZIP has no CSV/TXT')
   body=zf.read(names[0])
 text=decode_text(body[:500]).lstrip().lower()
 if text.startswith('<!doctype') or text.startswith('<html'):raise ValueError('resource returned HTML')
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

if __name__=='__main__':
 for i in (95141,109753):
  rows,url=dataset_rows(i);print(i,len(rows),url,list(rows[0])[:6])
