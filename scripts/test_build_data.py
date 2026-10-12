"""Tests for scripts/build_data.py. Run: python3 -m unittest discover -s scripts"""
import csv
import http.server
import io
import math
import os
import sys
import tempfile
import threading
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_data as b  # noqa: E402
import uncertainty as u  # noqa: E402

STAMPS = {key: f'Last-Modified of {key}' for key in b.SOURCES}


def built_from(stamps):
    """The data that a build leaves behind: the stamp of each FAOSTAT file that it used."""
    return {'meta': {'sources': {key: {'lastModified': value} for key, value in stamps.items()}},
            'years': [2024], 'world': {'production': [1]}, 'areas': [{'code': 1}]}


class UpToDateTests(unittest.TestCase):
    def test_current_when_each_file_has_the_stamp_of_the_last_build(self):
        self.assertTrue(b.is_current(built_from(STAMPS), STAMPS))

    def test_stale_when_one_file_is_newer(self):
        newer = dict(STAMPS, **{next(iter(STAMPS)): 'a later stamp'})
        self.assertFalse(b.is_current(built_from(STAMPS), newer))

    def test_stale_without_a_data_file(self):
        self.assertFalse(b.is_current(None, STAMPS))

    def test_stale_when_the_data_file_lacks_a_source(self):
        old = built_from(STAMPS)
        del old['meta']['sources'][next(iter(STAMPS))]
        self.assertFalse(b.is_current(old, STAMPS))

    def test_stale_when_faostat_sends_no_stamp(self):
        # Without a stamp the files cannot be compared, so the data must be built again.
        blank = dict(STAMPS, **{next(iter(STAMPS)): ''})
        self.assertFalse(b.is_current(built_from(blank), blank))

    def test_stale_when_the_data_file_has_no_areas(self):
        # A file that holds the stamps but not the data is not complete, so the data must be built again.
        for key in ('years', 'world', 'areas'):
            old = built_from(STAMPS)
            del old[key]
            self.assertFalse(b.is_current(old, STAMPS), key)


class ScriptFileTests(unittest.TestCase):
    def test_a_written_data_file_reads_back_unchanged(self):
        data = {'meta': {'retrieved': '2026-10-10', 'name': 'T\u00fcrkiye'}, 'years': [1961, 1962], 'areas': []}
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'honey_data.js')
            b.write(data, path)
            self.assertEqual(b.read_script(path, 'HONEY_DATA'), data)

    def test_a_missing_file_reads_as_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(b.read_script(os.path.join(folder, 'none.js'), 'HONEY_DATA'))

    def test_a_cut_off_file_reads_as_nothing(self):
        # A run that stopped in the middle of a write must lead to a new build, not to a crash.
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'honey_data.js')
            with open(path, 'w', encoding='utf-8') as f:
                f.write('/* header */\nwindow.HONEY_DATA = {"meta":{"retr')
            self.assertIsNone(b.read_script(path, 'HONEY_DATA'))

    def test_the_status_file_holds_the_date_of_the_latest_check(self):
        with tempfile.TemporaryDirectory() as folder:
            b.write_status(folder, '2026-10-17')
            b.write_status(folder, '2026-10-24')
            status = b.read_script(os.path.join(folder, b.STATUS_NAME), 'HONEY_STATUS')
            self.assertEqual(status, {'checked': '2026-10-24'})


def area(quantity, value, flags=None):
    return {'exportQty': quantity, 'exportValue': value, 'exportFlags': flags or 'A' * len(quantity)}


