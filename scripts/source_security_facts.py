#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt,json
from common import TZ,request_bytes,decode_text,load_json,save_json,num
URLS={'monthly_revenue':'https://openapi.twse.com.tw/v1/opendata/t187ap05_P','income_statement':'https://openapi.twse.com.tw/v1/opendata/t187ap06_X_ci','balance_sheet':'https://openapi.twse.com.tw/v1/opendata/t187ap07_X_ci'}

def fetch_json(url):
 b,_=request_bytes(url,timeout=60,retries=4);x=json.loads(decode_text(b));
 if not isinstance(x,list) or len(x)<10:raise ValueError(f'implausible row count: {len(x) if isinstance(x,list) else type(x)}')
 return x

def pick(r,*keys):
 for k in keys:
  if k in r and r[k] not in (None,''):return r[k]
 return None

def code(r):return str(pick(r,'公司代號','公司代碼','證券代號','Code','公司編號') or '').strip()
def row_period(r):
 y=pick(r,'年度','Year');q=pick(r,'季別','季','Quarter');ym=pick(r,'資料年月','年月','DataMonth')
 if ym:
  s=str(ym).strip().replace('/','').replace('-','');
  try:
   if len(s) in (5,6):
    yy=int(s[:-2]);yy=yy+1911 if yy<1911 else yy;return f'{yy:04d}-{int(s[-2:]):02d}'
  except:pass
 if y:
  yy=int(float(str(y).replace(',','')));yy=yy+1911 if yy<1911 else yy
  if q:return f'{yy:04d}-Q{int(float(q))}'
  return str(yy)
 return None

def compact(kind,r):
 base={'period':row_period(r),'company_name':pick(r,'公司名稱','CompanyName'),'statement_date':pick(r,'出表日期','Date')}
 if kind=='monthly_revenue':base.update({'revenue_month':num(pick(r,'營業收入-當月營收','當月營收','當月營業收入')),'revenue_yoy_pct':num(pick(r,'營業收入-去年同月增減(%)','去年同月增減(%)','去年同月增減百分比')),'revenue_ytd':num(pick(r,'累計營業收入-當月累計營收','當月累計營收')),'revenue_ytd_yoy_pct':num(pick(r,'累計營業收入-前期比較增減(%)','前期比較增減(%)'))})
 elif kind=='income_statement':base.update({'revenue':num(pick(r,'營業收入','Revenue')),'gross_profit':num(pick(r,'營業毛利（毛損）','營業毛利(毛損)','GrossProfit')),'operating_income':num(pick(r,'營業利益（損失）','營業利益(損失)','OperatingIncome')),'net_income':num(pick(r,'本期淨利（淨損）','本期淨利(淨損)','NetIncome')),'eps':num(pick(r,'基本每股盈餘（元）','基本每股盈餘(元)','基本每股盈餘','EPS'))})
 else:base.update({'assets':num(pick(r,'資產總額','資產總計','Assets')),'liabilities':num(pick(r,'負債總額','負債總計','Liabilities')),'equity':num(pick(r,'權益總額','權益總計','Equity')),'cash':num(pick(r,'現金及約當現金','CashAndCashEquivalents'))})
 return base

def run():
 bundle=load_json('alpha_engine.json',{});alpha=bundle.get('alpha') or {};screen=bundle.get('screen') or {};wanted={'2330'}|{str(x.get('ticker')) for x in alpha.get('stocks',[])}|{str(x.get('ticker')) for x in screen.get('deep_research_queue',[]) or []};old=load_json('security_official_facts.json',{'facts':{}});facts=dict(old.get('facts') or {});health={};now=dt.datetime.now(TZ).replace(microsecond=0)
 for kind,url in URLS.items():
  try:
   rows=fetch_json(url);used=0
   for r in rows:
    t=code(r)
    if t not in wanted:continue
    x=compact(kind,r);facts.setdefault(t,{})[kind]=x;used+=1
   health[kind]={'status':'ok','rows':len(rows),'matched':used,'url':url}
  except Exception as e:health[kind]={'status':'last_good' if facts else 'error','message':str(e),'url':url}
 out={'version':1,'updated_at':now.isoformat(),'facts':facts,'source_health':health,'universe':sorted(wanted),'guardrail':'Official facts are numeric evidence only; they cannot create BUY and missing endpoints retain last-good without inventing zero.'};save_json('security_official_facts.json',out);return out
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False,indent=2))
