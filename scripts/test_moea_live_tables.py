#!/usr/bin/env python3
import source_moea_live_tables as live

rows=['<html><body><table>','<tr><th>年</th><th>月</th><th>製造業</th></tr>']
# Deliberately omit the mutable page title/base-year text. The parser contract is
# the published table structure + plausible data, not a brittle prose signature.
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

print('MOEA LIVE TABLE TEST PASS')
