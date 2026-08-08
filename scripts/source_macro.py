import html,json,re
from common import *
GDP_COLS={
'GDP(生產面)(百萬元)':('dgbas.gdp.nominal.production','國內生產毛額 GDP（生產面，名目值）'),
'農、林、漁、牧業(百萬元)':('dgbas.gdp.industry.agriculture','農、林、漁、牧業 GDP（名目值）'),
'工業(1)~(5)(百萬元)':('dgbas.gdp.industry.industry_total','工業 GDP（名目值）'),
'礦業及土石採取業(1)(百萬元)':('dgbas.gdp.industry.mining','礦業及土石採取業 GDP（名目值）'),
'製造業(2)(百萬元)':('dgbas.gdp.industry.manufacturing','製造業 GDP（名目值）'),
'電力及燃氣供應業(3)(百萬元)':('dgbas.gdp.industry.electricity_gas','電力及燃氣供應業 GDP（名目值）'),
'用水供應及污染整治業(4)(百萬元)':('dgbas.gdp.industry.water_remediation','用水供應及污染整治業 GDP（名目值）'),
'營造工程業(5)(百萬元)':('dgbas.gdp.industry.construction','營造工程業 GDP（名目值）'),
'服務業(6)~(20)(百萬元)':('dgbas.gdp.industry.services_total','服務業 GDP（名目值）'),
'批發及零售業(6)(百萬元)':('dgbas.gdp.industry.wholesale_retail','批發及零售業 GDP（名目值）'),
'運輸及倉儲業(7)(百萬元)':('dgbas.gdp.industry.transport_storage','運輸及倉儲業 GDP（名目值）'),
'住宿及餐飲業(8)(百萬元)':('dgbas.gdp.industry.accommodation_food','住宿及餐飲業 GDP（名目值）'),
'出版、影音製作、傳播及資通訊服務業(9)(百萬元)':('dgbas.gdp.industry.information_communication','出版、影音、傳播及資通訊服務業 GDP（名目值）'),
'金融及保險業(10)(百萬元)':('dgbas.gdp.industry.finance_insurance','金融及保險業 GDP（名目值）'),
'不動產及住宅服務業(11)(百萬元)':('dgbas.gdp.industry.real_estate','不動產及住宅服務業 GDP（名目值）'),
'專業、科學及技術服務業(12)(百萬元)':('dgbas.gdp.industry.professional_scientific','專業、科學及技術服務業 GDP（名目值）'),
'支援服務業(13)(百萬元)':('dgbas.gdp.industry.support_services','支援服務業 GDP（名目值）'),
'公共行政及國防；強制性社會安全(14)(百萬元)':('dgbas.gdp.industry.public_admin_defense','公共行政及國防；強制性社會安全 GDP（名目值）'),
'教育業(15)(百萬元)':('dgbas.gdp.industry.education','教育業 GDP（名目值）'),
'醫療保健及社會工作服務業(16)(百萬元)':('dgbas.gdp.industry.health_social','醫療保健及社會工作服務業 GDP（名目值）'),
'藝術、娛樂及休閒服務業(17)(百萬元)':('dgbas.gdp.industry.arts_recreation','藝術、娛樂及休閒服務業 GDP（名目值）'),
'其他服務業(18)(百萬元)':('dgbas.gdp.industry.other_services','其他服務業 GDP（名目值）'),
'進口稅(19)(百萬元)':('dgbas.gdp.industry.import_duties','進口稅'),
'加值型營業稅(20)(百萬元)':('dgbas.gdp.industry.vat','加值型營業稅')}

def resolve_ndc():
 candidates=[]
 try:
  meta=json.loads(decode_text(request_bytes(URLS['ndc_meta'])[0]))
  def walk(x):
   if isinstance(x,dict):
    for v in x.values():
     if isinstance(v,str) and v.startswith('http') and ('csv' in v.lower() or 'download.ashx' in v.lower()):candidates.append(v)
     else:walk(v)
   elif isinstance(x,list):
    for v in x:walk(v)
  walk(meta)
 except Exception:pass
 if candidates:return candidates[0]
 page=html.unescape(decode_text(request_bytes(URLS['ndc_dataset'])[0]))
 m=re.search(r'https://ws\.ndc\.gov\.tw/Download\.ashx\?[^"\'<> ]+',page)
 if not m:raise RuntimeError('cannot resolve NDC GDP CSV resource URL')
 return m.group(0).replace('&amp;','&')

def update(offline=None):
 old=load_json('macro.json',{'series':{}}); out={'generated_from':'automated_official_sources','series':dict(old.get('series',{}))}
 rows=csv_rows_bytes(fetch_or_offline(offline,'mol_annual_major_economic_indicators.csv',URLS['mol_macro'])[0])
 specs=[('dgbas.gdp.growth_rate','經濟成長率','percent','經濟成長率','dgbas.gdp.common'),('dgbas.cpi.index','消費者物價指數','index','消費者物價-指數','dgbas.cpi.basic'),('dgbas.cpi.yoy','消費者物價指數年增率','percent','消費者物價-年增率','dgbas.cpi.basic')]
 for iid,name,unit,col,did in specs:
  data=[[str(r['年度']).strip(),num(r.get(col))] for r in rows if str(r.get('年度','')).strip() and num(r.get(col)) is not None]
  if len(data)<10:raise ValueError(f'MOL parse too few rows for {iid}')
  out['series'][iid]={'name':name,'unit':unit,'frequency':'annual','dataset_id':did,'data':data}
 nb=offline_bytes(offline,'ndc_industry_gdp_nominal.csv') if offline else request_bytes(resolve_ndc())[0]; nrows=csv_rows_bytes(nb)
 for col,(iid,name) in GDP_COLS.items():
  data=[[roc_year(r['民國年']),num(r.get(col))] for r in nrows if r.get('民國年') and num(r.get(col)) is not None]
  if data:out['series'][iid]={'name':name,'unit':'million_ntd','frequency':'annual','dataset_id':'dgbas.gdp.common','data':data}
 if len(out['series'].get('dgbas.gdp.nominal.production',{}).get('data',[]))<8:raise ValueError('NDC nominal GDP parse failed')
 save_json('macro.json',out); return {'latest_period':max_period(out),'rows':len(rows)+len(nrows),'message':'MOL annual GDP-growth/CPI + NDC nominal GDP refreshed'}
