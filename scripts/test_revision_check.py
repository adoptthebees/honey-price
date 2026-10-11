"""Tests for scripts/revision_check.py. Run: python3 -m unittest discover -s scripts"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import revision_check as rc  # noqa: E402
from test_uncertainty import wavy  # noqa: E402

YEARS = list(range(1961, 2001))      # the old release ends in 2000


def releases():
    """An old release of 14 official series, and a current release that has the same figures."""
    old = {}
    for code in range(1, 15):
        for year, value in zip(YEARS, wavy(100 * (code + 1) ** 1.5, code)):
            old[(code, year)] = (value, 'A')
    return old, dict(old)


class RevisionTests(unittest.TestCase):
    def test_an_estimate_that_a_country_made_official_is_compared_with_the_official_figure(self):
        old, current = releases()
        old[(1, 1995)] = (100.0, 'E')
        current[(1, 1995)] = (200.0, 'A')
        row = next(r for r in rc.revisions(old, current) if r['old'] == 'E')
        self.assertAlmostEqual(row['miss'], math.log(2))
        self.assertEqual((row['old'], row['new']), ('E', 'A'))

    def test_age_counts_the_years_before_the_latest_year_of_the_old_release(self):
        old, current = releases()
        rows = [r for r in rc.revisions(old, current)]
        self.assertEqual(min(r['age'] for r in rows), 0)
        self.assertEqual(max(r['age'] for r in rows), len(YEARS) - 1)

    def test_a_figure_that_did_not_change_is_inside_its_range(self):
        old, current = releases()
        self.assertEqual(rc.held(rc.revisions(old, current)), 1.0)

    def test_held_is_the_share_of_figures_inside_their_ranges(self):
        inside, outside = {'miss': 0.1, 'half': 0.2}, {'miss': -0.5, 'half': 0.2}
        self.assertEqual(rc.held([inside, outside, inside, inside]), 0.75)

    def test_a_figure_that_doubled_is_outside_the_range_of_an_official_value(self):
        old, current = releases()
        current[(2, 2000)] = (old[(2, 2000)][0] * 2, 'A')
        row = next(r for r in rc.revisions(old, current) if r['age'] == 0 and abs(r['miss']) > 0.5)
        self.assertGreater(abs(row['miss']), row['half'])

    def test_a_value_that_the_current_release_lacks_is_left_out(self):
        old, current = releases()
        del current[(3, 1990)]
        self.assertEqual(len(rc.revisions(old, current)), 14 * len(YEARS) - 1)

    def test_a_current_value_that_is_empty_or_zero_is_left_out(self):
        old, current = releases()
        current[(3, 1990)] = (None, 'M')      # FAO: missing value
        current[(4, 1990)] = (0, 'A')         # a log ratio with zero is not defined
        self.assertEqual(len(rc.revisions(old, current)), 14 * len(YEARS) - 2)


class WorldRevisionTests(unittest.TestCase):
    """The World total, which the build makes from its countries. FAO publishes it too."""

    @staticmethod
    def world_of(release):
        return {year: sum(release[(code, year)][0] for code in range(1, 15)) for year in YEARS}

    def test_a_world_total_that_did_not_change_is_inside_its_range(self):
        old, _ = releases()
        world = self.world_of(old)
        rows = rc.world_revisions(old, world, dict(world))
        self.assertEqual(len(rows), len(YEARS))
        self.assertEqual(rc.held(rows), 1.0)

    def test_a_world_total_that_doubled_is_outside_its_range(self):
        old, _ = releases()
        world = self.world_of(old)
        later = {**world, 2000: world[2000] * 2}
        row = next(r for r in rc.world_revisions(old, world, later) if r["age"] == 0)
        self.assertAlmostEqual(row["miss"], math.log(2))
        self.assertGreater(row["miss"], row["half"])

    def test_age_counts_the_years_before_the_latest_year_of_the_old_release(self):
        old, _ = releases()
        world = self.world_of(old)
        ages = [r["age"] for r in rc.world_revisions(old, world, dict(world))]
        self.assertEqual((min(ages), max(ages)), (0, len(YEARS) - 1))

    def test_a_year_that_either_total_lacks_is_left_out(self):
        old, _ = releases()
        world = self.world_of(old)
        later = {year: value for year, value in world.items() if year != 1990}
        self.assertEqual(len(rc.world_revisions(old, world, later)), len(YEARS) - 1)
        earlier = {**world, 1991: None}
        self.assertEqual(len(rc.world_revisions(old, earlier, dict(world))), len(YEARS) - 1)


if __name__ == '__main__':
    unittest.main()
