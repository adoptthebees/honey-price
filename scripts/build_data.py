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
    python3 scripts/build_data.py               # download only the files that FAOSTAT changed
    python3 scripts/build_data.py --refresh     # download the FAOSTAT files again
    python3 scripts/build_data.py --if-changed  # build only when FAOSTAT has newer files

Each run also writes data/honey_status.js. It holds the date of the latest check.
The GitHub workflow .github/workflows/update-data.yml runs --if-changed each week.
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
KG_PER_LB = 0.45359237  # exact: the international pound
STATUS_NAME = 'honey_status.js'  # next to the data file; holds the date of the latest check
# The page quotes how far to trust the unit value of a small export. This is the test behind it.
CHECK_FROM_YEAR = 2010
PRICE_BOUNDS_PER_LB = (0.40, 6.00)  # USD per lb: a honey export price outside this range is not plausible
# The FAO World export row should match the sum of the country rows. A larger difference is listed.
WORLD_GAP = 0.01

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
        'element_name': 'Export quantity (tonnes), export value (1000 US dollars) and import quantity (tonnes, used to test exports against production)',
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


def today():
    """The date in UTC, so that a run on a server and a run on a laptop agree."""
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


def upstream_stamps():
    """Return {source key: Last-Modified header} of the FAOSTAT files, without a download."""
    stamps = {}
    for key, source in SOURCES.items():
        request = urllib.request.Request(BASE_URL + source['zip'], method='HEAD')
        with urllib.request.urlopen(request, timeout=60) as response:
            stamps[key] = response.headers.get('Last-Modified', '')
    return stamps


def read_script(path, name):
    """Return the value of `window.NAME = ...;` in a file that this script wrote, else None."""
    prefix = f'window.{name} = '
    try:
        with open(path, encoding='utf-8') as f:
            text = f.read()
    except FileNotFoundError:
        return None
    start = text.find(prefix)
    if start < 0:
        return None
    try:
        return json.loads(text[start + len(prefix):].rstrip().removesuffix(';'))
    except ValueError:
        return None


def is_current(old, stamps):
    """True when `old`, the data in the data file, came from the files that FAOSTAT has now."""
    built = ((old or {}).get('meta') or {}).get('sources') or {}
    return all(stamps.get(key) and built.get(key, {}).get('lastModified') == stamps[key]
               for key in SOURCES)


def write_status(directory, checked):
    """Write the date of the latest check into a small file of its own.

    A check that finds nothing new then leaves the large data file as it is.
    """
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, STATUS_NAME), 'w', encoding='utf-8') as out:
        out.write('/* Generated by scripts/build_data.py. Do not edit by hand. */\n'
                  'window.HONEY_STATUS = ' + json.dumps({'checked': checked}) + ';\n')


def export_check(areas, years, min_tonnes, from_year=CHECK_FROM_YEAR, bounds=PRICE_BOUNDS_PER_LB):
    """How far to trust the unit value of a small export. The page quotes the result.

    Return the share of country years with a unit value outside `bounds` (USD per lb): for exports
    below `min_tonnes` the lowest and the highest year, and for exports from `min_tonnes` up all
    years together. Also return the share of the tonnage of the latest year that comes from
    exports of `min_tonnes` or more. Return None when the data cannot tell.
    """
    low, high = (b * 1000 / KG_PER_LB for b in bounds)  # USD per tonne
    small_years, large = [], [0, 0]
    for i, year in enumerate(years):
        if year < from_year:
            continue
        small = [0, 0]
        for a in areas:
            q, v = a['exportQty'][i], a['exportValue'][i]
            if a['exportFlags'][i] == ' ' or not q or not v:
                continue
            counts = small if q < min_tonnes else large
            counts[0] += 1
            counts[1] += int(not low <= v * 1000 / q <= high)
        if small[0]:
            small_years.append(small[1] / small[0])
    last = len(years) - 1
    exported = [a['exportQty'][last] for a in areas
                if a['exportFlags'][last] != ' ' and a['exportQty'][last]]
    if not small_years or not large[0] or not exported:
        return None
    return {
        'fromYear': from_year, 'toYear': years[last], 'minTonnes': min_tonnes,
        'lowPerLb': bounds[0], 'highPerLb': bounds[1],
        'smallOutside': [round(min(small_years), 4), round(max(small_years), 4)],
        'largeOutside': round(large[1] / large[0], 4),
        'aboveShare': round(sum(q for q in exported if q >= min_tonnes) / sum(exported), 4),
    }


def world_export_gaps(areas, world, years, tolerance=WORLD_GAP):
    """The years in which the FAO World export quantity differs from the sum of the country rows."""
    gaps = []
    for i, year in enumerate(years):
        w = world['exportQty'][i]
        if w:
            total = sum(a['exportQty'][i] or 0 for a in areas)
            if abs(total - w) / w > tolerance:
                gaps.append({'year': year, 'countries': round(total), 'world': round(w)})
    return gaps


def world_production_score(areas, world, last):
    """Score the World production row from the countries that add up to it.

    FAO flags the sum A or E whatever its parts are, so the flag says little about the sum.
    """
    conf, band = [], []
    for i, total in enumerate(world['production']):
        parts = [(a['production'][i], a['productionConf'][i], a['productionBand'][i] / 1000,
                  a['productionFlags'][i] == uncertainty.OFFICIAL)
                 for a in areas if a['production'][i] is not None]
        c, b = uncertainty.score_total('production', total, parts, last - i) if total else (None, None)
        conf.append(c)
        band.append(b)
    return conf, band


