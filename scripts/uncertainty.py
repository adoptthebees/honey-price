"""Confidence scores and uncertainty ranges for the honey series.

FAOSTAT publishes no error estimate for its figures. This module makes two things from the data.
Both are estimates. Neither is a statistical confidence interval of the measurement.

Range (about 90%)
  No figure is exact, so every value has a range: value times exp(+/- half width). The half
  width is the sum in quadrature of four parts.
  1. Reporting error: an assumption for each kind of figure (REPORT_ERROR).
  2. Revision: extra for the last three years, which FAO and national offices revise (REVISION).
  3. Rounding: 24,000 can stand for any figure from 23,500 to 24,500 (rounding_half).
  4. Estimate error: only for a value that is not official: estimated, imputed, from another
     organization, or marked with a flag that this module does not know. It is the size of the
     miss of a guess made from the neighbouring years.
     a. For each country and series, take the official years that have two official neighbours.
        The miss is ln(value) minus the mean of ln(neighbours).
     b. The robust spread of those misses is the country scale. A country with few such years
        borrows a pooled scale from countries of a similar size.
     c. K is the 90th percentile of the standardized misses of official values of all countries.
        This follows the real tails of the data and does not assume a normal curve.
     d. The estimate error is K * country scale * class factor * ESTIMATE_SCALE. The class factor
        is 1, or more when the data show that values of that class miss by more than official ones.
        A flag outside MODEL_FLAGS has the class factor 1.
  Parts 1 and 2 are assumptions that revisions support. FAO production values that were official
  in an old release and in the current one: in the latest year of a release the range held 92% of
  them (releases of 2022, 2023 and 2025 against the release of 2025). For price, the only
  measured revisions are USDA first estimates for US honey against the figures one year later,
  2017 to 2024: price moved by at most 11%, production by at most 1.1%.
  Part 4 is measured twice. K comes from the misses of official values against their neighbours.
  ESTIMATE_SCALE comes from FAO revisions: 110 FAO estimates and imputed values for production
  that a country later replaced with an official figure missed it by more than K predicts. The
  estimate error alone held 71% of them. Scaled by 2.5 it holds 90%. Price and export price have
  no old releases to test, so they are not scaled.
  A total that FAO adds up from countries gets its range and its score from its parts
  (score_total), not from the flag that FAO gives to the sum.

Score (5 to 90)
  A rubric, not a probability. It starts from the source flag, then loses points for age and for
  six measured problems (CHECKS). A check takes points in proportion to its problem and stops at
  its most points, so scores differ between values and between countries and do not sit in steps.
  1. Age: the last three years, which FAO collects again each year (AGE_PENALTY).
  2. Jump: the miss of the value from its two neighbours, in units of K times the country scale.
     A value with one neighbour only (the first year, the last year, a year beside a gap) is
     measured by its step from that neighbour, in units of K1 times the country scale. K1 is the
     90th percentile of the official steps.
  3. History: the share of the 11 years around the value that are not official.
  4. Thin: the country has fewer than 6 official years with official neighbours, so its scale
     comes from similar countries. The fewer such years, the more points.
  5. Rounding: half a unit of the last digit of the figure, as a share of the figure.
  6. Gap (producer price and export price): the producer price against the export price of the
     same country and year, compared with the usual ratio of that country.
  7. Supply (production and export price): exports above production plus imports.
  The weights are judgment. The revision test cannot measure them. Each deduction is a whole
  number, so the score is the start score minus the deductions that the page lists.
"""
import math
import statistics

