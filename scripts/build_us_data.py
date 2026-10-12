#!/usr/bin/env python3
"""Build data/us_supply.js from the USDA NASS honey reports.

Source:  USDA National Agricultural Statistics Service (NASS), Honey (annual) and
         Honey - Final Estimates, published on ESMIS (esmis.nal.usda.gov). Public domain.
Data:    colonies, yield, production, stocks, price and value by state, the United States
         and the other states, 2000 to the last year of the newest report.

Run from the project directory:
    python3 scripts/build_us_data.py               # download the reports that are not cached
    python3 scripts/build_us_data.py --refresh     # download the report files again
    python3 scripts/build_us_data.py --if-changed  # build only when ESMIS has a newer report

Each run also writes data/us_status.js. It holds the date of the latest check.
The GitHub workflow .github/workflows/update-us-data.yml runs --if-changed each week.
The script uses only the Python standard library and reuses the helpers of build_data.py.
"""
import argparse
import csv
import io
import itertools
import json
import math
import os
import re
import shutil
import tempfile
import urllib.parse
import urllib.request
import zipfile

import build_data as b

BASE_URL = 'https://esmis.nal.usda.gov'
AJAX_URL = BASE_URL + '/views/ajax'
VIEW_NAME = 'publication_releases_indexed'
VIEW_DISPLAY = 'all_releases_block'
MAX_PAGES = 50  # a guard: the release list has about 5 pages of 10 rows
# (node number, publication name, page name in the URL)
PUBLICATIONS = [
    (1256, 'Honey', 'honey'),
    (858, 'Honey - Final Estimates', 'honey-final-estimates'),
]
PUBLISHER = 'United States Department of Agriculture, National Agricultural Statistics Service (USDA NASS)'
HONEY_URL = BASE_URL + '/publication/honey'
FINAL_URL = BASE_URL + '/publication/honey-final-estimates'
STATUS_NAME = 'us_status.js'  # next to the data file; holds the date of the latest check
FIRST_YEAR = 2000
REVISION_FROM_YEAR = 2017  # the revisions are measured from this year on
TABLE_WORDS = 'Colonies, Yield, Production, Stocks, Price,'  # the table of states in every report
SMALL_PRODUCERS = 'less than 5 colonies'  # a table of small operations is not used
# Cells that NASS prints when a value is withheld or not reported. Each is None here.
WITHHELD = {'(D)', '(NA)', '(X)', '(Z)', ''}
THOUSAND = 1000  # NASS prints colonies, production, stocks and value in thousands
CENTS = 0.01  # the price of old reports is in cents

# The states and the District of Columbia: (name, USPS code).
STATES = [
    ('Alabama', 'AL'), ('Alaska', 'AK'), ('Arizona', 'AZ'), ('Arkansas', 'AR'), ('California', 'CA'),
    ('Colorado', 'CO'), ('Connecticut', 'CT'), ('Delaware', 'DE'), ('District of Columbia', 'DC'),
    ('Florida', 'FL'), ('Georgia', 'GA'), ('Hawaii', 'HI'), ('Idaho', 'ID'), ('Illinois', 'IL'),
    ('Indiana', 'IN'), ('Iowa', 'IA'), ('Kansas', 'KS'), ('Kentucky', 'KY'), ('Louisiana', 'LA'),
    ('Maine', 'ME'), ('Maryland', 'MD'), ('Massachusetts', 'MA'), ('Michigan', 'MI'), ('Minnesota', 'MN'),
    ('Mississippi', 'MS'), ('Missouri', 'MO'), ('Montana', 'MT'), ('Nebraska', 'NE'), ('Nevada', 'NV'),
    ('New Hampshire', 'NH'), ('New Jersey', 'NJ'), ('New Mexico', 'NM'), ('New York', 'NY'),
    ('North Carolina', 'NC'), ('North Dakota', 'ND'), ('Ohio', 'OH'), ('Oklahoma', 'OK'), ('Oregon', 'OR'),
    ('Pennsylvania', 'PA'), ('Rhode Island', 'RI'), ('South Carolina', 'SC'), ('South Dakota', 'SD'),
    ('Tennessee', 'TN'), ('Texas', 'TX'), ('Utah', 'UT'), ('Vermont', 'VT'), ('Virginia', 'VA'),
    ('Washington', 'WA'), ('West Virginia', 'WV'), ('Wisconsin', 'WI'), ('Wyoming', 'WY'),
]
STATE_NAMES = dict((code, name) for name, code in STATES)
# Every name and code that a report can print, mapped to the code used in the data file.
AREA_CODES = {}
for _name, _code in STATES:
    AREA_CODES[_name] = _code
    AREA_CODES[_code] = _code
