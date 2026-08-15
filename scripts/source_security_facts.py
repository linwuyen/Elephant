#!/usr/bin/env python3
from __future__ import annotations
import csv,datetime as dt,io,json,re
from common import TZ,request_bytes,decode_text,load_json,save_json,num

SOURCES=[
 ('monthly_revenue','TWSE','https://openapi.twse.com.tw/v1/opendata/t187ap05_L'),
 ('income_statement','TWSE','https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ci'),
 ('balance_sheet','TWSE','https://openapi.twse.com.tw/v1/opendata/t187ap07_L_ci'),
 ('monthly_revenue','TPEX','https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O'),
 ('income_statement','TPEX','https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap06_O_ci'),
 ('balance_sheet','TPEX','https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap07_O_ci'),
]
TPEX_CSV_FALLBACK={
 'income_statement':'https://mopsfin.twse.com.tw/opendata/t187ap06_O_ci.csv',
 'balance_sheet':'https://mopsfin.twse.com.tw/opendata/t187ap07_O_ci.csv',
}

def fetch_json(url):
 b,_=request_bytes(url,timeout=60,retries=4);x=json.loads(decode_text(b))
 if not isinstance(x,list) or len(x)<10:raise ValueError(f'implausible row count: {len(x) if isinstance(x,list) else type(x)}')
 return x

def fetch_csv(url):
 b,_=request_bytes(url,timeout=60,retries=4);text=decode_text(b).lstrip('\ufeff');rows=list(csv.DictReader(io.StringIO(text)))
 if len(rows)<10:raise ValueError(f'implausible CSV row count: {len(rows)}')
 return rows

def nk(k):return re.sub(r'\s+','',str(k or '').replace('\ufeff',''))
def pick(r,*keys):
 for k in keys:
  if k in r and r[k] not in (None,''):return r[k]
 wanted={nk(k) for k in keys}
 for k,v in r.items():
  if nk(k) in wanted and v not in (None,''):return v
 return None

def code(r):return str(pick(r,'公司代號','公司代碼','證券代號','Code','公司編號') or '').strip()
def row_period(r):
 y=pick(r,'年度','Year');q=pick(r,'季別','季','Quarter');ym=pick(r,'資料年月','年月','DataMonth')
 if ym:
  s=str(ym).strip().replace('/','').replace('-','')
  try:
   if len(s) in (5,6):
    yy=int(s[:-2]);yy=yy+1911 if yy<1911 else yy;return f'{yy:04d}-{int(s[-2:]):02d}'
  except Exception:pass
 if y:
  yy=int(float(str(y).replace(',','')));yy=yy+1911 if yy<1911 else yy
  if q:return f'{yy:04d}-Q{int(float(q))}'
  return str(yy)
 return None

def compact(kind,r,market):
 base={'period':row_period(r),'market':market,'company_name':pick(r,'公司名稱','CompanyName'),'statement_date':pick(r,'出表日期','Date')}
 if kind=='monthly_revenue':base.update({'revenue_month':num(pick(r,'營業收入-當月營收','當月營收','當月營業收入')),'revenue_yoy_pct':num(pick(r,'營業收入-去年同月增減(%)','去年同月增減(%)','去年同月增減百分比')),'revenue_ytd':num(pick(r,'累計營業收入-當月累計營收','當月累計營收')),'revenue_ytd_yoy_pct':num(pick(r,'累計營業收入-前期比較增減(%)','前期比較增減(%)'))})
 elif kind=='income_statement':base.update({'revenue':num(pick(r,'營業收入','Revenue')),'gross_profit':num(pick(r,'營業毛利（毛損）','營業毛利(毛損)','營業毛利（毛損）淨額','GrossProfit')),'operating_income':num(pick(r,'營業利益（損失）','營業利益(損失)','OperatingIncome')),'net_income':num(pick(r,'本期淨利（淨損）','本期淨利(淨損)','NetIncome')),'eps':num(pick(r,'基本每股盈餘（元）','基本每股盈餘(元)','基本每股盈餘','EPS'))})
 else:base.update({'assets':num(pick(r,'資產總額','資產總計','Assets')),'liabilities':num(pick(r,'負債總額','負債總計','Liabilities')),'equity':num(pick(r,'權益總額','權益總計','Equity')),'cash':num(pick(r,'現金及約當現金','CashAndCashEquivalents'))})
 return base

