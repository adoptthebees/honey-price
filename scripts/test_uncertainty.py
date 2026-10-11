"""Tests for scripts/uncertainty.py. Run: python3 -m unittest discover -s scripts"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uncertainty as u  # noqa: E402

YEARS = 40


def wavy(base, phase, amplitude=0.1):
    """A series with a steady wobble, so the same input always gives the same output."""
    return [base * math.exp(amplitude * math.sin(1.7 * i + phase) + 0.3 * amplitude * math.cos(0.9 * i + 2 * phase))
            for i in range(YEARS)]


def synthetic_countries(count=14):
    return {c: (wavy(100 * (c + 1) ** 1.5, c), 'A' * YEARS) for c in range(1, count + 1)}


class ResidualTests(unittest.TestCase):
    def test_miss_is_zero_on_a_geometric_run_and_log_distance_otherwise(self):
        flags = 'AAA'
        self.assertAlmostEqual(u.residuals([100, 110, 121], flags, False)[1], 0.0)
        self.assertAlmostEqual(u.residuals([100, 150, 100], flags, False)[1], math.log(1.5))

    def test_official_neighbours_option_skips_a_run_with_an_estimated_neighbour(self):
        self.assertIn(1, u.residuals([100, 110, 121], 'AAA', True))
        self.assertNotIn(1, u.residuals([100, 110, 121], 'EAA', True))
        self.assertIn(1, u.residuals([100, 110, 121], 'EAA', False))


class ScoreAndRangeTests(unittest.TestCase):
    def setUp(self):
        self.model = u.fit(synthetic_countries())
        self.values = wavy(1000, 0.4)

    def run_series(self, flags, kind='production'):
        return u.score_series(self.model, kind, self.values, flags, YEARS - 1)

    def test_official_values_have_no_range_and_model_values_have_one(self):
        flags = 'A' * 20 + 'E' + 'A' * 19
        conf, band = self.run_series(flags)
        self.assertEqual(band[10], 0)
        self.assertGreater(band[20], 0)

    def test_missing_values_have_no_score_and_no_range(self):
        values = list(self.values)
        values[5] = None
        conf, band = u.score_series(self.model, 'production', values, 'A' * 5 + ' ' + 'A' * 34, YEARS - 1)
        self.assertIsNone(conf[5])
        self.assertIsNone(band[5])

    def test_worse_source_gives_lower_score_and_wider_range(self):
        official = self.run_series('A' * YEARS)[0][10]
        estimated = self.run_series('E' * YEARS)[0][10]
        imputed = self.run_series('I' * YEARS)[0][10]
        self.assertGreater(official, estimated)
        self.assertGreater(estimated, imputed)

    def test_latest_year_is_penalised_and_prices_more_than_production(self):
        flags = 'A' * YEARS
        production = self.run_series(flags, 'production')[0]
        price = self.run_series(flags, 'price')[0]
        self.assertLess(production[-1], production[10])
        self.assertLess(price[-1], production[-1])
        self.assertEqual(production[-4], production[10])      # the fourth year back is settled

    def test_scale_that_had_to_be_borrowed_lowers_the_score(self):
        own = self.run_series('A' * YEARS)[0][10]
        short = [self.values[0], self.values[1], self.values[2]] + [None] * (YEARS - 3)
        conf, _ = u.score_series(self.model, 'production', short, 'AAA' + ' ' * (YEARS - 3), YEARS - 1)
        self.assertLess(conf[1], own)

    def test_scores_stay_in_the_documented_bounds(self):
        conf, band = self.run_series('I' * YEARS, 'price')
        for c in conf:
            self.assertTrue(u.MIN_SCORE <= c <= u.MAX_SCORE)
        for b in band:
            self.assertLessEqual(b, round(u.CAP * 1000))


class BalanceTests(unittest.TestCase):
    def test_penalty_grows_with_the_excess_of_exports(self):
        self.assertEqual(u.balance_penalty(1000, 900, 0), 0)
        self.assertEqual(u.balance_penalty(1000, 1100, 0), 10)
        self.assertEqual(u.balance_penalty(1000, 1300, 0), 20)

    def test_imports_count_as_supply_and_small_exports_are_ignored(self):
        self.assertEqual(u.balance_penalty(1000, 1300, 500), 0)
        self.assertEqual(u.balance_penalty(10, 90, 0), 0)
        self.assertEqual(u.balance_penalty(None, 5000, 0), 0)


class CalibrationTests(unittest.TestCase):
    def test_out_of_sample_coverage_is_close_to_ninety_percent(self):
        model = u.fit(synthetic_countries())
        self.assertGreater(model['k90'], 0.5)
        self.assertTrue(0.8 <= model['calibration']['coverage'] <= 1.0)
        self.assertGreater(model['calibration']['n'], 100)
        self.assertEqual(set(model['fclass']), set(u.MODEL_FLAGS))


if __name__ == '__main__':
    unittest.main()
