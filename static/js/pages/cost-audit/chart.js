// chart.js — hand-rolled SVG 30-day cost line chart.
// Uses CSS vars for colors; respects prefers-reduced-motion (no transitions added).

import { t } from '../../lib/i18n.js';
import { h } from '../../lib/components.js';
import { EmptyState } from '../../lib/components.js';
import { ENGINES, ENGINE_COLORS, ENGINE_LABEL, monthKey, fmtJpy, costForEngine } from './pricing.js';

export function renderChart(container, { days, series }) {
  container.replaceChildren();
  const W = container.clientWidth || 700;
  const H = 240;
  const padL = 56, padR = 16, padT = 12, padB = 28;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;

  let max = 0;
  for (const eng of ENGINES) for (const v of series[eng]) if (v > max) max = v;
  if (max <= 0) {
    container.appendChild(EmptyState({ icon: 'bar-chart-2', title: t('cost.chart.empty') }));
    return;
  }
  const yMax = Math.max(1, Math.ceil(max * 1.1));
  const svgNS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(svgNS, 'svg');
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.setAttribute('width', '100%');
  svg.setAttribute('height', String(H));
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', t('cost.chart.title'));

  for (let i = 0; i <= 4; i++) {
    const y = padT + innerH * (i / 4);
    const value = yMax * (1 - i / 4);
    const line = document.createElementNS(svgNS, 'line');
    line.setAttribute('x1', padL); line.setAttribute('x2', W - padR);
    line.setAttribute('y1', y);    line.setAttribute('y2', y);
    line.setAttribute('stroke', 'var(--border)');
    line.setAttribute('stroke-width', '1');
    svg.appendChild(line);
    const txt = document.createElementNS(svgNS, 'text');
    txt.setAttribute('x', padL - 6); txt.setAttribute('y', y + 4);
    txt.setAttribute('text-anchor', 'end');
    txt.setAttribute('fill', 'var(--text-3)');
    txt.setAttribute('font-size', '10');
    txt.setAttribute('font-family', 'JetBrains Mono, monospace');
    txt.textContent = fmtJpy(value);
    svg.appendChild(txt);
  }

  for (let i = 0; i < days.length; i += 5) {
    const x = padL + innerW * (i / (days.length - 1));
    const d = days[i];
    const txt = document.createElementNS(svgNS, 'text');
    txt.setAttribute('x', x); txt.setAttribute('y', H - 8);
    txt.setAttribute('text-anchor', 'middle');
    txt.setAttribute('fill', 'var(--text-3)');
    txt.setAttribute('font-size', '10');
    txt.textContent = `${d.getMonth() + 1}/${d.getDate()}`;
    svg.appendChild(txt);
  }

  for (const eng of ENGINES) {
    const points = series[eng].map((v, i) => {
      const x = padL + innerW * (i / (series[eng].length - 1));
      const y = padT + innerH * (1 - v / yMax);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
    const poly = document.createElementNS(svgNS, 'polyline');
    poly.setAttribute('points', points);
    poly.setAttribute('fill', 'none');
    poly.setAttribute('stroke', ENGINE_COLORS[eng] || 'var(--text-3)');
    poly.setAttribute('stroke-width', '2');
    poly.setAttribute('stroke-linejoin', 'round');
    poly.setAttribute('stroke-linecap', 'round');
    svg.appendChild(poly);
  }
  container.appendChild(svg);
}

export function chartHeader(usage) {
  const tk = monthKey(new Date());
  const last = new Date(); last.setMonth(last.getMonth() - 1);
  const lk = monthKey(last);
  const tCost = ENGINES.reduce((s, e) => s + costForEngine(e, usage[tk] || {}), 0);
  const lCost = ENGINES.reduce((s, e) => s + costForEngine(e, usage[lk] || {}), 0);
  let deltaTxt;
  if (lCost <= 0 && tCost <= 0) deltaTxt = t('cost.delta.flat');
  else if (lCost <= 0)          deltaTxt = t('cost.delta.up', { n: 100 });
  else {
    const pct = Math.round((tCost - lCost) / lCost * 100);
    deltaTxt = pct > 0 ? t('cost.delta.up', { n: pct })
             : pct < 0 ? t('cost.delta.down', { n: pct })
             : t('cost.delta.flat');
  }

  const legend = h('div', { class: 'flex flex-wrap gap-3 text-xs text-[var(--text-2)]', role: 'list', 'aria-label': 'legend' },
    ...ENGINES.map((e) =>
      h('span', { class: 'inline-flex items-center gap-1.5', role: 'listitem' },
        h('span', { class: 'inline-block w-3 h-3 rounded-full', style: { background: ENGINE_COLORS[e] } }),
        ENGINE_LABEL[e],
      )),
  );

  return h('div', { class: 'flex flex-wrap items-start justify-between gap-4 mb-4' },
    h('div', null,
      h('h2', { class: 'text-lg font-semibold text-[var(--text)]' }, t('cost.chart.title')),
      h('div', { class: 'mt-1 text-xs text-[var(--text-3)]' }, `${t('cost.total.lastMonth')}: ${fmtJpy(lCost)}`),
    ),
    h('div', { class: 'text-right' },
      h('div', { class: 'text-2xl font-semibold mono tabular-nums text-[var(--text)]' }, fmtJpy(tCost)),
      h('div', { class: 'text-xs text-[var(--text-3)]' }, `${t('cost.total.thisMonth')} · ${deltaTxt}`),
      h('div', { class: 'mt-2' }, legend),
    ),
  );
}