AREA_CODES.update({'United States': 'US', 'US': 'US', 'Other States': 'OTH', 'Oth Sts': 'OTH'})
AREA_NAMES = dict(STATE_NAMES, US='United States', OTH='Other States')
FOOTNOTE = re.compile(r'\s*\d+/')  # footnote marks such as " 5/"
YEAR = re.compile(r'(?<!\d)(\d{4})(?![\d-])')  # a year that is not part of a range such as 2013-2017
ROW = re.compile(r'<tr\b.*?</tr>', re.S)
RELEASE_DATE = re.compile(r'views-field-release-date[^>]*>(.*?)</td>', re.S)
RELEASE_FILES = re.compile(r'views-field-release-files[^>]*>(.*?)</td>', re.S)
TIME_DATE = re.compile(r'<time[^>]*datetime="([^"]*)"')
HREF = re.compile(r'href="([^"]+)"')


def fetch(url, data=None, headers=None):
    request = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def view_dom_id(node, page):
    """The id that the publication page gives its release list. The ESMIS ajax call needs it."""
    html = fetch(f'{BASE_URL}/publication/{page}').decode('utf-8')
    match = re.search(r'"view_args":"%d"[^}]*?"view_dom_id":"([^"]+)"' % node, html)
    if not match:
        raise ValueError(f'{page}: the release list of node {node} is not on the page')
    return match.group(1)


def ajax_page(node, number, dom_id):
    """The HTML of one page of the release list. ESMIS sends it inside a list of commands."""
    form = urllib.parse.urlencode({
        'view_name': VIEW_NAME, 'view_display_id': VIEW_DISPLAY, 'view_args': str(node),
        'view_path': f'/node/{node}', 'view_dom_id': dom_id, 'pager_element': '0', '_drupal_ajax': '1',
    }).encode('utf-8')
    body = fetch(f'{AJAX_URL}?page={number}', form, {
        'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded'})
    return ''.join(c.get('data', '') for c in json.loads(body) if c.get('command') == 'insert')


def release_rows(html):
    """Return (date, zip path or None) for each release row. A row without a date stops the build."""
    rows = []
    for row in ROW.findall(html):
        if '<td' not in row:  # the header row
            continue
        date = RELEASE_DATE.search(row)
        time = TIME_DATE.search(date.group(1)) if date else None
        if not time or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', time.group(1)[:10]):
            raise ValueError(f'a release row has no date: {row.strip()[:200]}')
        files = RELEASE_FILES.search(row)
        zips = [h for h in HREF.findall(files.group(1) if files else '') if h.endswith('.zip')]
        rows.append((time.group(1)[:10], zips[0] if zips else None))
    return rows


def to_releases(rows, publication):
    """Keep the releases with a zip file, which holds the data. A notice without a zip is skipped."""
    releases = [{'date': date, 'publication': publication, 'url': BASE_URL + path}
                for date, path in rows if path]
    if not releases:
        raise ValueError(f'{publication}: no release has a zip file')
    return releases


def releases():
    """Every release with a zip file of both publications, sorted by date."""
    found = []
    for node, publication, page in PUBLICATIONS:
        dom_id = view_dom_id(node, page)
        rows = []
        for number in itertools.islice(itertools.count(), MAX_PAGES):
            page_rows = release_rows(ajax_page(node, number, dom_id))
            if not page_rows:
                break
            rows += page_rows
        else:
            raise ValueError(f'{publication}: more than {MAX_PAGES} pages of releases')
        found += to_releases(rows, publication)
    return sorted(found, key=lambda r: r['date'])


def download(url, cache_dir, refresh):
    """Return the path of the zip file at `url`. The file is kept in `cache_dir` under its own name."""
    name = os.path.basename(url)
    path = os.path.join(cache_dir, name)
    if os.path.exists(path) and not refresh:
        print(f'cached     {name}')
        return path
    os.makedirs(cache_dir, exist_ok=True)
    part = path + '.part'
    with urllib.request.urlopen(url, timeout=120) as response:
        with open(part, 'wb') as out:
            shutil.copyfileobj(response, out)
        length = response.headers.get('Content-Length')
    b.complete(part, length)  # removes a cut-off or non-zip file and raises an error
    os.replace(part, path)
    print(f'downloaded {name} ({os.path.getsize(path):,} bytes)')
    return path


def price_unit(row):
    """'cents' or 'dollars', from the price cell of the units row."""
    cell = row[7].lower() if len(row) > 7 else ''
    if 'cent' in cell:
        return 'cents'
    if 'dollar' in cell:
        return 'dollars'
    raise ValueError(f'the price unit is not cents or dollars: {row!r}')


