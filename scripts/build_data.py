#!/usr/bin/env python3
"""Build data/honey_data.js from the FAOSTAT bulk download files.

Source:  FAOSTAT, Food and Agriculture Organization of the United Nations (FAO).
Item:    1182 "Natural honey".
Data:    QCL (Crops and livestock products), element 5510, Production, tonnes.
         PP  (Producer Prices), element 5532, Producer Price, USD per tonne, annual value.
         TCL (Trade: Crops and livestock products), elements 5910 and 5922,
             Export quantity (tonnes) and Export value (1000 USD).
License: CC BY 4.0 (FAO open data licensing for statistical databases).

Run from the project directory:
    python3 scripts/build_data.py            # download only the files that FAOSTAT changed
    python3 scripts/build_data.py --refresh  # download the FAOSTAT files again

The trade file is about 270 MB. The script uses only the Python standard library.
Confidence scores and ranges are made by scripts/uncertainty.py.
"""
import argparse
import csv
import datetime
import io
import itertools
import json
import os
import shutil
import tempfile
import urllib.request
import zipfile

import uncertainty  # the model in scripts/uncertainty.py

BASE_URL = 'https://bulks-faostat.fao.org/production/'
HONEY_ITEM = '1182'
WORLD_AREA = '5000'
# FAO area codes from 5000 up are groups (world, regions, income groups). Codes below are countries.
FIRST_GROUP_CODE = 5000
# The FAO group "China" is the sum of its parts (China, mainland and China, Taiwan
# Province of, and others). The table lists the parts, so the group is left out.
CHINA_GROUP = '351'
# Names such as "European Union (27) (excluding intra-trade)" are groups too.
GROUP_WORD = 'excluding'

SOURCES = {
    'production': {
        'dataset': 'QCL',
        'title': 'Crops and livestock products',
        'zip': 'Production_Crops_Livestock_E_All_Data_(Normalized).zip',
        'flags': 'Production_Crops_Livestock_E_Flags.csv',
        'tables': {'5510': 'production'},
        'element_name': 'Production (tonnes)',
        'page': 'https://www.fao.org/faostat/en/#data/QCL',
        'lineage': 'https://data.apps.fao.org/catalog/dataset/c2c0815f-6926-4400-acf3-974d8b9f847b',
    },
    'price': {
        'dataset': 'PP',
        'title': 'Producer Prices',
        'zip': 'Prices_E_All_Data_(Normalized).zip',
        'flags': 'Prices_E_Flags.csv',
        'tables': {'5532': 'price'},
        'element_name': 'Producer Price (USD/tonne)',
        'page': 'https://www.fao.org/faostat/en/#data/PP',
        'lineage': 'https://data.fao.org/catalog/dataset/47c17894-8ca1-4bd0-ba4d-6078e919e9b1',
    },
    'trade': {
        'dataset': 'TCL',
        'title': 'Trade: Crops and livestock products',
        'zip': 'Trade_CropsLivestock_E_All_Data_(Normalized).zip',
        'flags': 'Trade_CropsLivestock_E_Flags.csv',
        'tables': {'5910': 'exportQty', '5922': 'exportValue', '5610': 'importQty'},
        'element_name': 'Export quantity (tonnes), Export value (1000 USD) and Import quantity (tonnes, used for a check)',
        'page': 'https://www.fao.org/faostat/en/#data/TCL',
        'lineage': 'https://data.fao.org/catalog/dataset/f62abf31-1def-4f03-ba9e-5dade02038dc',
    },
}
TABLES = ('production', 'price', 'exportQty', 'exportValue')
CHECK_TABLES = ('importQty',)  # read only to check production against trade
# A country has an export price only from this export quantity. The page explains why.
MIN_EXPORT_TONNES = 100


def download(name, cache_dir, refresh):
    """Return (path, Last-Modified header). Download again when FAOSTAT has a newer file."""
    path = os.path.join(cache_dir, name)
    stamp = path + '.modified'  # the Last-Modified value of the cached file
    with urllib.request.urlopen(BASE_URL + name, timeout=120) as response:
        modified = response.headers.get('Last-Modified', '')
        cached = None
        if os.path.exists(path) and os.path.exists(stamp):
            with open(stamp, encoding='utf-8') as f:
                cached = f.read()
        if refresh or not modified or cached != modified:
            part = path + '.part'
            with open(part, 'wb') as out:
                shutil.copyfileobj(response, out)
            os.replace(part, path)
            with open(stamp, 'w', encoding='utf-8') as f:
                f.write(modified)
            print(f'downloaded {name} ({os.path.getsize(path):,} bytes)')
        else:
            print(f'cached     {name}')
    return path, modified


