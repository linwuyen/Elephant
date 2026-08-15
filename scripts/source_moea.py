import io
import re
import zipfile
from html.parser import HTMLParser
from common import *
from source_moea_live import base_year, fetch_live_page, validate_live_page

CODES={'Z','C','I1','I2','I3','I4','24','25','26','27','28','29','30','31','34','2610','2611','2612','2613','2640'}
KEYWORDS=('積體電路','半導體封裝','半導體測試')
SALES_INDEX_PAGE='https://service.moea.gov.tw/EE521/common/Common.aspx?code=D&no=5'

SALES_POS={
 'C':(0,'製造業'),'I1':(1,'金屬機電工業'),'24':(2,'基本金屬製造業'),'25':(3,'金屬製品製造業'),
 '28':(4,'電力設備及配備製造業'),'29':(5,'機械設備製造業'),'30':(6,'汽車及其零件製造業'),
 '31':(7,'其他運輸工具及其零件製造業'),'34':(8,'產業用機械設備維修及安裝業'),
 'I2':(9,'資訊電子工業'),'26':(10,'電子零組件製造業'),'27':(11,'電腦、電子產品及光學製品製造業'),
 'I3':(12,'化學工業'),'I4':(22,'民生工業')}

class RowsParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows=[]; self.row=None; self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='tr': self.row=[]
        elif tag in ('td','th') and self.row is not None: self.cell=[]
    def handle_data(self,data):
        if self.cell is not None: self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None and self.row is not None:
            self.row.append(re.sub(r'\s+',' ',''.join(self.cell)).strip()); self.cell=None
        elif tag=='tr' and self.row is not None:
            if self.row:self.rows.append(self.row)
            self.row=None

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

def resource_rows(offline,filename,url):
    body=offline_bytes(offline,filename) if offline else request_bytes(url)[0]
    return decode_resource(body,url)

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

def parse_live_sales_index(body):
    text=validate_live_page(body,'製造業銷售指數')
    hp=RowsParser(); hp.feed(text); current_year=None
    series={k:{'name':name,'data':[]} for k,(pos,name) in SALES_POS.items()}
    for row in hp.rows:
        for cell in row:
            m=re.fullmatch(r'(\d{3})年',cell)
            if m: current_year=int(m.group(1))+1911; break
        mi=next((i for i,c in enumerate(row) if re.fullmatch(r'\d{1,2}月',c)),None)
        if mi is None or current_year is None: continue
        month=int(re.sub(r'\D','',row[mi])); values=[]
        for cell in row[mi+1:]:
            v=num(cell)
            if v is not None: values.append(v)
        if len(values)<23: continue
        period=f'{current_year:04d}-{month:02d}'
        for key,(pos,name) in SALES_POS.items():
            if pos<len(values): series[key]['data'].append([period,values[pos]])
    for item in series.values():
        item['data']=[[p,v] for p,v in sorted(dict(item['data']).items())]
    if len(series['C']['data'])<5: raise ValueError(f'MOEA live sales-index parse too few months: {len(series["C"]["data"])}')
    return {'indicator_id':'moea.manufacturing.sales_index_current','name':'製造業銷售指數（現行基期）','unit':f'index_{base_year(body)}_100','series':series}

def live_sales_index():
    body=fetch_live_page(SALES_INDEX_PAGE,'製造業銷售指數',60,3)
    return parse_live_sales_index(body)

def update(offline=None):
    old=load_json('industry.json',{'datasets':{}})
    out={'generated_from':'automated_official_sources','datasets':dict(old.get('datasets',{}))}; total=0; warnings=[]

    # Required core dataset: current industrial production.
    rows=resource_rows(offline,'moea_industrial_production.csv',URLS['moea_indprod']); total+=len(rows)
    series=parse(rows,('統計值(指數)','統計值'),('生產指數',))
    if not series: raise ValueError('MOEA core production parse empty')
    out['datasets']['moea.industry.production']={'indicator_id':'moea.industry.production_index','name':'工業生產指數','unit':infer_unit(rows,'index_2021_100'),'series':series}

    # Sales is an exact published indicator but the EE521 ASP.NET transport is not
    # machine-stable on GitHub runners. Keep the last-good MOEA series when that
    # transport fails; Decision Score has an exact NDC republication fallback for
    # 製造業銷售量指數, so an HTML delivery outage must not take down core MOEA health.
    sales_refreshed=False
    if offline:
        rows=resource_rows(offline,'moea_manufacturing_sales_volume_index.csv',URLS['moea_sales_volume']); total+=len(rows)
        oldseries=parse(rows,('統計值(指數)','統計值'),('銷售量指數','銷售指數'))
        if not oldseries: raise ValueError('MOEA archived sales-volume parse empty')
        out['datasets']['moea.manufacturing.sales_volume']={'indicator_id':'moea.manufacturing.sales_volume_index','name':'製造業銷售量指數（歷史基期）','unit':infer_unit(rows,'index_2016_100'),'series':oldseries}
        sales_refreshed=True
    else:
        try:
            out['datasets']['moea.manufacturing.sales_index_current']=live_sales_index()
            sales_refreshed=True
        except Exception as e:
            warnings.append(f'current sales live transport unavailable; retained last-good MOEA series and Decision Score may use exact NDC 製造業銷售量指數 fallback ({type(e).__name__}: {e})')

    # Supplemental legacy datasets: preserve the last good copy if MOEA retires the old download URL.
    try:
        rows=resource_rows(offline,'moea_manufacturing_sales_value.csv',URLS['moea_sales_value']); total+=len(rows)
        series=parse(rows,('統計值(金額)','統計值'),('銷售價值',))
        if series: out['datasets']['moea.manufacturing.sales_value']={'indicator_id':'moea.manufacturing.sales_value','name':'製造業銷售價值','unit':infer_unit(rows,'thousand_ntd'),'series':series}
        else: warnings.append('sales_value parser returned no usable series; retained last-good copy')
    except Exception as e:
        warnings.append(f'sales_value legacy endpoint unavailable; retained last-good copy ({type(e).__name__})')

    try:
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
            if data: inv['series'][iid]={'name':name,'unit':'thousand_ntd','data':data}
        if inv['series']: out['datasets']['moea.manufacturing.investment']=inv
        else: warnings.append('investment parser returned no usable series; retained last-good copy')
    except Exception as e:
        warnings.append(f'investment legacy endpoint unavailable; retained last-good copy ({type(e).__name__})')

    save_json('industry.json',out)
    message='MOEA core production refreshed'
    if sales_refreshed: message+='; current sales index refreshed'
    else: message+='; sales HTML transport unavailable, exact official-series fallback remains available'
    if warnings: message+='; warnings: '+'; '.join(warnings)
    return {'latest_period':max_period(out),'rows':total,'message':message,'warnings':warnings}