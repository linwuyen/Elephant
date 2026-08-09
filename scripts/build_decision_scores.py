#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt, json, math
from pathlib import Path
from common import DATA, TZ, load_json, period_key, save_json

WEIGHTS={
 'growth':{'orders':.30,'exports':.20,'production':.20,'sales':.15,'inventory_balance':.15},
 'domestic':{'retail':.25,'food':.15,'wage':.20,'unemployment':.15,'net_entry':.10,'overtime':.15},
 'financial':{'m1b':.25,'m2':.25,'credit':.25,'loan_rate':.15,'stocks':.10},
}

def clamp(v,lo=-100,hi=100):return max(lo,min(hi,float(v)))
def month_shift(p,d):
    try:y,m=map(int,str(p).split('-'))
    except:return None
    i=y*12+m-1+d; return f'{i//12:04d}-{i%12+1:02d}'
def vmap(s):return {str(p):v for p,v in (s or {}).get('data',[])}
def value(s,p):return vmap(s).get(p)
def latest_before(s,p,max_lag=2):
    for lag in range(max_lag+1):
        q=month_shift(p,-lag); v=value(s,q)
        if v is not None:return v,q
    return None,None
def pct(a,b):return None if a is None or b in (None,0) else (float(a)/float(b)-1)*100
def yoy(s,p):return pct(value(s,p),value(s,month_shift(p,-12)))
def change(s,p,n):return pct(value(s,p),value(s,month_shift(p,-n)))
def latest_period(s):
    d=(s or {}).get('data',[]); return str(d[-1][0]) if d else None

def find_series(series,prefix,needles):
    cand=[]
    for k,s in series.items():
        if prefix and not k.startswith(prefix):continue
        name=(k+' '+str(s.get('name',''))).lower()
        score=sum(1 for n in needles if n.lower() in name)
        if score:cand.append((score,len(s.get('data',[])),k,s))
    return max(cand,default=(0,0,None,None))[3]

def component(key,name,raw,score,weight,period,note,source):
    if raw is None or score is None:return None
    return {'key':key,'name':name,'raw':round(float(raw),2),'score':round(clamp(score),2),'weight':weight,'period':period,'note':note,'source':source}
def aggregate(parts):
    parts=[p for p in parts if p]
    w=sum(p['weight'] for p in parts)
    if not parts or w<.45:return None
    score=sum(p['score']*p['weight'] for p in parts)/w
    confidence=min(100,round(w*100))
    return round(score,2),confidence,parts

def label(score):
    if score>=60:return '非常正向'
    if score>=25:return '正向'
    if score>=5:return '略偏正向'
    if score>-5:return '中性'
    if score>-25:return '略偏負向'
    if score>-60:return '負向'
    return '非常負向'

def history_periods(series_list,months=120):
    ps=set()
    for s in series_list:
        for p,_ in (s or {}).get('data',[]):
            if len(str(p))==7:ps.add(str(p))
    return sorted(ps,key=period_key)[-months:]

def growth_score(period,prod,sales,ndc,inputs):
    inp=inputs.get('series',{})
    order=find_series(inp,'orders.',('外銷訂單','總額')) or find_series(inp,'orders.',('外銷','訂單'))
    order_y=yoy(order,period) if order else None; order_p=period
    if order_y is None:
        diff=ndc.get('export_order_diffusion',{}); ov,op=latest_before(diff,period,1)
        order_y=ov; order_p=op; order_score=None if ov is None else ((ov-50)/15*100 if 0<=ov<=100 else change(diff,op,12) or 0)
        order_note='外銷訂單動向指數 fallback'
    else:
        order_score=order_y/20*100; order_note='外銷訂單金額 YoY'
    exp=ndc.get('customs_exports',{}); ev,ep=latest_before(exp,period,1); exp_y=yoy(exp,ep) if ep else None
    prod_y=yoy(prod,period)
    sv,sp=latest_before(sales,period,1); sales_y=yoy(sales,sp) if sp else None
    inv=ndc.get('manufacturing_inventory',{}); iv,ip=latest_before(inv,period,2); inv_y=yoy(inv,ip) if ip else None
    gap=None if inv_y is None or sales_y is None else inv_y-sales_y
    parts=[
      component('orders','外銷訂單',order_y,order_score,WEIGHTS['growth']['orders'],order_p,order_note,'MOEA/NDC'),
      component('exports','海關出口',exp_y,None if exp_y is None else exp_y/20*100,WEIGHTS['growth']['exports'],ep,'出口 YoY','NDC/Customs'),
      component('production','製造業生產',prod_y,None if prod_y is None else prod_y/20*100,WEIGHTS['growth']['production'],period,'製造業生產 YoY','MOEA'),
      component('sales','製造業銷售',sales_y,None if sales_y is None else sales_y/12*100,WEIGHTS['growth']['sales'],sp,'銷售資料允許落後 1 個月','MOEA'),
      component('inventory_balance','存貨壓力',gap,None if gap is None else (5-gap)/15*100,WEIGHTS['growth']['inventory_balance'],ip,'存貨 YoY 減銷售 YoY，差距越低越健康','NDC'),
    ]
    agg=aggregate(parts)
    if not agg:return None
    score,conf,parts=agg
    return {'period':period,'score':score,'label':label(score),'confidence':conf,'components':parts}