def read_tables(zip_path):
    """Return (year, price unit, rows) for each table of states in the zip file.

    Each row is (area name, colonies, yield, production, stocks, price, value), all as text.
    """
    with zipfile.ZipFile(zip_path) as archive:
        name = next((n for n in archive.namelist() if n.lower().endswith('.csv') and 'all' in n.lower()), None)
        if name is None:
            raise ValueError(f'{zip_path}: no csv file with "all" in its name')
        text = archive.read(name).decode('latin-1')
    tables = {}  # table number -> its rows, in file order
    for row in csv.reader(io.StringIO(text)):
        if len(row) >= 2:
            tables.setdefault(row[0], []).append(row)
    found = []
    for rows in tables.values():
        title = ' '.join(' '.join(c for c in r[2:] if c) for r in rows if r[1] == 't')
        title = ' '.join(title.split())
        if TABLE_WORDS not in title or 'State' not in title or SMALL_PRODUCERS in title:
            continue
        years = YEAR.findall(title)
        if not years:
            raise ValueError(f'{zip_path}: no year in the title: {title[:200]}')
        units = next((r for r in rows if r[1] == 'u'), None)
        if units is None:
            raise ValueError(f'{zip_path}: no units row in the table of {years[-1]}')
        items = [(r[2].strip() if len(r) > 2 else '', (r[3:9] + [''] * 6)[:6]) for r in rows if r[1] == 'd']
        merged = []
        i = 0
        while i < len(items):
            name, cells = items[i]
            # Before 2011, "Other States" is printed as "Oth" on one row and " Sts" on the next.
            if name == 'Oth' and not any(cells) and i + 1 < len(items):
                name, cells = name + ' ' + items[i + 1][0], items[i + 1][1]
                i += 1
            if name:
                merged.append((name, *cells))
            i += 1
        found.append((int(years[-1]), price_unit(units), merged))
    if not found:
        raise ValueError(f'{zip_path}: no table of states and United States')
    years = [t[0] for t in found]
    if len(set(years)) != len(years):
        raise ValueError(f'{zip_path}: a year has two tables: {years}')
    return found


def area_code(name):
    """The code of an area name printed in a report, such as 'California', 'CA' or 'United States 6/ 7/'."""
    clean = ' '.join(FOOTNOTE.sub('', name).split())
    code = AREA_CODES.get(clean)
    if code is None:
        raise ValueError(f'unknown area name: {name!r}')
    return code


def amount(cell, scale):
    """The number of one cell times `scale`. A withheld or empty cell is None.

    Scale THOUSAND gives an integer. Other scales give a rounded float.
    """
    text = cell.strip()
    if text in WITHHELD:
        return None
    try:
        number = float(text.replace(',', ''))
    except ValueError:
        raise ValueError(f'unexpected cell: {cell!r}') from None
    if scale == THOUSAND:
        return int(round(number * THOUSAND))
    return round(number * scale, 6)


def parse_report(report, tables):
    """Return the records of one report: (report index, year, area code, colonies, yield, production,
    stocks, price, value) in units of the data file."""
    records = []
    for year, unit, rows in tables:
        price_scale = CENTS if unit == 'cents' else 1
        for name, colonies, yield_, production, stocks, price, value in rows:
            records.append((report, year, area_code(name), amount(colonies, THOUSAND), amount(yield_, 1),
                            amount(production, THOUSAND), amount(stocks, THOUSAND),
                            amount(price, price_scale), amount(value, THOUSAND)))
    return records


def is_current(old, dates):
    """True when `old`, the data in the data file, has every release date in `dates`."""
    if not old or not all(old.get(key) for key in ('rows', 'years', 'geos')):
        return False
    built = {r.get('date') for r in old.get('reports') or []}
    return all(date in built for date in dates)