OFFICIAL = 'A'
MODEL_FLAGS = 'EIXB'        # non-official flags that get a class factor of their own
MIN_RUNS = 6                # official years with official neighbours needed for a country scale
SHRINK = 6                  # weight of the pooled scale, counted in such years
MIN_CLASS_N = 20            # values needed to measure a class factor
CAP = math.log(3)           # no range is wider than a factor of 3 either way
BASE = {'A': 90, 'X': 75, 'B': 75, 'E': 60, 'I': 40}
UNKNOWN_FLAG_BASE = 40
AGE_PENALTY = {             # penalty for the latest year, the one before, and the one before that
    'production': (10, 6, 3),
    'export': (10, 6, 3),
    'price': (20, 10, 5),   # prices are revised more: see the USDA example on the page
}
# Half width of the range of an official value, on a log scale. FAOSTAT gives no error for it,
# so these numbers are assumptions. They rest on the only revisions that we can measure: USDA
# first estimates for US honey against the figures revised one year later, 2017 to 2024.
# Production moved by at most 1.1% (median 0.1%). Price moved by at most 11% (median 2%).
# The tool assumes more for other countries, whose honey statistics are less developed.
REPORT_ERROR = {'production': 0.03, 'price': 0.04, 'export': 0.03}    # every year
REVISION = {                # added for the latest year, the one before, and the one before that
    'production': (0.05, 0.03, 0.015),
    'export': (0.05, 0.03, 0.015),
    'price': (0.11, 0.06, 0.03),
}
# See part 4 of the module text. Measured on FAO revisions of production only.
ESTIMATE_SCALE = {'production': 2.5, 'price': 1.0, 'export': 1.0}
# The tests behind REPORT_ERROR, REVISION and ESTIMATE_SCALE. They are measurements of one day,
# made with scripts/revision_check.py: three FAOSTAT releases of production against the release
# of 2025-12. They do not change when the data changes.
EVIDENCE = {
    'date': '2026-10-12',
    'releases': ['2022-09', '2023-12', '2025-02'],
    'against': '2025-12',
    'official': {'n': 136, 'held': 0.919},     # official in both releases, latest year of the old one
    'estimates': {'n': 110, 'held': 0.900, 'heldWithoutScale': 0.709},   # estimated then, official now
    # The World total that the build makes from the countries, against the World total that FAO
    # published later: all years, and the later change in the latest year of each old release.
    'world': {'n': 185, 'held': 1.0, 'latestChange': [0.087, 0.061, 0.035]},
    'usda': {'years': '2017 to 2024', 'production': 0.011, 'price': 0.11},   # largest US revisions
}
MIN_SCORE, MAX_SCORE = 5, 90
# What the score loses besides the age penalty. A check turns one measured problem into points:
# most * measure / full, in whole points and never above `most`. There is no free zone.
CHECKS = {                  # name: (code in the data file, most points, measure at the most points)
    'jump': ('j', 20, 1.5),       # miss from the neighbours, in units of K times the country scale
    'history': ('h', 15, 1.0),    # share of the years around it that are not official
    'thin': ('t', 10, 1.0),       # share of MIN_RUNS official years that the country lacks
    'rounding': ('r', 20, 0.5),   # half a unit of the last digit, as a share of the figure
    'gap': ('g', 15, 1.5),        # distance of the price ratio from the usual ratio, on a log scale
    'supply': ('s', 20, 0.25),    # exports above production plus imports, as a share of the supply
}
CODES = {'age': 'a', **{name: code for name, (code, _, _) in CHECKS.items()}}
HISTORY_YEARS = 11          # the years around a value that the history check looks at
MIN_GAP_YEARS = 5           # years with both prices needed to know the usual ratio of a country
MIN_SUPPLY_TONNES = 100     # smaller exports are not tested against the supply


def robust_sigma(xs):
    """Robust standard deviation: 1.4826 times the median absolute deviation."""
    xs = list(xs)
    m = statistics.median(xs)
    return 1.4826 * statistics.median(abs(x - m) for x in xs)


def robust_abs(xs):
    """Robust size of values that are centred on zero."""
    return 1.4826 * statistics.median(abs(x) for x in xs)


def p90(xs):
    """90th percentile with linear interpolation."""
    return statistics.quantiles(list(xs), n=10, method='inclusive')[8]


def residuals(values, flags, official_neighbours):
    """Miss of each interior value against the mean of its two neighbours, on a log scale.

    With official_neighbours, a miss counts only when both neighbours are official.
    """
    out = {}
    for i in range(1, len(values) - 1):
        a, b, c = values[i - 1], values[i], values[i + 1]
        if not (a and b and c) or min(a, b, c) <= 0:
            continue
        if official_neighbours and not (flags[i - 1] == OFFICIAL and flags[i + 1] == OFFICIAL):
            continue
        out[i] = math.log(b) - (math.log(a) + math.log(c)) / 2
    return out


def size_of(values):
    present = [v for v in values if v and v > 0]
    return statistics.median(present) if present else None


def own_scale(values, flags):
    """(scale, official misses). The scale is None when there are too few misses."""
    res = residuals(values, flags, True)
    official = [r for i, r in res.items() if flags[i] == OFFICIAL]
    return (robust_sigma(official) if len(official) >= MIN_RUNS else None), official


def shrunk(own, runs, pooled):
    if own is None:
        return pooled
    return math.sqrt((runs * own * own + SHRINK * pooled * pooled) / (runs + SHRINK))