def domestic_score(period,ndc,inputs):
    inp=inputs.get('series',{})
    retail=find_series(inp,'domestic.',('零售','營業額')) or find_series(inp,'domestic.',('零售',))
    food=find_series(inp,'domestic.',('餐飲','營業額')) or find_series(inp,'domestic.',('餐飲',))
    wage=inp.get('labor.avg_monthly_salary')
    unemp=inp.get('labor.unemployment_rate') or ndc.get('unemployment_rate',{})
    retail_y=yoy(retail,period) if retail else None; food_y=yoy(food,period) if food else None; wage_y=yoy(wage,period) if wage else None
    uv,up=latest_before(unemp,period,2)
    net=ndc.get('employee_net_entry_rate',{}); nv,np=latest_before(net,period,2)
    ot=ndc.get('overtime_hours',{}); ov,op=latest_before(ot,period,2); ot_y=yoy(ot,op) if op else None
    broad=ndc.get('wholesale_retail_food',{}); bv,bp=latest_before(broad,period,2); broad_y=yoy(broad,bp) if bp else None
    if retail_y is None:retail_y=broad_y; period_r=bp; retail_note='批零餐飲總體 YoY fallback'
    else:period_r=period; retail_note='零售營業額 YoY'
    parts=[
      component('retail','零售消費',retail_y,None if retail_y is None else retail_y/10*100,WEIGHTS['domestic']['retail'],period_r,retail_note,'MOEA/NDC'),
      component('food','餐飲消費',food_y,None if food_y is None else food_y/10*100,WEIGHTS['domestic']['food'],period,'餐飲營業額 YoY','MOEA'),
      component('wage','平均薪資',wage_y,None if wage_y is None else wage_y/6*100,WEIGHTS['domestic']['wage'],period,'平均月薪資 YoY；未做實質化時降低解讀強度','MOL/DGBAS'),
      component('unemployment','失業率',uv,None if uv is None else (4-float(uv))/1.5*100,WEIGHTS['domestic']['unemployment'],up,'低於 4% 視為較有利內需','DGBAS/NDC'),
      component('net_entry','受僱員工淨進入率',nv,None if nv is None else float(nv)/1.0*100,WEIGHTS['domestic']['net_entry'],np,'就業流入越高越正向','NDC'),
      component('overtime','加班工時',ot_y,None if ot_y is None else ot_y/10*100,WEIGHTS['domestic']['overtime'],op,'加班工時 YoY 作為勞動需求 proxy','NDC'),
    ]
    agg=aggregate(parts)
    if not agg:return None
    score,conf,parts=agg
    return {'period':period,'score':score,'label':label(score),'confidence':conf,'components':parts}

def direct_yoy(inp,absolute_key,yoy_key,period,fallback=None):
    ys=inp.get(yoy_key)
    if ys:
        v,p=latest_before(ys,period,2)
        if v is not None:return float(v),p,'CBC'
    s=inp.get(absolute_key) or fallback
    if s:
        v,p=latest_before(s,period,2)
        y=yoy(s,p) if p else None
        if y is not None:return y,p,'CBC' if inp.get(absolute_key) else 'NDC/CBC'
    return None,None,None

