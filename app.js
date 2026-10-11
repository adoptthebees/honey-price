// Honey price and production.
// Shows FAOSTAT "Natural honey": production, producer price, and export price.
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
  function fmtMass(tonnes, unit) {
    if (tonnes == null) return DASH;
    const v = massBig(tonnes, unit);
    if (unit === 'tonne') return f0.format(v);
    return (v >= 100 ? f1 : v >= 1 ? f2 : f3).format(v);
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
  const flagText = (kind, flag) => (flag && flag !== 'A' ? (FLAGS[kind][flag] || flag) : '');
  const FLAG_ORDER = ['A', 'E', 'I', 'X', 'B'];
  const FLAG_WORDS = { A: 'official', E: 'estimated', I: 'imputed', X: 'from other organizations', B: 'with a series break' };
  const flagWord = (flag) => FLAG_WORDS[flag] || flag;
  const breakdown = (parts, total) => FLAG_ORDER.filter((f) => parts[f])
    .map((f) => `${pct(parts[f] / total)} ${flagWord(f)}`).join(', ');

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

  // FAO asks countries for the last three years again in each yearly cycle.
  const PROVISIONAL_YEARS = 3;
  const provisionalFrom = years.length - PROVISIONAL_YEARS;
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

  // ---- Values, with the "Official figures only" switch ------------------------
  const visible = (value, flag) => (value != null && (!state.official || flag === 'A') ? value : null);
  const visibleSeries = (values, flags) => values.map((v, i) => visible(v, flags[i].trim()));
  // A unit value from a few tonnes is mostly noise. From 2010 to 2024, 17% to 39% of the country
  // years below 100 tonnes were outside $0.40 to $6 per lb, against 2% from 100 tonnes up.
  // So a country has an export price only from 100 tonnes. The World row has no such limit.
  const MIN_EXPORT_TONNES = 100;
  // The export price is the export value divided by the export quantity, in USD per tonne.
  function exportAt(src, i) {
    const flag = src.exportFlags[i].trim();
    if (!flag || (state.official && flag !== 'A')) return null;
    if (src !== D.world && src.exportQty[i] < MIN_EXPORT_TONNES) return null;
    return (src.exportValue[i] * 1000) / src.exportQty[i];
  }
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
  const exportSeries = (src) => years.map((_, i) => exportAt(src, i));

  // ---- Model for one year ----------------------------------------------------
  function modelFor(year) {
    const i = yearIndex.get(year);
    const world = visible(D.world.production[i], D.world.productionFlags[i].trim());
    const rows = [];
    for (const a of D.areas) {
      const production = visible(a.production[i], a.productionFlags[i].trim());
      const price = visible(a.price[i], a.priceFlags[i].trim());
      const exportPrice = exportAt(a, i);
      if (production == null && price == null && exportPrice == null) continue;
      rows.push({
        a, production, price, exportPrice,
        exportQty: exportPrice == null ? null : a.exportQty[i],
        exportSmall: exportPrice == null ? smallExport(a, i) : null,
        pFlag: a.productionFlags[i].trim(), cFlag: a.priceFlags[i].trim(), eFlag: a.exportFlags[i].trim(),
        share: production != null && world ? production / world : null,
        rank: null,
      });
    }
    rows.filter((r) => r.production != null)
      .sort((x, y) => y.production - x.production)
      .forEach((r, k) => { r.rank = k + 1; });
    return { i, world, worldFlag: D.world.productionFlags[i].trim(), rows };
  }

  // How reliable are the values of one year? This ignores the switch: it describes the raw data.
  function qualityFor(year) {
    const i = yearIndex.get(year);
    const add = (parts, flag, amount) => { parts[flag] = (parts[flag] || 0) + amount; };
    const q = { prod: {}, listed: 0, price: {}, nPrice: 0, exp: {}, expT: 0, nExp: 0, smallN: 0, smallT: 0,
      world: D.world.production[i], worldFlag: D.world.productionFlags[i].trim() };
    for (const a of D.areas) {
      if (a.production[i] != null) { add(q.prod, a.productionFlags[i].trim(), a.production[i]); q.listed += a.production[i]; }
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

  // cfg: { ys, color, label, marker, prefix, area, empty, tip(i), onPick(i) }
  // The x axis is always the full list of years. The last years are shaded: they are provisional.
  function lineChart(host, cfg) {
    host.textContent = '';
    const values = cfg.ys.filter((v) => v != null);
    if (!values.length) {
      host.append(h('p', { class: 'note', text: cfg.empty || 'No data.' }));
      return;
    }
    const W = Math.max(280, Math.round(host.clientWidth || 640));
    const H = 220;
    const m = { t: 12, r: 14, b: 26, l: 62 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const top = Math.max(...values);
    const step = niceStep((top || 1) / 4);
    const yMax = Math.ceil(top / step - 1e-9) * step || step;
    const decimals = step >= 1 ? 0 : Math.ceil(-Math.log10(step));
    const axis = nf(decimals);
    const n = years.length;
    const X = (i) => m.l + (i / (n - 1)) * iw;
    const Y = (v) => m.t + ih - (v / yMax) * ih;

    const svg = s('svg', { class: 'svg', viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': cfg.label });
    svg.append(s('rect', { class: 'prov', x: X(provisionalFrom), y: m.t, width: W - m.r - X(provisionalFrom), height: ih }));
    for (let k = 0; k * step <= yMax + step / 1e6; k++) {
      const v = k * step;
      svg.append(
        s('line', { class: 'grid', x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v) }),
        s('text', { class: 'tick', x: m.l - 8, y: Y(v) + 4, 'text-anchor': 'end' }, (cfg.prefix || '') + axis.format(v)),
      );
    }
    years.forEach((y, i) => {
      if (y % 10 === 0) svg.append(s('text', { class: 'tick', x: X(i), y: H - 6, 'text-anchor': 'middle' }, String(y)));
    });

    // Draw each run of years that have a value. A gap in the data stays a gap.
    const runs = [];
    let run = [];
    cfg.ys.forEach((v, i) => {
      if (v == null) { if (run.length) runs.push(run); run = []; } else run.push(i);
    });
    if (run.length) runs.push(run);
    for (const r of runs) {
      if (r.length === 1) {
        svg.append(s('circle', { cx: X(r[0]), cy: Y(cfg.ys[r[0]]), r: 2.5, fill: cfg.color }));
        continue;
      }
      const line = r.map((i, k) => `${k ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(cfg.ys[i]).toFixed(1)}`).join('');
      if (cfg.area) {
        svg.append(s('path', {
          d: `${line}L${X(r[r.length - 1]).toFixed(1)} ${Y(0)}L${X(r[0]).toFixed(1)} ${Y(0)}Z`,
          fill: cfg.color, 'fill-opacity': 0.12,
        }));
      }
      svg.append(s('path', { d: line, fill: 'none', stroke: cfg.color, 'stroke-width': 2, 'stroke-linejoin': 'round' }));
    }

    if (cfg.marker >= 0) {
      svg.append(s('line', { class: 'marker', x1: X(cfg.marker), x2: X(cfg.marker), y1: m.t, y2: m.t + ih }));
      const v = cfg.ys[cfg.marker];
      if (v != null) {
        svg.append(s('circle', { cx: X(cfg.marker), cy: Y(v), r: 4.5, fill: cfg.color, stroke: '#fff', 'stroke-width': 2 }));
      }
    }

    const guide = s('line', { class: 'guide', y1: m.t, y2: m.t + ih, visibility: 'hidden' });
    const dot = s('circle', { r: 4, fill: cfg.color, visibility: 'hidden' });
    const overlay = s('rect', { x: m.l, y: m.t, width: iw, height: ih, fill: 'transparent', style: 'cursor:pointer' });
    svg.append(guide, dot, overlay);
    const tip = h('div', { class: 'tip', hidden: true });

    const indexAt = (ev) => {
      const box = svg.getBoundingClientRect();
      const px = (ev.clientX - box.left) * (W / box.width);
      return Math.min(n - 1, Math.max(0, Math.round(((px - m.l) / iw) * (n - 1))));
    };
    overlay.addEventListener('pointermove', (ev) => {
      const i = indexAt(ev);
      const v = cfg.ys[i];
      guide.setAttribute('x1', X(i));
      guide.setAttribute('x2', X(i));
      guide.setAttribute('visibility', 'visible');
      if (v == null) {
        dot.setAttribute('visibility', 'hidden');
      } else {
        dot.setAttribute('cx', X(i));
        dot.setAttribute('cy', Y(v));
        dot.setAttribute('visibility', 'visible');
      }
      tip.textContent = cfg.tip(i);
      tip.hidden = false;
      tip.style.left = Math.min(88, Math.max(12, (X(i) / W) * 100)) + '%';
      tip.style.top = ((v == null ? m.t + ih : Y(v)) / H) * 100 + '%';
    });
    overlay.addEventListener('pointerleave', () => {
      guide.setAttribute('visibility', 'hidden');
      dot.setAttribute('visibility', 'hidden');
      tip.hidden = true;
    });
    overlay.addEventListener('click', (ev) => { if (cfg.onPick) cfg.onPick(indexAt(ev)); });
    host.append(svg, tip);
  }

  const pickYear = (i) => { state.year = years[i]; render(); };
  const withNote = (text, note) => `${text}${note ? ` (${note.toLowerCase()})` : ''}`;

  function productionTip(tonnes, flag, i) {
    return withNote(`${years[i]}: ${fmtMass(tonnes, state.unit)} ${UNITS[state.unit].big}`, flagText('production', flag));
  }
  function exportTip(src, i) {
    const u = UNITS[state.unit];
    const price = exportAt(src, i);
    const text = price == null ? `${years[i]}: no export price`
      : `${years[i]}: ${fmtPrice(price, state.unit)} per ${u.short}, ${fmtMass(src.exportQty[i], state.unit)} ${u.big} exported`;
    return withNote(text, flagText('trade', src.exportFlags[i].trim()));
  }

  function drawWorldCharts() {
    const unit = state.unit, u = UNITS[unit], marker = yearIndex.get(state.year);
    lineChart($('world-chart'), {
      ys: visibleSeries(D.world.production, D.world.productionFlags).map((t) => (t == null ? null : massBig(t, unit))),
      color: '#c77d00',
      area: true,
      label: `World honey production in ${u.big}, ${years[0]} to ${lastYear}`,
      marker,
      empty: 'No official figures.',
      tip: (i) => productionTip(D.world.production[i], D.world.productionFlags[i].trim(), i),
      onPick: pickYear,
    });
    lineChart($('world-price-chart'), {
      ys: exportSeries(D.world).map((p) => (p == null ? null : priceIn(p, unit))),
      color: '#6b4a1f',
      prefix: '$',
      label: `World honey export price in USD per ${u.short}, ${firstExportYear} to ${lastYear}`,
      marker,
      empty: 'No official figures.',
      tip: (i) => exportTip(D.world, i),
      onPick: pickYear,
    });
  }

  function drawDetailCharts() {
    const a = byCode.get(state.area);
    if (!a || !$('detail-production')) return;
    const unit = state.unit, u = UNITS[unit], marker = yearIndex.get(state.year);
    lineChart($('detail-production'), {
      ys: visibleSeries(a.production, a.productionFlags).map((t) => (t == null ? null : massBig(t, unit))),
      color: '#c77d00',
      area: true,
      label: `${a.name}: honey production in ${u.big}`,
      marker,
      empty: state.official ? 'No official production figures.' : 'FAOSTAT has no production figures for this country.',
      tip: (i) => productionTip(a.production[i], a.productionFlags[i].trim(), i),
      onPick: pickYear,
    });
    lineChart($('detail-price'), {
      ys: visibleSeries(a.price, a.priceFlags).map((p) => (p == null ? null : priceIn(p, unit))),
      color: '#6b4a1f',
      prefix: '$',
      label: `${a.name}: producer price in USD per ${u.short}`,
      marker,
      empty: state.official ? 'No official producer price.' : 'FAOSTAT has no producer price for this country.',
      tip: (i) => withNote(`${years[i]}: ${fmtPrice(a.price[i], unit)} per ${u.short}`, flagText('price', a.priceFlags[i].trim())),
      onPick: pickYear,
    });
    lineChart($('detail-export'), {
      ys: exportSeries(a).map((p) => (p == null ? null : priceIn(p, unit))),
      color: '#8a3b12',
      prefix: '$',
      label: `${a.name}: export price in USD per ${u.short}`,
      marker,
      empty: emptyExport(a),
      tip: (i) => exportTip(a, i),
      onPick: pickYear,
    });
  }

  // ---- Cards -----------------------------------------------------------------
  function renderCards(model) {
    const unit = state.unit, u = UNITS[unit], i = model.i;

    const t = model.world;
    $('card-production').textContent = t == null ? DASH : `${fmtMass(t, unit)} ${u.big}`;
    const other = unit === 'tonne' ? 'lb' : 'tonne';
    const note = flagText('production', model.worldFlag);
    $('card-production-sub').textContent = t != null
      ? `${fmtMass(t, other)} ${UNITS[other].big} in ${state.year}${note ? `. ${note}.` : ''}`
      : (D.world.production[i] == null ? `No figure for ${state.year}.` : `FAO has no official world total for ${state.year}.`);

    // The world export price uses the World row of FAOSTAT: export value divided by export quantity.
    const price = exportAt(D.world, i);
    if (price == null) {
      $('card-export').textContent = DASH;
      $('card-export-sub').textContent = D.world.exportFlags[i] === ' '
        ? `FAOSTAT has no export figures for ${state.year}.` : `FAO has no official world export figures for ${state.year}.`;
    } else {
      const exporters = model.rows.filter((r) => r.exportPrice != null);
      const total = exporters.reduce((sum, r) => sum + r.exportQty, 0);
      const official = exporters.filter((r) => r.eFlag === 'A').reduce((sum, r) => sum + r.exportQty, 0);
      $('card-export').textContent = `${fmtPrice(price, unit)} per ${u.short}`;
      $('card-export-sub').textContent = `Customs value divided by quantity. ${fmtMass(D.world.exportQty[i], unit)} ${u.big} exported in ${state.year}. `
        + (state.official || !total ? 'Official figures only.' : `${pct(official / total)} of the tonnage is official.`);
    }

    const priced = model.rows.filter((r) => r.price != null).sort((x, y) => x.price - y.price);
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

  function valueCell(text, kind, flag, hasValue, title) {
    const td = h('td', { class: 'num', text, title });
    const note = hasValue ? flagText(kind, flag) : '';
    if (note) td.append(h('sup', { class: 'flag', title: note, text: flag }));
    return td;
  }

  function renderTable(model) {
    const unit = state.unit, u = UNITS[unit];
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
        valueCell(fmtMass(r.production, unit), 'production', r.pFlag, r.production != null),
        h('td', { class: 'num', text: fmtShare(r.share) }),
        valueCell(fmtPrice(r.price, unit), 'price', r.cFlag, r.price != null),
        valueCell(fmtPrice(r.exportPrice, unit), 'trade', r.eFlag, r.exportPrice != null,
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
      + 'The table lists China, mainland and Taiwan Province of China as two rows. FAOSTAT "China" is their sum.'
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
    const production = visible(a.production[i], a.productionFlags[i].trim());
    const price = visible(a.price[i], a.priceFlags[i].trim());
    const exportPrice = exportAt(a, i);
    const expFlag = a.exportFlags[i].trim();
    const exportedQty = expFlag && (!state.official || expFlag === 'A') ? a.exportQty[i] : null;
    const share = production != null && model.world ? production / model.world : null;
    box.replaceChildren(
      h('div', { class: 'panel-head' },
        h('h2', { text: a.name }),
        h('button', { type: 'button', class: 'ghost', id: 'clear', text: 'Clear' })),
      h('dl', { class: 'facts' },
        h('dt', { text: `Production ${state.year}` }),
        h('dd', { text: production == null ? DASH : `${fmtMass(production, unit)} ${u.big}` }),
        h('dt', { text: 'Share of world' }),
        h('dd', { text: fmtShare(share) }),
        h('dt', { text: `Producer price ${state.year}` }),
        h('dd', { text: price == null ? DASH : `${fmtPrice(price, unit)} per ${u.short}` }),
        h('dt', { text: `Export price ${state.year}` }),
        h('dd', { text: exportPrice != null ? `${fmtPrice(exportPrice, unit)} per ${u.short}` : (exportedQty != null ? `${DASH} (under ${MIN_EXPORT_TONNES} t)` : DASH) }),
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

  // ---- Sources and footer ----------------------------------------------------
  function renderSources() {
    const meta = D.meta;
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
    resizeTimer = setTimeout(() => { drawWorldCharts(); drawDetailCharts(); }, 150);
  });

  // ---- Start -----------------------------------------------------------------
  readHash();
  $('year').min = years[0];
  $('year').max = lastYear;
  $('subtitle').textContent = `${D.meta.item.replace(/ \(.*\)$/, '')} data from ${D.meta.database}. `
    + `Production ${years[0]} to ${lastYear}. Producer price ${firstPriceYear} to ${lastYear}. Export price ${firstExportYear} to ${lastYear}.`;
  $('world-range').textContent = `${years[0]} to ${lastYear}`;
  $('price-range').textContent = `${firstExportYear} to ${lastYear}`;
  renderSources();
  render();
})();
