"""Confidence scores and uncertainty ranges for the honey series.

FAOSTAT publishes no error estimate for its figures. This module makes two things from the data.
Both are estimates. Neither is a statistical confidence interval of the measurement.

Range (about 90%)
  A value that a national authority reported as an official figure (flag A) gets no range:
  nothing in FAOSTAT measures its error. A value that FAO estimated or imputed, or took from
  another organization (flags E, I, X, B), gets a range. The range is the size of the miss of
  a guess made from the neighbouring years.
  1. For each country and series, take the official years that have two official neighbours.
     The miss is ln(value) minus the mean of ln(neighbours).
  2. The robust spread of those misses is the country scale. A country with few such years
     borrows a pooled scale from countries of a similar size.
  3. K is the 90th percentile of the standardized misses of official values. This follows the
     real tails of the data and does not assume a normal curve.
  4. The range is value times exp(+/- K * country scale * class factor). The class factor is 1,
     or more when the data show that values of that class miss by more than official ones.

Score (0 to 100)
  A rubric, not a probability. It starts from the source flag, then subtracts for a value that
  is in the last three years (FAO collects those again each year), for a value that is far from
  its neighbours, for a country scale that had to be borrowed, and for exports that exceed
  production plus imports. The weights are judgment. The distance test uses K from the data.
"""
import math
import statistics

OFFICIAL = 'A'
MODEL_FLAGS = 'EIXB'        # flags that get a range
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
FIT_PENALTY = (10, 20)      # beyond K, and beyond 1.5 K
BORROWED_PENALTY = 10
MIN_SCORE, MAX_SCORE = 5, 90
BALANCE_PENALTY = ((1.25, 20), (1.05, 10))   # exports over production plus imports


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
    """(scale, borrowed). Borrowed means the scale came from similar countries."""
    own, official = own_scale(values, flags)
    group = group_of(model, values)
    pooled = model['pooled'][group] if group is not None else model['pooled'][1]
    return shrunk(own, len(official), pooled), own is None


def fit(series):
    """Learn pooled scales, K and class factors from {code: (values, flags)} of countries."""
    owns = {}
    for code, (values, flags) in series.items():
        own, official = own_scale(values, flags)
        size = size_of(values)
        if own is not None and size:
            owns[code] = (own, len(official), size)
    sizes = sorted(s for _, _, s in owns.values())
    n = len(sizes)
    cuts = (sizes[n // 3], sizes[2 * n // 3]) if n >= 6 else (0, 0)
    everyone = statistics.median(o for o, _, _ in owns.values())
    pooled = []
    for g in range(3):
        members = [o for o, _, s in owns.values()
                   if (0 if s < cuts[0] else 1 if s < cuts[1] else 2) == g]
        pooled.append(statistics.median(members) if len(members) >= 3 else everyone)
    model = {'cuts': cuts, 'pooled': pooled, 'k90': None, 'fclass': {}, 'calibration': {}}

    # K from official misses, each one standardized with a scale that leaves the miss out.
    standardized = []   # (code, |d|)
    for code, (values, flags) in series.items():
        if code not in owns:
            continue
        res = residuals(values, flags, True)
        points = [(i, r) for i, r in res.items() if flags[i] == OFFICIAL]
        group = group_of(model, values)
        for k, (i, r) in enumerate(points):
            others = [x for j, (_, x) in enumerate(points) if j != k]
            own = robust_sigma(others) if len(others) >= MIN_RUNS else None
            sigma = shrunk(own, len(others), pooled[group])
            if sigma > 0:
                standardized.append((code, abs(r) / sigma))
    model['k90'] = p90(d for _, d in standardized)

    # Out-of-sample check: K from half of the countries, coverage on the other half.
    hits = total = 0
    for fold in (0, 1):
        k = p90(d for c, d in standardized if c % 2 != fold)
        test = [d for c, d in standardized if c % 2 == fold]
        hits += sum(d <= k for d in test)
        total += len(test)
    model['calibration'] = {'coverage': hits / total, 'n': total, 'countries': len(owns)}

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


def balance_penalty(production, export_qty, import_qty):
    """Penalty for a year in which exports exceed production plus imports."""
    if not production or not export_qty or export_qty < 100:
        return 0
    ratio = export_qty / (production + (import_qty or 0))
    for limit, penalty in BALANCE_PENALTY:
        if ratio > limit:
            return penalty
    return 0


def score_series(model, kind, values, flags, last, extra=None):
    """Return (confidence, range) lists aligned to values.

    confidence is a whole number from 5 to 90. range is the half width of the 90% range on a
    log scale in thousandths: 0 for an official value, None where there is no value.
    last is the index of the latest year of the whole data set.
    """
    sigma, borrowed = country_scale(model, values, flags)
    any_neighbours = residuals(values, flags, False)
    k = model['k90']
    ages = AGE_PENALTY[kind]
    conf, band = [], []
    for i, (v, f) in enumerate(zip(values, flags)):
        if v is None or f == ' ':
            conf.append(None)
            band.append(None)
            continue
        half = 0.0
        if f in MODEL_FLAGS:
            half = min(CAP, k * sigma * model['fclass'][f]['factor'])
        score = BASE.get(f, UNKNOWN_FLAG_BASE)
        age = last - i
        if 0 <= age < len(ages):
            score -= ages[age]
        miss = any_neighbours.get(i)
        if miss is not None and sigma > 0:
            z = abs(miss) / sigma
            score -= FIT_PENALTY[1] if z > 1.5 * k else FIT_PENALTY[0] if z > k else 0
        if borrowed:
            score -= BORROWED_PENALTY
        if extra:
            score -= extra[i]
        conf.append(max(MIN_SCORE, min(MAX_SCORE, round(score))))
        band.append(round(half * 1000))
    return conf, band


def describe(model):
    """The numbers the page shows about the model."""
    return {
        'k90': round(model['k90'], 3),
        'coverage': round(model['calibration']['coverage'], 3),
        'checked': model['calibration']['n'],
        'countries': model['calibration']['countries'],
        'scale': [round(s, 3) for s in model['pooled']],
        'classes': {f: {'factor': round(v['factor'], 2), 'n': v['n']} for f, v in model['fclass'].items()},
    }


def rubric():
    """The rules of the score, for the page."""
    return {
        'base': BASE,
        'age': {kind: list(penalties) for kind, penalties in AGE_PENALTY.items()},
        'fit': list(FIT_PENALTY),
        'borrowed': BORROWED_PENALTY,
        'balance': [list(rule) for rule in BALANCE_PENALTY],
        'min': MIN_SCORE,
        'max': MAX_SCORE,
        'provisionalYears': len(AGE_PENALTY['production']),
        'minRuns': MIN_RUNS,
        'cap': round(math.exp(CAP), 1),
    }
