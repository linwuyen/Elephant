#!/usr/bin/env python3
import json, math, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'

def load(n): return json.loads((DATA/n).read_text(encoding='utf-8'))
def fail(msg): print('VALIDATION ERROR:',msg,file=sys.stderr); raise SystemExit(1)
def periods(data): return [str(x[0]) for x in data]
def check_series(name,data,min_points=1):
    if len(data)<min_points: fail(f'{name}: only {len(data)} points')
    ps=periods(data)
    if len(ps)!=len(set(ps)): fail(f'{name}: duplicate periods')
    if ps!=sorted(ps): fail(f'{name}: periods not sorted')
    for p,v in data:
        if not isinstance(v,(int,float)) or not math.isfinite(v): fail(f'{name}: invalid value at {p}: {v}')

macro=load('macro.json'); pop=load('population.json'); ind=load('industry.json'); status=load('status.json')
for iid,minp in [('dgbas.gdp.growth_rate',20),('dgbas.cpi.yoy',10),('dgbas.gdp.nominal.production',8)]:
    s=macro.get('series',{}).get(iid); 
    if not s: fail('missing '+iid)
    check_series(iid,s['data'],minp)
gdp=macro['series']['dgbas.gdp.nominal.production']['data'][-1][1]
if not (1_000_000 < gdp < 100_000_000): fail(f'GDP implausible: {gdp}')
growth=macro['series']['dgbas.gdp.growth_rate']['data'][-1][1]
if not (-30 < growth < 30): fail(f'growth implausible: {growth}')
for iid,minp in [('ris.pop.year_end_total',30),('ris.pop.share_65_plus',30),('ris.pop.births',30),('ris.pop.deaths',30)]:
    s=pop.get('national',{}).get(iid)
    if not s: fail('missing '+iid)
    check_series(iid,s['data'],minp)
latest_pop=pop['national']['ris.pop.year_end_total']['data'][-1][1]
if not (15_000_000 < latest_pop < 30_000_000): fail(f'population implausible: {latest_pop}')
if len(pop.get('county_latest',[]))<20: fail('county latest has fewer than 20 areas')
prod=ind.get('datasets',{}).get('moea.industry.production',{})
if not prod.get('series'): fail('missing MOEA production series')
for key,s in prod['series'].items():
    check_series('industry:'+key,s.get('data',[]),3)
    for p,v in s.get('data',[]):
        if not (0 <= v < 2000): fail(f'industry index implausible {key} {p}: {v}')
for sid in ('dgbas','moea','ris','segis'):
    if sid not in status.get('sources',{}): fail('missing source status '+sid)
print('VALIDATION PASS')
print('macro series:',len(macro['series']))
print('county latest:',len(pop['county_latest']))
print('industry datasets:',len(ind['datasets']))
print('critical failures:',status.get('critical_failures',[]))