def assemble(records, reports, today):
    """Build the data object: the geos, years, rows, United States and revisions of the data file."""
    codes = {r[2] for r in records}
    if 'US' not in codes:
        raise ValueError('no record of the United States')
    states = sorted((c for c in codes if c not in ('US', 'OTH')), key=lambda c: AREA_NAMES[c])
    geo_codes = ['US'] + states + (['OTH'] if 'OTH' in codes else [])
    geo_index = {code: i for i, code in enumerate(geo_codes)}
    levels = {'US': 'country', 'OTH': 'other'}
    geos = [{'code': c, 'name': AREA_NAMES[c], 'level': levels.get(c, 'state')} for c in geo_codes]

    first_year = min(r[1] for r in records)
    last_year = max(r[1] for r in records)
    years = list(range(first_year, last_year + 1))
    year_index = {y: i for i, y in enumerate(years)}

    # One row per area and year, from the newest report that has it.
    newest = {}
    for record in records:
        key = (record[2], record[1])
        if key not in newest or record[0] > newest[key][0]:
            newest[key] = record
    rows = [[geo_index[code], year_index[year], rec[0], rec[3], rec[4], rec[5], rec[6], rec[7], rec[8]]
            for (code, year), rec in sorted(newest.items(), key=lambda k: (geo_index[k[0][0]], k[0][1]))]

    # The United States in every report: the first report and the next one that has the year.
    by_year = {}
    for record in sorted(records, key=lambda r: r[0]):
        if record[2] == 'US':
            by_year.setdefault(record[1], []).append(record)
    us = []
    second_of = {}
    for year in sorted(by_year):
        first = by_year[year][0]
        second = by_year[year][1] if len(by_year[year]) > 1 else None
        us.append([year, first[0], first[5], first[7],
                   second[0] if second else None, second[5] if second else None, second[7] if second else None])
        if second:
            second_of[year] = (first, second)

    # The revisions: the largest change between the first and the second report, from 2017 on.
    last_revised = max(second_of) if second_of else REVISION_FROM_YEAR
    production = price = 0.0
    for year in range(REVISION_FROM_YEAR, last_revised + 1):
        if year not in second_of:
            continue
        first, second = second_of[year]
        if first[5] and second[5]:
            production = max(production, abs(math.log(second[5] / first[5])))
        if first[7] and second[7]:
            price = max(price, abs(math.log(second[7] / first[7])))
    evidence = {'years': f'{REVISION_FROM_YEAR} to {last_revised}',
                'production': round(production, 4), 'price': round(price, 4)}

    return {
        'meta': {'publisher': PUBLISHER, 'source': 'Honey', 'url': HONEY_URL, 'finalEstimatesUrl': FINAL_URL,
                 'retrieved': today, 'last': max(r['date'] for r in reports)},
        'reports': [dict(r) for r in reports],
        'years': years,
        'geos': geos,
        'rows': rows,
        'us': us,
        'evidence': evidence,
    }


def write(data, out_path):
    header = ('/* Generated by scripts/build_us_data.py. Do not edit by hand.\n'
              ' * Source: USDA NASS, Honey (annual) and Honey - Final Estimates. Public domain.\n'
              f" * Retrieved: {data['meta']['retrieved']} */\n")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as out:
        out.write(header + 'window.HONEY_US_SUPPLY = '
                  + json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + ';\n')


def write_status(directory, checked):
    """Write the date of the latest check into a small file of its own.

    A check that finds nothing new then leaves the data file as it is.
    """
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, STATUS_NAME), 'w', encoding='utf-8') as out:
        out.write('/* Generated by scripts/build_us_data.py. Do not edit by hand. */\n'
                  'window.HONEY_US_STATUS = ' + json.dumps({'checked': checked}) + ';\n')


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--refresh', action='store_true', help='download the report files again')
    parser.add_argument('--if-changed', action='store_true',
                        help='build only when ESMIS has a report that the data file does not have')
    parser.add_argument('--cache', default=os.path.join(tempfile.gettempdir(), 'honey_price_cache', 'nass'),
                        help='directory for the downloaded report files')
    parser.add_argument('--out', default=os.path.join(root, 'data', 'us_supply.js'))
    args = parser.parse_args()
    day = b.today()
    folder = os.path.dirname(args.out)

    reports = releases()
    if args.if_changed and is_current(b.read_script(args.out, 'HONEY_US_SUPPLY'), [r['date'] for r in reports]):
        write_status(folder, day)
        print(f'up to date: ESMIS has no report newer than {args.out}. Checked {day}.')
        return

    records = []
    for index, report in enumerate(reports):
        path = download(report['url'], args.cache, args.refresh)
        records += parse_report(index, read_tables(path))
    data = assemble(records, reports, day)
    write(data, args.out)
    write_status(folder, day)

    publications = {}
    for report in reports:
        publications[report['publication']] = publications.get(report['publication'], 0) + 1
    print(f"reports read: {len(reports)} ("
          + ', '.join(f'{count} {name}' for name, count in publications.items()) + ')')
    print(f"years {data['years'][0]}-{data['years'][-1]}, {len(data['geos'])} areas, "
          f"{len(data['rows'])} rows, {len(data['reports'])} reports")
    us_rows = [r for r in data['rows'] if r[0] == 0]
    last = max(us_rows, key=lambda r: r[1])
    print(f"United States {data['years'][last[1]]}: production {last[5]:,} lb, price {last[7]:.2f} USD per lb")
    ev = data['evidence']
    print(f"evidence {ev['years']}: production {ev['production']}, price {ev['price']}")
    print(f"wrote {args.out} ({os.path.getsize(args.out):,} bytes)")


if __name__ == '__main__':
    main()
