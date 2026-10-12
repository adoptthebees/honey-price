"""Tests for scripts/uncertainty.py. Run: python3 -m unittest discover -s scripts"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uncertainty as u  # noqa: E402

YEARS = 40
FIGURE = 1234.5     # a figure with a decimal part is exact: it loses no points for rounding


def wavy(base, phase, amplitude=0.1):
    """A series with a steady wobble, so the same input always gives the same output."""
    return [base * math.exp(amplitude * math.sin(1.7 * i + phase) + 0.3 * amplitude * math.cos(0.9 * i + 2 * phase))
            for i in range(YEARS)]


def synthetic_countries(count=14):
    return {c: (wavy(100 * (c + 1) ** 1.5, c), 'A' * YEARS) for c in range(1, count + 1)}


def flat(value=FIGURE, years=YEARS):
    """A series without any wobble: every miss and every step is zero."""
    return [value] * years


class ResidualTests(unittest.TestCase):
    def test_miss_is_zero_on_a_geometric_run_and_log_distance_otherwise(self):
        flags = 'AAA'
        self.assertAlmostEqual(u.residuals([100, 110, 121], flags, False)[1], 0.0)
        self.assertAlmostEqual(u.residuals([100, 150, 100], flags, False)[1], math.log(1.5))

    def test_official_neighbours_option_skips_a_run_with_an_estimated_neighbour(self):
        self.assertIn(1, u.residuals([100, 110, 121], 'AAA', True))
        self.assertNotIn(1, u.residuals([100, 110, 121], 'EAA', True))
        self.assertIn(1, u.residuals([100, 110, 121], 'EAA', False))


class PointsTests(unittest.TestCase):
    """A check takes points in proportion to the problem that it measures."""

    def test_no_problem_takes_no_points(self):
        for name in u.CHECKS:
            self.assertEqual(u.points(name, 0), 0, name)

    def test_half_of_the_full_measure_takes_half_of_the_most_points(self):
        for name, (_, most, full) in u.CHECKS.items():
            self.assertAlmostEqual(u.points(name, full / 2), most / 2, delta=0.5, msg=name)

    def test_points_grow_with_the_measure_and_stop_at_the_most_points(self):
        for name, (_, most, full) in u.CHECKS.items():
            taken = [u.points(name, full * step / 10) for step in range(31)]
            self.assertEqual(taken, sorted(taken), name)
            self.assertEqual(taken[-1], most, name)
            self.assertEqual(u.points(name, 1000 * full), most, name)

    def test_a_small_problem_still_takes_a_point(self):
        # There is no free zone: a tenth of the full measure is already a problem.
        for name, (_, _, full) in u.CHECKS.items():
            self.assertGreaterEqual(u.points(name, full / 10), 1, name)


class HistoryShareTests(unittest.TestCase):
    def test_share_of_the_years_around_a_value_that_are_not_official(self):
        flags = 'A' * 5 + 'E' * 3 + 'A' * 15         # the 11 years 5 to 15 hold 3 estimates
        self.assertAlmostEqual(u.history_share(flags, 10), 3 / 11)

    def test_the_window_keeps_its_length_at_the_end_of_the_data(self):
        flags = 'A' * 20 + 'E' * 3                   # the 11 years 12 to 22 hold 3 estimates
        self.assertAlmostEqual(u.history_share(flags, 22), 3 / 11)
        self.assertAlmostEqual(u.history_share(flags[::-1], 0), 3 / 11)

    def test_years_without_a_value_do_not_count(self):
        self.assertAlmostEqual(u.history_share('AE  AAAAAAA', 5), 1 / 9)

    def test_a_window_without_values_has_no_history(self):
        self.assertEqual(u.history_share(' ' * 11, 5), 0.0)

    def test_a_series_shorter_than_the_window_uses_all_its_years(self):
        self.assertAlmostEqual(u.history_share('AEEA', 0), 0.5)


class SupplyTests(unittest.TestCase):
    def test_exports_below_supply_have_no_excess(self):
        self.assertEqual(u.supply_excess(1000, 900, 0), 0.0)

    def test_excess_is_the_share_of_the_supply_that_exports_exceed(self):
        self.assertAlmostEqual(u.supply_excess(1000, 1100, 0), 0.1)
        self.assertAlmostEqual(u.supply_excess(1000, 1300, 0), 0.3)

    def test_imports_count_as_supply(self):
        self.assertEqual(u.supply_excess(1000, 1300, 500), 0.0)
        self.assertAlmostEqual(u.supply_excess(1000, 2000, 500), 2000 / 1500 - 1)

    def test_small_exports_and_missing_figures_are_not_measured(self):
        self.assertEqual(u.supply_excess(10, 90, 0), 0.0)
        self.assertEqual(u.supply_excess(None, 5000, 0), 0.0)
        self.assertEqual(u.supply_excess(1000, None, 0), 0.0)


class PriceGapTests(unittest.TestCase):
    def test_a_year_with_the_usual_ratio_has_no_gap(self):
        self.assertEqual(u.price_gaps([200.0] * 6, [100.0] * 6), [0.0] * 6)

    def test_gap_is_the_distance_from_the_usual_ratio_on_a_logarithm_scale(self):
        prices = [200.0] * 5 + [800.0]               # the usual ratio is 2. The last year has 8.
        gaps = u.price_gaps(prices, [100.0] * 6)
        self.assertAlmostEqual(gaps[5], math.log(4))
        self.assertEqual(gaps[:5], [0.0] * 5)

    def test_the_usual_ratio_is_the_one_of_the_country_not_one_for_all(self):
        # A country that always sells for 5 times its export price has no gap.
        self.assertEqual(u.price_gaps([500.0] * 6, [100.0] * 6), [0.0] * 6)

    def test_a_year_without_both_prices_has_no_gap(self):
        prices = [200.0] * 5 + [None, 800.0]
        exports = [100.0] * 5 + [100.0, None]
        self.assertEqual(u.price_gaps(prices, exports)[5:], [0.0, 0.0])

    def test_a_country_with_few_years_of_both_prices_has_no_usual_ratio(self):
        self.assertEqual(u.price_gaps([200.0, 800.0, 200.0, 200.0], [100.0] * 4), [0.0] * 4)


class JumpMeasureTests(unittest.TestCase):
    SCALE, K, K1 = 0.1, 2.0, 3.0

    def measure(self, values, flags=None):
        return u.jump_measures(values, flags or 'A' * len(values), self.SCALE, self.K, self.K1)

    def test_a_value_between_two_neighbours_is_measured_by_its_miss_in_units_of_k(self):
        self.assertAlmostEqual(self.measure([100, 150, 100])[1], math.log(1.5) / self.SCALE / self.K)

    def test_a_value_on_the_line_through_its_neighbours_has_no_jump(self):
        self.assertAlmostEqual(self.measure([100, 110, 121])[1], 0.0)

    def test_a_value_with_one_neighbour_is_measured_by_its_step_in_units_of_k1(self):
        step = math.log(1.5) / self.SCALE / self.K1
        first, last = self.measure([100, 150])
        self.assertAlmostEqual(first, step)
        self.assertAlmostEqual(last, step)

    def test_a_value_next_to_a_missing_year_has_one_neighbour(self):
        step = math.log(1.5) / self.SCALE / self.K1
        measures = self.measure([100, 150, None, 150, 100], 'AA AA')
        self.assertAlmostEqual(measures[1], step)
        self.assertAlmostEqual(measures[3], step)

    def test_a_value_without_a_neighbour_or_without_a_scale_has_no_jump(self):
        self.assertEqual(self.measure([None, 100, None], ' A ')[1], 0.0)
        self.assertEqual(u.jump_measures([100, 150, 100], 'AAA', 0.0, self.K, self.K1), [0.0] * 3)

    def test_the_neighbours_can_have_any_flag(self):
        self.assertAlmostEqual(self.measure([100, 150, 100], 'IAE')[1], math.log(1.5) / self.SCALE / self.K)


class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.model = u.fit(synthetic_countries())

    def score(self, values, flags=None, kind='production', extra=None):
        flags = flags or 'A' * len(values)
        return u.score_series(self.model, kind, values, flags, len(values) - 1, extra)

    def scale(self, values):
        return u.country_scale(self.model, values, 'A' * len(values))[0]

    def test_every_value_has_a_score_a_range_and_deductions_and_a_missing_value_has_none(self):
        values = wavy(1000, 0.4)
        values[5] = None
        conf, band, why = self.score(values, 'A' * 5 + ' ' + 'A' * 34)
        self.assertEqual((len(conf), len(band), len(why)), (YEARS,) * 3)
        self.assertEqual((conf[5], band[5], why[5]), (None, None, None))
        self.assertTrue(all(c is not None and isinstance(d, dict) for i, (c, d) in enumerate(zip(conf, why)) if i != 5))

    def test_the_score_is_the_start_for_the_flag_minus_the_listed_deductions(self):
        # The tooltip lists the deductions, so the list must add up to the score.
        values = wavy(1000, 0.4)
        flags = 'AAAAEEAAIIAAXAAAAAAAB' + 'A' * (YEARS - 21)       # every flag that has a start score
        self.assertEqual(len(flags), YEARS)
        extra = {'supply': [0.05] * YEARS, 'gap': [0.2] * YEARS}
        for kind in ('production', 'price', 'export'):
            conf, _, why = self.score(values, flags, kind, extra)
            for flag, c, lost in zip(flags, conf, why):
                expected = u.BASE[flag] - sum(lost.values())
                self.assertEqual(c, max(u.MIN_SCORE, min(u.MAX_SCORE, expected)), (kind, flag, lost))

    def test_only_deductions_that_took_points_are_listed(self):
        _, _, why = self.score(flat())
        self.assertEqual(why[10], {})
        self.assertTrue(all(points > 0 for lost in self.score(wavy(1000, 0.4))[2] for points in lost.values()))

    def test_a_settled_official_value_without_a_problem_keeps_the_best_score(self):
        self.assertEqual(self.score(flat())[0][10], u.MAX_SCORE)

    def test_worse_source_gives_lower_score(self):
        official = self.score(flat(), 'A' * YEARS)[0][10]
        estimated = self.score(flat(), 'E' * YEARS)[0][10]
        imputed = self.score(flat(), 'I' * YEARS)[0][10]
        self.assertGreater(official, estimated)
        self.assertGreater(estimated, imputed)

    def test_the_latest_year_loses_points_and_a_price_loses_more_than_a_production_figure(self):
        production = self.score(flat(), kind='production')[0]
        price = self.score(flat(), kind='price')[0]
        self.assertLess(production[-1], production[-2])
        self.assertLess(production[-2], production[-3])
        self.assertLess(production[-3], production[-4])
        self.assertLess(price[-1], production[-1])
        self.assertEqual(production[-4], production[10])      # the fourth year back is settled

    def test_a_value_loses_points_in_proportion_to_its_jump_from_its_neighbours(self):
        base = flat()
        unit = self.model['k90'] * self.scale(base)             # a jump of 1 is K times the country scale
        lost = []
        for size in (0.0, 0.3, 0.6, 0.9):
            values = list(base)
            values[20] = base[0] * math.exp(size * unit)
            lost.append(self.score(values)[2][20].get('jump', 0))
        self.assertEqual(lost[0], 0)
        self.assertEqual(lost, sorted(set(lost)))               # more jump, more points
        self.assertEqual(lost[2], u.points('jump', 0.6))

    def test_the_first_and_the_latest_year_are_measured_against_their_one_neighbour(self):
        base = flat()
        unit = self.model['k1'] * self.scale(base)
        for end in (0, -1):
            values = list(base)
            values[end] = base[0] * math.exp(0.6 * unit)
            self.assertEqual(self.score(values)[2][end]['jump'], u.points('jump', 0.6), end)

    def test_a_value_loses_points_when_the_years_around_it_are_mostly_not_official(self):
        flags = 'A' * 15 + 'E' * 5 + 'A' + 'E' * 5 + 'A' * 14       # the 11 years around 20: 10 estimates
        self.assertEqual(self.score(flat(), flags)[2][20]['history'], u.points('history', 10 / 11))
        self.assertNotIn('history', self.score(flat(), 'A' * YEARS)[2][20])

    def test_a_country_with_few_official_years_loses_points_for_a_scale_that_it_had_to_borrow(self):
        def lost(years):
            values = flat()[:years] + [None] * (YEARS - years)
            flags = 'A' * years + ' ' * (YEARS - years)
            return self.score(values, flags)[2][0].get('thin', 0)
        record = [lost(years) for years in (2, 4, 6, 8, YEARS)]
        self.assertEqual(record[0], u.CHECKS['thin'][1])        # no official year with official neighbours
        self.assertEqual(record, sorted(record, reverse=True))  # more years, fewer points
        self.assertEqual(len(set(record[:3])), 3)               # strictly fewer while years are short
        self.assertEqual(record[3:], [0, 0])                    # 6 official years are enough

    def test_a_rounded_figure_loses_points_and_a_precise_one_does_not(self):
        rounded = self.score(flat(1000.0))[2][10]
        self.assertEqual(rounded['rounding'], u.CHECKS['rounding'][1])     # 1,000 can mean 500 to 1,500
        self.assertNotIn('rounding', self.score(flat(1234.5))[2][10])
        self.assertLess(self.score(flat(24137.0))[2][10].get('rounding', 0), rounded['rounding'])

    def test_exports_above_supply_and_a_price_gap_lose_points_and_are_listed(self):
        extra = {'supply': [0.1] * YEARS, 'gap': [0.3] * YEARS}
        plain = self.score(flat())
        measured = self.score(flat(), extra=extra)
        lost = measured[2][10]
        self.assertEqual((lost['supply'], lost['gap']), (u.points('supply', 0.1), u.points('gap', 0.3)))
        self.assertEqual(measured[0][10], plain[0][10] - lost['supply'] - lost['gap'])

    def test_scores_stay_in_the_documented_bounds(self):
        extra = {'supply': [9.0] * YEARS, 'gap': [9.0] * YEARS}
        conf, band, _ = self.score(wavy(1000, 0.4), 'I' * YEARS, 'price', extra)
        for c in conf:
            self.assertTrue(u.MIN_SCORE <= c <= u.MAX_SCORE)
        for b in band:
            self.assertLessEqual(b, round(u.CAP * 1000))

    def test_a_figure_of_zero_has_a_score_and_no_relative_range(self):
        conf, band, _ = self.score([0] * YEARS)
        self.assertEqual(band[10], 0)
        self.assertIsNotNone(conf[10])

    def test_official_values_of_the_latest_year_do_not_all_get_one_score(self):
        # The scores of countries differ with the record of each country, not in steps of ten.
        series = synthetic_countries()
        model = u.fit(series)
        latest = {u.score_series(model, 'production', v, f, YEARS - 1)[0][-1] for v, f in series.values()}
        self.assertGreaterEqual(len(latest), 5)


class RangeTests(unittest.TestCase):
    def setUp(self):
        self.model = u.fit(synthetic_countries())
        self.values = wavy(1000, 0.4)

    def band(self, flags, kind='production', values=None):
        return u.score_series(self.model, kind, values or self.values, flags, YEARS - 1)[1]

    def test_every_value_has_a_range_and_a_non_official_value_has_a_wider_one(self):
        band = self.band('A' * 20 + 'E' + 'A' * 19)
        self.assertGreater(band[10], 0)             # an official value is not exact
        self.assertGreater(band[20], band[10])

    def test_worse_source_gives_wider_range(self):
        official, estimated, imputed = (self.band(flag * YEARS)[10] for flag in 'AEI')
        self.assertLess(official, estimated)
        self.assertLessEqual(estimated, imputed)

    def test_a_flag_that_the_model_does_not_know_gets_the_estimate_error_too(self):
        # A new FAO flag is a non-official value. Its range is wider than an official one.
        official, unknown = (self.band(flag * YEARS)[10] for flag in 'AT')
        self.assertGreater(unknown, official)

    def test_an_official_value_has_a_range_of_each_kind(self):
        for kind in ('production', 'price', 'export'):
            self.assertTrue(all(b > 0 for b in self.band('A' * YEARS, kind)), kind)

    def test_each_of_the_three_latest_years_has_a_wider_range_than_the_year_before(self):
        band = self.band('A' * YEARS)
        self.assertGreater(band[-1], band[-2])
        self.assertGreater(band[-2], band[-3])
        self.assertGreater(band[-3], band[-4])
        self.assertEqual(band[-4], band[10])        # the fourth year back is settled

    def test_a_recent_price_is_revised_more_than_a_recent_production_figure(self):
        self.assertGreater(self.band('A' * YEARS, 'price')[-1], self.band('A' * YEARS, 'production')[-1])

    def test_a_non_official_range_never_falls_below_the_official_range(self):
        for kind in ('production', 'price', 'export'):
            official = self.band('A' * YEARS, kind)
            estimated = self.band('E' * YEARS, kind)
            self.assertTrue(all(e >= o for e, o in zip(estimated, official)), kind)

    def test_a_rounded_figure_has_a_wider_range_than_a_precise_one(self):
        # 24,000 may stand for any figure from 23,500 to 24,500.
        rounded = self.band('A' * YEARS, values=[24000] * YEARS)
        precise = self.band('A' * YEARS, values=[24137] * YEARS)
        self.assertGreater(rounded[10], precise[10])

    def test_a_missing_value_has_no_range(self):
        values = list(self.values)
        values[5] = None
        self.assertIsNone(self.band('A' * 5 + ' ' + 'A' * 34, values=values)[5])

    def test_a_figure_of_zero_has_no_relative_range(self):
        self.assertEqual(self.band('A' * YEARS, values=[0] * YEARS)[10], 0)


class CalibrationTests(unittest.TestCase):
    def test_out_of_sample_coverage_is_close_to_ninety_percent(self):
        model = u.fit(synthetic_countries())
        self.assertGreater(model['k90'], 0.5)
        self.assertTrue(0.8 <= model['calibration']['coverage'] <= 1.0)
        self.assertGreater(model['calibration']['n'], 100)
        self.assertEqual(set(model['fclass']), set(u.MODEL_FLAGS))

    def test_k_counts_the_official_misses_of_a_country_without_a_scale_of_its_own(self):
        # A country with 6 official values in a row has 4 misses: too few for a scale of its own.
        # Its misses still count for K, standardized with the pooled scale.
        series = synthetic_countries()
        short = wavy(500, 0.9)[:8]
        series[99] = (short[:1] + [None] + short[1:7], 'A ' + 'A' * 6)
        with_short, without = u.fit(series), u.fit(synthetic_countries())
        self.assertEqual(with_short['calibration']['n'], without['calibration']['n'] + 4)
        self.assertEqual(with_short['calibration']['countries'], without['calibration']['countries'] + 1)

    def test_a_fit_without_a_series_that_has_a_scale_stops_with_a_message(self):
        with self.assertRaisesRegex(ValueError, 'official'):
            u.fit({})
        with self.assertRaisesRegex(ValueError, 'official'):
            u.fit({1: ([None, 100.0, None], ' A ')})

    def test_k1_holds_about_ninety_percent_of_the_official_steps(self):
        series = synthetic_countries()
        model = u.fit(series)
        held = total = 0
        for values, flags in series.values():
            scale = u.country_scale(model, values, flags)[0]
            for i in range(1, YEARS):
                held += abs(math.log(values[i] / values[i - 1])) / scale <= model['k1']
                total += 1
        self.assertTrue(0.85 <= held / total <= 0.95, held / total)


class RoundingTests(unittest.TestCase):
    def test_a_figure_rounded_to_thousands_hides_half_a_thousand(self):
        self.assertAlmostEqual(u.rounding_half(24000), 500 / 24000)

    def test_a_figure_to_the_unit_hides_half_a_unit(self):
        self.assertAlmostEqual(u.rounding_half(31541), 0.5 / 31541)

    def test_a_figure_with_decimals_is_taken_as_exact(self):
        self.assertEqual(u.rounding_half(5930.4), 0.0)

    def test_a_missing_value_and_a_zero_hide_nothing(self):
        self.assertEqual(u.rounding_half(None), 0.0)
        self.assertEqual(u.rounding_half(0), 0.0)


class WhyTextTests(unittest.TestCase):
    """The data file keeps the deductions of a value as a short text. The page reads it."""

    def test_deductions_are_a_code_letter_and_points_in_a_fixed_order(self):
        self.assertEqual(u.why_text({'jump': 3, 'age': 10}), 'a10 j3')
        self.assertEqual(u.why_text({'jump': 3, 'age': 10}), u.why_text({'age': 10, 'jump': 3}))

    def test_a_value_without_deductions_has_an_empty_text(self):
        self.assertEqual(u.why_text({}), '')

    def test_a_missing_value_has_no_text(self):
        self.assertIsNone(u.why_text(None))

    def test_the_rubric_names_each_code_that_the_text_uses(self):
        names = ['age', *u.CHECKS]
        codes = u.rubric()['codes']
        self.assertEqual(sorted(codes.values()), sorted(names))
        text = u.why_text({name: 1 for name in names})
        self.assertEqual({part[0] for part in text.split()}, set(codes))


class TotalTests(unittest.TestCase):
    """FAO adds up a total from countries. Its range and score come from the parts."""

    def test_one_part_keeps_its_own_range(self):
        self.assertAlmostEqual(u.sum_half([100.0], [0.2], 100.0), 0.2)

    def test_independent_parts_partly_cancel(self):
        four = u.sum_half([100.0] * 4, [0.2] * 4, 400.0)
        self.assertAlmostEqual(four, math.log1p(2 * 100 * (math.exp(0.2) - 1) / 400))
        self.assertLess(four, 0.2)

    def test_a_part_with_a_range_of_zero_adds_nothing(self):
        half = u.sum_half([100.0, 300.0], [0.0, 0.2], 400.0)
        self.assertAlmostEqual(half, math.log1p(300 * (math.exp(0.2) - 1) / 400))

    def test_a_total_of_zero_has_no_range(self):
        self.assertIsNone(u.sum_half([0.0], [0.2], 0.0))

    def test_score_is_the_mean_of_the_part_scores_weighted_by_size(self):
        self.assertEqual(u.aggregate_conf([100.0, 300.0], [90, 50]), 60)

    def test_score_stays_in_the_documented_bounds(self):
        self.assertEqual(u.aggregate_conf([1.0, 1.0], [200, 200]), u.MAX_SCORE)
        self.assertEqual(u.aggregate_conf([1.0, 1.0], [0, 0]), u.MIN_SCORE)

    def test_a_half_rounds_up_as_the_points_of_a_check_do(self):
        self.assertEqual(u.aggregate_conf([1.0, 1.0], [62, 63]), 63)
        self.assertEqual(u.aggregate_conf([1.0, 1.0], [63, 64]), 64)

    def test_a_part_without_a_country_row_makes_the_total_less_certain(self):
        # (value, score, half width, official). In the first total 100 t has no country row.
        parts = [(100.0, 90, 0.03, True), (50.0, 60, 0.4, False)]
        full = parts + [(100.0, 90, 0.03, True)]
        gap = u.score_total('production', 250.0, parts, age=10)
        none = u.score_total('production', 250.0, full, age=10)
        self.assertGreater(gap[1], none[1])      # wider range
        self.assertLess(gap[0], none[0])         # lower score


if __name__ == '__main__':
    unittest.main()