class ExportCheckTests(unittest.TestCase):
    """The page quotes these figures, so they must follow the data."""
    YEARS = [2009, 2010, 2011]

    def setUp(self):
        self.areas = [
            area([1000, 1000, 1000], [2000, 2000, 50000]),    # $0.91 per lb, $0.91, then $22.68
            area([10, 10, 10], [1000, 1000, 100]),            # $45.36 per lb, $45.36, then $4.54
            area([5, 5, 5], [10000, 10, 10]),                 # $907 per lb, then $0.91 twice
            area([5, 5, 5], [10000, 10000, 10000], '   '),    # no flag: FAOSTAT has no export figure
        ]

    def check(self, **kwargs):
        return b.export_check(self.areas, self.YEARS, 100, from_year=2010, bounds=(0.40, 6.0), **kwargs)

    def test_share_of_small_exports_outside_the_bounds_is_the_lowest_and_highest_year(self):
        # 2010: one of two small exports is outside. 2011: none is.
        self.assertEqual(self.check()['smallOutside'], [0.0, 0.5])

    def test_years_before_the_start_year_do_not_count(self):
        # In 2009 both small exports are outside. A count of that year would give 1.0.
        self.assertLess(self.check()['smallOutside'][1], 1.0)

    def test_share_of_large_exports_outside_the_bounds_covers_all_years_together(self):
        self.assertEqual(self.check()['largeOutside'], 0.5)

    def test_tonnage_share_above_the_limit_is_for_the_latest_year(self):
        self.assertAlmostEqual(self.check()['aboveShare'], 1000 / 1015, places=4)

    def test_nothing_to_say_without_small_exports(self):
        self.areas = [area([1000, 1000, 1000], [2000, 2000, 2000])]
        self.assertIsNone(self.check())


class WorldGapTests(unittest.TestCase):
    YEARS = [2012, 2013]

    def gaps(self, world, countries, tolerance=0.01):
        areas = [{'exportQty': list(countries)}]
        return b.world_export_gaps(areas, {'exportQty': list(world)}, self.YEARS, tolerance)

    def test_a_year_in_which_countries_and_world_differ_is_listed_with_both_totals(self):
        self.assertEqual(self.gaps([100, 200], [100, 210]),
                         [{'year': 2013, 'countries': 210, 'world': 200}])

    def test_a_difference_of_exactly_the_tolerance_is_not_a_gap(self):
        self.assertEqual(self.gaps([100, 200], [101, 200]), [])

    def test_a_year_without_a_world_row_is_not_compared(self):
        self.assertEqual(self.gaps([None, 200], [50, 200]), [])

    def test_the_difference_is_measured_against_the_sum_of_the_countries(self):
        # 1.01 of 101.01 is under 1%; against the World total it would be over.
        self.assertEqual(self.gaps([100, 200], [101.01, 200]), [])

    def test_a_world_total_without_country_rows_is_a_gap(self):
        self.assertEqual(self.gaps([100, 200], [0, 200]), [{'year': 2012, 'countries': 0, 'world': 100}])

    def test_a_world_total_of_zero_against_country_rows_is_a_gap(self):
        self.assertEqual(self.gaps([0, 200], [50, 200]), [{'year': 2012, 'countries': 50, 'world': 0}])