def world_export_score(areas, world):
    """Score the World export price from the country prices, weighted by export value."""
    conf, band = [], []
    for i, flag in enumerate(world['exportFlags']):
        parts = [(a['exportValue'][i], a['exportConf'][i], a['exportBand'][i] / 1000)
                 for a in areas if a['exportConf'][i] is not None and a['exportValue'][i]]
        weights = [v for v, _, _ in parts]
        half = uncertainty.sum_half(weights, [h for _, _, h in parts], sum(weights)) if flag != ' ' else None
        conf.append(None if half is None else uncertainty.aggregate_conf(weights, [c for _, c, _ in parts]))
        band.append(None if half is None else round(half * 1000))
    return conf, band


def export_prices(rec, minimum):
    """Export price in USD per tonne and its flag for each year, from `minimum` tonnes up."""
    values, flags = [], []
    for q, v, f in zip(rec['exportQty'], rec['exportValue'], rec['exportFlags']):
        ok = f != ' ' and q and v and q >= minimum
        values.append(v * 1000 / q if ok else None)
        flags.append(f if ok else ' ')
    return values, ''.join(flags)


def score_areas(areas, world, years, imports):
    """Give each value of each country a score, a range and its deductions. Then do the World row.

    imports maps an area code to its import quantity for each year. A country that is not in it
    has no imports. The method is in scripts/uncertainty.py. Return the model of each kind.
    """
    last = len(years) - 1
    picks = {
        'production': lambda rec: (rec['production'], rec['productionFlags']),
        'price': lambda rec: (rec['price'], rec['priceFlags']),
        'export': lambda rec: export_prices(rec, MIN_EXPORT_TONNES),
    }
    models = {}
    for kind, pick in picks.items():
        models[kind] = uncertainty.fit({a['code']: pick(a) for a in areas})
        for a in areas:
            values, flags = pick(a)
            extra = {}
            if kind != 'price':     # exports against production plus imports: for production and exports
                bought = imports.get(a['code']) or [None] * len(years)
                extra['supply'] = [uncertainty.supply_excess(p, q, m)
                                   for p, q, m in zip(a['production'], a['exportQty'], bought)]
            if kind != 'production':   # a price against the other price of the same country
                extra['gap'] = uncertainty.price_gaps(a['price'], export_prices(a, MIN_EXPORT_TONNES)[0])
            conf, band, why = uncertainty.score_series(models[kind], kind, values, flags, last, extra)
            a[kind + 'Conf'], a[kind + 'Band'] = conf, band
            a[kind + 'Why'] = [uncertainty.why_text(taken) for taken in why]
    world['productionConf'], world['productionBand'] = world_production_score(areas, world, last)
    world['exportConf'], world['exportBand'] = world_export_score(areas, world)
    return models


def build(cache_dir, refresh, day):
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
    gaps = world_export_gaps(areas, world, years)

    # Score, range and deductions of every value. The method is in scripts/uncertainty.py.
    imports = {a['code']: series(tables['importQty'].get(str(a['code']), {}), years)[0] for a in areas}
    models = score_areas(areas, world, years, imports)

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
            'retrieved': day,
            'sources': files,
            'flags': {key: {f: flag_text[key][f] for f in sorted(letters)}
                      for key, letters in used.items()},
            'minExportTonnes': MIN_EXPORT_TONNES,
            'exportCheck': export_check(areas, years, MIN_EXPORT_TONNES),
            'worldExportGaps': gaps,
            'uncertainty': {
                'models': {kind: uncertainty.describe(model) for kind, model in models.items()},
                'rubric': uncertainty.rubric(),
            },
        },
        'years': years,
        'world': world,
        'areas': areas,
    }
    return data


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
    parser.add_argument('--if-changed', action='store_true',
                        help='build only when FAOSTAT has files newer than the data file was built from')
    parser.add_argument('--cache', default=os.path.join(tempfile.gettempdir(), 'honey_price_cache'),
                        help='directory for the downloaded files')
    parser.add_argument('--out', default=os.path.join(root, 'data', 'honey_data.js'))
    args = parser.parse_args()
    day = today()
    folder = os.path.dirname(args.out)

    if args.if_changed and is_current(read_script(args.out, 'HONEY_DATA'), upstream_stamps()):
        write_status(folder, day)
        print(f'up to date: FAOSTAT has no file newer than {args.out}. Checked {day}.')
        return

    os.makedirs(args.cache, exist_ok=True)
    data = build(args.cache, args.refresh, day)
    write(data, args.out)
    write_status(folder, day)

    last = data['years'][-1]
    priced = sum(1 for a in data['areas'] if a['price'][-1] is not None)
    exporters = sum(1 for a in data['areas'] if a['exportFlags'][-1] != ' ')
    print(f"wrote {args.out} ({os.path.getsize(args.out):,} bytes)")
    print(f"years {data['years'][0]}-{last}, {len(data['areas'])} areas; in {last}: "
          f"world production {data['world']['production'][-1]:,} t, {priced} areas with a producer price, "
          f"{exporters} areas with an export price")
    print('flags used:', data['meta']['flags'])
    for kind, model in data['meta']['uncertainty']['models'].items():
        print(f"uncertainty {kind}: K={model['k90']}, K1={model['k1']}, out-of-sample coverage {model['coverage']:.1%} "
              f"of {model['checked']} official values, class factors {model['classes']}")
    gaps = data['meta']['worldExportGaps']
    if gaps:
        print(f'check: the FAO World export row differs from the country rows by more than {WORLD_GAP:.0%} in:')
        for gap in gaps:
            print(f"   {gap['year']}: countries {gap['countries']:,} t, FAO World {gap['world']:,} t")


if __name__ == '__main__':
    main()
