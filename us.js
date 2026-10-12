// The United States panel. It reads data/us_supply.js (USDA NASS honey data) and draws
// the year facts, two charts and a state table. The data file loads only when the panel
// first comes into view, so the rest of the page does not wait for it.
// It uses the helpers in ui.js (window.HONEY_UI).
(() => {
  'use strict';
  const { UNITS, DASH, f0, f2, massBig, fmtMass, massText, priceIn, fmtPrice, frame, hover, hash, unit, h, s, link, INK, HALO } = window.HONEY_UI;

  const KG_PER_LB = 0.45359237;
  const nf1 = new Intl.NumberFormat('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const nf2 = f2;
  const COLOR_PROD = '#c77d00';
  const COLOR_PRICE = '#6b4a1f';
  const MISSING_FILE = 'The file data/us_supply.js did not load.';

  // NASS values are in pounds and US dollars per pound; the page converts them to the chosen unit.
  const tonnesOf = (lb) => (lb == null ? null : (lb * KG_PER_LB) / 1000);
  const usdPerTonneOf = (usdPerLb) => (usdPerLb == null ? null : (usdPerLb * 1000) / KG_PER_LB);
  const longDate = (iso) => new Date(iso + 'T12:00:00Z').toLocaleDateString('en-GB', {
    day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC',
  });

  // Row layout in window.HONEY_US_SUPPLY.rows: [geo, year, report, colonies, yield, production, stocks, price, value].
  const COL_IDX = { colonies: 3, yield: 4, production: 5, stocks: 6, price: 7, value: 8 };

  const state = {
    data: null,
    years: [],          // every year of the file, ascending
    usYears: [],        // years that have a US row, ascending
    rowAt: new Map(),   // "geo:yearIndex" -> row
    firstAt: new Map(), // year -> [year, firstReport, firstProduction, firstPrice, ...]
    year: null,
    sort: { key: 'production', dir: -1 },
  };
  let body = null;
  let select = null;

  function showError() {
    const target = document.getElementById('us-body');
    if (target) target.replaceChildren(h('p', { class: 'error', text: MISSING_FILE }));
  }

  function prepare(data) {
    state.data = data;
    state.years = data.years;
    state.rowAt = new Map();
    for (const r of data.rows) state.rowAt.set(r[0] + ':' + r[1], r);
    state.firstAt = new Map();
    for (const u of data.us) state.firstAt.set(u[0], u);
    state.usYears = data.years.filter((y, i) => state.rowAt.has('0:' + i));
  }

  // The sort works on the raw NASS values, so it does not depend on the unit.
  function colsFor(u) {
    const cfg = UNITS[u];
    return [
      { key: 'state', label: 'State', idx: null },
      { key: 'colonies', label: 'Colonies (thousands)', idx: COL_IDX.colonies,
        show: (v) => (v == null ? DASH : f0.format(v / 1000)) },
      { key: 'yield', label: u === 'lb' ? 'Yield (lb per colony)' : 'Yield (kg per colony)', idx: COL_IDX.yield,
        show: (v) => (v == null ? DASH : nf1.format(u === 'lb' ? v : v * KG_PER_LB)) },
      { key: 'production', label: `Production (${cfg.big})`, idx: COL_IDX.production,
        show: (v) => fmtMass(tonnesOf(v), u) },
      { key: 'stocks', label: `Stocks (${cfg.big})`, idx: COL_IDX.stocks,
        show: (v) => fmtMass(tonnesOf(v), u) },
      { key: 'price', label: `Price (USD per ${cfg.short})`, idx: COL_IDX.price,
        show: (v) => fmtPrice(usdPerTonneOf(v), u) },
      { key: 'value', label: 'Value (USD million)', idx: COL_IDX.value,
        show: (v) => (v == null ? DASH : nf1.format(v / 1e6)) },
    ];
  }

  // Rows with no value sort last in either direction.
  function sortItems(items, cols) {
    const col = cols.find((c) => c.key === state.sort.key) || cols[0];
    const get = (item) => (col.idx == null ? item.name : item.row[col.idx]);
    const dir = state.sort.dir;
    return items.slice().sort((a, b) => {
      const x = get(a), y = get(b);
      if (x == null && y == null) return 0;
      if (x == null) return 1;
      if (y == null) return -1;
      if (typeof x === 'string') return x.localeCompare(y) * dir;
      return (x - y) * dir;
    });
  }

  function facts(us, i, u) {
    const cfg = UNITS[u];
    const year = state.years[i];
    const [, , rep, col, yld, prod, stk, price, value] = us;
    const lead = prod != null ? `${massText(tonnesOf(prod), u)} of honey` : 'production not published';
    const colTxt = col != null ? ` from ${nf2.format(col / 1e6)} million colonies` : '';
    const yldTxt = yld != null ? ` (${nf1.format(u === 'lb' ? yld : yld * KG_PER_LB)} ${u === 'lb' ? 'lb' : 'kg'} per colony)` : '';
    const parts = [`${year}: ${lead}${colTxt}${yldTxt}.`];
    if (price != null) parts.push(`Average price ${fmtPrice(usdPerTonneOf(price), u)} per ${cfg.short}.`);
    if (value != null) parts.push(`Value $${nf1.format(value / 1e6)} million.`);
    if (stk != null) parts.push(`Stocks on 15 December ${massText(tonnesOf(stk), u)}.`);
    parts.push(`Report of ${longDate(state.data.reports[rep].date)}.`);
    return h('p', { class: 'us-facts', text: parts.join(' ') });
  }

  // The first estimate of the selected year, shown only when a newer report revised it.
  function firstLine(us, i, u) {
    const first = state.firstAt.get(state.years[i]);
    if (!first || first[1] == null || first[1] === us[2]) return null;
    const cfg = UNITS[u];
    return h('p', { class: 'us-facts note', text:
      `First estimate (${longDate(state.data.reports[first[1]].date)}): ` +
      `${first[2] == null ? DASH : massText(tonnesOf(first[2]), u)}, ` +
      `${first[3] == null ? DASH : fmtPrice(usdPerTonneOf(first[3]), u)} per ${cfg.short}.` });
  }

  // Raw values per year: the newest report (last) and the first estimate (first, only when it differs).
  function seriesFor(field) {
    const last = [], first = [];
    state.years.forEach((year, j) => {
      const r = state.rowAt.get('0:' + j);
      const e = state.firstAt.get(year);
      last.push(r ? r[field] : null);
      const differs = r && e && e[1] != null && e[1] !== r[2];
      first.push(differs ? (field === COL_IDX.production ? e[2] : e[3]) : null);
    });
    return { last, first };
  }

  // Draws one chart into box. Values are plotted in the unit of the page; tips use the raw values.
  function drawChart(box, cfg) {
    const { u, series, toPlot, fmtRaw, prefix, label, color } = cfg;
    const values = series.last.concat(series.first).filter((v) => v != null).map(toPlot);
    const top = (Math.max(0, ...values) * 1.1) || 1;
    const f = frame({ years: state.years, host: box, top, height: 250, bottom: 24, prefix, label });
    const layer = s('g', { 'clip-path': `url(#${f.defs.firstChild.id})` });
    f.svg.append(layer);
    const { X, Y, m, ih } = f;
    const i = state.years.indexOf(state.year);

    // Thin link from the first estimate to the newest value of the same year.
    series.first.forEach((raw, j) => {
      if (raw == null || series.last[j] == null) return;
      layer.append(s('line', { x1: X(j), x2: X(j), y1: Y(toPlot(raw)), y2: Y(toPlot(series.last[j])), stroke: INK, 'stroke-width': 1, opacity: 0.7 }));
    });

    // Line through the newest values; a missing year breaks it.
    let d = '', pen = false;
    series.last.forEach((raw, j) => {
      if (raw == null) { pen = false; return; }
      d += (pen ? 'L' : 'M') + X(j).toFixed(1) + ' ' + Y(toPlot(raw)).toFixed(1);
      pen = true;
    });
    if (d) layer.append(s('path', { d, fill: 'none', stroke: INK, 'stroke-width': 1.5, opacity: 0.85 }));

    layer.append(s('line', { class: 'marker', x1: X(i), x2: X(i), y1: m.t, y2: m.t + ih }));

    series.first.forEach((raw, j) => {
      if (raw == null) return;
      layer.append(s('circle', { cx: X(j), cy: Y(toPlot(raw)), r: 3.5, fill: '#fff', stroke: color, 'stroke-width': 1.5 }));
    });
    series.last.forEach((raw, j) => {
      if (raw == null) return;
      layer.append(s('circle', { ...HALO, cx: X(j), cy: Y(toPlot(raw)), r: 3.5, fill: color }));
    });
    const sel = series.last[i];
    if (sel != null) layer.append(s('circle', { cx: X(i), cy: Y(toPlot(sel)), r: 7, fill: 'none', stroke: INK, 'stroke-width': 1.75 }));

    const tip = hover(f, {
      tip(j) {
        const year = state.years[j];
        const r = state.rowAt.get('0:' + j);
        if (!r) return `${year}: no data`;
        const lines = [`${year}: ${fmtRaw(series.last[j], u)} \u00b7 report of ${longDate(state.data.reports[r[2]].date)}`];
        if (series.first[j] != null) {
          const e = state.firstAt.get(year);
          lines.push(`First estimate ${longDate(state.data.reports[e[1]].date)}: ${fmtRaw(series.first[j], u)}`);
        }
        return lines.join('\n');
      },
      at(j) {
        const raw = series.last[j] != null ? series.last[j] : series.first[j];
        return raw == null ? m.t : Y(toPlot(raw));
      },
      onPick(j) {
        if (state.rowAt.has('0:' + j)) pick(state.years[j]);
      },
    });
    box.append(f.svg, tip);
  }

  function table(i, u) {
    const cols = colsFor(u);
    const states = [], others = [];
    state.data.geos.forEach((geo, g) => {
      const r = state.rowAt.get(g + ':' + i);
      if (!r || geo.level === 'country') return;
      (geo.level === 'other' ? others : states).push({ name: geo.name, row: r });
    });
    const sorted = sortItems(states, cols).concat(others);
    const rowCells = (row, name) => cols.map((c) => (c.idx == null
      ? h('td', { text: name })
      : h('td', { class: 'num', text: c.show(row[c.idx]) })));
    const usRow = state.rowAt.get('0:' + i);
    const tbl = h('table', { id: 'us-table' },
      h('thead', null, h('tr', null, cols.map((c) => {
        const active = state.sort.key === c.key;
        return h('th', { class: c.idx == null ? null : 'num', 'aria-sort': active ? (state.sort.dir === 1 ? 'ascending' : 'descending') : null },
          h('button', { class: 'sort', type: 'button', 'data-key': c.key, text: c.label }));
      }))),
      h('tbody', null, sorted.map((item) => h('tr', null, rowCells(item.row, item.name)))),
      h('tfoot', null, h('tr', null, usRow ? rowCells(usRow, 'United States') : [h('td', { text: 'United States' })])),
    );
    return h('div', { class: 'table-wrap' }, tbl);
  }

  function source() {
    const meta = state.data.meta;
    return h('p', { class: 'note' },
      'Source: USDA NASS, ', link(meta.url, 'Honey'), `, report of ${longDate(meta.last)}. ` +
      'Revised values come from the newest report that has the year; ',
      link(meta.finalEstimatesUrl, 'Final Estimates'), ' revise 2013 to 2017.');
  }

  function render() {
    if (!body || !state.data) return;
    const u = unit.get();
    const active = document.activeElement;
    const focusKey = active && active.closest && active.closest('#us-table') ? active.dataset.key : null;
    body.replaceChildren();
    const i = state.years.indexOf(state.year);
    const us = state.rowAt.get('0:' + i);
    if (!us) {
      const first = state.usYears[0], last = state.usYears[state.usYears.length - 1];
      body.append(h('p', { class: 'note', text: `No data for this year. The data go from ${first} to ${last}.` }));
      return;
    }
    const prodBox = h('div', { class: 'chart' }, h('h3', { text: `Production (${UNITS[u].big})` }));
    const priceBox = h('div', { class: 'chart' }, h('h3', { text: `Average price (USD per ${UNITS[u].short})` }));
    const first = firstLine(us, i, u);
    body.append(facts(us, i, u));
    if (first) body.append(first);
    body.append(h('p', { class: 'note', text: 'Filled dot: the newest report. Open dot: the first estimate, when a later report revised it.' }));
    body.append(h('div', { class: 'charts' }, prodBox, priceBox), table(i, u), source());
    drawChart(prodBox, {
      u, series: seriesFor(COL_IDX.production), color: COLOR_PROD, prefix: '', label: 'Production by year',
      toPlot: (raw) => massBig(tonnesOf(raw), u),
      fmtRaw: (raw, unitKey) => massText(tonnesOf(raw), unitKey),
    });
    drawChart(priceBox, {
      u, series: seriesFor(COL_IDX.price), color: COLOR_PRICE, prefix: '$', label: 'Average price by year',
      toPlot: (raw) => priceIn(usdPerTonneOf(raw), u),
      fmtRaw: (raw, unitKey) => `${fmtPrice(usdPerTonneOf(raw), unitKey)} per ${UNITS[unitKey].short}`,
    });
    if (focusKey) {
      const b = body.querySelector(`#us-table button.sort[data-key="${focusKey}"]`);
      if (b) b.focus();
    }
  }

  function pick(year) {
    state.year = year;
    select.value = String(year);
    hash.write({ uy: year });
    render();
  }

  function init() {
    if (!window.HONEY_US_SUPPLY) { showError(); return; }
    prepare(window.HONEY_US_SUPPLY);
    body = document.getElementById('us-body');
    select = document.getElementById('us-year');
    body.replaceChildren();
    const desc = state.usYears.slice().reverse();
    select.replaceChildren(...desc.map((y) => h('option', { value: y, text: String(y) })));

    // The address may name a year; an unknown or invalid year falls back to the last year.
    const want = Number(hash.read().get('uy'));
    state.year = state.usYears.includes(want) ? want : state.usYears[state.usYears.length - 1];
    select.value = String(state.year);

    select.addEventListener('change', () => pick(Number(select.value)));
    body.addEventListener('click', (ev) => {
      const b = ev.target.closest('button.sort');
      if (!b) return;
      const key = b.dataset.key;
      if (state.sort.key === key) state.sort.dir = -state.sort.dir;
      else state.sort = { key, dir: key === 'state' ? 1 : -1 };
      render();
    });
    unit.onChange(() => render());
    let timer = null;
    window.addEventListener('resize', () => {
      clearTimeout(timer);
      timer = setTimeout(render, 150);
    });
    render();
  }

  function load() {
    const script = document.createElement('script');
    script.src = 'data/us_supply.js';
    script.onload = () => init();
    script.onerror = () => showError();
    document.body.append(script);
  }

  const status = window.HONEY_US_STATUS;
  const statusLine = document.getElementById('us-status');
  if (status && statusLine) statusLine.textContent = `US data last checked ${status.checked}`;

  // Load the data only when the panel first comes into view.
  const section = document.getElementById('us');
  if (section && 'IntersectionObserver' in window) {
    const io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) {
        io.disconnect();
        load();
      }
    });
    io.observe(section);
  } else {
    load();
  }
})();
