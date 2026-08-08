#!/usr/bin/env python3
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'

def load(n, default=None):
    p = DATA / n
    if not p.exists():
        return {} if default is None else default
    return json.loads(p.read_text(encoding='utf-8'))

def fail(msg):
    print('VALIDATION ERROR:', msg, file=sys.stderr)
    raise SystemExit(1)

def periods(data):
    return [str(x[0]) for x in data]

def check_series(name, data, min_points=1):
    if len(data) < min_points:
        fail(f'{name}: only {len(data)} points')
    ps = periods(data)
    if len(ps) != len(set(ps)):
        fail(f'{name}: duplicate periods')
    if ps != sorted(ps):
        fail(f'{name}: periods not sorted')
    for p, v in data:
        if not isinstance(v, (int, float)) or not math.isfinite(v):
            fail(f'{name}: invalid value at {p}: {v}')

macro = load('macro.json')
pop = load('population.json')
ind = load('industry.json')
status = load('status.json')
summary = load('summary.json')
ndc = load('ndc.json', {})
revisions = load('revisions.json', {'history': [], 'new_revisions': []})

for iid, minp in [('dgbas.gdp.growth_rate', 20), ('dgbas.cpi.yoy', 10), ('dgbas.gdp.nominal.production', 8)]:
    s = macro.get('series', {}).get(iid)
    if not s:
        fail('missing ' + iid)
    check_series(iid, s['data'], minp)

gdp = macro['series']['dgbas.gdp.nominal.production']['data'][-1][1]
if not (1_000_000 < gdp < 100_000_000):
    fail(f'GDP implausible: {gdp}')
growth = macro['series']['dgbas.gdp.growth_rate']['data'][-1][1]
if not (-30 < growth < 30):
    fail(f'growth implausible: {growth}')

for iid, minp in [('ris.pop.year_end_total', 30), ('ris.pop.share_65_plus', 30), ('ris.pop.births', 30), ('ris.pop.deaths', 30)]:
    s = pop.get('national', {}).get(iid)
    if not s:
        fail('missing ' + iid)
    check_series(iid, s['data'], minp)

latest_pop = pop['national']['ris.pop.year_end_total']['data'][-1][1]
if not (15_000_000 < latest_pop < 30_000_000):
    fail(f'population implausible: {latest_pop}')
if len(pop.get('county_latest', [])) < 20:
    fail('county latest has fewer than 20 areas')

prod = ind.get('datasets', {}).get('moea.industry.production', {})
if not prod.get('series'):
    fail('missing MOEA production series')
for key, s in prod['series'].items():
    check_series('industry:' + key, s.get('data', []), 3)
    for p, v in s.get('data', []):
        if not (0 <= v < 2000):
            fail(f'industry index implausible {key} {p}: {v}')

for sid in ('dgbas', 'moea', 'ris', 'ndc', 'segis'):
    if sid not in status.get('sources', {}):
        fail('missing source status ' + sid)

if status.get('sources', {}).get('ndc', {}).get('status') == 'ok':
    for iid in ('leading_no_trend', 'coincident_no_trend', 'policy_score'):
        s = ndc.get('series', {}).get(iid)
        if not s:
            fail('missing NDC series ' + iid)
        check_series('ndc:' + iid, s.get('data', []), 12)
    pmi = ndc.get('series', {}).get('pmi')
    if pmi:
        check_series('ndc:pmi', pmi.get('data', []), 6)
        if not (0 < pmi['data'][-1][1] < 100):
            fail('NDC PMI implausible')

if summary.get('version') != 2:
    fail('summary version missing/unsupported')
if not summary.get('headline') or not summary.get('stance'):
    fail('summary headline missing')
if len(summary.get('takeaways', [])) < 3:
    fail('summary has fewer than 3 takeaways')
if summary.get('data_last_check_at') != status.get('last_check_at'):
    fail('summary not built from current status snapshot')

cycle = summary.get('cycle', {})
score = cycle.get('score')
if score is None or not (-100 <= score <= 100):
    fail(f'invalid cycle score: {score}')
mom = cycle.get('momentum_score')
if mom is None or not (-100 <= mom <= 100):
    fail(f'invalid momentum score: {mom}')
breadth = cycle.get('breadth')
if breadth is not None and not (0 <= breadth <= 100):
    fail(f'invalid industry breadth: {breadth}')
components = cycle.get('components', [])
if len(components) < 3:
    fail('cycle score has too few components')

conf = summary.get('confidence', {})
if conf.get('score') is None or not (0 <= conf['score'] <= 100):
    fail('invalid confidence score')
if conf.get('label') not in ('High', 'Medium', 'Low'):
    fail('invalid confidence label')

snap = summary.get('snapshot', {})
if not snap.get('fingerprint') or len(snap.get('fingerprint')) < 8:
    fail('summary snapshot fingerprint missing')
if len(snap.get('metrics', {})) < 5:
    fail('summary snapshot has too few metrics')

for row in summary.get('turning_points', []):
    if row.get('significance') is None or not (0 <= row['significance'] <= 100):
        fail('invalid turning point significance')
for row in summary.get('divergences', []):
    if row.get('severity') is None or not (0 <= row['severity'] <= 100):
        fail('invalid divergence severity')

if revisions.get('version') != 1:
    fail('revision tracker version missing')
for r in revisions.get('new_revisions', []):
    if not all(k in r for k in ('source', 'dataset', 'series', 'period', 'old', 'new')):
        fail('malformed revision record')

print('VALIDATION PASS')
print('macro series:', len(macro['series']))
print('county latest:', len(pop['county_latest']))
print('industry datasets:', len(ind['datasets']))
print('ndc series:', len(ndc.get('series', {})))
print('summary takeaways:', len(summary.get('takeaways', [])))
print('turning points:', len(summary.get('turning_points', [])))
print('divergences:', len(summary.get('divergences', [])))
print('cycle score:', summary.get('cycle', {}).get('score'))
print('confidence:', summary.get('confidence', {}).get('label'))
print('critical failures:', status.get('critical_failures', []))
