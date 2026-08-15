#!/usr/bin/env python3
import source_moea as moea
import source_moea_live_tables as live

rows=['<html><body><table>','<tr><th>年</th><th>月</th><th>製造業</th></tr>']
# Deliberately omit mutable title/base-year prose. The parser contract is table
# structure + plausible data; transport health is handled separately.
for i in range(13):
    y=114 if i<8 else 115
    m=i+5 if i<8 else i-7
    if i in (0,8):rows.append(f'<tr><td>{y}年</td><td>{"" if i==0 else "1-5月"}</td><td>999</td></tr>')
    vals=[f'{100+i+j/10:.2f}' for j in range(33)]
    rows.append('<tr><td></td><td>'+str(m)+'月</td>'+''.join(f'<td>{x}</td>' for x in vals)+'</tr>')
rows.append('</table></body></html>')
body=''.join(rows).encode('utf-8')

sales=live.parse_sales(body,min_observations=13)
assert len(sales['series']['C']['data'])==13
assert sales['series']['C']['data'][0]==['2025-05',100.0]
assert sales['series']['C']['data'][-1]==['2026-05',112.0]
assert sales['series']['I2']['data'][0][1]==100.9

inventory=live.parse_inventory(body,min_observations=13)
assert len(inventory['data'])==13
assert inventory['data'][0]==['2025-05',100.0]
assert inventory['data'][-1]==['2026-05',112.0]
assert inventory['layout']=='official_live_table_structural'

bad=b'<html><body><table><tr><td>no data</td></tr></table></body></html>'
for fn in (live.parse_sales,live.parse_inventory):
    try:fn(bad)
    except ValueError:pass
    else:raise AssertionError('empty/invalid live table must fail closed')

# Publication-lag contract: last-good official data is usable only inside a
# bounded two-month freshness window. It must never turn into an indefinite
# stale-data exemption.
assert moea.month_gap('2026-06','2026-05')==1
assert moea.month_gap('2026-07','2026-05')==2
assert moea.month_gap('2026-08','2026-05')==3
assert live._month_gap('2026-06','2026-05')==1

existing={
    'latest_period':'2026-06',
    'series':{
        'inventory.manufacturing_index':{
            'name':'製造業 / 存貨指數',
            'data':[[f'2025-{m:02d}',100+m] for m in range(5,13)]+[[f'2026-{m:02d}',110+m] for m in range(1,6)],
        }
    },
    'catalogs':{},
}
real_load=live.load_json
real_request=live.request_bytes
try:
    live.load_json=lambda *args,**kwargs: existing
    def fail_request(*args,**kwargs):
        raise RuntimeError('synthetic EE521 outage')
    live.request_bytes=fail_request
    retained=live.update_inventory()
    assert retained['latest_period']=='2026-05'
    assert retained['rows']==13
    assert 'freshness window' in retained['message']

    stale=dict(existing)
    stale['latest_period']='2026-08'
    live.load_json=lambda *args,**kwargs: stale
    try:
        live.update_inventory()
    except RuntimeError as exc:
        assert 'synthetic EE521 outage' in str(exc)
    else:
        raise AssertionError('inventory transport outage must fail once last-good data is >2 months stale')
finally:
    live.load_json=real_load
    live.request_bytes=real_request

print('MOEA LIVE TABLE TEST PASS')
