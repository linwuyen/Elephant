import re
from common import *
CODES={'Z','C','I1','I2','I3','I4','24','25','26','27','28','29','30','31','34','2610','2611','2612','2613','2640'}
KEYWORDS=('積體電路','半導體封裝','半導體測試')

def infer_unit(rows,fallback):
    units=[str(r.get('計量單位','')).strip() for r in rows if str(r.get('計量單位','')).strip()]
    u=units[0] if units else ''
    if '110年=100' in u or '2021' in u:return 'index_2021_100'
    if '105年=100' in u or '2016' in u:return 'index_2016_100'
    if '千元' in u:return 'thousand_ntd'
    return fallback

def parse(rows,value_col,aliases=()):
    matched=[r for r in rows if str(r.get('統計項目','')).strip() in aliases]
    source=matched if matched else [r for r in rows if num(r.get(value_col)) is not None]
    grouped={}
    for r in source:
        y=r.get('資料期(民國年)'); v=num(r.get(value_col))
        if not y or v is None:continue
        try:p=roc_month(y)
        except Exception:continue
        code=str(r.get('行業代碼','')).strip(); name=str(r.get('行業別','')).strip()
        if not(code in CODES or any(k in name for k in KEYWORDS)):continue
        item=grouped.setdefault(code or name,{'name':name or code,'data':[]})
        item['data'].append([p,v])
    for x in grouped.values():
        dedup={p:v for p,v in x['data']}; x['data']=sorted(dedup.items())
    return grouped

def update(offline=None):
    old=load_json('industry.json',{'datasets':{}})
    out={'generated_from':'automated_official_sources','datasets':dict(old.get('datasets',{}))}; total=0
    specs=[
      ('moea.industry.production','moea_industrial_production.csv','moea_indprod','moea.industry.production_index','工業生產指數','index_2021_100',('生產指數',),'統計值(指數)'),
      ('moea.manufacturing.sales_volume','moea_manufacturing_sales_volume_index.csv','moea_sales_volume','moea.manufacturing.sales_volume_index','製造業銷售指數','index_2021_100',('銷售量指數','銷售指數'),'統計值(指數)'),
      ('moea.manufacturing.sales_value','moea_manufacturing_sales_value.csv','moea_sales_value','moea.manufacturing.sales_value','製造業銷售價值','thousand_ntd',('銷售價值',),'統計值(金額)')]
    for ds,fn,urlkey,iid,name,fallback,aliases,vcol in specs:
        rows=csv_rows_bytes(fetch_or_offline(offline,fn,URLS[urlkey])[0]); total+=len(rows)
        series=parse(rows,vcol,aliases)
        if not series:
            stats=sorted({str(r.get('統計項目','')).strip() for r in rows})[:12]
            raise ValueError(f'MOEA parse empty: {ds}; columns={list(rows[0]) if rows else []}; stats={stats}')
        out['datasets'][ds]={'indicator_id':iid,'name':name,'unit':infer_unit(rows,fallback),'series':series}
    rows=csv_rows_bytes(fetch_or_offline(offline,'moea_manufacturing_investment_operations.csv',URLS['moea_investment'])[0]); total+=len(rows)
    inv={'name':'製造業投資及營運','unit':'thousand_ntd','series':{}}
    for aliases,iid,name in [(('營業額',),'moea.manufacturing.operating_revenue','製造業營業額'),(('固定資產增購額','固定資產增購'),'moea.manufacturing.fixed_asset_additions','製造業固定資產增購額')]:
        data=[]
        for r in rows:
            stat=str(r.get('統計項目','')).strip()
            if not any(a in stat for a in aliases):continue
            y=r.get('資料期(民國年)'); q=str(r.get('資料期(季)','')).strip(); v=num(r.get('統計值(金額)'))
            if y and q and v is not None:
                qn=re.sub(r'\D','',q)
                if qn:data.append([f'{roc_year(y)}-Q{qn}',v])
        data=sorted(dict(data).items())
        if not data:raise ValueError(f'MOEA investment parse empty: {iid}')
        inv['series'][iid]={'name':name,'unit':'thousand_ntd','data':data}
    out['datasets']['moea.manufacturing.investment']=inv
    save_json('industry.json',out)
    return {'latest_period':max_period(out),'rows':total,'message':'MOEA d/e/f/ec official CSV refreshed'}