def read_rows(zip_path, source):
    """Yield the honey rows of one source: the item, its elements, and annual values only."""
    with zipfile.ZipFile(zip_path) as archive:
        data_name = next(n for n in archive.namelist() if n.endswith('(Normalized).csv'))
        with archive.open(data_name) as raw:
            lines = io.TextIOWrapper(raw, encoding='utf-8')
            header = next(lines)
            # A cheap text filter first. The exact test is on the parsed columns.
            rows = csv.DictReader(itertools.chain([header], (l for l in lines if HONEY_ITEM in l)))
            for row in rows:
                if (row['Item Code'] == HONEY_ITEM
                        and row['Element Code'] in source['tables']
                        and row.get('Months', 'Annual value') == 'Annual value'):
                    yield row


def read_flags(zip_path, name):
    with zipfile.ZipFile(zip_path) as archive:
        text = archive.read(name).decode('utf-8')
    return {row['Flag']: row['Description']
            for row in csv.DictReader(io.StringIO(text), skipinitialspace=True)}


def number(value):
    """Integer when the value is whole, else a float, so the JSON stays short."""
    return int(value) if value == int(value) else round(value, 6)


def series(rows, years):
    """Return (values, flags) aligned to years. A year without a value is None."""
    values, flags = [], []
    for year in years:
        value, flag = rows.get(year, (None, ''))
        values.append(None if value is None else number(value))
        if len(flag) > 1:
            raise ValueError(f'unexpected flag {flag!r}')
        flags.append(flag or ' ')
    return values, ''.join(flags)


def combine_flags(*flags):
    """One flag for a value made from two figures. It is official only if both are official."""
    if all(f == 'A' for f in flags):
        return 'A'
    for f in 'IEX':
        if f in flags:
            return f
    return next((f for f in flags if f not in ('A', ' ')), ' ')


def export_flags(quantity, quantity_flags, value, value_flags):
    """A flag for each year in which the export price can be calculated, else a space."""
    return ''.join(combine_flags(qf, vf) if q and v else ' '
                   for q, qf, v, vf in zip(quantity, quantity_flags, value, value_flags))


def is_group(code, name):
    return int(code) >= FIRST_GROUP_CODE or code == CHINA_GROUP or GROUP_WORD in name


