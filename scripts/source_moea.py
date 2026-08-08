import re
from common import *
CODES={'Z','C','I1','I2','I3','I4','24','25','26','27','28','29','30','31','34','2610','2611','2612','2613','2640'}
KEYWORDS=('積體電路','半導體封裝','半導體測試')
def parse(rows,stat,value_col):
 grouped={}
 for r in rows:
  if str(r.get('統計項目','')).strip()!=stat:continue
  y=r.get('資料期(民國年)'); v=num(r.get(value_col))
  if not y or v is None:continue
  p=roc_month(y); code=str(r.get('行業代碼','')).strip(); name=str(r.get('行業別','')).strip()
  if not(code in CODES or any(k in name for k in KEYWORDS)):continue
  item=grouped.setdefault(code or name,{'name':name or code,'data':[]}); item['data'].append([p,v])
 for x in grouped.values():x['data'].sort(key=lambda r:r[0])
 return grouped
def update(offline=None):
 old=load_json('industry.json',{'datasets':{}}); out={'generated_from':'automated_official_sources','datasets':dict(old.get('datasets',{}))}; total=0
 specs=[('moea.industry.production','moea_industrial_production.csv','moea_indprod','moea.industry.production_index','工業生產指數','index_2021_100','生產指數','統計值(指數)'),('moea.manufacturing.sales_volume','moea_manufacturing_sales_volume_index.csv','moea_sales_volume','moea.manufacturing.sales_volume_index','製造業銷售量指數','index_2021_100','銷售量指數','統計值(指數)'),('moea.manufacturing.sales_value','moea_manufacturing_sales_value.csv','moea_sales_value','moea.manufacturing.sales_value','製造業銷售價值','thousand_ntd','銷售價值','統計值(金額)')]
 for ds,fn,urlkey,iid,name,unit,stat,vcol in specs:
  rows=csv_rows_bytes(fetch_or_offline(offline,fn,URLS[urlkey])[0]); total+=len(rows); series=parse(rows,stat,vcol)
  if not series:raise ValueError(f'MOEA parse empty: {ds}')
  out['datasets'][ds]={'indicator_id':iid,'name':name,'unit':unit,'series':series}
 rows=csv_rows_bytes(fetch_or_offline(offline,'moea_manufacturing_investment_operations.csv',URLS['moea_investment'])[0]); total+=len(rows); inv={'series':{}}
 for stat,iid,name in [('營業額','moea.manufacturing.operating_revenue','製造業營業額'),('固定資產增購額','moea.manufacturing.fixed_asset_additions','製造業固定資產增購額')]:
  data=[]
  for r in rows:
   if str(r.get('統計項目','')).strip()!=stat:continue
   y=r.get('資料期(民國年)'); q=str(r.get('資料期(季)','')).strip(); v=num(r.get('統計值(金額)'))
   if y and q and v is not None:data.append([f'{roc_year(y)}-{q if q.startswith("Q") else "Q"+re.sub(r"\D","",q)}',v])
  data.sort(key=lambda x:x[0]); inv['series'][iid]={'name':name,'unit':'thousand_ntd','data':data}
 out['datasets']['moea.manufacturing.investment']=inv; save_json('industry.json',out)
 return {'latest_period':max_period(out),'rows':total,'message':'MOEA d/e/f/ec official CSV refreshed'}
