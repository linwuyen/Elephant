#!/usr/bin/env python3
import json
from common import DATA,save_json

MEMORY={'2408','3006','5351','2451','5289','8299'}
PROPERTY={'6177'}
UTILITY={'8926'}
FINANCIAL=set()

def load(n,d=None):
 p=DATA/n;return json.loads(p.read_text(encoding='utf-8')) if p.exists() else ({} if d is None else d)
def classify(row):
 t=str(row.get('ticker',''));s=' '.join(str(row.get(k,'')) for k in ('name','industry','thesis')).lower()
 if t in MEMORY or any(x in s for x in ('記憶體','memory','dram','nand','flash')):return 'CYCLICAL_MEMORY'
 if t in PROPERTY or any(x in s for x in ('建設','營造','property','construction')):return 'PROPERTY'
 if t in UTILITY or any(x in s for x in ('汽電','電力','utility')):return 'UTILITY'
 if t in FINANCIAL:return 'FINANCIAL'
 if any(x in s for x in ('ai','server','cloud','光通訊','hpc','datacenter')):return 'SECULAR_GROWTH'
 if any(x in s for x in ('控股','資產','holding','asset')):return 'ASSET_NAV'
 return 'GENERAL_INDUSTRIAL'

def effective_model(row,a):
 vm=row.get('valuation_model',{});actual=vm.get('model_type')
 if actual!='scenario_PE':return actual
 if a=='CYCLICAL_MEMORY' and vm.get('normalized_eps') is not None:return 'normalized_midcycle_pe'
 if a=='SECULAR_GROWTH' and vm.get('forward_eps') is not None:return 'scenario_forward_pe'
 if a=='GENERAL_INDUSTRIAL':
  if vm.get('normalized_eps') is not None:return 'normalized_pe'
  if vm.get('forward_eps') is not None:return 'scenario_forward_pe'
 return actual

def generate():
 routes=load('valuation_archetypes.json').get('routes',{});bundle=load('alpha_engine.json');alpha=bundle.get('alpha',{});screen=bundle.get('screen',{});rows=[]
 allrows=[]
 for r in screen.get('deep_research_queue',[]) or []:allrows.append(('DISCOVERY',r))
 for r in alpha.get('stocks',[]) or []:allrows.append(('RESEARCHED',r))
 seen=set()
 for stage,r in allrows:
  t=str(r.get('ticker'))
  if (stage,t) in seen:continue
  seen.add((stage,t));a=classify(r);contract=routes.get(a,{});raw=r.get('valuation_model',{}).get('model_type') if stage=='RESEARCHED' else None;effective=effective_model(r,a) if stage=='RESEARCHED' else None;preferred=contract.get('preferred_models',[])
  rows.append({'stage':stage,'ticker':t,'name':r.get('name'),'archetype':a,'preferred_models':preferred,'required_inputs':contract.get('required_inputs',[]),'current_model':raw,'effective_model':effective,'route_status':'MODEL_FIT' if stage=='RESEARCHED' and effective in preferred else ('REVIEW_MODEL_FIT' if stage=='RESEARCHED' else 'ROUTE_ASSIGNED')})
 out={'version':1,'status':'COMPLETE','routes':rows,'guardrail':'Archetype chooses valuation method; aliases are resolved from actual model inputs and never change Alpha action.'};save_json('valuation_routes.json',out);return out
if __name__=='__main__':print(json.dumps(generate(),ensure_ascii=False,indent=2))
