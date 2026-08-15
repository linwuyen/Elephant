#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt, html, json, re
from common import TZ, request_bytes, decode_text, save_json, load_json

SOURCES={
 'TAIWAN_BROAD':{'name':'0050 / FTSE TWSE Taiwan 50 proxy','url':'https://www.yuantaetfs.com/product/detail/0050/Basic_information','kind':'EQUITY_PE','max_age_days':120},
 'GLOBAL_EQUITY':{'name':'Vanguard Total World Stock ETF (VT)','url':'https://investor.vanguard.com/investment-products/etfs/profile/vt','kind':'EQUITY_PE','max_age_days':120},
 'CASH':{'name':'CBC discount-rate proxy','url':'https://www.cbc.gov.tw/en/cp-448-192435-024f3-2.html','kind':'RATE','max_age_days':120},
}

def raw_normalized(text):
 t=html.unescape(text or '')
 for a,b in ((r'\u002F','/'),(r'\u002f','/'),(r'\/','/'),(r'\u0026','&'),(r'\u0025','%'),(r'\u003A',':'),(r'\u003a',':')):t=t.replace(a,b)
 return re.sub(r'\s+',' ',t)
def plain(text):
 text=re.sub(r'<style\b[^>]*>.*?</style>',' ',text,flags=re.I|re.S);text=re.sub(r'<[^>]+>',' ',text);text=html.unescape(text).replace('&#37;','%');return re.sub(r'\s+',' ',text).strip()
def date_norm(s):
 if not s:return None
 for fmt in ('%Y/%m/%d','%m/%d/%Y','%Y-%m-%d','%B %d, %Y','%b %d, %Y'):
  try:return dt.datetime.strptime(s.strip(),fmt).date().isoformat()
  except ValueError:pass
 return None

def parse_0050(text):
 candidates=(plain(text),raw_normalized(text));pe=asof=None
 for t in candidates:
  m=re.search(r'(20\d{2}/\d{2}/\d{2}).{0,1200}?(?:本益比|P/?E(?:\s*ratio)?)\D{0,80}?([0-9]+(?:\.[0-9]+)?)',t,re.I|re.S)
  if m:asof=date_norm(m.group(1));pe=float(m.group(2));break
  m=re.search(r'(?:本益比|P/?E(?:\s*ratio)?)\D{0,120}?([0-9]+(?:\.[0-9]+)?)',t,re.I|re.S)
  if m:pe=float(m.group(1));break
 if pe is None or not 3<=pe<=100:raise ValueError('0050 PE not found/plausible')
 return {'pe':round(pe,4),'as_of':asof}

def parse_vt(text):
 candidates=(plain(text),raw_normalized(text));pe=asof=None
 for t in candidates:
  md=re.search(r'Characteristics.{0,80}?as\s+of\s+(\d{2}/\d{2}/20\d{2})',t,re.I|re.S)
  if md:asof=date_norm(md.group(1))
  pats=(r'P\s*/\s*E\s+ratio\D{0,160}?([0-9]+(?:\.[0-9]+)?)\s*x?',r'P/E\s*ratio.{0,400}?(?:value|displayValue|fundValue)["\s:=\\]+([0-9]+(?:\.[0-9]+)?)',r'(?:label|name)["\s:=\\]+P/E\s*ratio.{0,500}?([0-9]+(?:\.[0-9]+)?)\s*x?')
  for p in pats:
   mp=re.search(p,t,re.I|re.S)
   if mp:pe=float(mp.group(1));break
  if pe is not None:break
 if pe is None or not 3<=pe<=100:raise ValueError('VT PE not found/plausible in visible or serialized characteristics')
 return {'pe':round(pe,4),'as_of':asof}

def parse_cbc(text):
 t=plain(text);m=re.search(r'discount\s+rate(?:[^0-9%]{0,140})(?:unchanged\s+at|at|to)\s*([0-9]+(?:\.[0-9]+)?)\s*%',t,re.I)
 if not m:m=re.search(r'discount\s+rate.{0,180}?([0-9]+(?:\.[0-9]+)?)\s*%',t,re.I)
 if not m:raise ValueError('CBC discount rate not found')
 rate=float(m.group(1))
 if not 0<=rate<=20:raise ValueError('CBC rate implausible')
 md=re.search(r'(?:Release Date|Date)[:\s]+([A-Za-z]+\s+\d{1,2},\s+20\d{2})',t,re.I)
 return {'rate_pct':round(rate,4),'as_of':date_norm(md.group(1)) if md else None}

def parse(key,text):return {'TAIWAN_BROAD':parse_0050,'GLOBAL_EQUITY':parse_vt,'CASH':parse_cbc}[key](text)

def run():
 old=load_json('opportunity_market_facts.json',{'version':1,'facts':{}});facts=dict(old.get('facts') or {});now=dt.datetime.now(TZ).replace(microsecond=0);health={}
 for key,src in SOURCES.items():
  try:
   b,_=request_bytes(src['url'],timeout=30,retries=3);row=parse(key,decode_text(b));row['as_of']=row.get('as_of') or now.date().isoformat();row.update({'name':src['name'],'source_url':src['url'],'source_quality':'FIRST_PARTY_ISSUER' if key!='CASH' else 'FIRST_PARTY','retrieved_at':now.isoformat(),'status':'OK','kind':src['kind'],'max_age_days':src['max_age_days']});facts[key]=row;health[key]={'status':'ok','as_of':row.get('as_of'),'message':'fresh parse'}
  except Exception as e:
   prior=facts.get(key);health[key]={'status':'last_good' if prior else 'error','as_of':prior.get('as_of') if prior else None,'message':str(e)}
 out={'version':2,'updated_at':now.isoformat(),'facts':facts,'source_health':health,'note':'Live first-party parse is preferred. Last-good facts are retained only while their model freshness gate remains valid; stale facts make the alternative unavailable.'};save_json('opportunity_market_facts.json',out);return out

if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False,indent=2))