def build(cache_dir, refresh):
    tables = {name: {} for name in TABLES + CHECK_TABLES}  # name -> area code -> {year: (value, flag)}
    names, files, flag_text = {}, {}, {}
    for key, source in SOURCES.items():
        path, modified = download(source['zip'], cache_dir, refresh)
        count = 0
        for row in read_rows(path, source):
            count += 1
            value = row['Value']
            names.setdefault(row['Area Code'], row['Area'])
            table = tables[source['tables'][row['Element Code']]]
            table.setdefault(row['Area Code'], {})[int(row['Year'])] = (
                float(value) if value else None, row['Flag'])
        if not count:
            raise ValueError(f"no honey rows found in {source['zip']}")
        flag_text[key] = read_flags(path, source['flags'])
        files[key] = {
            'dataset': source['dataset'], 'title': source['title'], 'element': source['element_name'],
            'page': source['page'], 'lineage': source['lineage'],
            'file': source['zip'], 'lastModified': modified,
        }

    years = sorted({year
                    for name in TABLES
                    for rows in tables[name].values()
                    for year, (value, _) in rows.items() if value is not None})

    if CHINA_GROUP in tables['price'] and any(v is not None for v, _ in tables['price'][CHINA_GROUP].values()):
        raise ValueError('the China group has prices, so leaving it out would drop data')

    def record(code):
        out = {}
        for name in TABLES:
            out[name], out[name + 'Flags'] = series(tables[name].get(code, {}), years)
        out['exportFlags'] = export_flags(out['exportQty'], out['exportQtyFlags'],
                                          out['exportValue'], out['exportValueFlags'])
        return out

    def keep(rec):
        # Output only what the page uses: the combined export flag, not the two single flags.
        slim = {k: v for k, v in rec.items() if k not in ('exportQtyFlags', 'exportValueFlags')}
        return slim

    world = keep(record(WORLD_AREA))
    for name in ('price', 'priceFlags'):
        del world[name]  # FAOSTAT has no world producer price

    areas = []
    for code in sorted({c for table in tables.values() for c in table}, key=lambda c: names[c]):
        if is_group(code, names[code]):
            continue
        rec = record(code)
        if all(v is None for name in TABLES for v in rec[name]):
            continue
        areas.append({'code': int(code), 'name': names[code], **keep(rec)})

    # FAO publishes a World export row. It should match the sum of the country rows.
    gaps = []
    for i, year in enumerate(years):
        w = world['exportQty'][i]
        if w:
            total = sum(a['exportQty'][i] or 0 for a in areas)
            if abs(total - w) / w > 0.01:
                gaps.append(f'{year}: countries {total:,.0f} t, FAO World {w:,.0f} t')

    # Confidence scores and ranges for every value. The method is in scripts/uncertainty.py.
    last = len(years) - 1

    def export_prices(rec, minimum):
        """Export price in USD per tonne and its flag for each year, from `minimum` tonnes up."""
        values, flags = [], []
        for q, v, f in zip(rec['exportQty'], rec['exportValue'], rec['exportFlags']):
            ok = f != ' ' and q and v and q >= minimum
            values.append(v * 1000 / q if ok else None)
            flags.append(f if ok else ' ')
        return values, ''.join(flags)

    def balance(rec, code):
        imports, _ = series(tables['importQty'].get(code, {}), years)
        return [uncertainty.balance_penalty(p, q, m)
                for p, q, m in zip(rec['production'], rec['exportQty'], imports)]

    kinds = {
        'production': lambda rec: (rec['production'], rec['productionFlags']),
        'price': lambda rec: (rec['price'], rec['priceFlags']),
        'export': lambda rec: export_prices(rec, MIN_EXPORT_TONNES),
    }
    models = {}
    for kind, pick in kinds.items():
        models[kind] = uncertainty.fit({a['code']: pick(a) for a in areas})
        for a in areas:
            values, flags = pick(a)
            extra = None if kind == 'price' else balance(a, str(a['code']))
            a[kind + 'Conf'], a[kind + 'Band'] = uncertainty.score_series(
                models[kind], kind, values, flags, last, extra)
    world['productionConf'], world['productionBand'] = uncertainty.score_series(
        models['production'], 'production', world['production'], world['productionFlags'], last)
    values, flags = export_prices(world, 0)
    world['exportConf'], world['exportBand'] = uncertainty.score_series(
        models['export'], 'export', values, flags, last)

    used = {'production': set(world['productionFlags']), 'price': set(), 'trade': set(world['exportFlags'])}
    for area in areas:
        used['production'] |= set(area['productionFlags'])
        used['price'] |= set(area['priceFlags'])
        used['trade'] |= set(area['exportFlags'])
    for letters in used.values():
        letters.discard(' ')

    data = {
        'meta': {
            'publisher': 'Food and Agriculture Organization of the United Nations (FAO)',
            'database': 'FAOSTAT',
            'item': 'Natural honey (FAOSTAT item code 1182)',
            'license': 'CC BY 4.0',
            'licenseUrl': 'https://creativecommons.org/licenses/by/4.0/',
            'retrieved': datetime.date.today().isoformat(),
            'sources': files,
            'flags': {key: {f: flag_text[key][f] for f in sorted(letters)}
                      for key, letters in used.items()},
            'minExportTonnes': MIN_EXPORT_TONNES,
            'uncertainty': {
                'models': {kind: uncertainty.describe(model) for kind, model in models.items()},
                'rubric': uncertainty.rubric(),
            },
        },
        'years': years,
        'world': world,
        'areas': areas,
    }
    return data, gaps


def write(data, out_path):
    header = ('/* Generated by scripts/build_data.py. Do not edit by hand.\n'
              ' * Source: FAOSTAT (FAO), item 1182 Natural honey. License: CC BY 4.0.\n'
              f" * Retrieved: {data['meta']['retrieved']} */\n")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as out:
        out.write(header + 'window.HONEY_DATA = '
                  + json.dumps(data, separators=(',', ':'), ensure_ascii=False) + ';\n')


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--refresh', action='store_true', help='download the FAOSTAT files again')
    parser.add_argument('--cache', default=os.path.join(tempfile.gettempdir(), 'honey_price_cache'),
                        help='directory for the downloaded files')
    parser.add_argument('--out', default=os.path.join(root, 'data', 'honey_data.js'))
    args = parser.parse_args()
    os.makedirs(args.cache, exist_ok=True)

    data, gaps = build(args.cache, args.refresh)
    write(data, args.out)

    last = data['years'][-1]
    priced = sum(1 for a in data['areas'] if a['price'][-1] is not None)
    exporters = sum(1 for a in data['areas'] if a['exportFlags'][-1] != ' ')
    print(f"wrote {args.out} ({os.path.getsize(args.out):,} bytes)")
    print(f"years {data['years'][0]}-{last}, {len(data['areas'])} areas; in {last}: "
          f"world production {data['world']['production'][-1]:,} t, {priced} areas with a producer price, "
          f"{exporters} areas with an export price")
    print('flags used:', data['meta']['flags'])
    for kind, model in data['meta']['uncertainty']['models'].items():
        print(f"uncertainty {kind}: K={model['k90']}, out-of-sample coverage {model['coverage']:.1%} "
              f"of {model['checked']} official values, class factors {model['classes']}")
    if gaps:
        print('check: the FAO World export row differs from the country rows by more than 1% in:')
        for gap in gaps:
            print('  ', gap)


if __name__ == '__main__':
    main()
