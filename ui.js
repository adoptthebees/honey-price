// Shared helpers for the honey price page: units, number formats, DOM and SVG builders,
// the frame and tooltip of a line chart, and the address bar. app.js and us.js use them.
// They are exposed as window.HONEY_UI. This file loads before app.js.
(() => {
  'use strict';

  // ---- Units -----------------------------------------------------------------
  // FAOSTAT values are in tonnes. Prices are USD per tonne. US values are in pounds.
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
  const f0 = nf(0), f2 = nf(2);

  const massBig = (tonnes, unit) => (tonnes * UNITS[unit].perTonne) / UNITS[unit].bigDiv;
  // Digits for a number of size r. A whole-number unit (tonnes, or lb and kg below a million) uses no digits from 10 up.
  function digitsFor(r, whole) {
    if (whole && r >= 10) return 0;
    if (r >= 100) return 1;
    if (r >= 1) return 2;
    return Math.min(12, 1 - Math.floor(Math.log10(r)));
  }
  // The digits follow ref, so that the two ends of a range get the same number of digits.
  // If that would round a non-zero value to 0, the value gets its own digits instead.
  function fmtNum(v, ref, whole) {
    if (v === 0) return '0';
    let d = digitsFor(ref, whole);
    if (Number(v.toFixed(d)) === 0) d = digitsFor(v, whole);
    return nf(d).format(v);
  }
  function fmtMass(tonnes, unit, ref = tonnes) {
    if (tonnes == null) return DASH;
    return fmtNum(massBig(tonnes, unit), massBig(ref, unit), unit === 'tonne');
  }
  // A mass with its unit. A mass below one big unit shows in the small unit (lb or kg).
  function massText(tonnes, unit) {
    if (tonnes == null) return DASH;
    const u = UNITS[unit];
    if (unit === 'tonne' || massBig(tonnes, unit) >= 1) return `${fmtMass(tonnes, unit)} ${u.big}`;
    const small = tonnes * u.perTonne;
    return `${fmtNum(small, small, true)} ${u.short}`;
  }
  const priceIn = (usdPerTonne, unit) => usdPerTonne / UNITS[unit].perTonne;
  function fmtPrice(usdPerTonne, unit) {
    if (usdPerTonne == null) return DASH;
    return '$' + (unit === 'tonne' ? f0 : f2).format(priceIn(usdPerTonne, unit));
  }
  const fmtShare = (x) => (x == null ? DASH : x === 0 ? '0%' : x < 0.0005 ? '<0.1%' : (x * 100).toFixed(1) + '%');
  const pct = (x) => (x > 0 && x < 0.005 ? '<1%' : Math.round(x * 100) + '%');
  const norm = (text) => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

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

  // A number that makes SVG ids unique on the page.
  let idCount = 0;
  const uid = () => ++idCount;

  // ---- Line chart (SVG) ------------------------------------------------------
  function niceStep(raw) {
    const exp = Math.floor(Math.log10(raw));
    const f = raw / 10 ** exp;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * 10 ** exp;
  }

  // Ink for lines, whiskers and the selected year. A white halo keeps a point readable over a line.
  const INK = '#2a2118';
  const HALO = { stroke: '#fff', 'stroke-width': 1.2, 'paint-order': 'stroke' };

  // The frame of a chart: the grid and the labels, and the shading of the provisional years
  // when the page gives provisionalFrom. The x axis is always the full list of years, and the
  // y axis starts at 0.
  // cfg: { years, provisionalFrom (optional index), host, top, step, prefix, suffix, label, height, bottom }
  function frame(cfg) {
    const { years } = cfg;
    const W = Math.max(280, Math.round(cfg.host.clientWidth || 640));
    const H = cfg.height;
    const m = { t: 18, r: 14, b: cfg.bottom, l: 74 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const step = cfg.step || niceStep((cfg.top || 1) / 4);
    const yMax = Math.ceil(cfg.top / step - 1e-9) * step || step;
    const axis = nf(step >= 1 ? 0 : Math.ceil(-Math.log10(step)));
    const n = years.length;
    const X = (i) => m.l + (i / (n - 1)) * iw;
    const Y = (v) => m.t + ih - (v / yMax) * ih;

    const svg = s('svg', { class: 'svg', viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': cfg.label });
    const clipId = `clip${uid()}`;
    const clip = s('clipPath', { id: clipId });
    clip.append(s('rect', { x: m.l, y: m.t - 2, width: iw, height: ih + 4 }));
    const defs = s('defs');
    defs.append(clip);
    svg.append(defs);
    if (cfg.provisionalFrom != null) {
      svg.append(s('rect', { class: 'prov', x: X(cfg.provisionalFrom), y: m.t, width: W - m.r - X(cfg.provisionalFrom), height: ih }));
      svg.append(
        s('line', { class: 'prov-edge', x1: X(cfg.provisionalFrom), x2: X(cfg.provisionalFrom), y1: m.t, y2: m.t + ih }),
        s('text', { class: 'prov-label', x: X(cfg.provisionalFrom) - 5, y: m.t - 6, 'text-anchor': 'end' }, 'provisional'),
      );
    }
    for (let k = 0; k * step <= yMax + step / 1e6; k++) {
      const v = k * step;
      svg.append(
        s('line', { class: v === 0 ? 'grid zero' : 'grid', x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v) }),
        s('text', { class: 'tick', x: m.l - 8, y: Y(v) + 4, 'text-anchor': 'end' }, (cfg.prefix || '') + axis.format(v) + (cfg.suffix || '')),
      );
    }
    years.forEach((y, i) => {
      if (y % 10 === 0) svg.append(s('text', { class: 'tick', x: X(i), y: H - 6, 'text-anchor': 'middle' }, String(y)));
      else if (y % 5 === 0) svg.append(s('line', { class: 'axis-tick', x1: X(i), x2: X(i), y1: m.t + ih, y2: m.t + ih + 4 }));
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

  // ---- Address bar -----------------------------------------------------------
  // The address keeps the keys of every part of the page. A write changes only the keys given:
  // a value of null removes its key.
  const hash = {
    read() {
      return new URLSearchParams(location.hash.slice(1));
    },
    write(updates) {
      const p = hash.read();
      for (const [k, v] of Object.entries(updates)) {
        if (v == null) p.delete(k);
        else p.set(k, String(v));
      }
      try { history.replaceState(null, '', '#' + p); } catch (e) { /* some pages refuse this */ }
    },
  };

  // The unit control is shared by the FAOSTAT panels and the United States panels.
  // Unit keys: 'lb', 'kg', 'tonne'. The control starts on pounds.
  const unit = {
    get() {
      const checked = document.querySelector('input[name="unit"]:checked');
      return checked ? checked.value : 'lb';
    },
    onChange(fn) {
      for (const radio of document.querySelectorAll('input[name="unit"]')) {
        radio.addEventListener('change', () => fn(unit.get()));
      }
    },
  };

  // The year of the page is shared the same way. app.js owns the slider and sets the year;
  // any part of the page can ask for a year (a click on a chart) and listen for a change.
  const yearListeners = [];
  let pageYear = null;
  const year = {
    get() { return pageYear; },
    set(y) {
      if (y === pageYear) return;
      pageYear = y;
      for (const fn of yearListeners) fn(y);
    },
    onChange(fn) { yearListeners.push(fn); },
  };

  window.HONEY_UI = {
    UNITS, DASH, f0, f2, massBig, fmtMass, massText, priceIn, fmtPrice, fmtShare, pct, norm,
    h, s, link, uid, INK, HALO, frame, hover, hash, unit, year,
  };
})();