def financial_score(period,ndc,inputs):
    inp=inputs.get('series',{})
    m1y,m1p,m1src=direct_yoy(inp,'cbc.m1b','cbc.m1b_yoy',period,ndc.get('m1b'))
    m2y,m2p,m2src=direct_yoy(inp,'cbc.m2','cbc.m2_yoy',period,None)
    cy,cp,csrc=direct_yoy(inp,'cbc.credit','cbc.credit_yoy',period,ndc.get('financial_loans_investments'))
    rate=inp.get('cbc.interbank_rate') or inp.get('cbc.loan_rate') or ndc.get('new_loan_rate',{})
    rv,rp=latest_before(rate,period,2); r12=value(rate,month_shift(rp,-12)) if rp else None; rdelta=None if rv is None or r12 is None else float(rv)-float(r12)
    stocks=inp.get('cbc.stock_index') or ndc.get('stock_index',{}); sv,sp=latest_before(stocks,period,1); s6=change(stocks,sp,6) if sp else None
    parts=[
      component('m1b','M1B',m1y,None if m1y is None else m1y/8*100,WEIGHTS['financial']['m1b'],m1p,'M1B YoY',m1src or 'CBC'),
      component('m2','M2',m2y,None if m2y is None else m2y/7*100,WEIGHTS['financial']['m2'],m2p,'M2 YoY','CBC'),
      component('credit','金融機構放款與投資',cy,None if cy is None else cy/8*100,WEIGHTS['financial']['credit'],cp,'放款與投資 YoY',csrc or 'CBC'),
      component('loan_rate','隔夜拆款利率',rdelta,None if rdelta is None else -rdelta/.75*100,WEIGHTS['financial']['loan_rate'],rp,'相較一年前利率下降為正向；使用央行金融業隔夜拆款加權平均利率','CBC'),
      component('stocks','股價環境',s6,None if s6 is None else s6/15*100,WEIGHTS['financial']['stocks'],sp,'央行金融統計月報股價指數 6M 變化作風險偏好 proxy','CBC'),
    ]
    agg=aggregate(parts)
    if not agg:return None
    score,conf,parts=agg
    return {'period':period,'score':score,'label':label(score),'confidence':conf,'components':parts}

def generate():
    industry=load_json('industry.json',{}); ndcobj=load_json('ndc.json',{}); inputs=load_json('decision_inputs.json',{'series':{}}); summary=load_json('summary.json',{})
    ndc=ndcobj.get('series',{}); prod=(industry.get('datasets',{}).get('moea.industry.production',{}).get('series',{}).get('C',{})); sales=(industry.get('datasets',{}).get('moea.manufacturing.sales_index_current',{}).get('series',{}).get('C',{}))
    current_period=latest_period(prod) or ndcobj.get('latest_period')
    current={'growth_persistence':growth_score(current_period,prod,sales,ndc,inputs),'domestic_demand':domestic_score(current_period,ndc,inputs),'financial_conditions':financial_score(current_period,ndc,inputs)}
    allseries=[prod,sales,*ndc.values(),*inputs.get('series',{}).values()]
    periods=[p for p in history_periods(allseries,120) if not current_period or p<=current_period]
    history={'growth_persistence':[],'domestic_demand':[],'financial_conditions':[]}
    for p in periods:
        for k,fn in [('growth_persistence',lambda:growth_score(p,prod,sales,ndc,inputs)),('domestic_demand',lambda:domestic_score(p,ndc,inputs)),('financial_conditions',lambda:financial_score(p,ndc,inputs))]:
            r=fn()
            if r:history[k].append({x:r[x] for x in ('period','score','label','confidence')})
    obj={'version':1,'generated_at':dt.datetime.now(TZ).replace(microsecond=0).isoformat(),'current':current,'history':history,'methodology':{'scale':'-100..+100','common_as_of':current_period,'missing':'缺值重新正規化權重，Confidence 依可用權重下降','growth':WEIGHTS['growth'],'domestic':WEIGHTS['domestic'],'financial':WEIGHTS['financial']},'sources':inputs.get('catalogs',{})}
    save_json('decision_scores.json',obj)
    summary['decision_scores']={k:v for k,v in current.items() if v}
    if current.get('growth_persistence'):
        g=current['growth_persistence']; summary.setdefault('watchlist',[]).insert(0,f"Growth Persistence {g['score']:+.0f}/100（{g['label']}）：觀察訂單→出口→生產→銷售是否延續。")
    save_json('summary.json',summary)
    return obj

if __name__=='__main__':generate()
