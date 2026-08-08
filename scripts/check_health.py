#!/usr/bin/env python3
import datetime as dt
import json
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
TZ=ZoneInfo('Asia/Taipei')
NOW=dt.datetime.now(TZ)

status=json.loads((DATA/'status.json').read_text(encoding='utf-8'))
industry=json.loads((DATA/'industry.json').read_text(encoding='utf-8'))
errors=[]

for source in ('dgbas','moea','ris'):
    if status.get('sources',{}).get(source,{}).get('status')!='ok':
        errors.append(f'{source}: source status is not ok')

def year_of(period):
    m=re.match(r'^(\d{4})',str(period or ''))
    return int(m.group(1)) if m else None

def month_age(period):
    m=re.match(r'^(\d{4})-(\d{2})$',str(period or ''))
    if not m:return None
    y,mo=map(int,m.groups())
    return (NOW.year-y)*12+(NOW.month-mo)

# Annual sources should at least contain the previous calendar year by August.
for source in ('dgbas','ris'):
    latest=status.get('sources',{}).get(source,{}).get('latest_period')
    year=year_of(latest)
    if year is None or year < NOW.year-1:
        errors.append(f'{source}: stale annual data, latest={latest}, expected >= {NOW.year-1}')

# MOEA is monthly; allow a four-month publication/revision lag.
moea_latest=status.get('sources',{}).get('moea',{}).get('latest_period')
age=month_age(moea_latest)
if age is None or age > 4:
    errors.append(f'moea: stale core data, latest={moea_latest}, age_months={age}')

# The current-base sales index is a separate series and gets its own freshness gate.
sales=(industry.get('datasets',{}).get('moea.manufacturing.sales_index_current',{})
       .get('series',{}).get('C',{}).get('data',[]))
if not sales:
    errors.append('moea: current sales-index series is missing')
else:
    sales_latest=str(sales[-1][0])
    sales_age=month_age(sales_latest)
    if sales_age is None or sales_age > 4:
        errors.append(f'moea: current sales index stale, latest={sales_latest}, age_months={sales_age}')

if errors:
    print('Health/freshness check failed:', file=sys.stderr)
    for error in errors: print(' - '+error, file=sys.stderr)
    raise SystemExit(1)

print('All critical sources healthy and fresh enough for their publication cadence.')
print('SEGIS remains non-critical until a stable public export or credentials are available.')