def group_of(model, values):
    size = size_of(values)
    if size is None:
        return None
    low, high = model['cuts']
    return 0 if size < low else 1 if size < high else 2


def country_scale(model, values, flags):
    """(scale, runs). runs is the number of official misses behind the scale of the country itself.

    With fewer than MIN_RUNS the scale is borrowed: it comes from similar countries.
    """
    own, official = own_scale(values, flags)
    group = group_of(model, values)
    pooled = model['pooled'][group] if group is not None else model['pooled'][1]
    return shrunk(own, len(official), pooled), len(official)


def fit(series):
    """Learn pooled scales, K and class factors from {code: (values, flags)} of countries."""
    owns = {}
    for code, (values, flags) in series.items():
        own, official = own_scale(values, flags)
        size = size_of(values)
        if own is not None and size:
            owns[code] = (own, len(official), size)
    if not owns:
        raise ValueError(f'no series has {MIN_RUNS} official values with 2 official neighbours')
    sizes = sorted(s for _, _, s in owns.values())
    n = len(sizes)
    cuts = (sizes[n // 3], sizes[2 * n // 3]) if n >= 6 else (0, 0)
    everyone = statistics.median(o for o, _, _ in owns.values())
    pooled = []
    for g in range(3):
        members = [o for o, _, s in owns.values()
                   if (0 if s < cuts[0] else 1 if s < cuts[1] else 2) == g]
        pooled.append(statistics.median(members) if len(members) >= 3 else everyone)
    model = {'cuts': cuts, 'pooled': pooled, 'k90': None, 'k1': None, 'fclass': {}, 'calibration': {}}

    # K from the official misses of every country, each one standardized with a scale that leaves
    # the miss out. A country without a scale of its own uses the pooled scale of its group.
    standardized = []   # (code, |d|)
    for code, (values, flags) in series.items():
        res = residuals(values, flags, True)
        points = [(i, r) for i, r in res.items() if flags[i] == OFFICIAL]
        group = group_of(model, values)
        for k, (i, r) in enumerate(points):
            others = [x for j, (_, x) in enumerate(points) if j != k]
            own = robust_sigma(others) if len(others) >= MIN_RUNS else None
            sigma = shrunk(own, len(others), pooled[group if group is not None else 1])
            if sigma > 0:
                standardized.append((code, abs(r) / sigma))
    model['k90'] = p90(d for _, d in standardized)

    # K1: the same for the step from a neighbour, for a value that has one neighbour only.
    steps = []
    for values, flags in series.values():
        sigma, _ = country_scale(model, values, flags)
        for i in range(1, len(values)):
            a, b = values[i - 1], values[i]
            if sigma > 0 and flags[i - 1] == OFFICIAL and flags[i] == OFFICIAL and a and b and a > 0 and b > 0:
                steps.append(abs(math.log(b / a)) / sigma)
    model['k1'] = p90(steps)

    # Out-of-sample check: K from half of the countries, coverage on the other half.
    hits = total = 0
    for fold in (0, 1):
        k = p90(d for c, d in standardized if c % 2 != fold)
        test = [d for c, d in standardized if c % 2 == fold]
        hits += sum(d <= k for d in test)
        total += len(test)
    model['calibration'] = {'coverage': hits / total, 'n': total, 'countries': len({c for c, _ in standardized})}

    # Class factors: do values of a class miss by more than official values do?
    by_class = {f: [] for f in MODEL_FLAGS + OFFICIAL}
    for code, (values, flags) in series.items():
        sigma, _ = country_scale(model, values, flags)
        for i, r in residuals(values, flags, True).items():
            if flags[i] in by_class and sigma > 0:
                by_class[flags[i]].append(r / sigma)
    base = robust_abs(by_class[OFFICIAL])
    for f in MODEL_FLAGS:
        n_f = len(by_class[f])
        factor = max(1.0, robust_abs(by_class[f]) / base) if n_f >= MIN_CLASS_N else 1.0
        model['fclass'][f] = {'factor': factor, 'n': n_f}
    return model


def supply_excess(production, export_qty, import_qty):
    """How far exports are above production plus imports, as a share of that supply.

    0 when exports are not above the supply, when a figure is missing, and for exports below
    MIN_SUPPLY_TONNES.
    """
    if not production or not export_qty or export_qty < MIN_SUPPLY_TONNES:
        return 0.0
    return max(0.0, export_qty / (production + (import_qty or 0)) - 1)


def price_gaps(prices, export_prices):
    """How far the producer price is from the export price of the same year, for each year.

    The measure is the distance, on a log scale, of the ratio of the two prices from the usual
    ratio of the country: the median over its years with both prices. A country with fewer than
    MIN_GAP_YEARS such years has no usual ratio. A year without both prices has no gap: 0.
    """
    ratios = {i: math.log(p / e) for i, (p, e) in enumerate(zip(prices, export_prices))
              if p and e and p > 0 and e > 0}
    if len(ratios) < MIN_GAP_YEARS:
        return [0.0] * len(prices)
    usual = statistics.median(ratios.values())
    return [abs(ratios[i] - usual) if i in ratios else 0.0 for i in range(len(prices))]


def history_share(flags, i, width=HISTORY_YEARS):
    """Share of the values in the `width` years around year i that are not official.

    The window keeps its length at the first and the last year of the data. A year without a
    value does not count.
    """
    low = max(0, min(i - width // 2, len(flags) - width))
    window = [f for f in flags[low:low + width] if f != ' ']
    return sum(f != OFFICIAL for f in window) / len(window) if window else 0.0


def jump_measures(values, flags, sigma, k, k1):
    """How far each value is from its neighbours, in units of K times the country scale.

    A value with a neighbour on each side is measured by its miss. A value with one neighbour
    only (the first year, the last year, or a year beside a missing one) is measured by its step
    from that neighbour, in units of K1 times the country scale. The neighbours can have any flag.
    A value without a neighbour, a zero, and a country without a scale have the measure 0.
    """
    n = len(values)
    out = [0.0] * n
    if not sigma > 0:
        return out
    misses = residuals(values, flags, False)
    present = [bool(v and v > 0) for v in values]
    for i, v in enumerate(values):
        if not present[i]:
            continue
        if i in misses:
            out[i] = abs(misses[i]) / sigma / k
        elif i > 0 and present[i - 1]:
            out[i] = abs(math.log(v / values[i - 1])) / sigma / k1
        elif i + 1 < n and present[i + 1]:
            out[i] = abs(math.log(v / values[i + 1])) / sigma / k1
    return out


def whole(x):
    """The nearest whole number. A half goes up."""
    return math.floor(x + 0.5)


def points(check, measure):
    """Whole points that a check takes off the score for a problem of size `measure`."""
    _, most, full = CHECKS[check]
    return whole(most * min(1.0, measure / full))


def age_penalty(kind, age):
    """Score penalty for a value `age` years before the latest year of the data."""
    ages = AGE_PENALTY[kind]
    return ages[age] if 0 <= age < len(ages) else 0


def revision_half(kind, age):
    """Half width, on a log scale, that FAO and national offices may still revise."""
    steps = REVISION[kind]
    return steps[age] if 0 <= age < len(steps) else 0.0


def rounding_half(value):
    """Half a unit of the last digit of a whole-number figure, as a share of the figure.

    A figure that ends in zeros is rounded: 24,000 can stand for any figure from 23,500 to
    24,500. A figure with decimals, a zero and a missing value count as exact.
    """
    if not value or value <= 0 or value != int(value):
        return 0.0
    whole = int(value)
    unit = 1
    while whole % (unit * 10) == 0:
        unit *= 10
    return 0.5 * unit / whole


def score_series(model, kind, values, flags, last, extra=None):
    """Return (confidence, range, deductions) lists aligned to values.

    confidence is a whole number from 5 to 90: the start score of the flag minus the deductions.
    deductions is a dict {check: points} for each value, with age first and only the checks that
    took points, so the page can list them. range is the half width of the range on a log scale
    in thousandths: None where there is no value, and 0 only for a figure of zero, which has no
    relative range. last is the index of the latest year of the whole data set.

    extra holds the measures of the checks that need other series, as supply_excess and
    price_gaps return them: {'supply': [...], 'gap': [...]}, each aligned to values.
    """
    sigma, runs = country_scale(model, values, flags)
    k = model['k90']
    jumps = jump_measures(values, flags, sigma, k, model['k1'])
    thin = max(0, MIN_RUNS - runs) / MIN_RUNS
    outside = extra or {}
    conf, band, why = [], [], []
    for i, (v, f) in enumerate(zip(values, flags)):
        if v is None or f == ' ':
            conf.append(None)
            band.append(None)
            why.append(None)
            continue
        age = last - i
        estimate = (min(CAP, ESTIMATE_SCALE[kind] * k * sigma * model['fclass'].get(f, {}).get('factor', 1.0))
                    if f != OFFICIAL else 0.0)
        half = math.sqrt(REPORT_ERROR[kind] ** 2 + revision_half(kind, age) ** 2
                         + rounding_half(v) ** 2 + estimate ** 2)
        measures = {'jump': jumps[i], 'history': history_share(flags, i), 'thin': thin,
                    'rounding': rounding_half(v)}
        for name in ('gap', 'supply'):
            measures[name] = outside[name][i] if name in outside else 0.0
        lost = {'age': age_penalty(kind, age)}
        lost.update((name, points(name, measures[name])) for name in CHECKS)
        lost = {name: taken for name, taken in lost.items() if taken}
        score = BASE.get(f, UNKNOWN_FLAG_BASE) - sum(lost.values())
        conf.append(max(MIN_SCORE, min(MAX_SCORE, score)))
        band.append(round(min(CAP, half) * 1000) if v > 0 else 0)
        why.append(lost)
    return conf, band, why


def why_text(deductions):
    """The deductions of a value as the short text of the data file, such as 'a10 j3 h4'.

    Each part is a code letter and whole points, in the fixed order of CODES. None for no value.
    """
    if deductions is None:
        return None
    return ' '.join(f'{code}{deductions[name]}' for name, code in CODES.items() if name in deductions)


def sum_half(values, halves, total):
    """Half width, on a log scale, of the range of a sum of parts with independent errors.

    Each part has the half width of its own range on a log scale. The errors of the parts
    partly cancel in a sum, so the range of the total is narrower than the range of a part.
    """
    if not total or total <= 0:
        return None
    spread = math.sqrt(sum((v * math.expm1(h)) ** 2 for v, h in zip(values, halves)))
    return math.log1p(spread / total)


def aggregate_conf(values, confs):
    """Score of a total: the scores of its parts, weighted by the size of each part."""
    pairs = [(v, c) for v, c in zip(values, confs) if c is not None]
    weight = sum(v for v, _ in pairs)
    if not weight:
        return None
    return max(MIN_SCORE, min(MAX_SCORE, whole(sum(v * c for v, c in pairs) / weight)))


def score_total(kind, total, parts, age):
    """Return (confidence, range) of a total that FAO adds up from countries.

    parts is a list of (value, score, half width on a log scale, official) for each country with
    a figure. Part of the total can have no country row. It counts as an estimated value with the
    mean range of the non-official parts. The range is in thousandths, as in score_series.
    """
    rest = max(0.0, total - sum(v for v, _, _, _ in parts))
    others = [(v, h) for v, _, h, official in parts if not official] or [(v, h) for v, _, h, _ in parts]
    size = sum(v for v, _ in others)
    half_rest = sum(v * h for v, h in others) / size if size else REPORT_ERROR[kind]
    values = [v for v, _, _, _ in parts] + [rest]
    halves = [h for _, _, h, _ in parts] + [half_rest]
    scores = [c for _, c, _, _ in parts] + [max(MIN_SCORE, BASE['E'] - age_penalty(kind, age))]
    half = sum_half(values, halves, total)
    return aggregate_conf(values, scores), None if half is None else round(half * 1000)


def describe(model):
    """The numbers the page shows about the model."""
    return {
        'k90': round(model['k90'], 3),
        'k1': round(model['k1'], 3),
        'coverage': round(model['calibration']['coverage'], 3),
        'checked': model['calibration']['n'],
        'countries': model['calibration']['countries'],
        'scale': [round(s, 3) for s in model['pooled']],
        'classes': {f: {'factor': round(v['factor'], 2), 'n': v['n']} for f, v in model['fclass'].items()},
    }


def rubric():
    """The rules of the score and of the range, for the page."""
    return {
        'base': BASE,
        'age': {kind: list(penalties) for kind, penalties in AGE_PENALTY.items()},
        'checks': {name: {'code': code, 'most': most, 'full': full}
                   for name, (code, most, full) in CHECKS.items()},
        'codes': {code: name for name, code in CODES.items()},
        'historyYears': HISTORY_YEARS,
        'minGapYears': MIN_GAP_YEARS,
        'minSupplyTonnes': MIN_SUPPLY_TONNES,
        'min': MIN_SCORE,
        'max': MAX_SCORE,
        'provisionalYears': len(AGE_PENALTY['production']),
        'minRuns': MIN_RUNS,
        'cap': round(math.exp(CAP), 1),
        'report': dict(REPORT_ERROR),
        'revision': {kind: list(steps) for kind, steps in REVISION.items()},
        'estimateScale': dict(ESTIMATE_SCALE),
        'evidence': EVIDENCE,
    }
