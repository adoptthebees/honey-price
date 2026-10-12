// Honey price and production.
// Shows FAOSTAT "Natural honey": production, producer price, and export price.
// Each value has a confidence score and a range. Both are made by scripts/uncertainty.py
// and explained on the page.
// The data is in data/honey_data.js. Run scripts/build_data.py to make that file again.
(() => {
  'use strict';

  const D = window.HONEY_DATA;
  const $ = (id) => document.getElementById(id);

  if (!D) {
    const message = document.createElement('p');
    message.className = 'error';
    message.textContent = 'data/honey_data.js did not load. Run scripts/build_data.py to build it.';
    $('app').replaceChildren(message);
    return;
  }

  // ---- Shared helpers (ui.js) ------------------------------------------------
  const { UNITS, DASH, f0, massBig, fmtMass, massText, priceIn, fmtPrice, fmtShare, pct, norm, h, s, link, uid, INK, HALO, frame, hover, hash, year: pageYear } = window.HONEY_UI;

  // ---- FAOSTAT flags ---------------------------------------------------------
  // "A" means official, so it gets no mark. The other letters say how a value was made.
  const FLAGS = D.meta.flags; // { production: {...}, price: {...}, trade: {...} }
  const FLAG_KIND = { production: 'production', price: 'price', export: 'trade' };
  const flagText = (kind, flag) => (flag && flag !== 'A' ? (FLAGS[kind][flag] || flag) : '');
  const FLAG_ORDER = ['A', 'E', 'I', 'X', 'B'];
  const FLAG_WORDS = { A: 'official', E: 'estimated', I: 'imputed', X: 'external', B: 'series break' };
  const flagWord = (flag) => FLAG_WORDS[flag] || flag;
  const breakdown = (parts, total) => FLAG_ORDER.filter((f) => parts[f])
    .map((f) => `${pct(parts[f] / total)} ${flagWord(f)}`).join(', ');

  // ---- Confidence tiers ------------------------------------------------------
  const TIERS = [
    { min: 80, key: 'high', name: 'high', color: '#3f8f5a' },
    { min: 60, key: 'medium', name: 'medium', color: '#c9a227' },
    { min: 40, key: 'low', name: 'low', color: '#d9822b' },
    { min: 0, key: 'vlow', name: 'very low', color: '#b3402e' },
  ];
  const tierOf = (conf) => TIERS.find((t) => conf >= t.min);

  // ---- Data lookups ----------------------------------------------------------
  const years = D.years;
  const lastYear = years[years.length - 1];
  const yearIndex = new Map(years.map((y, i) => [y, i]));
  const byCode = new Map(D.areas.map((a) => [a.code, a]));
  const firstYearWith = (test) => years[Math.max(0, years.findIndex((_, i) => test(i)))];
  const firstPriceYear = firstYearWith((i) => D.areas.some((a) => a.price[i] != null));
  const firstExportYear = firstYearWith((i) => D.world.exportFlags[i] !== ' ');
  const MIN_EXPORT_TONNES = D.meta.minExportTonnes;
  const RUBRIC = D.meta.uncertainty.rubric;

  // FAO asks countries for the last three years again in each yearly cycle.
  const provisionalFrom = years.length - RUBRIC.provisionalYears;
  const isProvisional = (year) => yearIndex.get(year) >= provisionalFrom;

  // The page covers the years of every source. The United States data (data/us_supply.js) go
  // beyond the last FAOSTAT year. In such a year the FAOSTAT panels show the last FAOSTAT year
  // and say so: faoYear() is the year that they show.
  const usYears = (window.HONEY_US_SUPPLY || {}).years || [];
  const firstPageYear = Math.min(years[0], ...usYears);
  const lastPageYear = Math.max(lastYear, ...usYears);
  const faoYear = () => Math.min(Math.max(state.year, years[0]), lastYear);
  const beyondFao = () => state.year > lastYear;
  // The year of a FAOSTAT panel, with its label when the page is in a later year.
  const faoLabel = () => (beyondFao() ? `${faoYear()}, the last FAOSTAT year` : String(faoYear()));

  // ---- State -----------------------------------------------------------------
  const state = { year: lastPageYear, unit: 'lb', area: null, sort: 'production', dir: -1, query: '', official: false };

  function readHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    const y = Number(p.get('y'));
    if (Number.isInteger(y) && y >= firstPageYear && y <= lastPageYear) state.year = y;
    const u = p.get('u');
    if (u && Object.hasOwn(UNITS, u)) state.unit = u;
    const a = Number(p.get('a'));
    if (p.has('a') && byCode.has(a)) state.area = a;
    state.official = p.get('o') === '1';
  }
  // The address keeps only what differs from the default: the last year, pounds, no country, the
  // switch off. So a link or a bookmark made in one year still opens the last year in the next.
  function writeHash() {
    hash.write({
      y: state.year === lastPageYear ? null : state.year,
      u: state.unit === 'lb' ? null : state.unit,
      a: state.area,
      o: state.official ? '1' : null,
    });
  }

  // ---- Points ----------------------------------------------------------------
  // A point is one value with its FAO flag, its confidence score and its range.
  // kind is "production", "price" or "export". The value is in tonnes or in USD per tonne.
  // The export price is the export value divided by the export quantity. A unit value from a few
  // tonnes is noisy (see meta.exportCheck), so a country has an export price only from
  // MIN_EXPORT_TONNES. The World row has no such limit.
  // With "Official values only" on, a country value that is not marked A is not a point. The
  // World values stay: FAO adds them up from the countries, estimates included.
  function pointOf(src, kind, i) {
    let value;
    let flag;
    if (kind === 'export') {
      flag = src.exportFlags[i].trim();
      if (!flag || (src !== D.world && src.exportQty[i] < MIN_EXPORT_TONNES)) return null;
      value = (src.exportValue[i] * 1000) / src.exportQty[i];
    } else {
      value = src[kind][i];
      flag = src[kind + 'Flags'][i].trim();
      if (value == null) return null;
    }
    if (state.official && src !== D.world && flag !== 'A') return null;
    const band = src[kind + 'Band'][i];
    const spread = Math.exp(band / 1000);
    return { value, flag, conf: src[kind + 'Conf'][i], band, why: (src[kind + 'Why'] || [])[i] ?? null, lo: value / spread, hi: value * spread };
  }
  const pointSeries = (src, kind) => years.map((_, i) => pointOf(src, kind, i));

  // The quantity of a country export that is too small for a price, or null.
  function smallExport(src, i) {
    const flag = src.exportFlags[i].trim();
    if (!flag || (state.official && flag !== 'A')) return null;
    return src.exportQty[i] < MIN_EXPORT_TONNES ? src.exportQty[i] : null;
  }
  function emptyExport(a) {
    if (state.official) return 'No official export price.';
    return a.exportFlags.trim() !== ''
      ? `Exports never reached ${MIN_EXPORT_TONNES} tonnes in a year, so there is no export price.`
      : 'FAOSTAT has no export data for this country.';
  }
  // Why a country has no export price for a year: a quantity under the limit, a value that the switch hides, or both.
  function exportCause(a, i) {
    const flag = a.exportFlags[i].trim();
    if (!flag) return DASH;
    const causes = [];
    if (a.exportQty[i] < MIN_EXPORT_TONNES) causes.push(`under ${MIN_EXPORT_TONNES} tonnes`);
    if (state.official && flag !== 'A') causes.push('not official');
    return causes.length ? `${DASH} (${causes.join('; ')})` : DASH;
  }

  // How to show a value of each kind in the selected unit.
  function fmtFor(kind) {
    const unit = state.unit, u = UNITS[unit];
    return kind === 'production'
      ? { num: (t) => fmtMass(t, unit), range: (lo, hi) => `${fmtMass(lo, unit, hi)} to ${fmtMass(hi, unit, hi)}`, unit: ` ${u.big}` }
      : { num: (p) => fmtPrice(p, unit), range: (lo, hi) => `${fmtPrice(lo, unit)} to ${fmtPrice(hi, unit)}`, unit: ` per ${u.short}` };
  }

  // What each deduction of the score means. The data file keeps the deductions of a value as text,
  // a code letter and whole points for each deduction, such as "a10 j3" (see meta.uncertainty.rubric).
  const WHY_LABELS = {
    age: 'recent year, which FAO still revises',
    jump: 'jump from the neighbor years',
    history: 'estimated or imputed years nearby',
    thin: 'few official years to measure this country',
    rounding: 'figure may be rounded',
    gap: 'producer price far from the export price',
    supply: 'exports above production plus imports',
  };
  // The score as a sum, one line each: the start score of the flag, then each deduction.
  // A World value has no deductions: its score is the mean of the country scores.
  function scoreSteps(p, isWorld) {
    if (p.why == null) return isWorld ? ['Mean of the country scores, weighted by size.'] : [];
    const parts = p.why.split(' ').filter(Boolean).map((part) => [RUBRIC.codes[part[0]], Number(part.slice(1))]);
    const taken = parts.reduce((sum, [, points]) => sum + points, 0);
    const start = RUBRIC.base[p.flag] ?? p.conf + taken;
    const lines = [`Score ${p.conf}: starts at ${start} (${flagWord(p.flag)})`];
    for (const [name, points] of parts) lines.push(`\u2212${points} ${WHY_LABELS[name]}`);
    if (start - taken !== p.conf) lines.push(`The score stays between ${RUBRIC.min} and ${RUBRIC.max}.`);
    return lines;
  }

  // The text that says everything about a point. The first line has the value, the source, the
  // range and the score. Then comes one line for each part of the score.
  function describe(kind, p, i, extra, isWorld) {
    const fmt = fmtFor(kind);
    const parts = [`${years[i]}: ${fmt.num(p.value)}${fmt.unit}`];
    parts.push(isWorld ? 'FAO total of the countries'
      : p.flag === 'A' ? 'official' : (flagText(FLAG_KIND[kind], p.flag) || p.flag).toLowerCase());
    if (p.band) parts.push(`range ${fmt.range(p.lo, p.hi)}`);
    parts.push(`confidence ${p.conf} (${tierOf(p.conf).name})`);
    if (isProvisional(years[i])) parts.push('provisional');
    if (extra) parts.push(extra);
    return [parts.join(' \u00b7 '), ...scoreSteps(p, isWorld)].join('\n');
  }
  function chartTip(kind, src, i) {
    const p = pointOf(src, kind, i);
    if (!p) return `${years[i]}: ${kind === 'export' ? 'no export price' : 'no value'}`;
    return describe(kind, p, i, kind === 'export' ? `${massText(src.exportQty[i], state.unit)} exported` : null, src === D.world);
  }
  // The score is out of a copied selection (see styles.css), so a copied table keeps clean numbers.
  const confPill = (p, title) => h('span', {
    class: `conf conf-${tierOf(p.conf).key}`, role: 'img', title, 'aria-label': `confidence ${p.conf}, ${tierOf(p.conf).name}`, text: String(p.conf),
  });

  // ---- Model for one year ----------------------------------------------------
  function modelFor(year) {
    const i = yearIndex.get(year);
    const wp = pointOf(D.world, 'production', i);
    const world = wp ? wp.value : null;
    const rows = [];
    for (const a of D.areas) {
      const pp = pointOf(a, 'production', i);
      const pc = pointOf(a, 'price', i);
      const pe = pointOf(a, 'export', i);
      if (!pp && !pc && !pe) continue;
      const production = pp ? pp.value : null;
      rows.push({
        a, pp, pc, pe, production,
        price: pc ? pc.value : null,
        exportPrice: pe ? pe.value : null,
        exportQty: pe ? a.exportQty[i] : null,
        exportSmall: pe ? null : smallExport(a, i),
        share: production != null && world ? production / world : null,
        rank: null,
      });
    }
    rows.filter((r) => r.production != null)
      .sort((x, y) => y.production - x.production)
      .forEach((r, k) => { r.rank = k + 1; });
    return { i, world, wp, worldFlag: D.world.productionFlags[i].trim(), rows };
  }

  // For every year: the tonnes of production that each FAO flag makes, over the listed countries.
  // This is the raw data: the switch "Official values only" does not change it.
  const COMPOSITION = years.map((_, i) => {
    const parts = {};
    let total = 0;
    for (const a of D.areas) {
      const tonnes = a.production[i];
      if (tonnes == null) continue;
      const flag = a.productionFlags[i].trim();
      parts[flag] = (parts[flag] || 0) + tonnes;
      total += tonnes;
    }
    return total > 0 ? { parts, total } : null;
  });

  // How reliable are the values of one year? This ignores the switch: it describes the raw data.
  function qualityFor(year) {
    const i = yearIndex.get(year);
    const add = (parts, flag, amount) => { parts[flag] = (parts[flag] || 0) + amount; };
    const comp = COMPOSITION[i];
    const q = { prod: comp ? comp.parts : {}, listed: comp ? comp.total : 0, price: {}, nPrice: 0, exp: {}, expT: 0, nExp: 0, smallN: 0, smallT: 0,
      tiers: { high: 0, medium: 0, low: 0, vlow: 0 },
      world: D.world.production[i], worldFlag: D.world.productionFlags[i].trim() };
    for (const a of D.areas) {
      if (a.production[i] != null) q.tiers[tierOf(a.productionConf[i]).key] += 1;
      if (a.price[i] != null) { add(q.price, a.priceFlags[i].trim(), 1); q.nPrice += 1; }
      const f = a.exportFlags[i].trim();
      if (f && a.exportQty[i] >= MIN_EXPORT_TONNES) { add(q.exp, f, a.exportQty[i]); q.expT += a.exportQty[i]; q.nExp += 1; }
      else if (f) { q.smallN += 1; q.smallT += a.exportQty[i]; }
    }
    return q;
  }

  // ---- Line chart (SVG) ------------------------------------------------------
  // A small drawing of a marker, for the keys under a chart.
  function glyph(flag, color) {
    const svg = s('svg', { viewBox: '0 0 14 14', width: 14, height: 14, 'aria-hidden': 'true' });
    const ring = { fill: '#fff', stroke: color, 'stroke-width': 1.5 };
    if (flag === 'A') svg.append(s('circle', { cx: 7, cy: 7, r: 3.2, fill: color }));
    else if (flag === 'E') svg.append(s('circle', { cx: 7, cy: 7, r: 3.6, ...ring }));
    else if (flag === 'I') svg.append(s('path', { d: 'M7 2.5L11.5 7L7 11.5L2.5 7Z', ...ring }));
    else if (flag === 'X') svg.append(s('rect', { x: 3.8, y: 3.8, width: 6.4, height: 6.4, fill: color }));
    else svg.append(s('rect', { x: 3.8, y: 3.8, width: 6.4, height: 6.4, ...ring }));
    return svg;
  }

  // The keys under a chart. Only the marks that the chart uses are listed.
  function legend(pts, color) {
    const flags = FLAG_ORDER.filter((f) => pts.some((p) => p && p.flag === f));
    const keys = flags.map((f) => h('span', { class: 'key' }, glyph(f, color), flagWord(f)));
    if (pts.some((p) => p && p.band)) keys.push(h('span', { class: 'key' }, h('span', { class: 'swatch band' }), 'range'));
    keys.push(h('span', { class: 'key' }, h('span', { class: 'swatch prov' }), 'provisional'));
    keys.push(h('span', { class: 'key' }, h('span', { class: 'swatch strip' }), 'confidence: high to very low'));
    keys.push(h('a', { href: '#confidence-method', text: 'How this is made' }));
    return h('div', { class: 'legend' }, keys);
  }

  // cfg: { pts, conv, color, label, marker, prefix, empty, tip(i), onPick(i) }
  // pts has one point (or null) for each year.
  function lineChart(host, cfg) {
    host.textContent = '';
    const { pts, conv } = cfg;
    const have = pts.map((p, i) => (p ? i : -1)).filter((i) => i >= 0);
    if (!have.length) {
      host.append(h('p', { class: 'note', text: cfg.empty || 'No data.' }));
      return;
    }
    const val = (i) => conv(pts[i].value), lo = (i) => conv(pts[i].lo), hi = (i) => conv(pts[i].hi);
    // A very wide range must not crush the rest of the chart. The scale follows the values;
    // a range that goes above it is cut off at the top.
    const top = Math.min(Math.max(...have.map(hi)), Math.max(...have.map(val)) * 1.5);
    const f = frame({ years, provisionalFrom, host, top, prefix: cfg.prefix, label: cfg.label, height: cfg.height, bottom: 40 });
    const { svg, layer, W, m, iw, ih, n, X, Y } = f;
    const radius = W < 420 ? 2.8 : 3.6;

    // Runs of years that have a point. A gap in the data stays a gap.
    const runs = [];
    let run = [];
    pts.forEach((p, i) => {
      if (!p) { if (run.length) runs.push(run); run = []; } else run.push(i);
    });
    if (run.length) runs.push(run);

    // 1. The range. The band follows the range of each point.
    for (const r of runs) {
      if (!r.some((i) => pts[i].band)) continue;
      const up = r.map((i, k) => `${k ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(hi(i)).toFixed(1)}`).join('');
      const down = r.slice().reverse().map((i) => `L${X(i).toFixed(1)} ${Y(lo(i)).toFixed(1)}`).join('');
      layer.append(s('path', { d: `${up}${down}Z`, fill: cfg.color, 'fill-opacity': 0.25, stroke: cfg.color, 'stroke-opacity': 0.4, 'stroke-width': 0.5 }));
    }
    // 2. The line, thin: the points are what counts.
    for (const r of runs) {
      if (r.length < 2) continue;
      const d = r.map((i, k) => `${k ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(val(i)).toFixed(1)}`).join('');
      layer.append(s('path', { d, fill: 'none', stroke: INK, 'stroke-width': 1.5, 'stroke-linejoin': 'round', opacity: 0.85 }));
    }
    // 3. A bar for the range of each point that has one. It is faint: the band carries the range,
    //    the bar only marks the year.
    for (const i of have) {
      if (!pts[i].band) continue;
      const x = X(i);
      layer.append(s('line', { x1: x, x2: x, y1: Y(hi(i)), y2: Y(lo(i)), stroke: INK, 'stroke-width': 1, opacity: 0.2 }));
    }
    svg.append(layer);

    // 4. A marker for every point. The shape says how FAO made the value. A faint marker
    //    has a low confidence score.
    for (const i of have) {
      const p = pts[i], x = X(i), y = Y(val(i));
      const opacity = (0.5 + 0.5 * (p.conf / RUBRIC.max)).toFixed(2);
      const ring = { fill: '#fff', stroke: cfg.color, 'stroke-width': 1.5, opacity };
      let mark;
      if (p.flag === 'A') mark = s('circle', { cx: x, cy: y, r: radius, fill: cfg.color, opacity, ...HALO });
      else if (p.flag === 'E') mark = s('circle', { cx: x, cy: y, r: radius + 0.5, ...ring });
      else if (p.flag === 'I') {
        const k = radius + 1.2;
        mark = s('path', { d: `M${x} ${y - k}L${x + k} ${y}L${x} ${y + k}L${x - k} ${y}Z`, ...ring });
      } else if (p.flag === 'X') mark = s('rect', { x: x - radius, y: y - radius, width: 2 * radius, height: 2 * radius, fill: cfg.color, opacity, ...HALO });
      else mark = s('rect', { x: x - radius, y: y - radius, width: 2 * radius, height: 2 * radius, ...ring });
      svg.append(mark);
    }

    // 5. A strip under the chart: one cell for each year, colored by the confidence score.
    const stripY = m.t + ih + 8;
    const cell = iw / (n - 1);
    svg.append(s('text', { class: 'tick', x: m.l - 8, y: stripY + 7, 'text-anchor': 'end' }, 'confidence'));
    for (const i of have) {
      svg.append(s('rect', { x: Math.max(m.l, X(i) - cell / 2), y: stripY, width: cell - 1, height: 8, fill: tierOf(pts[i].conf).color }));
    }

    if (cfg.marker >= 0) {
      svg.append(s('line', { class: 'marker', x1: X(cfg.marker), x2: X(cfg.marker), y1: m.t, y2: m.t + ih }));
      if (pts[cfg.marker]) {
        svg.append(s('circle', { cx: X(cfg.marker), cy: Y(val(cfg.marker)), r: radius + 3.5, fill: 'none', stroke: INK, 'stroke-width': 1.75 }));
      }
    }

    const tip = hover(f, { tip: cfg.tip, at: (i) => (pts[i] ? Y(val(i)) : m.t + ih), onPick: cfg.onPick });
    host.append(svg, tip, legend(pts, cfg.color));
  }

  // How a bar of the source chart is filled, for each FAO flag. Official is solid, estimated is lighter,
  // and imputed has thin diagonal lines. Other organizations are brown.
  const STACK_COLOR = { A: ['#c77d00', 1], E: ['#c77d00', 0.5], X: ['#6b4a1f', 0.7], B: ['#6b4a1f', 0.35] };
  const stackFill = (flag, hatchId) => (flag === 'I'
    ? { fill: `url(#${hatchId})` }
    : { fill: STACK_COLOR[flag][0], 'fill-opacity': STACK_COLOR[flag][1] });
  function hatchPattern(id) {
    const pattern = s('pattern', { id, width: 4, height: 4, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' });
    pattern.append(s('line', { x1: 2, y1: 0, x2: 2, y2: 4, stroke: '#c77d00', 'stroke-width': 1.6 }));
    return pattern;
  }

  function stackLegend(rows, hatchId) {
    const keys = FLAG_ORDER.filter((f) => rows.some((c) => c && c.parts[f])).map((f) => {
      const swatch = s('svg', { viewBox: '0 0 14 10', width: 14, height: 10, 'aria-hidden': 'true' });
      swatch.append(s('rect', { width: 14, height: 10, rx: 2, ...stackFill(f, hatchId) }));
      return h('span', { class: 'key' }, swatch, flagWord(f));
    });
    keys.push(h('span', { class: 'key' }, h('span', { class: 'swatch prov' }), 'provisional'));
    return h('div', { class: 'legend' }, keys);
  }

  // One bar for each year: the share of the listed production that each kind of source makes.
  // cfg: { rows (see COMPOSITION), label, marker, tip(i), onPick(i) }
  function stackChart(host, cfg) {
    host.textContent = '';
    const f = frame({ years, provisionalFrom, host, top: 100, step: 25, suffix: '%', label: cfg.label, height: 230, bottom: 28 });
    const { svg, m, iw, ih, n, X, Y } = f;
    const hatchId = `hatch${uid()}`;
    f.defs.append(hatchPattern(hatchId));
    const bar = Math.max(2, (iw / (n - 1)) * 0.78);
    cfg.rows.forEach((c, i) => {
      if (!c) return;
      let base = 0;
      for (const flag of FLAG_ORDER) {
        if (!c.parts[flag]) continue;
        const share = (c.parts[flag] / c.total) * 100;
        svg.append(s('rect', { x: X(i) - bar / 2, y: Y(base + share), width: bar, height: Y(base) - Y(base + share), ...stackFill(flag, hatchId) }));
        base += share;
      }
    });
    svg.append(s('line', { class: 'marker', x1: X(cfg.marker), x2: X(cfg.marker), y1: m.t, y2: m.t + ih }));
    const tip = hover(f, { tip: cfg.tip, at: () => m.t + ih * 0.15, onPick: cfg.onPick });
    host.append(svg, tip, stackLegend(cfg.rows, hatchId));
  }

  const pickYear = (i) => { state.year = years[i]; render(); };

  function compositionTip(i) {
    const c = COMPOSITION[i];
    if (!c) return `${years[i]}: no production values`;
    return `${years[i]}: ${breakdown(c.parts, c.total)} of ${fmtMass(c.total, state.unit)} ${UNITS[state.unit].big} listed`
      + (isProvisional(years[i]) ? ' \u00b7 provisional' : '');
  }

  function drawQualityChart() {
    stackChart($('quality-chart'), {
      rows: COMPOSITION,
      label: `Production by source, ${years[0]} to ${lastYear}`,
      marker: yearIndex.get(faoYear()),
      tip: compositionTip,
      onPick: pickYear,
    });
  }

  function drawWorldCharts() {
    const unit = state.unit, u = UNITS[unit], marker = yearIndex.get(faoYear());
    lineChart($('world-chart'), {
      pts: pointSeries(D.world, 'production'),
      conv: (t) => massBig(t, unit),
      color: '#c77d00',
      height: 290,
      label: `World honey production in ${u.big}, ${years[0]} to ${lastYear}, with confidence`,
      marker,
      empty: 'No values.',
      tip: (i) => chartTip('production', D.world, i),
      onPick: pickYear,
    });
    lineChart($('world-price-chart'), {
      pts: pointSeries(D.world, 'export'),
      conv: (p) => priceIn(p, unit),
      color: '#2f6f7e',
      height: 290,
      prefix: '$',
      label: `World honey export price in USD per ${u.short}, ${firstExportYear} to ${lastYear}, with confidence`,
      marker,
      empty: 'No values.',
      tip: (i) => chartTip('export', D.world, i),
      onPick: pickYear,
    });
  }

  function drawDetailCharts() {
    const a = byCode.get(state.area);
    if (!a || !$('detail-production')) return;
    const unit = state.unit, u = UNITS[unit], marker = yearIndex.get(state.year);
    lineChart($('detail-production'), {
      pts: pointSeries(a, 'production'),
      conv: (t) => massBig(t, unit),
      color: '#c77d00',
      height: 210,
      label: `${a.name}: honey production in ${u.big}, with confidence`,
      marker,
      empty: state.official ? 'No official production values.' : 'FAOSTAT has no production values for this country.',
      tip: (i) => chartTip('production', a, i),
      onPick: pickYear,
    });
    lineChart($('detail-price'), {
      pts: pointSeries(a, 'price'),
      conv: (p) => priceIn(p, unit),
      color: '#6b4a1f',
      height: 210,
      prefix: '$',
      label: `${a.name}: producer price in USD per ${u.short}, with confidence`,
      marker,
      empty: state.official ? 'No official producer price.' : 'FAOSTAT has no producer price for this country.',
      tip: (i) => chartTip('price', a, i),
      onPick: pickYear,
    });
    lineChart($('detail-export'), {
      pts: pointSeries(a, 'export'),
      conv: (p) => priceIn(p, unit),
      color: '#2f6f7e',
      height: 210,
      prefix: '$',
      label: `${a.name}: export price in USD per ${u.short}, with confidence`,
      marker,
      empty: emptyExport(a),
      tip: (i) => chartTip('export', a, i),
      onPick: pickYear,
    });
  }

  // ---- Cards -----------------------------------------------------------------
  // The World export row should match the country rows. The build lists the years in which it does not.
  const worldGapOf = (year) => (D.meta.worldExportGaps || []).find((g) => g.year === year);
  const worldGapText = (g) => `FAO's world total is ${fmtShare(Math.abs(g.countries - g.world) / g.countries)} `
    + `${g.world < g.countries ? 'below' : 'above'} the sum of the countries.`;

  function renderCards(model) {
    const unit = state.unit, u = UNITS[unit], i = model.i;
    // Each FAOSTAT area names its year, because the page can be in a later year.
    $('card-production-title').textContent = `World production, ${faoLabel()}`;
    $('card-export-title').textContent = `World export price, ${faoLabel()}`;
    $('card-range-title').textContent = `Producer price range, ${faoLabel()}`;

    const wp = model.wp;
    $('card-production').textContent = wp ? `${fmtMass(wp.value, unit)} ${u.big}` : DASH;
    const other = unit === 'tonne' ? 'lb' : 'tonne';
    if (wp) {
      const c = COMPOSITION[i];
      $('card-production-sub').textContent = `${fmtMass(wp.value, other)} ${UNITS[other].big}.`
        + (c ? ` ${pct((c.parts.A || 0) / c.total)} of the listed production is official.` : '')
        + (wp.band ? ` Range ${fmtMass(wp.lo, unit, wp.hi)} to ${fmtMass(wp.hi, unit, wp.hi)} ${u.big}.` : '')
        + ` Confidence ${wp.conf} (${tierOf(wp.conf).name}).`;
    } else {
      $('card-production-sub').textContent = `No value for ${faoYear()}.`;
    }

    // The world export price uses the World row of FAOSTAT: export value divided by export quantity.
    const we = pointOf(D.world, 'export', i);
    if (!we) {
      $('card-export').textContent = DASH;
      $('card-export-sub').textContent = `FAOSTAT has no export values for ${faoYear()}.`;
    } else {
      const q = qualityFor(faoYear());
      const gap = worldGapOf(faoYear());
      $('card-export').textContent = `${fmtPrice(we.value, unit)} per ${u.short}`;
      $('card-export-sub').textContent = `Export value divided by export quantity. ${massText(D.world.exportQty[i], unit)} exported.`
        + (q.expT ? ` ${pct((q.exp.A || 0) / q.expT)} of the tonnage is official.` : '')
        + ` Range ${fmtPrice(we.lo, unit)} to ${fmtPrice(we.hi, unit)}. Confidence ${we.conf} (${tierOf(we.conf).name}).`
        + (gap ? ` ${worldGapText(gap)}` : '');
    }

    const priced = model.rows.filter((r) => r.pc).sort((x, y) => x.price - y.price);
    if (!priced.length) {
      $('card-range').textContent = DASH;
      $('card-range-sub').textContent = faoYear() < firstPriceYear
        ? `Producer prices start in ${firstPriceYear}.` : `No producer price for ${faoYear()}.`;
    } else {
      const low = priced[0], high = priced[priced.length - 1];
      $('card-range').textContent = `${fmtPrice(low.price, unit)} to ${fmtPrice(high.price, unit)} per ${u.short}`;
      $('card-range-sub').textContent = `${low.a.name} (lowest) to ${high.a.name} (highest). ${priced.length} countries have a price.`;
    }
  }

  // ---- Reliability list ------------------------------------------------------
  function renderQuality() {
    const q = qualityFor(faoYear());
    $('quality-year').textContent = faoLabel();
    const items = [];
    if (beyondFao()) {
      items.push(`FAOSTAT has no values for ${state.year} yet. This panel, the World charts and the table show ${faoYear()}, its last year.`);
    }
    if (q.listed > 0) {
      const world = q.world == null ? '' : ` The listed countries make ${fmtShare(q.listed / q.world)} of the world total.`;
      items.push(`Production by source: ${breakdown(q.prod, q.listed)}.${world}`);
      const t = q.tiers;
      items.push(`Production confidence, ${t.high + t.medium + t.low + t.vlow} countries: ${t.high} high (80 or more), ${t.medium} medium (60 to 79), `
        + `${t.low} low (40 to 59), ${t.vlow} very low (under 40).`);
    } else {
      items.push(`Production: FAOSTAT has no values for ${faoYear()}.`);
    }
    items.push(q.nPrice
      ? `Producer price: ${q.nPrice} countries, ${breakdown(q.price, q.nPrice)}.`
      : `Producer price: FAOSTAT has none for ${faoYear()}.`);
    items.push(q.nExp
      ? `Export price: ${q.nExp} countries exported ${MIN_EXPORT_TONNES} tonnes or more. By tonnage, ${breakdown(q.exp, q.expT)}. `
        + `${q.smallN} smaller exporters have no price, because small exports give noisy averages. They export ${pct(q.smallT / (q.expT + q.smallT))} of the tonnage.`
      : (q.smallN ? `Export price: no country exported ${MIN_EXPORT_TONNES} tonnes or more.` : `Export price: FAOSTAT has none for ${faoYear()}.`));
    const list = items.map((text) => h('li', { text }));
    if (isProvisional(faoYear())) {
      list.push(h('li', {},
        `${faoYear()} is provisional: FAO and national offices revise the last three years. `,
        h('a', { href: '#sources', text: 'See an example.' })));
    }
    $('quality-list').replaceChildren(...list);
  }

  // ---- Table -----------------------------------------------------------------
  const COLS = [
    { key: 'rank', label: () => '#', sort: false, num: true },
    { key: 'name', label: () => 'Country or area', sort: true, first: 1 },
    { key: 'production', label: () => `Production (${UNITS[state.unit].big})`, sort: true, num: true, first: -1 },
    { key: 'share', label: () => 'Share of world', sort: true, num: true, first: -1 },
    { key: 'price', label: () => `Producer price (USD per ${UNITS[state.unit].short})`, sort: true, num: true, first: -1 },
    { key: 'exportPrice', label: () => `Export price (USD per ${UNITS[state.unit].short})`, sort: true, num: true, first: -1 },
  ];
  const headRow = $('table').tHead.rows[0];
  for (const c of COLS) {
    headRow.append(h('th', { scope: 'col', 'data-key': c.key, class: c.num ? 'num' : null },
      c.sort ? h('button', { type: 'button', class: 'sort' }) : h('span')));
  }

  function sortRows(rows) {
    const key = state.sort, dir = state.dir;
    const val = (r) => (key === 'name' ? r.a.name : r[key]);
    return rows.slice().sort((x, y) => {
      const vx = val(x), vy = val(y);
      if (vx == null && vy == null) return x.a.name.localeCompare(y.a.name);
      if (vx == null) return 1;
      if (vy == null) return -1;
      const c = key === 'name' ? vx.localeCompare(vy) : vx - vy;
      return c * dir || x.a.name.localeCompare(y.a.name);
    });
  }

  // A cell with a value, the mark of its source, and its confidence score.
  function valueCell(kind, p, text, i, title) {
    const td = h('td', { class: 'num', text, title });
    if (p) {
      const note = flagText(FLAG_KIND[kind], p.flag);
      if (note) td.append(h('sup', { class: 'flag', title: note, 'aria-label': note, text: p.flag }));
      td.append(confPill(p, describe(kind, p, i)));
    }
    return td;
  }

  // The letters that a table value can show, each with its meaning, such as "E = Estimated value".
  function letterNotes() {
    const seen = new Map();
    for (const kind of ['production', 'price', 'trade']) {
      for (const [flag, text] of Object.entries(FLAGS[kind])) {
        if (flag !== 'A' && flag !== 'M' && !seen.has(flag)) seen.set(flag, text);
      }
    }
    return FLAG_ORDER.filter((flag) => seen.has(flag)).map((flag) => `${flag} = ${seen.get(flag)}`).join('; ');
  }

  function renderTable(model) {
    const unit = state.unit, u = UNITS[unit], i = model.i;
    for (const th of headRow.cells) {
      const c = COLS.find((x) => x.key === th.dataset.key);
      th.firstElementChild.textContent = c.label();
      if (c.sort) th.setAttribute('aria-sort', state.sort === c.key ? (state.dir > 0 ? 'ascending' : 'descending') : 'none');
    }

    const q = norm(state.query.trim());
    const shown = sortRows(model.rows.filter((r) => !q || norm(r.a.name).includes(q)));
    const frag = document.createDocumentFragment();
    for (const r of shown) {
      const selected = r.a.code === state.area;
      const tr = h('tr', { 'data-code': r.a.code, class: selected ? 'selected' : null });
      tr.append(
        h('td', { class: 'num rank', text: r.rank == null ? DASH : String(r.rank) }),
        h('td', {}, h('button', {
          type: 'button', class: 'link', 'data-code': r.a.code, text: r.a.name,
          'aria-current': selected ? 'true' : null,
        })),
        valueCell('production', r.pp, fmtMass(r.production, unit), i),
        h('td', { class: 'num', text: fmtShare(r.share) }),
        valueCell('price', r.pc, fmtPrice(r.price, unit), i),
        valueCell('export', r.pe, fmtPrice(r.exportPrice, unit), i,
          r.exportQty != null ? `${r.a.name} exported ${massText(r.exportQty, unit)}`
            : r.exportSmall != null ? `${r.a.name} exported only ${massText(r.exportSmall, unit)}. That is too little for a reliable price.` : null),
      );
      frag.append(tr);
    }
    $('table').tBodies[0].replaceChildren(frag);

    const count = (key) => model.rows.filter((r) => r[key] != null).length;
    const listed = model.rows.reduce((sum, r) => sum + (r.production || 0), 0);
    const listedShare = model.world ? listed / model.world : null;
    const gap = !state.official && listedShare != null && listedShare < 0.9995
      ? ` The listed countries make ${fmtShare(listedShare)} of it. The rest has no country row in FAOSTAT.` : '';
    $('countries-title').textContent = `Countries and areas, ${faoLabel()}`;
    $('table-note').textContent = `${shown.length} of ${model.rows.length} countries and areas in ${faoYear()}. `
      + `${count('price')} have a producer price and ${count('exportPrice')} an export price (${MIN_EXPORT_TONNES} tonnes or more exported). `
      + `Shares use the FAOSTAT world total.${gap} `
      + 'FAOSTAT "China" is the sum of China, mainland and Taiwan Province of China, so the table lists those two. '
      + `The small number after a value is its confidence score (5 to 90). A letter after a value means the value is not official: ${letterNotes()}.`
      + (state.official ? ' "Official values only" is on: the table hides non-official values. Shares still use the full world total.' : '');
  }

  // ---- Detail panel ----------------------------------------------------------
  function renderDetail(model) {
    const box = $('detail');
    const a = byCode.get(state.area);
    if (!a) {
      box.replaceChildren(
        h('h2', { text: 'Country detail' }),
        h('p', { class: 'note', text: 'Select a country in the table to see its production, producer price and export price over time.' }),
      );
      return;
    }
    const unit = state.unit, u = UNITS[unit], i = model.i;
    const pp = pointOf(a, 'production', i), pc = pointOf(a, 'price', i), pe = pointOf(a, 'export', i);
    const share = pp && model.world ? pp.value / model.world : null;
    const expFlag = a.exportFlags[i].trim();
    const exportedQty = expFlag && (!state.official || expFlag === 'A') ? a.exportQty[i] : null;
    // A fact: the value, its confidence score and its range.
    const fact = (label, kind, p, text) => [
      h('dt', { text: label }),
      h('dd', {}, text, p ? confPill(p, describe(kind, p, i)) : null,
        p && p.band ? h('small', { text: `range ${fmtFor(kind).range(p.lo, p.hi)}` }) : null),
    ];
    box.replaceChildren(
      h('div', { class: 'panel-head' },
        h('h2', { text: a.name }),
        h('button', { type: 'button', class: 'ghost', id: 'clear', text: 'Clear' })),
      h('dl', { class: 'facts' },
        fact(`Production ${faoYear()}`, 'production', pp, pp ? `${fmtMass(pp.value, unit)} ${u.big}` : DASH),
        h('dt', { text: 'Share of world' }),
        h('dd', { text: fmtShare(share) }),
        fact(`Producer price ${faoYear()}`, 'price', pc, pc ? `${fmtPrice(pc.value, unit)} per ${u.short}` : DASH),
        fact(`Export price ${faoYear()}`, 'export', pe,
          pe ? `${fmtPrice(pe.value, unit)} per ${u.short}` : exportCause(a, i)),
        h('dt', { text: `Exported ${faoYear()}` }),
        h('dd', { text: exportedQty == null ? DASH : massText(exportedQty, unit) })),
      h('h3', { text: `Production (${u.big})` }),
      h('div', { id: 'detail-production', class: 'chart' }),
      h('h3', { text: `Producer price (USD per ${u.short})` }),
      h('div', { id: 'detail-price', class: 'chart' }),
      h('h3', { text: `Export price (USD per ${u.short})` }),
      h('div', { id: 'detail-export', class: 'chart' }),
    );
    drawDetailCharts();
  }

  // ---- Sources, method and footer --------------------------------------------
  function renderSources() {
    const meta = D.meta, models = meta.uncertainty.models;
    const day = (text) => {
      const d = new Date(text);
      return Number.isNaN(d.getTime()) ? text : d.toISOString().slice(0, 10);
    };
    for (const key of ['production', 'price', 'trade']) {
      const f = meta.sources[key];
      $('src-' + key).replaceChildren(
        `Data set ${f.dataset}: `, link(f.page, f.title), `. Element: ${f.element}. File dated ${day(f.lastModified)}. `,
        link(f.lineage, 'FAO description of this data set'), '.');
    }
    const marks = (kind) => Object.entries(meta.flags[kind])
      .map(([flag, text]) => `${flag} = ${text}`).join('; ');
    $('flags-list').replaceChildren(...[['Production', 'production'], ['Producer price', 'price'], ['Export price', 'trade']]
      .map(([label, kind]) => h('li', { text: `${label}: ${marks(kind)}.` })));
    $('flags-note').textContent = 'An export price takes the weaker mark of its value and its quantity. '
      + 'The switch "Official values only" keeps the values marked A.';

    // The export price: the numbers of the page come from the build, so they follow the data.
    const c = meta.exportCheck;
    $('export-check').textContent = c
      ? `The page shows an export price for a country only when it exports ${c.minTonnes} tonnes or more in the year, because small exports give noisy averages. `
        + `From ${c.fromYear} to ${c.toYear}, ${fmtShare(c.smallOutside[0])} to ${fmtShare(c.smallOutside[1])} of country years below ${c.minTonnes} tonnes `
        + `had a price outside $${c.lowPerLb.toFixed(2)} to $${c.highPerLb.toFixed(2)} per lb, against ${fmtShare(c.largeOutside)} from ${c.minTonnes} tonnes up. `
        + `In ${c.toYear}, the countries above the limit made ${fmtShare(c.aboveShare)} of the tonnage that countries exported.`
      : '';
    const gaps = meta.worldExportGaps || [];
    $('export-world').textContent = `The world export price uses the world total of FAO, which also counts exporters below ${meta.minExportTonnes} tonnes.`
      + (gaps.length ? ` The world total differs from the sum of the countries in ${gaps.map((g) => `${g.year} (${fmtShare(Math.abs(g.countries - g.world) / g.countries)} ${g.world < g.countries ? 'below' : 'above'})`).join(', ')}.` : '');

    // The method of the ranges and the scores, with the numbers of this data set.
    const r = RUBRIC, b = r.base, e = r.evidence;
    const names = { production: 'production', price: 'producer price', export: 'export price' };
    const andList = (items) => (items.length > 1 ? `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}` : items.join(''));
    const perKind = (fn) => andList(Object.entries(names).map(([k, name]) => `${name} ${fn(k)}`));
    const share = (x) => `${+(x * 100).toFixed(1)}%`;           // 0.015 becomes 1.5%
    const whole = (x) => `${Math.round(x * 100)}%`;
    const pm = (x) => `\u00b1${share(x)}`;
    const widened = [];
    for (const [kind, name] of Object.entries(names)) {
      for (const [flag, k] of Object.entries(models[kind].classes)) {
        if (k.factor > 1) widened.push(`${name}, ${flagWord(flag)}: \u00d7${k.factor} (measured on ${k.n} values)`);
      }
    }
    $('cm-parts').replaceChildren(...[
      `Reporting error (an assumption): ${perKind((k) => pm(r.report[k]))}.`,
      'Revision (an assumption): FAO and national offices revise the last three years. For the latest year, the year before and the year before that: '
        + `production ${andList(r.revision.production.map(pm))}; producer price ${andList(r.revision.price.map(pm))}; export price ${andList(r.revision.export.map(pm))}.`,
      'Rounding: a value that ends in zeros is rounded, so 24,000 can mean 23,500 to 24,500.',
      'Estimate error, for estimated, imputed and external values only: the tool guesses each official value from its two neighbors and measures the miss. '
        + `K says how far a guess can miss: 90% of official values miss by less than K times the scale of their country. K is ${perKind((k) => models[k].k90.toFixed(2))} (a normal curve gives 1.64). `
        + (widened.length ? `A flag with larger misses than official values widens the range: ${widened.join('; ')}. ` : '')
        + `For production the estimate error is multiplied by ${r.estimateScale.production} (see the revision test). `
        + `No range is more than ${r.cap} times the value, up or down.`,
    ].map((text) => h('li', { text })));
    $('cm-tests').replaceChildren(...[
      'Neighbor test: the tool hid each official value that has two official neighbors and made a range from the neighbors. '
        + 'It learned K on half of the countries and tested it on the other half. The range held '
        + andList(Object.entries(names).map(([k, name]) => `${(models[k].coverage * 100).toFixed(1)}% of ${f0.format(models[k].checked)} ${name} values`)) + '.',
      `Revision test (production, ${e.date}): the tool compared three older FAOSTAT versions (${e.releases.join(', ')}) with the version of ${e.against}. `
        + `In the last year of an old version, the range held ${whole(e.official.held)} of ${e.official.n} official values. `
        + `In all years, it held ${whole(e.estimates.held)} of ${e.estimates.n} estimates that a country later replaced with an official value. `
        + `Without the \u00d7${r.estimateScale.production} multiplier it held ${whole(e.estimates.heldWithoutScale)} of them.`,
      `World total test: the range of the World total, made from the countries of an old version, held ${whole(e.world.held)} of ${e.world.n} years. `
        + `In the last year of each old version, FAO later raised the World total by ${andList(e.world.latestChange.map(share))}.`,
      `USDA revised its first estimates for US honey, ${e.usda.years}, by at most ${share(e.usda.production)} for production and ${share(e.usda.price)} for price.`,
      'Producer price and export price have no older versions to test.',
    ].map((text) => h('li', { text })));
    const ck = r.checks;
    $('cm-rubric').replaceChildren(...[
      `Start from the source: official ${b.A}, external ${b.X}, series break ${b.B}, estimated ${b.E}, imputed ${b.I}.`,
      `Age: subtract ${r.age.production.join(', ')} for the latest year and the two before it (production and export price), or ${r.age.price.join(', ')} for producer price.`,
      `Each check below takes points in proportion to the problem that it measures, in whole points, up to a maximum. A small problem costs a point or two. There is no free zone, so scores differ from value to value.`,
      `Jump, up to ${ck.jump.most}: how far a value is from its neighbor years, in units of K times the scale of its country. The maximum comes at ${ck.jump.full} units. `
        + `The first year, the latest year and a year beside a gap have one neighbor: the tool then measures the step from that neighbor against K1 (${perKind((k) => models[k].k1.toFixed(2))}), the 90th percentile of official steps.`,
      `History, up to ${ck.history.most}: the share of the ${r.historyYears} years around the value that are not official.`,
      `Few official years, up to ${ck.thin.most}: a country with fewer than ${r.minRuns} official years with official neighbors has no scale of its own, so the tool borrows one from similar countries. The fewer such years, the more points.`,
      `Rounding, up to ${ck.rounding.most}: a figure that ends in zeros can hide rounding. The points grow with the share of the figure that the rounding can hide.`,
      `Price gap, up to ${ck.gap.most} (producer price and export price): how far the ratio of the two prices of one country and year is from the usual ratio of that country. The tool needs ${r.minGapYears} years with both prices.`,
      `Supply, up to ${ck.supply.most} (production and export price): exports above production plus imports, for exports of ${r.minSupplyTonnes} tonnes or more. The maximum comes at ${Math.round(ck.supply.full * 100)}% above the supply.`,
      `The score stays between ${r.min} and ${r.max}. High is 80 or more, medium 60 to 79, low 40 to 59, very low under 40. The weights are a judgment.`,
    ].map((text) => h('li', { text })));

    $('footer').replaceChildren(
      'Data: ', link('https://www.fao.org/faostat/en/#home', meta.database), ', ', meta.publisher, '. License: ',
      link(meta.licenseUrl, meta.license), ', except that FAO says the export values, which come from UNSD and Eurostat, may carry extra restrictions. ',
      link(meta.sources.trade.lineage, 'See the FAO description.'), ' 1 lb is exactly 0.45359237 kg.');
  }

  // ---- Render ----------------------------------------------------------------
  function render() {
    const focused = document.activeElement;
    const refocus = focused && focused.matches('button.link') ? focused.dataset.code : null;
    const model = modelFor(faoYear());
    $('year').value = state.year;
    $('year-out').textContent = state.year;
    $('provisional').hidden = beyondFao() || !isProvisional(state.year);
    $('year-latest').hidden = state.year === lastPageYear;
    $('year-latest').textContent = `Go to ${lastPageYear}, the last year`;
    $('year-hint').textContent = beyondFao()
      ? `FAOSTAT has no values for ${state.year} yet. The World and country parts show ${lastYear}, its last year. The United States parts show ${state.year}.`
      : (usYears.length ? `FAOSTAT values end in ${lastYear}. The United States has USDA values to ${lastPageYear}.` : '');
    $('official').checked = state.official;
    for (const radio of document.querySelectorAll('input[name="unit"]')) radio.checked = radio.value === state.unit;
    renderCards(model);
    renderQuality();
    drawQualityChart();
    drawWorldCharts();
    renderTable(model);
    renderDetail(model);
    writeHash();
    pageYear.set(state.year);
    if (refocus) {
      const again = document.querySelector(`button.link[data-code="${refocus}"]`);
      if (again) again.focus();
    }
  }

  // ---- Events ----------------------------------------------------------------
  $('year').addEventListener('input', (ev) => { state.year = Number(ev.target.value); render(); });
  for (const radio of document.querySelectorAll('input[name="unit"]')) {
    radio.addEventListener('change', () => { state.unit = radio.value; render(); });
  }
  $('official').addEventListener('change', (ev) => { state.official = ev.target.checked; render(); });
  $('year-latest').addEventListener('click', () => { state.year = lastPageYear; render(); });
  $('search').addEventListener('input', (ev) => { state.query = ev.target.value; render(); });
  headRow.addEventListener('click', (ev) => {
    const th = ev.target.closest('th');
    if (!th || !ev.target.closest('button.sort')) return;
    const c = COLS.find((x) => x.key === th.dataset.key);
    if (state.sort === c.key) state.dir = -state.dir;
    else { state.sort = c.key; state.dir = c.first; }
    render();
  });
  $('table').tBodies[0].addEventListener('click', (ev) => {
    const tr = ev.target.closest('tr[data-code]');
    if (!tr) return;
    state.area = Number(tr.dataset.code);
    render();
  });
  $('detail').addEventListener('click', (ev) => {
    if (ev.target.closest('#clear')) { state.area = null; render(); }
  });
  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { drawQualityChart(); drawWorldCharts(); drawDetailCharts(); }, 150);
  });

  // ---- Start -----------------------------------------------------------------
  readHash();
  $('year').min = firstPageYear;
  $('year').max = lastPageYear;
  $('subtitle').textContent = `${D.meta.item.replace(/ \(.*\)$/, '')} data from ${D.meta.database}: `
    + `production ${years[0]} to ${lastYear}, producer price ${firstPriceYear} to ${lastYear}, export price ${firstExportYear} to ${lastYear}.`
    + (usYears.length ? ` United States data from USDA NASS: ${usYears[0]} to ${usYears[usYears.length - 1]}.` : '');
  // A click on a United States chart asks for a year through the shared bus.
  pageYear.onChange((y) => { if (y !== state.year) { state.year = y; render(); } });
  // The date of the build, and the date of the latest check for newer FAOSTAT files.
  const stamp = (date) => h('time', { datetime: date, text: date });
  const checked = (window.HONEY_STATUS || {}).checked || D.meta.retrieved;
  $('updated').replaceChildren('Updated ', stamp(D.meta.retrieved), '. FAOSTAT last checked ', stamp(checked), '.');
  $('world-range').textContent = `${years[0]} to ${lastYear}`;
  $('price-range').textContent = `${firstExportYear} to ${lastYear}`;
  $('quality-range').textContent = `${years[0]} to ${lastYear}`;
  renderSources();
  render();
})();
