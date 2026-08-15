#!/usr/bin/env python3
from __future__ import annotations
import re
from common import decode_text,load_json,num,period_key,request_bytes,save_json
from source_decision import dedup
from source_moea import RowsParser,SALES_POS

SALES_URL='https://service.moea.gov.tw/EE521/common/Common.aspx?code=D&no=5'
INVENTORY_URL='https://service.moea.gov.tw/EE521/common/Common.aspx?code=D&no=6'
INVENTORY_CATALOG='https://data.gov.tw/dataset/109753'

def _clean(x):return re.sub(r'\s+','',str(x or '')).replace('\xa0','')
def _rows(body):
 text=decode_text(body);p=RowsParser();p.feed(text)
 if len(p.rows)<5:raise ValueError(f'MOEA live table has too few HTML rows: {len(p.rows)}')
 return p.rows

def _year_month_rows(rows):
 current_year=None
 for row in rows:
  for cell in row:
   m=re.fullmatch(r'(\d{3})年',_clean(cell))
   if m:current_year=int(m.group(1))+1911;break
  mi=next((i for i,c in enumerate(row) if re.fullmatch(r'\d{1,2}月',_clean(c))),None)
  if mi is None or current_year is None:continue
  month=int(re.sub(r'\D','',row[mi]));vals=[v for v in (num(c) for c in row[mi+1:]) if v is not None]
  if vals:yield current_year,month,vals

def _month_gap(newer,older):
 try:
  ny,nm=map(int,str(newer).split('-'));oy,om=map(int,str(older).split('-'))
 except Exception:return 999
 return (ny-oy)*12+(nm-om)

def parse_sales(body,min_observations=5):
 rows=_rows(body);series={k:{'name':name,'data':[]} for k,(pos,name) in SALES_POS.items()}
 for year,month,vals in _year_month_rows(rows):
  if len(vals)<23:continue
  period=f'{year:04d}-{month:02d}'
  for key,(pos,name) in SALES_POS.items():
   if pos<len(vals):series[key]['data'].append([period,float(vals[pos])])
 for item in series.values():item['data']=dedup(item['data'])
 total=series['C']['data']
 if len(total)<min_observations:raise ValueError(f'MOEA sales live table parsed too few months: {len(total)}')
 if not all(0<float(v)<1000 for _,v in total[-24:]):raise ValueError('MOEA sales live values outside plausible index range')
 return {'indicator_id':'moea.manufacturing.sales_index_2021','name':'製造業銷售指數（現行基期）','unit':'index_2021_100','series':series,'source_url':SALES_URL,'parse_contract':'HTML table structure + explicit numeric column order; no brittle page-title signature'}

def live_sales_index():return parse_sales(request_bytes(SALES_URL,60,3)[0])

def parse_inventory(body,min_observations=13):
 data=[]
 for year,month,vals in _year_month_rows(_rows(body)):
  data.append([f'{year:04d}-{month:02d}',float(vals[0])])
 data=dedup(data)
 if len(data)<min_observations:raise ValueError(f'MOEA inventory live table parsed too few months: {len(data)}')
 if not all(0<float(v)<1000 for _,v in data[-24:]):raise ValueError('MOEA inventory live values outside plausible index range')
 return {'name':'製造業 / 存貨指數','unit':'index_2021_100','data':data,'selection':'MOEA current statistics table / 製造業 total (first published series)','layout':'official_live_table_structural','catalog':INVENTORY_CATALOG,'source_url':INVENTORY_URL}

def update_inventory(_offline=None):
 obj=load_json('decision_inputs.json',{'series':{},'catalogs':{}})
 if _offline:return {'latest_period':obj.get('latest_period'),'rows':0,'message':'inventory live source skipped in offline mode'}
 try:
  incoming=parse_inventory(request_bytes(INVENTORY_URL,60,3)[0])
 except Exception as e:
  existing=obj.get('series',{}).get('inventory.manufacturing_index',{})
  data=existing.get('data',[])
  inv_period=str(data[-1][0]) if data else None
  as_of=obj.get('latest_period')
  gap=_month_gap(as_of,inv_period) if as_of and inv_period else 999
  if data and 0<=gap<=2:
   return {'latest_period':inv_period,'rows':len(data),'message':f'MOEA inventory HTML transport unavailable; retained last-good official manufacturing-total index {inv_period} within {gap}-month freshness window ({type(e).__name__}: {e})','warnings':[f'live inventory transport unavailable; last-good official series retained within freshness window ({type(e).__name__})']}
  raise
 series=dict(obj.get('series',{}));series['inventory.manufacturing_index']=incoming;obj['series']=series;cats=dict(obj.get('catalogs',{}));cats['inventory_manufacturing_live']=INVENTORY_CATALOG;obj['catalogs']=cats;obj['latest_period']=max((s['data'][-1][0] for s in series.values() if s.get('data')),key=period_key,default=obj.get('latest_period'));notes=list(obj.get('supplement_notes',[]));note='MOEA manufacturing total inventory index is parsed structurally from the official current-statistics table; page-title wording is not used as a data contract.'
 if note not in notes:notes.append(note)
 obj['supplement_notes']=notes[-20:];save_json('decision_inputs.json',obj);return {'latest_period':incoming['data'][-1][0],'rows':len(incoming['data']),'message':'MOEA manufacturing inventory refreshed from structural live-table parser'}
