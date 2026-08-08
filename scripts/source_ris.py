import re,tempfile
from pathlib import Path
from common import *
from minixls import workbook
T1=[('ris.pop.year_end_total','年底人口總數','person'),('ris.pop.total_increase_rate','人口年增加率','per_mille'),('ris.pop.increase_index','人口增加指數','index'),('ris.pop.natural_increase','自然增加人口數','person'),('ris.pop.natural_increase_rate','自然增加率','per_mille'),('ris.pop.births','出生人數','person'),('ris.pop.crude_birth_rate','粗出生率','per_mille'),('ris.pop.deaths','死亡人數','person'),('ris.pop.crude_death_rate','粗死亡率','per_mille')]
T2=[('ris.pop.age_0_14','0–14歲人口','person'),('ris.pop.age_15_64','15–64歲人口','person'),('ris.pop.age_65_plus','65歲以上人口','person'),('ris.pop.share_0_14','0–14歲人口占比','percent'),('ris.pop.share_15_64','15–64歲人口占比','percent'),('ris.pop.share_65_plus','65歲以上人口占比','percent'),('ris.pop.child_dependency_ratio','幼年人口依賴比','percent'),('ris.pop.elderly_dependency_ratio','老年人口依賴比','percent'),('ris.pop.aging_index','老化指數','percent'),('ris.pop.dependency_ratio','扶養比','percent')]
AGE={2:'total',3:'age_0',4:'age_1_4_total',9:'age_5_9',10:'age_10_14',21:'age_65_69',22:'age_70_74',23:'age_75_79',24:'age_80_84',25:'age_85_89',26:'age_90_94',27:'age_95_99',28:'age_100_plus'}
GEO={'新北市':'65000','臺北市':'63000','台北市':'63000','桃園市':'68000','臺中市':'66000','台中市':'66000','臺南市':'67000','台南市':'67000','高雄市':'64000','宜蘭縣':'10002','新竹縣':'10004','苗栗縣':'10005','彰化縣':'10007','南投縣':'10008','雲林縣':'10009','嘉義縣':'10010','屏東縣':'10013','臺東縣':'10014','台東縣':'10014','花蓮縣':'10015','澎湖縣':'10016','基隆市':'10017','新竹市':'10018','嘉義市':'10020','金門縣':'09020','連江縣':'09007'}
def clean(s):
 s=str(s).replace('\u3000',' ').strip(); m=re.search(r'[A-Za-z]',s); return re.sub(r'\s+','',s[:m.start()] if m else s)
def bundle(offline):
 if offline:return Path(offline)/'History-Table-01-2025.xls',Path(offline)/'History-Table-02-2025.xls',Path(offline)/'Table01-y2025.xls','2025'
 for y in range(dt.datetime.now(TZ).year,2022,-1):
  tmp=[]
  try:
   for n in (f'History-Table-01-{y}.xls',f'History-Table-02-{y}.xls',f'Table01-y{y}.xls'):
    p=Path(tempfile.gettempdir())/('elephant_'+n); p.write_bytes(request_bytes(f"{URLS['ris_base']}/{n}",60,2)[0]); tmp.append(p)
   return *tmp,str(y)
  except Exception:pass
 raise RuntimeError('no current RIS annual XLS bundle could be downloaded')
def update(offline=None):
 p1,p2,p3,year=bundle(offline); pop={'generated_from':'automated_official_sources','national':{},'county_history':{},'county_latest':[],'latest_period':None}
 for path,sheet,row0,specs in ((p1,'1',5,T1),(p2,'2',4,T2)):
  cells=workbook(str(path))[sheet]; maxr=max(r for r,c in cells)
  for idx,(iid,name,unit) in enumerate(specs,1):
   data=[[str(int(cells[(r,0)])),float(cells[(r,idx)])] for r in range(row0,maxr+1) if isinstance(cells.get((r,0)),(int,float)) and isinstance(cells.get((r,idx)),(int,float))]
   if data:pop['national'][iid]={'name':name,'unit':unit,'data':data}
 by={}; obs=0
 for sheet,cells in workbook(str(p3)).items():
  if not str(sheet).isdigit():continue
  yr=int(sheet); maxr=max(r for r,c in cells)
  for r in range(4,maxr+1,3):
   name=clean(cells.get((r+1,0),'')); gid=GEO.get(name)
   if not gid:continue
   vals={k:cells.get((r,c)) for c,k in AGE.items()}; total=vals.get('total')
   if not isinstance(total,(int,float)) or total<=0:continue
   young=sum(float(vals[k]) for k in ('age_0','age_1_4_total','age_5_9','age_10_14') if isinstance(vals.get(k),(int,float))); old=sum(float(vals[k]) for k in ('age_65_69','age_70_74','age_75_79','age_80_84','age_85_89','age_90_94','age_95_99','age_100_plus') if isinstance(vals.get(k),(int,float)))
   rec={'period':str(yr),'geo_id':gid,'name':name,'population':round(total),'age_0_14':round(young),'age_65_plus':round(old),'share_65_plus':round(old/total*100,2),'aging_index':round(old/young*100,2) if young else None}; by.setdefault(gid,{'name':name,'data':[]})['data'].append(rec); obs+=1
 for g in by.values():g['data'].sort(key=lambda x:x['period'])
 latest=max((r['period'] for g in by.values() for r in g['data']),default=None); pop['county_history']=by; pop['latest_period']=latest; pop['county_latest']=sorted([g['data'][-1] for g in by.values() if g['data'] and g['data'][-1]['period']==latest],key=lambda x:x['population'],reverse=True)
 if len(pop['national'].get('ris.pop.year_end_total',{}).get('data',[]))<30 or len(pop['county_latest'])<20:raise ValueError('RIS parse validation failed')
 save_json('population.json',pop); return {'latest_period':max_period(pop),'rows':obs,'message':f'RIS annual XLS bundle {year} refreshed'}
