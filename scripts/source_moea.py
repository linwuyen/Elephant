import io
import re
import zipfile
from common import *

CODES={'Z','C','I1','I2','I3','I4','24','25','26','27','28','29','30','31','34','2610','2611','2612','2613','2640'}
KEYWORDS=('積體電路','半導體封裝','半導體測試')
SALES_VOLUME_PRIMARY='https://service.moea.gov.tw/EE520/opendata/%E7%B6%93%E6%BF%9F%E9%83%A8%E7%B5%B1%E8%A8%88%E8%99%95_%E8%A3%BD%E9%80%A0%E6%A5%AD%E9%8A%B7%E5%94%AE%E9%87%8F%E6%8C%87%E6%95%B8_%E6%8C%89%E5%9B%9B%E5%A4%A7%E8%A1%8C%E6%A5%AD%E7%B5%B1%E8%A8%88.csv'
SALES_VOLUME_BACKUP='https://dmz9.moea.gov.tw/gmweb/opendata/%E7%B6%93%E6%BF%9F%E9%83%A8%E7%B5%B1%E8%A8%88%E8%99%95_%E8%A3%BD%E9%80%A0%E6%A5%AD%E9%8A%B7%E5%94%AE%E9%87%8F%E6%8C%87%E6%95%B8.zip'

def pick(row,*keys):
    for key in keys:
        value=row.get(key)
        if value is not None and str(value).strip()!='': return value
    return None

def month_period(value):
    digits=re.sub(r'\D','',str(value or ''))
    if len(digits)==6 and int(digits[:4])>=1911:
        year=int(digits[:4]); month=int(digits[4:])
    elif len(digits)>=5:
        year=int(digits[:-2]); month=int(digits[-2:]); year=year if year>=1911 else year+1911
    elif len(digits)==4:
        year=int(digits[:3])+1911; month=int(digits[3:])
    else: raise ValueError(f'unsupported month period: {value!r}')
    if not 1<=month<=12: raise ValueError(f'invalid month: {value!r}')
    return f'{year:04d}-{month:02d}'

def decode_resource(body,url):
    if body[:2]==b'PK':
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            names=[n for n in zf.namelist() if n.lower().endswith(('.csv','.txt')) and not n.endswith('/')]
            if not names: raise ValueError(f'ZIP contains no CSV: {url}')
            body=zf.read(names[0])
    prefix=decode_text(body[:500]).lstrip().lower()
    if prefix.startswith('<!doctype') or prefix.startswith('<html'):
        raise ValueError(f'official resource returned HTML instead of data: {url}')
    rows=csv_rows_bytes(body)
    if not rows: raise ValueError(f'official resource returned no rows: {url}')
    return rows

def resource_rows(offline,filename,url,backups=()):
    if offline: return decode_resource(offline_bytes(offline,filename),str(Path(offline)/filename))
    errors=[]
    for candidate in (url,*backups):
        try:return decode_resource(request_bytes(candidate)[0],candidate)
        except Exception as e:errors.append(f'{candidate}: {type(e).__name__}: {e}')
    raise RuntimeError('all official resource candidates failed | '+' | '.join(errors))

def infer_unit(rows,fallback):
    units=[str(pick(r,'計量單位','單位') or '').strip() for r in rows if pick(r,'計量單位','單位')]
    u=units[0] if units else ''
    if '110年=100' in u or '2021' in u:return 'index_2021_100'
    if '105年=100' in u or '2016' in u:return 'index_2016_100'
    if '千元' in u:return 'thousand_ntd'
    return fallback

def parse(rows,value_cols,aliases=()):
    if isinstance(value_cols,str): value_cols=(value_cols,)
    matched=[r for r in rows if str(pick(r,'統計項目','項目') or '').strip() in aliases]
    def value_of(r): return num(pick(r,*value_cols,'統計值'))
    source=matched if matched else [r for r in rows if value_of(r) is not None]
    grouped={}
    for r in source:
        raw_period=pick(r,'資料期(民國年)','資料期','年月','年月份'); v=value_of(r)
        if not raw_period or v is None:continue
        try:p=month_period(raw_period)
        except Exception:continue
        code=str(pick(r,'行業代碼','產業代碼','代碼') or '').strip()
        name=str(pick(r,'行業別','產業別','行業名稱','統計項目') or '').strip()
        if not(code in CODES or any(k in name for k in KEYWORDS)):continue
        item=grouped.setdefault(code or name,{'name':name or code,'data':[]}); item['data'].append([p,v])
    for x in grouped.values():
        dedup={p:v for p,v in x['data']}; x['data']=[[p,v] for p,v in sorted(dedup.items())]
    return grouped

def update(offline=None):
    old=load_json('industry.json',{'datasets':{}}); out={'generated_from':'automated_official_sources','datasets':dict(old.get('datasets',{}))}; total=0
    specs=[
      ('moea.industry.production','moea_industrial_production.csv',URLS['moea_indprod'],(),'moea.industry.production_index','工業生產指數','index_2021_100',('生產指數',),('統計值(指數)',)),
      ('moea.manufacturing.sales_volume','moea_manufacturing_sales_volume_index.csv',SALES_VOLUME_PRIMARY,(SALES_VOLUME_BACKUP,),'moea.manufacturing.sales_volume_index','製造業銷售指數','index_2021_100',('銷售量指數','銷售指數'),('統計值(指數)','統計值')),
      ('moea.manufacturing.sales_value','moea_manufacturing_sales_value.csv',URLS['moea_sales_value'],(),'moea.manufacturing.sales_value','製造業銷售價值','thousand_ntd',('銷售價值',),('統計值(金額)','統計值'))]
    for ds,fn,url,backups,iid,name,fallback,aliases,vcols in specs:
        rows=resource_rows(offline,fn,url,backups); total+=len(rows); series=parse(rows,vcols,aliases)
        if not series:
            stats=sorted({str(pick(r,'統計項目','項目') or '').strip() for r in rows})[:12]
            raise ValueError(f'MOEA parse empty: {ds}; columns={list(rows[0]) if rows else []}; stats={stats}')
        out['datasets'][ds]={'indicator_id':iid,'name':name,'unit':infer_unit(rows,fallback),'series':series}
    rows=resource_rows(offline,'moea_manufacturing_investment_operations.csv',URLS['moea_investment']); total+=len(rows)
    inv={'name':'製造業投資及營運','unit':'thousand_ntd','series':{}}
    for aliases,iid,name in [(('營業額',),'moea.manufacturing.operating_revenue','製造業營業額'),(('固定資產增購額','固定資產增購'),'moea.manufacturing.fixed_asset_additions','製造業固定資產增購額')]:
        data=[]
        for r in rows:
            stat=str(pick(r,'統計項目','項目') or '').strip()
            if not any(a in stat for a in aliases):continue
            y=pick(r,'資料期(民國年)','年度'); q=str(pick(r,'資料期(季)','季') or '').strip(); v=num(pick(r,'統計值(金額)','統計值'))
            if y and q and v is not None:
                qn=re.sub(r'\D','',q)
                if qn:data.append([f'{roc_year(y)}-Q{qn}',v])
        data=[[p,v] for p,v in sorted(dict(data).items())]
        if not data:raise ValueError(f'MOEA investment parse empty: {iid}')
        inv['series'][iid]={'name':name,'unit':'thousand_ntd','data':data}
    out['datasets']['moea.manufacturing.investment']=inv; save_json('industry.json',out)
    return {'latest_period':max_period(out),'rows':total,'message':'MOEA official d/f/ec + sales-index resource refreshed'}
