"""Tests for scripts/build_us_data.py. Run: python3 -m unittest discover -s scripts -p test_us_data.py"""
import csv
import gzip
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
import build_us_data as us  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_DATA = os.path.join(ROOT, 'data', 'us_supply.js')
TODAY = '2026-10-12'

# A report of the layout of 2002 to 2010: postal codes, cents, a row "Oth" with "Sts" on the next row.
OLD_ROWS = [
    ['2', 't', 'Honey: Released February 28, 2002, by the National Agricultural Statistics Service (NASS).'],
    ['2', 't', 'Honey:  Number of Colonies, Yield, Production, Stocks, Price,'],
    ['2', 't', 'and Value by State and United States, 2000 1/ 2/'],
    ['2', 'h', '', '', '', '', '', '', ''],
    ['2', 'u', '', '1,000', 'Pounds', '1,000 Pounds', '1,000 Pounds', 'Cents', '1,000 Dollars'],
    ['2', 'd', 'CA', '440', '70', '30800', '11396', '59', '18172'],
    ['2', 'd', 'FL', '232', '(D)', '24360', '', '54', '13154'],
    ['2', 'd', '', '', '', '', '', '', ''],
    ['2', 'd', 'Oth', '', '', '', '', '', ''],
    ['2', 'd', ' Sts 4/ 5/', '17', '40', '685', '270', '173', '1183'],
    ['2', 'd', 'US 5/', '2620', '84.1', '220339', '85328', '59.7', '132742'],
    ['2', 'c', ''],
    ['3', 't', 'Honey: Released February 28, 2002, by the National Agricultural Statistics Service (NASS).'],
    ['3', 't', 'Honey:  Number of Colonies, Yield, Production, Stocks, Price,'],
    ['3', 't', 'and Value by State and United States, 2001 1/'],
    ['3', 'u', '', '1,000', 'Pounds', '1,000 Pounds', '1,000 Pounds', 'Cents', '1,000 Dollars'],
    ['3', 'd', 'CA', '450', '72', '32400', '12000', '61', '19000'],
    ['3', 'd', 'US 5/', '2700', '80.0', '216000', '80000', '62.5', '135000'],
]

# A report of the layout of 2026: full names, dollars, a table of small producers that must be skipped.
NEW_ROWS = [
    ['19', 't', 'Honey: Released March 13, 2026, by the National Agricultural Statistics Service (NASS).'],
    ['19', 't', 'Colonies, Yield, Production, Stocks, Price, and Value \x96 States and United States: 2024'],
    ['19', 't', '[Colonies which produced honey in more than one State were counted in each State]'],
    ['19', 'u', '', '(1,000)', '(pounds)', '(1,000 pounds)', '(1,000 pounds)', '(dollars)', '(1,000 dollars)'],
    ['19', 'd', 'California', '310', '43', '13330', '3466', '1.96', '26127'],
    ['19', 'd', 'Florida', '124', '33', '4092', '532', '3.14', '12849'],
    ['19', 'd', '', '', '', '', '', '', ''],
    ['19', 'd', 'Other States 5/ 6/', '342', '45', '15264', '3356', '4.03', '61514'],
    ['19', 'd', 'United States 6/ 7/', '2597', '51.7', '134393', '40807', '2.41', '323887'],
    ['20', 't', 'Honey: Released March 13, 2026, by the National Agricultural Statistics Service (NASS).'],
    ['20', 't', 'Colonies, Yield, Production, Stocks, Price, and Value \x96 States and United States: 2025'],
    ['20', 't', '[Colonies which produced honey in more than one State were counted in each State]'],
    ['20', 'u', '', '(1,000)', '(pounds)', '(1,000 pounds)', '(1,000 pounds)', '(dollars)', '(1,000 dollars)'],
    ['20', 'd', 'Florida', '113', '32', '3616', '723', '3.94', '14247'],
    ['20', 'd', 'Other States 5/ 6/', '317', '49', '15604', '4192', '3.75', '58515'],
    ['20', 'd', 'United States 6/ 7/', '2412', '48.0', '115716', '34840', '3.05', '352934'],
    ['21', 't', 'Honey: Released March 13, 2026, by the National Agricultural Statistics Service (NASS).'],
    ['21', 't', 'Number of Colonies, Yield, and Production \x96 United States: 2024 and 2025'],
    ['21', 't', '[Operations with less than 5 colonies that also qualify as a farm]'],
    ['21', 'd', 'United States', '1', '2', '3', '', '', ''],
]


def csv_bytes(rows):
    out = io.StringIO()
    csv.writer(out).writerows(rows)
    return out.getvalue().encode('latin-1')


