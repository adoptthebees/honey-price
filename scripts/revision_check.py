#!/usr/bin/env python3
"""Test the ranges of scripts/uncertainty.py against real FAO revisions of production.

FAO publishes its figures again twice a year and changes some of them. Compare an old release
with the current one, value by value:
  official in both        shows how much FAO revises an official figure.
  estimate, then official shows how far an FAO estimate or imputed value was from the figure
                          that a country gave later: the nearest thing to the truth.
  World total             the total that the build makes from the country values, against the
                          World total that FAO published later.
The module makes ranges from the old release alone. A range must hold the later figure about
nine times in ten. The numbers in uncertainty.EVIDENCE come from this test.

    python3 scripts/revision_check.py OLD.zip [OLD.zip ...] [--current CURRENT.zip]

OLD.zip is an older copy of Production_Crops_Livestock_E_All_Data_(Normalized).zip. The default
current file is the one that scripts/build_data.py keeps in its cache.
"""
import argparse
import csv
import io
import itertools
import math
import os
import tempfile
import zipfile

import build_data
import uncertainty

HONEY_ITEM, PRODUCTION = '1182', '5510'
WORLD_AREA, CHINA_GROUP = 5000, 351
CURRENT = os.path.join(tempfile.gettempdir(), 'honey_price_cache',
                       'Production_Crops_Livestock_E_All_Data_(Normalized).zip')


def whole(value):
    """An integer when the value is whole, as in the data file, so that rounding shows."""
    return None if value is None else int(value) if value == int(value) else value


def read_production(zip_path):
    """Return (countries, world) of honey production.

    countries is {(area code, year): (value, flag)} for the country rows. world is
    {year: value} for the World row of FAOSTAT.
    """
    countries, world = {}, {}
    with zipfile.ZipFile(zip_path) as archive:
        name = next(n for n in archive.namelist() if n.endswith('(Normalized).csv'))
        with archive.open(name) as raw:
            lines = io.TextIOWrapper(raw, encoding='utf-8', errors='replace')
            header = next(lines)
            for row in csv.DictReader(itertools.chain([header], (l for l in lines if HONEY_ITEM in l))):
                if row['Item Code'] != HONEY_ITEM or row['Element Code'] != PRODUCTION:
                    continue
                code, year = int(row['Area Code']), int(row['Year'])
                value = whole(float(row['Value'])) if row['Value'] else None
                if code == WORLD_AREA:
                    world[year] = value
                elif code < WORLD_AREA and code != CHINA_GROUP:
                    countries[(code, year)] = (value, row['Flag'])
    return countries, world


def scored(old):
    """The series of an old release, with the score and the range of each value."""
    years = list(range(1961, max(year for _, year in old) + 1))
    series = {}
    for code in sorted({code for code, _ in old}):
        cells = [old.get((code, year), (None, '')) for year in years]
        series[code] = ([value for value, _ in cells], ''.join(flag or ' ' for _, flag in cells))
    model = uncertainty.fit(series)
    last = len(years) - 1
    scores = {code: uncertainty.score_series(model, 'production', values, flags, last)
              for code, (values, flags) in series.items()}
    return years, last, series, scores


def revisions(old, current):
    """One record for each value that two releases share.

    The record has the age of the value (years before the latest year of the old release), the
    flag in each release, ln(current / old) and the half width of the range that the module
    makes from the old release alone.
    """
    years, last, series, scores = scored(old)
    rows = []
    for code, (values, flags) in series.items():
        band = scores[code][1]
        for i, year in enumerate(years):
            later = current.get((code, year))
            if not values[i] or values[i] <= 0 or flags[i] == ' ' or not later or not later[0] or later[0] <= 0:
                continue
            rows.append({'age': last - i, 'old': flags[i], 'new': later[1],
                         'miss': math.log(later[0] / values[i]), 'half': band[i] / 1000})
    return rows


def world_revisions(old, old_world, current_world):
    """The same test for the World total, which the build makes from the country values.

    One record for each year in which the old release and the current release both have a World
    total. The range comes from the countries of the old release alone. The World value that FAO
    published in the old release is the value that the range surrounds.
    """
    years, last, series, scores = scored(old)
    areas = [{'production': values, 'productionFlags': flags,
              'productionConf': scores[code][0], 'productionBand': scores[code][1]}
             for code, (values, flags) in series.items()]
    _, band = build_data.world_production_score(
        areas, {'production': [old_world.get(year) for year in years]}, last)
    rows = []
    for i, year in enumerate(years):
        before, after = old_world.get(year), current_world.get(year)
        if before and after and before > 0 and after > 0 and band[i] is not None:
            rows.append({'age': last - i, 'miss': math.log(after / before), 'half': band[i] / 1000})
    return rows


def held(rows):
    """The share of rows in which the later figure lies inside the range."""
    return sum(abs(r['miss']) <= r['half'] for r in rows) / len(rows) if rows else None


def by_age(rows):
    """Split rows into the latest year of the old release, the year before, two before, and older."""
    return [(label, [r for r in rows if (r['age'] == age if age < 3 else r['age'] >= 3)])
            for label, age in (('latest year', 0), ('1 year before', 1), ('2 years before', 2), ('older', 3))]


def report(title, rows):
    print(f'{title}: {len(rows)} values, range held {held(rows):.1%}' if rows else f'{title}: no values')
    for label, part in by_age(rows):
        if part:
            print(f'    {label:15s} n={len(part):5d}  held {held(part):6.1%}')


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('old', nargs='+', help='older copies of the FAOSTAT production file')
    parser.add_argument('--current', default=CURRENT, help='the current FAOSTAT production file')
    args = parser.parse_args()
    current, current_world = read_production(args.current)
    releases = [read_production(path) for path in args.old]
    rows = [row for old, _ in releases for row in revisions(old, current)]
    official = [r for r in rows if r['old'] == uncertainty.OFFICIAL and r['new'] == uncertainty.OFFICIAL]
    estimates = [r for r in rows if r['old'] != uncertainty.OFFICIAL and r['new'] == uncertainty.OFFICIAL]
    report('official in both releases', official)
    report('estimate, then official', estimates)
    scale = dict(uncertainty.ESTIMATE_SCALE)
    uncertainty.ESTIMATE_SCALE['production'] = 1.0       # the same test without the scale
    try:
        plain = [r for old, _ in releases for r in revisions(old, current)
                 if r['old'] != uncertainty.OFFICIAL and r['new'] == uncertainty.OFFICIAL]
    finally:
        uncertainty.ESTIMATE_SCALE.update(scale)
    print(f'estimate, then official, without the scale: range held {held(plain):.1%}')
    world = [r for old, old_world in releases for r in world_revisions(old, old_world, current_world)]
    report('World total', world)
    latest = [r for r in world if r['age'] == 0]
    print('World total in the latest year of each old release, later value against old value: '
          + ', '.join(f"{math.expm1(r['miss']):+.1%} (range \u00b1{math.expm1(r['half']):.1%})" for r in latest))


if __name__ == '__main__':
    main()