def newer(a,b):return str((a or {}).get('period') or '')>=str((b or {}).get('period') or '')
def ingest(rows,kind,market,wanted,facts):
 used=0
 for r in rows:
  t=code(r)
  if t not in wanted:continue
  x=compact(kind,r,market);slot=facts.setdefault(t,{});prev=slot.get(kind)
  if prev is None or newer(x,prev):slot[kind]=x
  used+=1
 return used

def run():
 bundle=load_json('alpha_engine.json',{});alpha=bundle.get('alpha') or {};screen=bundle.get('screen') or {};wanted={'2330'}|{str(x.get('ticker')) for x in alpha.get('stocks',[])}|{str(x.get('ticker')) for x in screen.get('deep_research_queue',[]) or []};old=load_json('security_official_facts.json',{'facts':{}});facts=dict(old.get('facts') or {});health={};now=dt.datetime.now(TZ).replace(microsecond=0);total_matches=0;market_matches={'TWSE':0,'TPEX':0}
 for kind,market,url in SOURCES:
  key=f'{kind}_{market}'
  try:
   rows=fetch_json(url);used=ingest(rows,kind,market,wanted,facts);mode='openapi'
   if used==0 and market=='TPEX' and kind in TPEX_CSV_FALLBACK:
    csv_url=TPEX_CSV_FALLBACK[kind];rows=fetch_csv(csv_url);used=ingest(rows,kind,market,wanted,facts);mode='mops_csv_fallback';url_used=csv_url
   else:url_used=url
   total_matches+=used;market_matches[market]+=used;health[key]={'status':'ok' if used>0 else 'no_target_match','transport_rows':len(rows),'matched':used,'mode':mode,'url':url_used}
  except Exception as e:
   has_last_good=any((v or {}).get(kind,{}).get('market')==market for v in facts.values());health[key]={'status':'last_good' if has_last_good else 'error','matched':0,'message':str(e),'url':url}
 covered=sum(1 for t in wanted if facts.get(t));markets_with_matches=sum(1 for v in market_matches.values() if v>0);tpex_targets={t for t in wanted if (facts.get(t,{}).get('monthly_revenue') or {}).get('market')=='TPEX'}
 tpex_income=sum(1 for t in tpex_targets if facts.get(t,{}).get('income_statement',{}).get('market')=='TPEX');tpex_balance=sum(1 for t in tpex_targets if facts.get(t,{}).get('balance_sheet',{}).get('market')=='TPEX')
 if total_matches==0:raise RuntimeError('listed-market security fact ingestion matched zero target securities; fail closed')
 if covered<max(5,len(wanted)//3):raise RuntimeError(f'listed-market security fact coverage implausibly low: {covered}/{len(wanted)}')
 if markets_with_matches<2:raise RuntimeError(f'expected both TWSE and TPEX target coverage, got {market_matches}')
 if tpex_targets and (tpex_income==0 or tpex_balance==0):raise RuntimeError(f'TPEx quarterly fact coverage is zero for target universe: income={tpex_income}, balance={tpex_balance}, targets={len(tpex_targets)}')
 out={'version':3,'updated_at':now.isoformat(),'facts':facts,'source_health':health,'universe':sorted(wanted),'coverage':{'target_count':len(wanted),'covered_tickers':covered,'covered_pct':round(covered/len(wanted)*100,1),'matched_rows':total_matches,'market_matches':market_matches,'tpex_target_count':len(tpex_targets),'tpex_income_covered':tpex_income,'tpex_balance_covered':tpex_balance},'guardrail':'Only listed TWSE (L) and TPEx (O) sources are valid. TPEx quarterly OpenAPI falls back to official MOPS CSV. Zero quarterly coverage for TPEx targets fails closed; missing data is never invented.'};save_json('security_official_facts.json',out);return out
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False,indent=2))
