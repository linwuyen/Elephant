#!/usr/bin/env python3
from source_regime_official import parse_cbc_m2, parse_cbc_rates, parse_core_cpi, parse_headline_cpi, parse_ppi


def xml_series(item, values, typ='年增率'):
    rows = []
    for period, value in values:
        rows.append(f'<row><Item>{item}</Item><TIME_PERIOD>{period}</TIME_PERIOD><FREQ>M</FREQ><TYPE>{typ}</TYPE><Item_VALUE>{value}</Item_VALUE></row>')
    return ('<root>' + ''.join(rows) + '</root>').encode()


def monthly_values(start_year=2025, count=20, base=1.5):
    out = []
    y, m = start_year, 1
    for i in range(count):
        out.append((f'{y:04d}{m:02d}', base + i * 0.05))
        m += 1
        if m == 13:
            y += 1
            m = 1
    return out


def test_dgbas_direct_yoy():
    headline = parse_headline_cpi(xml_series('總指數', monthly_values(base=1.8)))['dgbas.cpi.monthly_yoy']['data']
    core = parse_core_cpi(xml_series('核心物價', monthly_values(base=1.6)))['dgbas.cpi.core_yoy']['data']
    ppi = parse_ppi(xml_series('生產者物價總指數', monthly_values(base=3.0)))['dgbas.ppi.yoy']['data']
    assert len(headline) == 20 and headline[-1][0] == '2026-08'
    assert len(core) == 20 and abs(core[-1][1] - 2.55) < 1e-9
    assert len(ppi) == 20 and abs(ppi[0][1] - 3.0) < 1e-9


def test_dgbas_index_to_yoy():
    vals = []
    for year, factor in ((2024, 1.0), (2025, 1.02)):
        for month in range(1, 13):
            vals.append((f'{year:04d}{month:02d}', 100.0 * factor))
    data = parse_headline_cpi(xml_series('總指數', vals, typ='指數'))['dgbas.cpi.monthly_yoy']['data']
    assert len(data) == 12
    assert all(abs(v - 2.0) < 1e-9 for _, v in data)


def test_cbc_m2():
    html = '<table>' + ''.join(f'<tr><td>2026.{m:02d}</td><td>{5.0 + m / 10:.2f}</td></tr>' for m in range(1, 13)) + '</table>'
    data = parse_cbc_m2(html)['cbc.m2.yoy']['data']
    assert len(data) == 12
    assert data[-1] == ['2026-12', 6.2]


def test_cbc_rate():
    html = '<table><tr><td>2022/3/18</td><td>1.375</td></tr><tr><td>2024/3/22</td><td>2.000</td></tr></table>'
    data = parse_cbc_rates(html)['cbc.discount_rate']['data']
    assert data[-1] == ['2024-03', 2.0]


def main():
    test_dgbas_direct_yoy()
    test_dgbas_index_to_yoy()
    test_cbc_m2()
    test_cbc_rate()
    print('SOURCE REGIME OFFICIAL TEST PASS')


if __name__ == '__main__':
    main()
