// Honey price and production.
// Shows FAOSTAT "Natural honey": production, producer price, and export price.
// Each value has a confidence score. A value that FAO did not get as an official figure also has
// a 90% range. Both are made by scripts/uncertainty.py and explained on the page.
// The data is in data/honey_data.js. Run scripts/build_data.py to make that file again.
(() => {
  'use strict';

  const D = window.HONEY_DATA;
  const $ = (id) => document.getElementById(id);

  if (!D) {
    const message = document.createElement('p');
    message.className = 'error';
    message.textContent = 'The file data/honey_data.js did not load. Run scripts/build_data.py to make it.';
    $('app').replaceChildren(message);
    return;
  }

  // ---- Units -----------------------------------------------------------------
  // Production and trade in FAOSTAT are in tonnes. Prices are USD per tonne.
  // 1 lb = 0.45359237 kg exactly (international pound, 1959).
  const KG_PER_LB = 0.45359237;
  const UNITS = {
    lb: { perTonne: 1000 / KG_PER_LB, short: 'lb', big: 'million lb', bigDiv: 1e6 },
    kg: { perTonne: 1000, short: 'kg', big: 'million kg', bigDiv: 1e6 },
    tonne: { perTonne: 1, short: 't', big: 'tonnes', bigDiv: 1 },
  };

  // ---- Formatting ------------------------------------------------------------
  const DASH = '\u2014';
  const nf = (digits) => new Intl.NumberFormat('en-US', {
    minimumFractionDigits: digits, maximumFractionDigits: digits,
  });
  const f0 = nf(0), f1 = nf(1), f2 = nf(2), f3 = nf(3);

  const massBig = (tonnes, unit) => (tonnes * UNITS[unit].perTonne) / UNITS[unit].bigDiv;
  // The digits follow ref, so that the two ends of a range get the same number of digits.
  function fmtMass(tonnes, unit, ref = tonnes) {
    if (tonnes == null) return DASH;
    const v = massBig(tonnes, unit);
    if (unit === 'tonne') return f0.format(v);
    const r = massBig(ref, unit);
    return (r >= 100 ? f1 : r >= 1 ? f2 : f3).format(v);
  }
  const priceIn = (usdPerTonne, unit) => usdPerTonne / UNITS[unit].perTonne;
  function fmtPrice(usdPerTonne, unit) {
    if (usdPerTonne == null) return DASH;
    return '$' + (unit === 'tonne' ? f0 : f2).format(priceIn(usdPerTonne, unit));
  }
  const fmtShare = (x) => (x == null ? DASH : x < 0.0005 ? '<0.1%' : (x * 100).toFixed(1) + '%');
  const pct = (x) => (x > 0 && x < 0.005 ? '<1%' : Math.round(x * 100) + '%');
  const norm = (text) => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

  // ---- FAOSTAT flags ---------------------------------------------------------
  // "A" means official, so it gets no mark. The other letters say how a value was made.
  const FLAGS = D.meta.flags; // { production: {...}, price: {...}, trade: {...} }
  const FLAG_KIND = { production: 'production', price: 'price', export: 'trade' };
  const flagText = (kind, flag) => (flag && flag !== 'A' ? (FLAGS[kind][flag] || flag) : '');
  const FLAG_ORDER = ['A', 'E', 'I', 'X', 'B'];
  const FLAG_WORDS = { A: 'official', E: 'estimated', I: 'imputed', X: 'from other organizations', B: 'with a series break' };
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

  // ---- DOM helpers -----------------------------------------------------------
  function h(tag, attrs, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === 'class') e.className = v;
      else if (k === 'text') e.textContent = v;
      else e.setAttribute(k, v === true ? '' : v);
    }
    for (const kid of kids.flat()) if (kid != null) e.append(kid);
    return e;
  }
  function s(tag, attrs, text) {
    const e = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
    if (text != null) e.textContent = text;
    return e;
  }
  const link = (href, text) => h('a', { href, target: '_blank', rel: 'noopener noreferrer', text });

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

  // ---- State -----------------------------------------------------------------
  const state = { year: lastYear, unit: 'lb', area: null, sort: 'production', dir: -1, query: '', official: false };

  function readHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    const y = Number(p.get('y'));
    if (yearIndex.has(y)) state.year = y;
    const u = p.get('u');
    if (u && Object.hasOwn(UNITS, u)) state.unit = u;
    const a = Number(p.get('a'));
    if (p.has('a') && byCode.has(a)) state.area = a;
    state.official = p.get('o') === '1';
  }
  function writeHash() {
    const p = new URLSearchParams({ y: state.year, u: state.unit });
    if (state.area != null) p.set('a', state.area);
    if (state.official) p.set('o', '1');
    try { history.replaceState(null, '', '#' + p); } catch (e) { /* some pages refuse this */ }
  }

  // ---- Points ----------------------------------------------------------------
  // A point is one value with its FAO flag, its confidence score and its 90% range.
  // kind is "production", "price" or "export". The value is in tonnes or in USD per tonne.
  // The export price is the export value divided by the export quantity.
  // A unit value from a few tonnes is mostly noise. From 2010 to 2024, 17% to 39% of the country
  // years below 100 tonnes were outside $0.40 to $6 per lb, against 2% from 100 tonnes up.
  // So a country has an export price only from MIN_EXPORT_TONNES. The World row has no such limit.
  // With "Official figures only" on, a value that is not marked A is not a point.
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
    if (state.official && flag !== 'A') return null;
    const band = src[kind + 'Band'][i];
    const spread = Math.exp(band / 1000);
    return { value, flag, conf: src[kind + 'Conf'][i], band, lo: value / spread, hi: value * spread };
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
      ? `This country never exported ${MIN_EXPORT_TONNES} tonnes or more in a year, so it has no export price here.`
      : 'FAOSTAT has no export price for this country.';
  }

  // How to show a value of each kind in the selected unit.
  function fmtFor(kind) {
    const unit = state.unit, u = UNITS[unit];
    return kind === 'production'
      ? { num: (t) => fmtMass(t, unit), range: (lo, hi) => `${fmtMass(lo, unit, hi)} to ${fmtMass(hi, unit, hi)}`, unit: ` ${u.big}` }
      : { num: (p) => fmtPrice(p, unit), range: (lo, hi) => `${fmtPrice(lo, unit)} to ${fmtPrice(hi, unit)}`, unit: ` per ${u.short}` };
  }

  // One line that says everything about a point: value, source, range, confidence.
  function describe(kind, p, i, extra) {
    const fmt = fmtFor(kind);
    const parts = [`${years[i]}: ${fmt.num(p.value)}${fmt.unit}`];
    parts.push(p.flag === 'A' ? 'official' : (flagText(FLAG_KIND[kind], p.flag) || p.flag).toLowerCase());
    if (p.band) parts.push(`90% range ${fmt.range(p.lo, p.hi)}`);
    parts.push(`confidence ${p.conf} (${tierOf(p.conf).name})`);
    if (isProvisional(years[i])) parts.push('provisional');
    if (extra) parts.push(extra);
    return parts.join(' \u00b7 ');
  }
  function chartTip(kind, src, i) {
    const p = pointOf(src, kind, i);
    if (!p) return `${years[i]}: ${kind === 'export' ? 'no export price' : 'no figure'}`;
    const u = UNITS[state.unit];
    return describe(kind, p, i, kind === 'export' ? `${fmtMass(src.exportQty[i], state.unit)} ${u.big} exported` : null);
  }
  // The score is out of a copied selection (see styles.css), so a copied table keeps clean numbers.
  const confPill = (p, title) => h('span', {
    class: `conf conf-${tierOf(p.conf).key}`, role: 'img', title, 'aria-label': `confidence ${p.conf} of 100, ${tierOf(p.conf).name}`, text: String(p.conf),
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
  // This is the raw data: the switch "Official figures only" does not change it.
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
  function niceStep(raw) {
    const exp = Math.floor(Math.log10(raw));
    const f = raw / 10 ** exp;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * 10 ** exp;
  }

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
    if (pts.some((p) => p && p.band)) keys.push(h('span', { class: 'key' }, h('span', { class: 'swatch band' }), '90% range'));
    keys.push(h('span', { class: 'key' }, h('span', { class: 'swatch prov' }), 'provisional'));
    keys.push(h('span', { class: 'key' }, h('span', { class: 'swatch strip' }), 'confidence: high to very low'));
    keys.push(h('a', { href: '#confidence-method', text: 'How this is made' }));
    return h('div', { class: 'legend' }, keys);
  }

  let chartCount = 0;

  // The frame of a chart: the shading of the provisional years, the grid and the labels.
  // The x axis is always the full list of years, and the y axis starts at 0.
  // cfg: { host, top, step, prefix, suffix, label, height, bottom }
  function frame(cfg) {
    const W = Math.max(280, Math.round(cfg.host.clientWidth || 640));
    const H = cfg.height;
    const m = { t: 12, r: 14, b: cfg.bottom, l: 62 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const step = cfg.step || niceStep((cfg.top || 1) / 4);
    const yMax = Math.ceil(cfg.top / step - 1e-9) * step || step;
    const axis = nf(step >= 1 ? 0 : Math.ceil(-Math.log10(step)));
    const n = years.length;
    const X = (i) => m.l + (i / (n - 1)) * iw;
    const Y = (v) => m.t + ih - (v / yMax) * ih;

    const svg = s('svg', { class: 'svg', viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': cfg.label });
    const clipId = `clip${++chartCount}`;
    const clip = s('clipPath', { id: clipId });
    clip.append(s('rect', { x: m.l, y: m.t - 2, width: iw, height: ih + 4 }));
    const defs = s('defs');
    defs.append(clip);
    svg.append(defs, s('rect', { class: 'prov', x: X(provisionalFrom), y: m.t, width: W - m.r - X(provisionalFrom), height: ih }));
    for (let k = 0; k * step <= yMax + step / 1e6; k++) {
      const v = k * step;
      svg.append(
        s('line', { class: 'grid', x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v) }),
        s('text', { class: 'tick', x: m.l - 8, y: Y(v) + 4, 'text-anchor': 'end' }, (cfg.prefix || '') + axis.format(v) + (cfg.suffix || '')),
      );
    }
    years.forEach((y, i) => {
      if (y % 10 === 0) svg.append(s('text', { class: 'tick', x: X(i), y: H - 6, 'text-anchor': 'middle' }, String(y)));
    });
    // What a chart puts in this group is cut off at the frame.
    const layer = s('g', { 'clip-path': `url(#${clipId})` });
    return { svg, defs, layer, W, H, m, iw, ih, n, X, Y };
  }

  // The guide line, the tooltip and the click on a chart.
  // cfg: { tip(i) gives the text, at(i) gives the y of the point that the tip stands at, onPick(i) }
  function hover(f, cfg) {
    const { svg, W, m, iw, ih, n, X } = f;
    const guide = s('line', { class: 'guide', y1: m.t, y2: m.t + ih + 14, visibility: 'hidden' });
    const overlay = s('rect', { x: m.l, y: m.t, width: iw, height: ih + 16, fill: 'transparent', class: 'hit' });
    svg.append(guide, overlay);
    const tip = h('div', { class: 'tip', hidden: true });
    const indexAt = (ev) => {
      const box = svg.getBoundingClientRect();
      const px = (ev.clientX - box.left) * (W / box.width);
      return Math.min(n - 1, Math.max(0, Math.round(((px - m.l) / iw) * (n - 1))));
    };
    overlay.addEventListener('pointermove', (ev) => {
      const i = indexAt(ev);
      guide.setAttribute('x1', X(i));
      guide.setAttribute('x2', X(i));
      guide.setAttribute('visibility', 'visible');
      tip.textContent = cfg.tip(i);
      tip.hidden = false;
      // The tip stays inside the chart, and goes below the point where there is no room above it.
      const scale = svg.getBoundingClientRect().width / W, half = tip.offsetWidth / 2;
      const y = cfg.at(i) * scale;
      tip.style.left = Math.max(half, Math.min(W * scale - half, X(i) * scale)) + 'px';
      tip.style.top = y + 'px';
      tip.classList.toggle('below', y < tip.offsetHeight * 1.4);
    });
    overlay.addEventListener('pointerleave', () => {
      guide.setAttribute('visibility', 'hidden');
      tip.hidden = true;
    });
    overlay.addEventListener('click', (ev) => cfg.onPick(indexAt(ev)));
    return tip;
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
    const f = frame({ host, top, prefix: cfg.prefix, label: cfg.label, height: 250, bottom: 40 });
    const { svg, layer, W, m, iw, ih, n, X, Y } = f;
    const radius = W < 420 ? 2.4 : 3.2;

    // Runs of years that have a point. A gap in the data stays a gap.
    const runs = [];
    let run = [];
    pts.forEach((p, i) => {
      if (!p) { if (run.length) runs.push(run); run = []; } else run.push(i);
    });
    if (run.length) runs.push(run);

    // 1. The 90% range. It is as wide as the range of each point and a point of an
    //    official figure has none, so the band pinches to the line there.
    for (const r of runs) {
      if (!r.some((i) => pts[i].band)) continue;
      const up = r.map((i, k) => `${k ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(hi(i)).toFixed(1)}`).join('');
      const down = r.slice().reverse().map((i) => `L${X(i).toFixed(1)} ${Y(lo(i)).toFixed(1)}`).join('');
      layer.append(s('path', { d: `${up}${down}Z`, fill: cfg.color, 'fill-opacity': 0.15 }));
    }
    // 2. The line, thin: the points are what counts.
    for (const r of runs) {
      if (r.length < 2) continue;
      const d = r.map((i, k) => `${k ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(val(i)).toFixed(1)}`).join('');
      layer.append(s('path', { d, fill: 'none', stroke: cfg.color, 'stroke-width': 1.25, 'stroke-linejoin': 'round', opacity: 0.7 }));
    }
    // 3. A bar for the range of each point that has one.
    for (const i of have) {
      if (!pts[i].band) continue;
      const x = X(i), opacity = (0.35 + 0.65 * (pts[i].conf / RUBRIC.max)).toFixed(2);
      layer.append(
        s('line', { x1: x, x2: x, y1: Y(hi(i)), y2: Y(lo(i)), stroke: cfg.color, 'stroke-width': 1, opacity }),
        s('line', { x1: x - 2.5, x2: x + 2.5, y1: Y(hi(i)), y2: Y(hi(i)), stroke: cfg.color, 'stroke-width': 1, opacity }),
        s('line', { x1: x - 2.5, x2: x + 2.5, y1: Y(lo(i)), y2: Y(lo(i)), stroke: cfg.color, 'stroke-width': 1, opacity }),
      );
    }
    svg.append(layer);

    // 4. A marker for every point. The shape says how FAO made the value. A faint marker
    //    has a low confidence score.
    for (const i of have) {
      const p = pts[i], x = X(i), y = Y(val(i));
      const opacity = (0.45 + 0.55 * (p.conf / RUBRIC.max)).toFixed(2);
      const ring = { fill: '#fff', stroke: cfg.color, 'stroke-width': 1.5, opacity };
      let mark;
      if (p.flag === 'A') mark = s('circle', { cx: x, cy: y, r: radius, fill: cfg.color, opacity });
      else if (p.flag === 'E') mark = s('circle', { cx: x, cy: y, r: radius + 0.5, ...ring });
      else if (p.flag === 'I') {
        const k = radius + 1.2;
        mark = s('path', { d: `M${x} ${y - k}L${x + k} ${y}L${x} ${y + k}L${x - k} ${y}Z`, ...ring });
      } else if (p.flag === 'X') mark = s('rect', { x: x - radius, y: y - radius, width: 2 * radius, height: 2 * radius, fill: cfg.color, opacity });
      else mark = s('rect', { x: x - radius, y: y - radius, width: 2 * radius, height: 2 * radius, ...ring });
      svg.append(mark);
    }

    // 5. A strip under the chart: one cell for each year, colored by the confidence score.
    const stripY = m.t + ih + 8;
    const cell = iw / (n - 1);
    svg.append(s('text', { class: 'tick', x: m.l - 8, y: stripY + 6, 'text-anchor': 'end' }, 'confidence'));
    for (const i of have) {
      svg.append(s('rect', { x: Math.max(m.l, X(i) - cell / 2), y: stripY, width: cell, height: 6, fill: tierOf(pts[i].conf).color }));
    }

    if (cfg.marker >= 0) {
      svg.append(s('line', { class: 'marker', x1: X(cfg.marker), x2: X(cfg.marker), y1: m.t, y2: m.t + ih }));
      if (pts[cfg.marker]) {
        svg.append(s('circle', { cx: X(cfg.marker), cy: Y(val(cfg.marker)), r: radius + 3, fill: 'none', stroke: cfg.color, 'stroke-width': 1.5 }));
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
    const f = frame({ host, top: 100, step: 25, suffix: '%', label: cfg.label, height: 200, bottom: 28 });
    const { svg, m, iw, ih, n, X, Y } = f;
    const hatchId = `hatch${chartCount}`;
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
    if (!c) return `${years[i]}: no production figures`;
    return `${years[i]}: ${breakdown(c.parts, c.total)} of ${fmtMass(c.total, state.unit)} ${UNITS[state.unit].big} listed`
      + (isProvisional(years[i]) ? ' \u00b7 provisional' : '');
  }

  function drawQualityChart() {
    stackChart($('quality-chart'), {
      rows: COMPOSITION,
      label: `Share of the listed honey production by how FAO got the figure, ${years[0]} to ${lastYear}`,
      marker: yearIndex.get(state.year),
      tip: compositionTip,
      onPick: pickYear,
    });
  }

  function drawWorldCharts() {
    const unit = state.unit, u = UNITS[unit], marker = yearIndex.get(state.year);
    lineChart($('world-chart'), {
      pts: pointSeries(D.world, 'production'),
      conv: (t) => massBig(t, unit),
      color: '#c77d00',
      label: `World honey production in ${u.big}, ${years[0]} to ${lastYear}, with confidence`,
      marker,
      empty: 'No official figures.',
      tip: (i) => chartTip('production', D.world, i),
      onPick: pickYear,
    });
    lineChart($('world-price-chart'), {
      pts: pointSeries(D.world, 'export'),
      conv: (p) => priceIn(p, unit),
      color: '#6b4a1f',
      prefix: '$',
      label: `World honey export price in USD per ${u.short}, ${firstExportYear} to ${lastYear}, with confidence`,
      marker,
      empty: 'No official figures.',
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
      label: `${a.name}: honey production in ${u.big}, with confidence`,
      marker,
      empty: state.official ? 'No official production figures.' : 'FAOSTAT has no production figures for this country.',
      tip: (i) => chartTip('production', a, i),
      onPick: pickYear,
    });
    lineChart($('detail-price'), {
      pts: pointSeries(a, 'price'),
      conv: (p) => priceIn(p, unit),
      color: '#6b4a1f',
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
      color: '#8a3b12',
      prefix: '$',
      label: `${a.name}: export price in USD per ${u.short}, with confidence`,
      marker,
      empty: emptyExport(a),
      tip: (i) => chartTip('export', a, i),
      onPick: pickYear,
    });
  }

  // ---- Cards -----------------------------------------------------------------
  function renderCards(model) {
    const unit = state.unit, u = UNITS[unit], i = model.i;

    const wp = model.wp;
    $('card-production').textContent = wp ? `${fmtMass(wp.value, unit)} ${u.big}` : DASH;
    const other = unit === 'tonne' ? 'lb' : 'tonne';
    if (wp) {
      const note = flagText('production', wp.flag);
      $('card-production-sub').textContent = `${fmtMass(wp.value, other)} ${UNITS[other].big} in ${state.year}.`
        + (note ? ` ${note}.` : '')
        + (wp.band ? ` 90% range ${fmtMass(wp.lo, unit)} to ${fmtMass(wp.hi, unit)} ${u.big}.` : '')
        + ` Confidence ${wp.conf} (${tierOf(wp.conf).name}).`;
    } else {
      $('card-production-sub').textContent = D.world.production[i] == null
        ? `No figure for ${state.year}.` : `FAO has no official world total for ${state.year}.`;
    }

    // The world export price uses the World row of FAOSTAT: export value divided by export quantity.
    const we = pointOf(D.world, 'export', i);
    if (!we) {
      $('card-export').textContent = DASH;
      $('card-export-sub').textContent = D.world.exportFlags[i] === ' '
        ? `FAOSTAT has no export figures for ${state.year}.` : `FAO has no official world export figures for ${state.year}.`;
    } else {
      const exporters = model.rows.filter((r) => r.pe);
      const total = exporters.reduce((sum, r) => sum + r.exportQty, 0);
      const official = exporters.filter((r) => r.pe.flag === 'A').reduce((sum, r) => sum + r.exportQty, 0);
      $('card-export').textContent = `${fmtPrice(we.value, unit)} per ${u.short}`;
      $('card-export-sub').textContent = `Customs value divided by quantity. ${fmtMass(D.world.exportQty[i], unit)} ${u.big} exported in ${state.year}. `
        + (state.official || !total ? 'Official figures only. ' : `${pct(official / total)} of the tonnage is official. `)
        + `Confidence ${we.conf} (${tierOf(we.conf).name}).`;
    }

    const priced = model.rows.filter((r) => r.pc).sort((x, y) => x.price - y.price);
    if (!priced.length) {
      $('card-range').textContent = DASH;
      $('card-range-sub').textContent = state.year < firstPriceYear
        ? `Producer prices start in ${firstPriceYear}.` : `No producer price for ${state.year}.`;
    } else {
      const low = priced[0], high = priced[priced.length - 1];
      $('card-range').textContent = `${fmtPrice(low.price, unit)} to ${fmtPrice(high.price, unit)} per ${u.short}`;
      $('card-range-sub').textContent = `${low.a.name} to ${high.a.name}. ${priced.length} countries have a price.`;
    }
  }

  // ---- Reliability list ------------------------------------------------------
  function renderQuality() {
    const q = qualityFor(state.year);
    $('quality-year').textContent = state.year;
    const items = [];
    if (q.listed > 0) {
      const world = q.world == null ? ''
        : ` The world total is ${q.worldFlag === 'A' ? 'official' : flagWord(q.worldFlag)}. The listed countries add up to ${fmtShare(q.listed / q.world)} of it.`;
      items.push(`Production: ${breakdown(q.prod, q.listed)} of the listed production.${world}`);
      const t = q.tiers;
      items.push(`Confidence: of ${t.high + t.medium + t.low + t.vlow} countries with a production figure, ${t.high} score high (80 or more), `
        + `${t.medium} medium, ${t.low} low and ${t.vlow} very low (under 40).`);
    } else {
      items.push(`Production: FAOSTAT has no figures for ${state.year}.`);
    }
    items.push(q.nPrice
      ? `Producer price: ${q.nPrice} countries have a price. By count, ${breakdown(q.price, q.nPrice)}.`
      : `Producer price: FAOSTAT has none for ${state.year}.`);
    items.push(q.nExp
      ? `Export price: ${q.nExp} countries exported at least ${MIN_EXPORT_TONNES} tonnes and have a price. By tonnage, ${breakdown(q.exp, q.expT)}. `
        + `${q.smallN} smaller exporters have no price here, because an average over a few tonnes is not reliable. They make ${pct(q.smallT / (q.expT + q.smallT))} of the tonnage.`
      : (q.smallN ? `Export price: no country exported ${MIN_EXPORT_TONNES} tonnes or more.` : `Export price: FAOSTAT has none for ${state.year}.`));
    const list = items.map((text) => h('li', { text }));
    if (isProvisional(state.year)) {
      list.push(h('li', {},
        `${state.year} is provisional. FAO collects the last three years again each year, and national offices revise recent figures. `,
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
          r.exportQty != null ? `${r.a.name} exported ${fmtMass(r.exportQty, unit)} ${u.big}`
            : r.exportSmall != null ? `${r.a.name} exported only ${fmtMass(r.exportSmall, unit)} ${u.big}. That is too little for a reliable price.` : null),
      );
      frag.append(tr);
    }
    $('table').tBodies[0].replaceChildren(frag);

    const count = (key) => model.rows.filter((r) => r[key] != null).length;
    const listed = model.rows.reduce((sum, r) => sum + (r.production || 0), 0);
    const listedShare = model.world ? listed / model.world : null;
    const gap = listedShare != null && listedShare < 0.9995
      ? ` The listed countries add up to ${fmtShare(listedShare)} of the world total. The rest is in the world total but has no country row in FAOSTAT.` : '';
    $('table-note').textContent = `${shown.length} of ${model.rows.length} countries and areas for ${state.year}. `
      + `${count('price')} have a producer price and ${count('exportPrice')} have an export price (at least ${MIN_EXPORT_TONNES} tonnes exported). Shares use the FAOSTAT world total.${gap} `
      + 'The table lists China, mainland and Taiwan Province of China as two rows. FAOSTAT "China" is their sum. '
      + 'The small number after a value is its confidence score from 0 to 100: hover it for the details. '
      + 'The letter E, I or X marks a value that FAO did not get as an official figure.'
      + (state.official ? ' Official figures only: values that FAO marks E, I or X are hidden.' : '');
  }

  // ---- Detail panel ----------------------------------------------------------
  function renderDetail(model) {
    const box = $('detail');
    const a = byCode.get(state.area);
    if (!a) {
      box.replaceChildren(
        h('h2', { text: 'Country detail' }),
        h('p', { class: 'note', text: 'Select a country in the table to see its production and price history.' }),
      );
      return;
    }
    const unit = state.unit, u = UNITS[unit], i = model.i;
    const pp = pointOf(a, 'production', i), pc = pointOf(a, 'price', i), pe = pointOf(a, 'export', i);
    const share = pp && model.world ? pp.value / model.world : null;
    const expFlag = a.exportFlags[i].trim();
    const exportedQty = expFlag && (!state.official || expFlag === 'A') ? a.exportQty[i] : null;
    // A fact: the value, its confidence score, and its range if it has one.
    const fact = (label, kind, p, text) => [
      h('dt', { text: label }),
      h('dd', {}, text, p ? confPill(p, describe(kind, p, i)) : null,
        p && p.band ? h('small', { text: `90% range ${fmtFor(kind).range(p.lo, p.hi)}` }) : null),
    ];
    box.replaceChildren(
      h('div', { class: 'panel-head' },
        h('h2', { text: a.name }),
        h('button', { type: 'button', class: 'ghost', id: 'clear', text: 'Clear' })),
      h('dl', { class: 'facts' },
        fact(`Production ${state.year}`, 'production', pp, pp ? `${fmtMass(pp.value, unit)} ${u.big}` : DASH),
        h('dt', { text: 'Share of world' }),
        h('dd', { text: fmtShare(share) }),
        fact(`Producer price ${state.year}`, 'price', pc, pc ? `${fmtPrice(pc.value, unit)} per ${u.short}` : DASH),
        fact(`Export price ${state.year}`, 'export', pe,
          pe ? `${fmtPrice(pe.value, unit)} per ${u.short}` : (exportedQty != null ? `${DASH} (under ${MIN_EXPORT_TONNES} t)` : DASH)),
        h('dt', { text: `Exported ${state.year}` }),
        h('dd', { text: exportedQty == null ? DASH : `${fmtMass(exportedQty, unit)} ${u.big}` })),
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
      .filter(([flag]) => flag !== 'M')
      .map(([flag, text]) => `${flag} = ${text}`).join('; ');
    $('flags-text').textContent = `Production: ${marks('production')}. Producer price: ${marks('price')}. `
      + `Export price: ${marks('trade')}. An export price takes the weaker mark of its export value and its export quantity. `
      + 'The switch "Official figures only" keeps only the values marked A.';

    // The method of the confidence score and the ranges, with the numbers of this data set.
    const names = { production: 'production', price: 'producer price', export: 'export price' };
    const each = (fn) => Object.entries(names).map(([k, name]) => fn(models[k], name));
    $('cm-k').textContent = each((m, name) => `${name} ${m.k90.toFixed(2)}`).join(', ')
      + ' (a normal curve would give 1.64)';
    $('cm-cap').textContent = String(RUBRIC.cap);
    const widened = [];
    for (const [kind, name] of Object.entries(names)) {
      for (const [flag, c] of Object.entries(models[kind].classes)) {
        if (c.factor > 1) widened.push(`${name}, ${flagWord(flag)}: \u00d7${c.factor} (measured on ${c.n} values)`);
      }
    }
    $('cm-class').textContent = widened.length ? widened.join('; ') : 'none';
    $('cm-test').textContent = 'Test: for each official figure that has two official neighbors, the tool hid the figure, made a range from the neighbors, and looked at whether the range contained the figure. '
      + 'The countries were split in two halves: K was learned on one half and tried on the other, and then the halves were swapped. '
      + 'The range contained the figure ' + each((m, name) => `${(m.coverage * 100).toFixed(1)}% of the time for ${name} (${f0.format(m.checked)} figures)`).join(', ')
      + '. This shows that the ranges have the right size for a guess made from the neighbors. It does not show how far FAO estimates are from the truth.';
    const r = RUBRIC, b = r.base;
    $('cm-rubric').replaceChildren(...[
      `Start from the source: official ${b.A}, other organization ${b.X}, series break ${b.B}, estimated ${b.E}, imputed ${b.I}.`,
      `Subtract ${r.age.production.join(', ')} for the latest year and the two before it (production and export price). `
        + `Subtract ${r.age.price.join(', ')} for producer price, because prices are revised more.`,
      `Subtract ${r.fit[0]} if the value is farther from its neighbors than K times the scale of the country, and ${r.fit[1]} if it is farther than 1.5 times that.`,
      `Subtract ${r.borrowed} if the country has fewer than ${r.minRuns} official years with official neighbors, so that its scale is borrowed.`,
      `Subtract ${r.balance[1][1]} or ${r.balance[0][1]} if exports are more than ${Math.round((r.balance[1][0] - 1) * 100)}% or ${Math.round((r.balance[0][0] - 1) * 100)}% above production plus imports (production and export price).`,
      `The score stays between ${r.min} and ${r.max}. High is 80 or more, medium 60 to 79, low 40 to 59, very low under 40.`,
    ].map((text) => h('li', { text })));

    $('footer').replaceChildren(
      'Data: ', link('https://www.fao.org/faostat/en/#home', meta.database), ', ', meta.publisher, '. License: ',
      link(meta.licenseUrl, meta.license), ', except that FAO says the export figures, which come from UNSD and Eurostat, might be subject to additional restrictions. ',
      link(meta.sources.trade.lineage, 'See the FAO description.'), ` Retrieved ${meta.retrieved}. 1 lb is exactly 0.45359237 kg.`);
  }

  // ---- Render ----------------------------------------------------------------
  function render() {
    const focused = document.activeElement;
    const refocus = focused && focused.matches('button.link') ? focused.dataset.code : null;
    const model = modelFor(state.year);
    $('year').value = state.year;
    $('year-out').textContent = state.year;
    $('provisional').hidden = !isProvisional(state.year);
    $('official').checked = state.official;
    for (const radio of document.querySelectorAll('input[name="unit"]')) radio.checked = radio.value === state.unit;
    renderCards(model);
    renderQuality();
    drawQualityChart();
    drawWorldCharts();
    renderTable(model);
    renderDetail(model);
    writeHash();
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
  $('year').min = years[0];
  $('year').max = lastYear;
  $('subtitle').textContent = `${D.meta.item.replace(/ \(.*\)$/, '')} data from ${D.meta.database}. `
    + `Production ${years[0]} to ${lastYear}. Producer price ${firstPriceYear} to ${lastYear}. Export price ${firstExportYear} to ${lastYear}.`;
  $('world-range').textContent = `${years[0]} to ${lastYear}`;
  $('price-range').textContent = `${firstExportYear} to ${lastYear}`;
  $('quality-range').textContent = `${years[0]} to ${lastYear}`;
  renderSources();
  render();
})();