class WorldExportScoreTests(unittest.TestCase):
    def countries(self):
        # (export value, score, half width in thousandths) for 2 countries in 2 years
        return [
            {'exportValue': [1000, 3000], 'exportConf': [90, 60], 'exportBand': [200, 300]},
            {'exportValue': [3000, 1000], 'exportConf': [50, 80], 'exportBand': [200, 100]},
        ]

    def test_the_score_is_the_mean_of_the_country_scores_weighted_by_export_value(self):
        conf, _ = b.world_export_score(self.countries(), {'exportFlags': 'AA'})
        self.assertEqual(conf, [(1000 * 90 + 3000 * 50) // 4000, (3000 * 60 + 1000 * 80) // 4000])

    def test_errors_of_two_equal_countries_partly_cancel_in_the_total(self):
        # Two countries of the same size and the same half width h. The errors are independent, so
        # the total has the half width ln(1 + (e^h - 1) / sqrt(2)): less than h, more than zero.
        same = [{'exportValue': [1000], 'exportConf': [70], 'exportBand': [200]}] * 2
        _, band = b.world_export_score(same, {'exportFlags': 'A'})
        self.assertEqual(band, [round(1000 * math.log1p(math.expm1(0.2) / math.sqrt(2)))])
        self.assertTrue(0 < band[0] < 200)

    def test_a_year_without_a_world_export_has_no_score_and_no_range(self):
        self.assertEqual(b.world_export_score(self.countries(), {'exportFlags': ' A'}),
                         ([None, 65], [None, band_of(self.countries(), 1)]))

    def test_a_country_without_a_score_does_not_count(self):
        countries = self.countries() + [{'exportValue': [9000, 9000], 'exportConf': [None, None], 'exportBand': [None, None]}]
        self.assertEqual(b.world_export_score(countries, {'exportFlags': 'AA'}),
                         b.world_export_score(self.countries(), {'exportFlags': 'AA'}))


def band_of(countries, i):
    """The half width of the World export price in year i, by the formula of the independent errors."""
    values = [c['exportValue'][i] for c in countries]
    halves = [c['exportBand'][i] / 1000 for c in countries]
    spread = math.sqrt(sum((v * math.expm1(h)) ** 2 for v, h in zip(values, halves)))
    return round(1000 * math.log1p(spread / sum(values)))


class WorldProductionScoreTests(unittest.TestCase):
    LAST = 3          # 4 years: the ages are 3, 2, 1 and 0

    @staticmethod
    def country(value, conf, band, flag):
        return {'production': [value] * 4, 'productionConf': [conf] * 4,
                'productionBand': [band] * 4, 'productionFlags': flag * 4}

    def score(self, world, *countries):
        return b.world_production_score(list(countries), {'production': world}, self.LAST)

    def official(self):
        return [self.country(100.0, 90, 30, 'A'), self.country(100.0, 90, 30, 'A')]

    def test_a_world_total_that_is_the_sum_of_the_countries_has_the_score_of_the_countries(self):
        conf, band = self.score([200.0] * 4, *self.official())
        self.assertEqual(conf, [90] * 4)
        self.assertTrue(all(0 < x < 30 for x in band))        # 2 independent errors partly cancel

    def test_a_part_of_the_total_without_a_country_row_lowers_the_score(self):
        conf, _ = self.score([300.0] * 4, *self.official())
        self.assertTrue(all(c < 90 for c in conf))

    def test_the_part_without_a_country_row_is_less_certain_in_the_latest_year(self):
        # The rest counts as an estimated value, and an estimate of a recent year is revised more.
        conf, _ = self.score([300.0] * 4, *self.official())
        self.assertLess(conf[3], conf[0])

    def test_the_part_without_a_country_row_has_the_range_of_the_non_official_countries(self):
        # A small estimated country with a wide range sets the range of the part without a row.
        # The 2 official countries have a narrow range, so the total is much wider with the part.
        countries = self.official() + [self.country(1.0, 50, 500, 'E')]
        _, exact = self.score([201.0] * 4, *countries)
        _, with_rest = self.score([301.0] * 4, *countries)
        self.assertTrue(all(w > 5 * e for w, e in zip(with_rest, exact)))

    def test_a_year_without_a_world_total_has_no_score(self):
        conf, band = self.score([200.0, None, 200.0, 200.0], *self.official())
        self.assertEqual((conf[1], band[1]), (None, None))


SCORE_YEARS = list(range(1980, 2020))


def wobble(base, phase):
    return [base * math.exp(0.1 * math.sin(1.7 * i + phase) + 0.03 * math.cos(0.9 * i + 2 * phase))
            for i in range(len(SCORE_YEARS))]


def scored_area(code):
    """A country with official values in every year. Its export price equals its producer price."""
    n = len(SCORE_YEARS)
    price = wobble(2000 + 100 * code, code)
    export_qty = wobble(300 + 20 * code, code + 1)
    return {'code': code, 'name': f'Country {code}',
            'production': wobble(5000 + 700 * code, code + 2), 'productionFlags': 'A' * n,
            'price': price, 'priceFlags': 'A' * n,
            'exportQty': export_qty, 'exportValue': [q * p / 1000 for q, p in zip(export_qty, price)],
            'exportFlags': 'A' * n}


class ScoreAreasTests(unittest.TestCase):
    """The build gives each value a score, a range and the deductions that the page lists."""
    KINDS = ('production', 'price', 'export')

    def setUp(self):
        self.areas = [scored_area(code) for code in range(1, 13)]
        n = len(SCORE_YEARS)
        self.world = {'production': [sum(a['production'][i] for a in self.areas) for i in range(n)],
                      'productionFlags': 'A' * n, 'exportFlags': 'A' * n}

    def score(self, imports=None):
        return b.score_areas(self.areas, self.world, SCORE_YEARS, imports or {})

    @staticmethod
    def lost(area, kind, i):
        """The deductions stored for one value, as {code letter: points}."""
        return {part[0]: int(part[1:]) for part in area[kind + 'Why'][i].split()}

    def test_each_value_gets_a_score_a_range_and_deductions_of_its_own_kind(self):
        self.score()
        for a in self.areas:
            for kind in self.KINDS:
                for suffix in ('Conf', 'Band', 'Why'):
                    self.assertEqual(len(a[kind + suffix]), len(SCORE_YEARS), (a['code'], kind, suffix))

    def test_a_year_without_a_value_has_no_score_no_range_and_no_deductions(self):
        a = self.areas[0]
        a['production'][7] = None
        a['productionFlags'] = a['productionFlags'][:7] + ' ' + a['productionFlags'][8:]
        self.score()
        self.assertEqual((a['productionConf'][7], a['productionBand'][7], a['productionWhy'][7]), (None, None, None))

    def test_exports_below_the_limit_have_no_export_price_and_so_no_score(self):
        a = self.areas[2]
        a['exportQty'][5] = b.MIN_EXPORT_TONNES - 1.0
        self.score()
        self.assertEqual((a['exportConf'][5], a['exportWhy'][5]), (None, None))
        self.assertIsNotNone(a['exportConf'][6])

    def test_the_stored_deductions_add_up_to_the_stored_score(self):
        self.score()
        for a in self.areas:
            for kind in self.KINDS:
                for conf, text in zip(a[kind + 'Conf'], a[kind + 'Why']):
                    taken = sum(int(part[1:]) for part in text.split())
                    self.assertEqual(conf, max(u.MIN_SCORE, u.BASE['A'] - taken), (a['code'], kind, text))

    def test_exports_above_supply_take_points_from_production_and_export_price_only(self):
        a = self.areas[0]
        a['exportQty'][10] = a['production'][10] * 1.5       # far above the supply
        a['exportValue'][10] = a['exportQty'][10] * a['price'][10] / 1000
        self.score()
        most = u.CHECKS['supply'][1]
        self.assertEqual(self.lost(a, 'production', 10)['s'], most)
        self.assertEqual(self.lost(a, 'export', 10)['s'], most)
        self.assertNotIn('s', self.lost(a, 'price', 10))
        self.assertNotIn('s', self.lost(self.areas[1], 'production', 10))

    def test_imports_count_as_supply(self):
        a = self.areas[0]
        a['exportQty'][10] = a['production'][10] * 1.5
        a['exportValue'][10] = a['exportQty'][10] * a['price'][10] / 1000
        self.score({a['code']: list(a['production'])})        # imports as large as the production
        self.assertNotIn('s', self.lost(a, 'production', 10))

    def test_a_producer_price_far_from_the_export_price_takes_points_from_both_prices_only(self):
        a = self.areas[1]
        a['price'][20] *= 4                                   # the usual ratio is 1. In this year it is 4.
        self.score()
        for kind in ('price', 'export'):
            self.assertEqual(self.lost(a, kind, 20)['g'], u.points('gap', math.log(4)), kind)
        self.assertNotIn('g', self.lost(a, 'production', 20))
        self.assertNotIn('g', self.lost(a, 'price', 21))

    def test_the_world_row_gets_a_score_and_a_range_from_the_countries(self):
        self.score()
        for key in ('productionConf', 'productionBand', 'exportConf', 'exportBand'):
            self.assertEqual(len(self.world[key]), len(SCORE_YEARS), key)
            self.assertNotIn(None, self.world[key], key)

    def test_the_model_of_each_kind_is_returned(self):
        models = self.score()
        self.assertEqual(set(models), set(self.KINDS))
        for model in models.values():
            self.assertGreater(model['k90'], 0)
            self.assertGreater(model['k1'], 0)


# ---- The FAOSTAT files -----------------------------------------------------------------------
# Three small zip files in the layout of the FAOSTAT bulk download: one normalized CSV and one
# flags CSV each. The build reads them through a download function that returns the local path.

FIXTURE_YEARS = list(range(1980, 2020))
COLUMNS = ['Area Code', 'Area Code (M49)', 'Area', 'Item Code', 'Item Code (CPC)', 'Item',
           'Element Code', 'Element', 'Year Code', 'Year', 'Unit', 'Value', 'Flag', 'Note']
PRICE_COLUMNS = COLUMNS[:8] + ['Months Code', 'Months'] + COLUMNS[8:]
FLAG_ROWS = [('A', 'Official figure'), ('E', 'Estimated value'), ('I', 'Value imputed by a receiving agency'),
             ('M', 'Missing value; data cannot exist'), ('X', 'Figure from external organization')]


def fao_row(code, name, element, year, value, flag, months=None):
    row = {'Area Code': code, 'Area Code (M49)': f"'{int(code):03d}", 'Area': name, 'Item Code': b.HONEY_ITEM,
           'Item Code (CPC)': "'02910", 'Item': 'Natural honey', 'Element Code': element, 'Element': 'x',
           'Year Code': year, 'Year': year, 'Unit': 't', 'Value': value, 'Flag': flag, 'Note': ''}
    if months is not None:
        row['Months Code'], row['Months'] = months
    return row


def country_rows(code, name, element, values, flags='A', months=None):
    """One row for each year. flags is one letter for all rows, or one letter for each year."""
    per_year = len(flags) == len(values)
    return [fao_row(code, name, element, year, '' if v is None else v, flags[i] if per_year else flags, months)
            for i, (year, v) in enumerate(zip(FIXTURE_YEARS, values))]


def write_zip(folder, source, rows, columns=COLUMNS, flags=FLAG_ROWS):
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    flag_text = 'Flag,Description\n' + ''.join(f'{flag},{description}\n' for flag, description in flags)
    path = os.path.join(folder, source['zip'])
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr(source['zip'].replace('.zip', '.csv'), text.getvalue())
        archive.writestr(source['flags'], flag_text)
    return path


def fixture_rows(production=None, price=None, trade=None):
    """The rows of each FAOSTAT file: three countries, the World row and two groups."""
    areas = [scored_area(code) for code in (1, 2, 3)]
    n = len(FIXTURE_YEARS)
    production = list(production or [])
    price = list(price or [])
    trade = list(trade or [])
    for a in areas:
        code, name = str(a['code']), a['name']
        production += country_rows(code, name, '5510', a['production'])
        price += country_rows(code, name, '5532', a['price'], months=('7021', 'Annual value'))
        price += country_rows(code, name, '5532', [p * 2 for p in a['price']], months=('7001', 'January'))
        trade += country_rows(code, name, '5910', a['exportQty'])
        trade += country_rows(code, name, '5922', a['exportValue'])
        trade += country_rows(code, name, '5610', [10] * n)
    world = [sum(a['production'][i] for a in areas) for i in range(n)]
    production += country_rows(b.WORLD_AREA, 'World', '5510', world)
    production += country_rows(b.CHINA_GROUP, 'China', '5510', areas[0]['production'])
    production += country_rows('5100', 'Africa', '5510', world)
    production += country_rows('96', 'Europe (excluding Finland)', '5510', world)
    trade += country_rows(b.WORLD_AREA, 'World', '5910', [sum(a['exportQty'][i] for a in areas) for i in range(n)])
    trade += country_rows(b.WORLD_AREA, 'World', '5922', [sum(a['exportValue'][i] for a in areas) for i in range(n)])
    return {'production': production, 'price': price, 'trade': trade}


class BuildTests(unittest.TestCase):
    """The build on the three FAOSTAT files, read from a folder instead of the FAOSTAT server."""

    def build(self, rows, flags=FLAG_ROWS):
        with tempfile.TemporaryDirectory() as folder:
            for key, source in b.SOURCES.items():
                write_zip(folder, source, rows[key], PRICE_COLUMNS if key == 'price' else COLUMNS, flags)
            original = b.download
            b.download = lambda name, cache_dir, refresh: (os.path.join(cache_dir, name), f'stamp of {name}')
            try:
                return b.build(folder, False, '2026-10-12')
            finally:
                b.download = original

    def test_the_build_keeps_the_countries_and_leaves_out_the_groups(self):
        data = self.build(fixture_rows())
        self.assertEqual([a['name'] for a in data['areas']], ['Country 1', 'Country 2', 'Country 3'])
        self.assertEqual(data['years'], FIXTURE_YEARS)
        self.assertEqual(data['meta']['sources']['trade']['lastModified'], f"stamp of {b.SOURCES['trade']['zip']}")

    def test_the_price_of_a_year_is_the_annual_value_not_a_month(self):
        data = self.build(fixture_rows())
        self.assertAlmostEqual(data['areas'][0]['price'][0], scored_area(1)['price'][0], places=5)

    def test_a_row_without_a_value_is_a_gap_whatever_its_flag_says(self):
        # FAO marks a year in which the value cannot exist with M. The page and the model treat it
        # as a year without a value, so its flag is a space.
        rows = fixture_rows(production=country_rows('4', 'Country 4', '5510', [None] * 5 + [100] * 35, 'M' * 5 + 'A' * 35))
        data = self.build(rows)
        four = next(a for a in data['areas'] if a['name'] == 'Country 4')
        self.assertEqual(four['productionFlags'][:6], '     A')
        self.assertEqual(four['production'][:6], [None] * 5 + [100])
        self.assertNotIn('M', data['meta']['flags']['production'])

    def test_a_value_without_a_flag_stops_the_build(self):
        rows = fixture_rows(production=country_rows('4', 'Country 4', '5510', [100] * 40, ''))
        with self.assertRaisesRegex(ValueError, 'flag'):
            self.build(rows)

    def test_a_flag_with_two_letters_stops_the_build_even_without_a_value(self):
        rows = fixture_rows(production=country_rows('4', 'Country 4', '5510', [None] * 40, 'AE'))
        with self.assertRaisesRegex(ValueError, "'AE'"):
            self.build(rows)

    def test_two_rows_for_one_country_and_year_stop_the_build(self):
        extra = country_rows('1', 'Country 1', '5510', [1] * 40)[:1]
        with self.assertRaisesRegex(ValueError, '1980'):
            self.build(fixture_rows(production=extra))

    def test_a_flag_letter_that_the_flags_file_lacks_stops_the_build(self):
        rows = fixture_rows(production=country_rows('4', 'Country 4', '5510', [100] * 40, 'X'))
        with self.assertRaisesRegex(ValueError, "'X'"):
            self.build(rows, flags=[f for f in FLAG_ROWS if f[0] != 'X'])

    def test_the_china_group_with_prices_stops_the_build(self):
        rows = fixture_rows(price=country_rows(b.CHINA_GROUP, 'China', '5532', [1] * 40, months=('7021', 'Annual value')))
        with self.assertRaisesRegex(ValueError, 'China'):
            self.build(rows)


# ---- The download ----------------------------------------------------------------------------

class CutServer(http.server.BaseHTTPRequestHandler):
    """Sends the zip file of the test. With `cut`, it sends only half of the bytes it announced."""
    body = b''
    cut = False

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Length', str(len(self.body)))
        self.send_header('Last-Modified', 'Mon, 05 Oct 2026 00:00:00 GMT')
        self.end_headers()
        self.wfile.write(self.body[:len(self.body) // 2] if self.cut else self.body)

    def log_message(self, *args):
        pass


class DownloadTests(unittest.TestCase):
    def setUp(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('data.csv', 'x' * 2000)
        CutServer.body = buffer.getvalue()
        CutServer.cut = False
        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), CutServer)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base_url = b.BASE_URL
        b.BASE_URL = f'http://127.0.0.1:{self.server.server_address[1]}/'
        self.folder = tempfile.TemporaryDirectory()

    def tearDown(self):
        b.BASE_URL = self.base_url
        self.server.shutdown()
        self.server.server_close()
        self.folder.cleanup()

    def test_a_complete_download_is_kept_with_its_stamp(self):
        path, modified = b.download('file.zip', self.folder.name, False)
        self.assertEqual(modified, 'Mon, 05 Oct 2026 00:00:00 GMT')
        with open(path + '.modified', encoding='utf-8') as f:
            self.assertEqual(f.read(), modified)
        self.assertTrue(zipfile.is_zipfile(path))

    def test_a_cut_off_download_stops_the_build_and_is_not_cached(self):
        CutServer.cut = True
        with self.assertRaisesRegex(ValueError, 'bytes'):
            b.download('file.zip', self.folder.name, False)
        self.assertEqual(os.listdir(self.folder.name), [])

    def test_a_file_that_is_not_a_zip_file_stops_the_build(self):
        CutServer.body = b'<html>not found</html>'
        with self.assertRaisesRegex(ValueError, 'zip'):
            b.download('file.zip', self.folder.name, False)
        self.assertEqual(os.listdir(self.folder.name), [])


if __name__ == '__main__':
    unittest.main()
