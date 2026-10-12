"""Tests for scripts/stamp_page.py and the versions in index.html. Run: python3 -m unittest discover -s scripts"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stamp_page as sp  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class StampTests(unittest.TestCase):
    def test_a_reference_gets_the_version_of_the_file(self):
        html = '<link rel="stylesheet" href="styles.css">\n<script src="app.js"></script>\n'
        versions = {'styles.css': 'abcd1234', 'app.js': '0badf00d'}
        self.assertEqual(sp.stamp(html, versions),
                         '<link rel="stylesheet" href="styles.css?v=abcd1234">\n<script src="app.js?v=0badf00d"></script>\n')

    def test_an_old_version_is_replaced(self):
        html = '<script src="app.js?v=00000000"></script>'
        self.assertEqual(sp.stamp(html, {'app.js': '0badf00d'}), '<script src="app.js?v=0badf00d"></script>')

    def test_a_file_with_the_same_name_in_another_folder_is_not_touched(self):
        html = '<script src="data/app.js"></script>'
        self.assertEqual(sp.stamp(html, {'app.js': '0badf00d'}), html)

    def test_the_version_follows_the_content_of_the_file(self):
        self.assertEqual(len(sp.version(b'x')), 8)
        self.assertNotEqual(sp.version(b'x'), sp.version(b'y'))


class IndexTests(unittest.TestCase):
    def test_index_html_refers_to_the_current_version_of_each_page_file(self):
        # A browser keeps a script for a while. A new version in the address makes it get the new file.
        with open(os.path.join(ROOT, 'index.html'), encoding='utf-8') as f:
            html = f.read()
        self.assertEqual(sp.stamp(html, sp.versions(ROOT)), html,
                         'index.html is not current: run python3 scripts/stamp_page.py')


if __name__ == '__main__':
    unittest.main()