def make_zip(folder, name, files):
    path = os.path.join(folder, name)
    with zipfile.ZipFile(path, 'w') as archive:
        for member, data in files.items():
            archive.writestr(member, data)
    return path


class ZipTests(unittest.TestCase):
    """Two synthetic zip files: the old layout (cents) and the new layout (dollars)."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.old = make_zip(self.folder.name, 'old.zip',
                            {'hony_all.csv': csv_bytes(OLD_ROWS), 'help.htm': b'<html></html>'})
        self.new = make_zip(self.folder.name, 'new.zip',
                            {'hony_all_tables.csv': csv_bytes(NEW_ROWS), 'hony_index.htm': b'<html></html>'})

    def tearDown(self):
        self.folder.cleanup()


class ReadTablesTests(ZipTests):
    def test_the_tables_are_found_by_title_and_the_years_are_read(self):
        self.assertEqual([t[0] for t in us.read_tables(self.old)], [2000, 2001])
        self.assertEqual([t[0] for t in us.read_tables(self.new)], [2024, 2025])

    def test_the_price_unit_is_cents_or_dollars(self):
        self.assertEqual([t[1] for t in us.read_tables(self.old)], ['cents', 'cents'])
        self.assertEqual([t[1] for t in us.read_tables(self.new)], ['dollars', 'dollars'])

    def test_each_row_keeps_its_name_and_six_cells(self):
        _, _, rows = us.read_tables(self.old)[0]
        self.assertEqual(rows[0], ('CA', '440', '70', '30800', '11396', '59', '18172'))


class ParseReportTests(ZipTests):
    def records(self, zip_path, report=0):
        return us.parse_report(report, us.read_tables(zip_path))

    def find(self, records, geo, year):
        return next(r for r in records if r[2] == geo and r[1] == year)

    def test_cents_become_dollars_and_thousands_are_multiplied(self):
        ca = self.find(self.records(self.old), 'CA', 2000)
        self.assertEqual(ca, (0, 2000, 'CA', 440000, 70.0, 30800000, 11396000, 0.59, 18172000))

    def test_dollars_are_kept_as_they_are(self):
        us_row = self.find(self.records(self.new), 'US', 2025)
        self.assertEqual(us_row, (0, 2025, 'US', 2412000, 48.0, 115716000, 34840000, 3.05, 352934000))

    def test_withheld_and_blank_cells_are_none(self):
        fl = self.find(self.records(self.old), 'FL', 2000)
        self.assertIsNone(fl[4])
        self.assertIsNone(fl[6])
        self.assertEqual(fl[5], 24360000)

    def test_footnote_marks_are_stripped_and_names_become_codes(self):
        self.assertEqual({r[2] for r in self.records(self.old)}, {'CA', 'FL', 'OTH', 'US'})
        self.assertEqual({r[2] for r in self.records(self.new)}, {'CA', 'FL', 'OTH', 'US'})

    def test_an_unknown_name_stops_the_build(self):
        with self.assertRaisesRegex(ValueError, 'Atlantis'):
            us.parse_report(0, [(2025, 'dollars', [('Atlantis', '1', '2', '3', '4', '5', '6')])])


# Records: (report index, year, geo, colonies, yield, production, stocks, price, value)
REPORTS = [
    {'date': '2018-03-14', 'publication': 'Honey', 'url': 'u0'},
    {'date': '2019-05-16', 'publication': 'Honey', 'url': 'u1'},
    {'date': '2026-03-13', 'publication': 'Honey', 'url': 'u2'},
]
RECORDS = [
    (0, 2016, 'US', 2000000, 50.0, 100000000, 5000000, 1.00, 100000000),
    (1, 2016, 'US', 2000000, 50.0, 1000000000, 5000000, 1.00, 100000000),
    (0, 2017, 'US', 2000000, 50.0, 100000000, 5000000, 2.00, 100000000),
    (1, 2017, 'US', 2000000, 50.0, 100000000, 5000000, 2.00, 100000000),
    (0, 2018, 'US', 3000000, 50.0, 100000000, 5000000, 2.00, 100000000),
    (1, 2018, 'US', 3000000, 50.0, 105000000, 5000000, 2.50, 100000000),
    (2, 2025, 'US', 2500000, 50.0, 300000000, 5000000, 3.00, 100000000),
    (0, 2017, 'CA', 1000000, 40.0, 9000000, 100000, 1.90, 18000000),
    (0, 2018, 'CA', 1000000, 40.0, 10000000, 100000, 2.00, 20000000),
    (1, 2018, 'CA', 1000000, 41.0, 11000000, 100000, 2.10, 21000000),
    (0, 2018, 'AL', 500000, 30.0, 4000000, 50000, 2.20, 8800000),
    (0, 2018, 'OTH', 200000, 30.0, 1000000, 5000, 2.30, 2300000),
]


class AssembleTests(unittest.TestCase):
    def setUp(self):
        self.data = us.assemble(RECORDS, REPORTS, TODAY)

    def test_the_geos_start_with_the_us_and_end_with_the_other_states(self):
        self.assertEqual([g['code'] for g in self.data['geos']], ['US', 'AL', 'CA', 'OTH'])
        self.assertEqual(self.data['geos'][0], {'code': 'US', 'name': 'United States', 'level': 'country'})
        self.assertEqual(self.data['geos'][1], {'code': 'AL', 'name': 'Alabama', 'level': 'state'})
        self.assertEqual(self.data['geos'][3], {'code': 'OTH', 'name': 'Other States', 'level': 'other'})

    def test_years_are_a_full_range(self):
        self.assertEqual(self.data['years'], list(range(2016, 2026)))

    def test_rows_take_the_newest_report_for_each_area_and_year(self):
        rows = {(r[0], r[1]): r for r in self.data['rows']}
        self.assertEqual(len(self.data['rows']), 8)
        self.assertEqual(rows[(0, 0)][2], 1)  # US 2016 comes from the second report
        self.assertEqual(rows[(2, 1)][2], 0)  # California 2017 is only in the first report
        self.assertEqual(rows[(2, 2)][2], 1)  # California 2018 comes from the second report
        self.assertEqual(rows[(2, 2)][5], 11000000)
        self.assertEqual(rows[(2, 2)][7], 2.1)

    def test_us_has_the_first_and_second_report_or_nulls(self):
        self.assertEqual(self.data['us'], [
            [2016, 0, 100000000, 1.0, 1, 1000000000, 1.0],
            [2017, 0, 100000000, 2.0, 1, 100000000, 2.0],
            [2018, 0, 100000000, 2.0, 1, 105000000, 2.5],
            [2025, 2, 300000000, 3.0, None, None, None],
        ])

    def test_evidence_is_the_largest_revision_from_2017(self):
        # 2016 has a revision of ten times, but the rule starts in 2017.
        self.assertEqual(self.data['evidence'],
                         {'years': '2017 to 2018', 'production': round(math.log(1.05), 4),
                          'price': round(math.log(1.25), 4)})

    def test_meta_and_reports(self):
        self.assertEqual(self.data['meta']['retrieved'], TODAY)
        self.assertEqual(self.data['meta']['last'], '2026-03-13')
        self.assertEqual(self.data['meta']['source'], 'Honey')
        self.assertEqual(self.data['reports'], REPORTS)


class CurrentTests(unittest.TestCase):
    DATES = ['2018-03-14', '2026-03-13']

    def old(self):
        return {'reports': [{'date': d} for d in self.DATES], 'years': [2000], 'geos': [{'code': 'US'}],
                'rows': [[0, 0, 0, 1, 1.0, 1, 1, 1.0, 1]]}

    def test_current_when_every_release_is_in_the_file(self):
        self.assertTrue(us.is_current(self.old(), self.DATES))

    def test_not_current_when_a_release_is_new(self):
        self.assertFalse(us.is_current(self.old(), self.DATES + ['2026-10-01']))

    def test_not_current_without_rows(self):
        old = self.old()
        del old['rows']
        self.assertFalse(us.is_current(old, self.DATES))

    def test_not_current_without_a_file(self):
        self.assertFalse(us.is_current(None, self.DATES))


class ScriptFileTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.folder.cleanup()

    def test_a_written_data_file_reads_back_unchanged(self):
        data = us.assemble(RECORDS, REPORTS, TODAY)
        path = os.path.join(self.folder.name, 'us_supply.js')
        us.write(data, path)
        self.assertEqual(b.read_script(path, 'HONEY_US_SUPPLY'), data)
        with open(path, encoding='utf-8') as f:
            text = f.read()
        self.assertTrue(text.startswith('/* Generated by scripts/build_us_data.py. Do not edit by hand.\n'))
        self.assertIn('window.HONEY_US_SUPPLY = {"evidence":', text)

    def test_the_status_file_reads_back(self):
        us.write_status(self.folder.name, TODAY)
        path = os.path.join(self.folder.name, 'us_status.js')
        self.assertEqual(b.read_script(path, 'HONEY_US_STATUS'), {'checked': TODAY})


class CutServer(http.server.BaseHTTPRequestHandler):
    """Sends the zip file of the test. With `cut`, it sends only half of the bytes it announced."""
    body = b''
    cut = False

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Length', str(len(self.body)))
        self.end_headers()
        self.wfile.write(self.body[:len(self.body) // 2] if self.cut else self.body)

    def log_message(self, *args):
        pass


class DownloadTests(unittest.TestCase):
    def setUp(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('hony_all.csv', 'x' * 2000)
        CutServer.body = buffer.getvalue()
        CutServer.cut = False
        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), CutServer)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}/release-files/hony0326.zip'
        self.folder = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.folder.cleanup()

    def test_a_complete_download_is_kept_under_its_file_name(self):
        path = us.download(self.url, self.folder.name, False)
        self.assertEqual(os.path.basename(path), 'hony0326.zip')
        self.assertTrue(zipfile.is_zipfile(path))

    def test_a_cut_off_download_stops_the_build_and_is_not_kept(self):
        CutServer.cut = True
        with self.assertRaisesRegex(ValueError, 'bytes'):
            us.download(self.url, self.folder.name, False)
        self.assertEqual(os.listdir(self.folder.name), [])

    def test_a_cached_file_is_not_downloaded_again(self):
        path = us.download(self.url, self.folder.name, False)
        CutServer.cut = True  # a second request would give a cut-off file and an error
        self.assertEqual(us.download(self.url, self.folder.name, False), path)


PAGE = '''<tbody>
<tr>
<td class="views-field views-field-release-date"><time datetime="2026-03-13T12:00:00Z">Mar 13 2026</time>
</td>
<td class="views-field views-field-release-files"><a href="/sites/default/release-files/795818/hony0326.pdf">pdf</a><a href="/sites/default/release-files/795818/hony0326.zip">zip</a></td>
</tr>
<tr>
<td class="views-field views-field-release-date"><time datetime="2019-02-06T12:00:00Z">Feb 06 2019</time>
</td>
<td class="views-field views-field-release-files"><a href="/sites/default/release-files/1/notice.pdf">pdf</a></td>
</tr>
</tbody>'''


class ReleaseListTests(unittest.TestCase):
    def test_each_row_gives_its_date_and_its_zip_file(self):
        self.assertEqual(us.release_rows(PAGE), [
            ('2026-03-13', '/sites/default/release-files/795818/hony0326.zip'),
            ('2019-02-06', None),
        ])

    def test_a_row_without_a_date_stops_with_an_error(self):
        broken = PAGE.replace('<time', '<span').replace('</time>', '</span>')
        with self.assertRaisesRegex(ValueError, 'date'):
            us.release_rows(broken)

    def test_only_releases_with_a_zip_file_are_kept(self):
        self.assertEqual(us.to_releases(us.release_rows(PAGE), 'Honey'), [{
            'date': '2026-03-13', 'publication': 'Honey',
            'url': 'https://esmis.nal.usda.gov/sites/default/release-files/795818/hony0326.zip'}])

    def test_a_list_without_a_zip_file_stops_with_an_error(self):
        with self.assertRaisesRegex(ValueError, 'zip'):
            us.to_releases([('2019-02-06', None)], 'Honey')


class RealFileTests(unittest.TestCase):
    """Checks the committed data file, once it is built."""

    def setUp(self):
        if not os.path.exists(REAL_DATA):
            self.skipTest('data/us_supply.js is not built yet')
        self.data = b.read_script(REAL_DATA, 'HONEY_US_SUPPLY')
        self.assertIsNotNone(self.data)

    def test_the_keys_are_the_specified_ones(self):
        self.assertEqual(set(self.data), {'meta', 'reports', 'years', 'geos', 'rows', 'us', 'evidence'})
        self.assertEqual(set(self.data['meta']),
                         {'publisher', 'source', 'url', 'finalEstimatesUrl', 'retrieved', 'last'})
        self.assertEqual(set(self.data['evidence']), {'years', 'production', 'price'})

    def test_years_run_from_2000_to_the_last_year(self):
        self.assertEqual(self.data['years'], list(range(2000, self.data['years'][-1] + 1)))

    def test_geos_start_with_the_us(self):
        self.assertEqual(self.data['geos'][0], {'code': 'US', 'name': 'United States', 'level': 'country'})

    def test_rows_and_us_rows_have_the_right_length_and_indexes(self):
        geos, years, reports = len(self.data['geos']), len(self.data['years']), len(self.data['reports'])
        for row in self.data['rows']:
            self.assertEqual(len(row), 9)
            self.assertTrue(0 <= row[0] < geos and 0 <= row[1] < years and 0 <= row[2] < reports)
        for row in self.data['us']:
            self.assertEqual(len(row), 7)
            self.assertTrue(0 <= row[1] < reports)
            self.assertTrue(row[4] is None or 0 <= row[4] < reports)

    def test_the_file_is_under_100_kb_after_gzip(self):
        with open(REAL_DATA, 'rb') as f:
            self.assertLess(len(gzip.compress(f.read())), 100 * 1024)


if __name__ == '__main__':
    unittest.main()
