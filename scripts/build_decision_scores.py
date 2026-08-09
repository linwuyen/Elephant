#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt
from common import TZ, load_json, period_key, save_json

WEIGHTS={
 'growth':{'orders':.30,'exports':.20,'production':.20,'sales':.15,'inventory_balance':.15},
 'domestic':{'retail':.25,'food':.15,'real_wage':.25,'unemployment':.20,'employment':.15},
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
        name=k+' '+str(s.get('name','')); low=name.lower(); score=sum(1 for n in needles if n.lower() in low)
        if score:cand.append((score,len(s.get('data',[])),-len(name),k,s))
    return max(cand,default=(0,0,0,None,None))[4]

def find_inventory(series):
    cand=[]
    for k,s in series.items():
        if not k.startswith('inventory.'):continue
        name=str(s.get('name',k))
        if '製造業' not in name or '存貨' not in name:continue
        exact=10 if name.startswith('製造業 /') or name.startswith('製造業/') or name=='製造業' else 0
        cand.append((exact,-len(name),len(s.get('data',[])),s))
    return max(cand,default=(0,0,0,None))[3]

def component(key,name,raw,score,weight,period,note,source):
    if raw is None or score is None:return None
    return {'key':key,'name':name,'raw':round(float(raw),2),'score':round(clamp(score),2),'weight':weight,'period':period,'note':note,'source':source}
def aggregate(parts):
    parts=[p for p in parts if p]; w=sum(p['weight'] for p in parts)
    if not parts or w<.45:return None
    score=sum(p['score']*p['weight'] for p in parts)/w
    return round(score,2),min(100,round(w*100)),parts

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
        order_y=ov; order_p=op; order_score=None if ov is None else ((ov-50)/15*100 if 0<=ov<=100 else change(diff,op,12) or 0); order_note='外銷訂單動向指數 fallback'
    else:order_score=order_y/20*100; order_note='外銷訂單金額 YoY'
    exp=inp.get('customs.exports_total') or ndc.get('customs_exports',{}); _,ep=latest_before(exp,period,1); exp_y=yoy(exp,ep) if ep else None
    prod_y=yoy(prod,period)
    _,sp=latest_before(sales,period,1); sales_y=yoy(sales,sp) if sp else None
    inv=find_inventory(inp) or ndc.get('manufacturing_inventory',{}); _,ip=latest_before(inv,period,2); inv_y=yoy(inv,ip) if ip else None
    gap=None if inv_y is None or sales_y is None else inv_y-sales_y
    parts=[
      component('orders','外銷訂單',order_y,order_score,WEIGHTS['growth']['orders'],order_p,order_note,'MOEA'),
      component('exports','海關出口',exp_y,None if exp_y is None else exp_y/20*100,WEIGHTS['growth']['exports'],ep,'出口總值 YoY','Customs'),
      component('production','製造業生產',prod_y,None if prod_y is None else prod_y/20*100,WEIGHTS['growth']['production'],period,'製造業生產 YoY','MOEA'),
      component('sales','製造業銷售',sales_y,None if sales_y is None else sales_y/12*100,WEIGHTS['growth']['sales'],sp,'銷售資料允許落後 1 個月','MOEA'),
      component('inventory_balance','存貨壓力',gap,None if gap is None else (5-gap)/15*100,WEIGHTS['growth']['inventory_balance'],ip,'製造業存貨 YoY 減銷售 YoY，差距越低越健康','MOEA'),
    ]
    agg=aggregate(parts)
    if not agg:return None
    score,conf,parts=agg; return {'period':period,'score':score,'label':label(score),'confidence':conf,'components':parts}

def domestic_score(period,ndc,inputs):
    inp=inputs.get('series',{})
    retail=find_series(inp,'domestic.',('零售','營業額')) or find_series(inp,'domestic.',('零售',))
    food=find_series(inp,'domestic.',('餐飲','營業額')) or find_series(inp,'domestic.',('餐飲',))
    _,rp=latest_before(retail,period,1); retail_y=yoy(retail,rp) if rp else None
    _,fp=latest_before(food,period,1); food_y=yoy(food,fp) if fp else None
    broad=ndc.get('wholesale_retail_food',{}); _,bp=latest_before(broad,period,2); broad_y=yoy(broad,bp) if bp else None
    if retail_y is None:retail_y= broad_y; rp=bp; retail_note='批零餐飲總體 YoY fallback'
    else:retail_note='零售營業額 YoY'
    wage=inp.get('dgbas.total_monthly_salary') or inp.get('labor.avg_monthly_salary'); _,wp=latest_before(wage,period,2); wage_y=yoy(wage,wp) if wp else None
    cpi=inp.get('labor.cpi_yoy'); cpi_v,cp=latest_before(cpi,wp or period,2); real_wage=None if wage_y is None or cpi_v is None else wage_y-float(cpi_v)
    unemp=inp.get('labor.unemployment_rate') or ndc.get('unemployment_rate',{}); uv,up=latest_before(unemp,period,2)
    emp=inp.get('dgbas.employment_total'); _,emp_p=latest_before(emp,period,2); emp_y=yoy(emp,emp_p) if emp_p else None
    parts=[
      component('retail','零售消費',retail_y,None if retail_y is None else retail_y/10*100,WEIGHTS['domestic']['retail'],rp,retail_note,'MOEA'),
      component('food','餐飲消費',food_y,None if food_y is None else food_y/10*100,WEIGHTS['domestic']['food'],fp,'餐飲營業額 YoY','MOEA'),
      component('real_wage','實質薪資動能',real_wage,None if real_wage is None else real_wage/4*100,WEIGHTS['domestic']['real_wage'],wp,'平均每月總薪資 YoY 減 CPI YoY','DGBAS/MOL'),
      component('unemployment','失業率',uv,None if uv is None else (4-float(uv))/1.5*100,WEIGHTS['domestic']['unemployment'],up,'低於 4% 視為較有利內需','DGBAS/MOL'),
      component('employment','受僱員工人數',emp_y,None if emp_y is None else emp_y/2*100,WEIGHTS['domestic']['employment'],emp_p,'工業及服務業受僱員工人數 YoY','DGBAS'),
    ]
    agg=aggregate(parts)
    if not agg:return None
    score,conf,parts=agg; return {'period':period,'score':score,'label':label(score),'confidence':conf,'components':parts}

def direct_yoy(inp,absolute_key,yoy_key,period,fallback=None):
    ys=inp.get(yoy_key)
    if ys:
        v,p=latest_before(ys,period,2)
        if v is not None:return float(v),p,'CBC'
    s=inp.get(absolute_key) or fallback
    if s:
        _,p=latest_before(s,period,2); y=yoy(s,p) if p else None
        if y is not None:return y,p,'CBC' if inp.get(absolute_key) else 'NDC/CBC'
    return None,None,None

def financial_score(period,ndc,inputs):
    inp=inputs.get('series',{})
    m1y,m1p,m1src=direct_yoy(inp,'cbc.m1b','cbc.m1b_yoy',period,ndc.get('m1b')); m2y,m2p,_=direct_yoy(inp,'cbc.m2','cbc.m2_yoy',period,None); cy,cp,csrc=direct_yoy(inp,'cbc.credit','cbc.credit_yoy',period,ndc.get('financial_loans_investments'))
    rate=inp.get('cbc.interbank_rate') or inp.get('cbc.loan_rate') or ndc.get('new_loan_rate',{}); rv,rp=latest_before(rate,period,2); r12=value(rate,month_shift(rp,-12)) if rp else None; rdelta=None if rv is None or r12 is None else float(rv)-float(r12)
    stocks=inp.get('cbc.stock_index') or ndc.get('stock_index',{}); _,sp=latest_before(stocks,period,1); s6=change(stocks,sp,6) if sp else None
    parts=[
      component('m1b','M1B',m1y,None if m1y is None else m1y/8*100,WEIGHTS['financial']['m1b'],m1p,'M1B YoY',m1src or 'CBC'),
      component('m2','M2',m2y,None if m2y is None else m2y/7*100,WEIGHTS['financial']['m2'],m2p,'M2 YoY','CBC'),
      component('credit','金融機構放款與投資',cy,None if cy is None else cy/8*100,WEIGHTS['financial']['credit'],cp,'放款與投資 YoY',csrc or 'CBC'),
      component('loan_rate','隔夜拆款利率',rdelta,None if rdelta is None else -rdelta/.75*100,WEIGHTS['financial']['loan_rate'],rp,'相較一年前利率下降為正向','CBC'),
      component('stocks','股價環境',s6,None if s6 is None else s6/15*100,WEIGHTS['financial']['stocks'],sp,'股價指數 6M 變化作風險偏好 proxy','CBC'),
    ]
    agg=aggregate(parts)
    if not agg:return None
    score,conf,parts=agg; return {'period':period,'score':score,'label':label(score),'confidence':conf,'components':parts}

def generate():
    industry=load_json('industry.json',{}); ndcobj=load_json('ndc.json',{}); inputs=load_json('decision_inputs.json',{'series':{}}); summary=load_json('summary.json',{})
    ndc=ndcobj.get('series',{}); prod=industry.get('datasets',{}).get('moea.industry.production',{}).get('series',{}).get('C',{}); sales=industry.get('datasets',{}).get('moea.manufacturing.sales_index_current',{}).get('series',{}).get('C',{})
    current_period=latest_period(prod) or ndcobj.get('latest_period')
    current={'growth_persistence':growth_score(current_period,prod,sales,ndc,inputs),'domestic_demand':domestic_score(current_period,ndc,inputs),'financial_conditions':financial_score(current_period,ndc,inputs)}
    allseries=[prod,sales,*ndc.values(),*inputs.get('series',{}).values()]; periods=[p for p in history_periods(allseries,120) if not current_period or p<=current_period]
    history={'growth_persistence':[],'domestic_demand':[],'financial_conditions':[]}
    for p in periods:
        for k,fn in [('growth_persistence',lambda:growth_score(p,prod,sales,ndc,inputs)),('domestic_demand',lambda:domestic_score(p,ndc,inputs)),('financial_conditions',lambda:financial_score(p,ndc,inputs))]:
            r=fn()
            if r:history[k].append({x:r[x] for x in ('period','score','label','confidence')})
    obj={'version':1,'generated_at':dt.datetime.now(TZ).replace(microsecond=0).isoformat(),'current':current,'history':history,'methodology':{'scale':'-100..+100','common_as_of':current_period,'missing':'缺值重新正規化權重，Confidence 依可用權重下降','growth':WEIGHTS['growth'],'domestic':WEIGHTS['domestic'],'financial':WEIGHTS['financial']},'sources':inputs.get('catalogs',{})}; save_json('decision_scores.json',obj)
    summary['decision_scores']={k:v for k,v in current.items() if v}
    if current.get('growth_persistence'):
        g=current['growth_persistence']; summary.setdefault('watchlist',[]).insert(0,f"Growth Persistence {g['score']:+.0f}/100（{g['label']}）：觀察訂單→出口→生產→銷售→存貨是否延續。")
    save_json('summary.json',summary); return obj

if __name__=='__main__':generate()
