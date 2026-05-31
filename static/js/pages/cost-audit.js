// pages/cost-audit.js — §4.6 Cost & Audit page entry.
// Composes 4 sections: chart, monthly breakdown table, budget gauge, virtualized audit log.
// Data sources: api.getUsage(), api.getAuditLog(), api.getConfig()/saveConfig().
// Pricing is display-only (see ./cost-audit/pricing.js) — backend doesn't expose pricing.

import * as api from '../lib/api.js';
import { t } from '../lib/i18n.js';
import { h, classes, Card, Button, Switch, Toast } from '../lib/components.js';
import {
  ENGINES, ENGINE_LABEL, monthKey, fmtJpy, fmtInt,
  costForEngine, engineCallStats, build30dSeries,
} from './cost-audit/pricing.js';
import { renderChart, chartHeader } from './cost-audit/chart.js';
import { renderAudit } from './cost-audit/audit-table.js';

const PREFERS_REDUCED_MOTION = typeof window !== 'undefined'
  && window.matchMedia
  && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// ---------- Monthly breakdown table ----------

function renderTable(usage, audit) {
  const mk = monthKey(new Date());
  const row = usage[mk] || {};
  const sinceMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1).getTime();
  let sortBy = 'cost', sortDir = -1;

  const data = ENGINES.map((eng) => ({
    engine: eng,
    calls: engineCallStats(audit, eng, sinceMonth),
    in:    row[`${eng}_input_tokens`] || 0,
    out:   row[`${eng}_output_tokens`] || 0,
    audio: row[`${eng}_whisper_seconds`] || 0,
    cost:  costForEngine(eng, row),
  }));

  const tbody = h('tbody', null);
  const tfoot = h('tfoot', null);

  function paint() {
    const sorted = [...data].sort((a, b) => {
      const av = a[sortBy], bv = b[sortBy];
      if (typeof av === 'string') return av.localeCompare(bv) * sortDir;
      return ((av || 0) - (bv || 0)) * sortDir;
    });
    tbody.replaceChildren(...sorted.map((r) =>
      h('tr', { class: 'border-t border-[var(--border)]' },
        h('td', { class: 'py-2 px-3 text-sm font-medium text-[var(--text)]' }, ENGINE_LABEL[r.engine] || r.engine),
        h('td', { class: 'py-2 px-3 text-sm mono tabular-nums text-[var(--text-2)] text-right' }, fmtInt(r.calls)),
        h('td', { class: 'py-2 px-3 text-sm mono tabular-nums text-[var(--text-2)] text-right' }, fmtInt(r.in)),
        h('td', { class: 'py-2 px-3 text-sm mono tabular-nums text-[var(--text-2)] text-right' }, fmtInt(r.out)),
        h('td', { class: 'py-2 px-3 text-sm mono tabular-nums text-[var(--text-2)] text-right' }, fmtInt(r.audio)),
        h('td', { class: 'py-2 px-3 text-sm mono tabular-nums font-semibold text-[var(--text)] text-right' }, fmtJpy(r.cost)),
      )));
    const tot = data.reduce((s, r) => ({
      calls: s.calls + r.calls, in: s.in + r.in, out: s.out + r.out, audio: s.audio + r.audio, cost: s.cost + r.cost,
    }), { calls: 0, in: 0, out: 0, audio: 0, cost: 0 });
    tfoot.replaceChildren(h('tr', { class: 'border-t-2 border-[var(--border)] bg-[var(--surface-2)]' },
      h('td', { class: 'py-2 px-3 text-sm font-semibold text-[var(--text)]' }, t('cost.table.totals')),
      h('td', { class: 'py-2 px-3 text-sm mono tabular-nums font-semibold text-right' }, fmtInt(tot.calls)),
      h('td', { class: 'py-2 px-3 text-sm mono tabular-nums font-semibold text-right' }, fmtInt(tot.in)),
      h('td', { class: 'py-2 px-3 text-sm mono tabular-nums font-semibold text-right' }, fmtInt(tot.out)),
      h('td', { class: 'py-2 px-3 text-sm mono tabular-nums font-semibold text-right' }, fmtInt(tot.audio)),
      h('td', { class: 'py-2 px-3 text-sm mono tabular-nums font-semibold text-right' }, fmtJpy(tot.cost)),
    ));
  }

  const cols = [
    { key: 'engine', label: t('cost.table.engine'),       align: 'left'  },
    { key: 'calls',  label: t('cost.table.calls'),        align: 'right' },
    { key: 'in',     label: t('cost.table.inputTokens'),  align: 'right' },
    { key: 'out',    label: t('cost.table.outputTokens'), align: 'right' },
    { key: 'audio',  label: t('cost.table.audioSec'),     align: 'right' },
    { key: 'cost',   label: t('cost.table.cost'),         align: 'right' },
  ];
  const thead = h('thead', null, h('tr', null, ...cols.map((c) =>
    h('th', {
      scope: 'col',
      class: `py-2 px-3 text-xs font-semibold uppercase tracking-wide text-[var(--text-3)] cursor-pointer select-none text-${c.align}`,
      onClick: () => { if (sortBy === c.key) sortDir = -sortDir; else { sortBy = c.key; sortDir = -1; } paint(); },
      'aria-sort': sortBy === c.key ? (sortDir === 1 ? 'ascending' : 'descending') : 'none',
    }, c.label))));

  paint();
  return Card({
    title: t('cost.table.title'),
    children: h('div', { class: 'overflow-x-auto' },
      h('table', { class: 'w-full' }, thead, tbody, tfoot)),
  });
}

// ---------- Budget setting card ----------

function renderBudget(cfg, currentSpend, onSave) {
  const budget = Number(cfg.monthly_budget_jpy || 0);
  const cutoff = !!cfg.enable_budget_cutoff;
  const pct = budget > 0 ? Math.min(999, Math.round(currentSpend / budget * 100)) : 0;
  const barColor = pct >= 90 ? 'bg-[var(--danger)]'
                 : pct >= 60 ? 'bg-[var(--warning)]'
                 : 'bg-[var(--success)]';
  const gaugeText = budget > 0
    ? (pct > 100 ? t('cost.budget.over', { pct })
                 : t('cost.budget.gauge', { spent: fmtJpy(currentSpend), budget: fmtJpy(budget), pct }))
    : t('cost.budget.help');

  const input = h('input', {
    type: 'number', id: 'budget-input',
    class: classes.input + ' mono tabular-nums max-w-xs',
    min: '0', step: '100',
    value: String(budget),
    placeholder: t('cost.budget.placeholder'),
    'aria-describedby': 'budget-help',
  });
  let cutoffOn = cutoff;

  return Card({
    title: t('cost.budget.title'),
    children: h('div', { class: 'space-y-4' },
      h('div', null,
        h('label', { class: classes.label, for: 'budget-input' }, t('cost.budget.label')),
        input,
        h('div', { id: 'budget-help', class: 'text-xs text-[var(--text-3)] mt-1' }, t('cost.budget.help')),
      ),
      budget > 0 ? h('div', null,
        h('div', {
          class: 'h-3 w-full rounded-full bg-[var(--surface-2)] overflow-hidden',
          role: 'progressbar',
          'aria-valuemin': '0', 'aria-valuemax': String(budget),
          'aria-valuenow': String(Math.round(currentSpend)),
          'aria-label': t('cost.budget.title'),
        }, h('div', {
          class: `h-full ${barColor} ${PREFERS_REDUCED_MOTION ? '' : 'transition-all'}`,
          style: { width: `${Math.min(100, pct)}%` },
        })),
        h('div', { class: 'mt-2 text-sm mono tabular-nums text-[var(--text-2)]' }, gaugeText),
      ) : null,
      Switch({
        id: 'budget-cutoff', label: t('cost.budget.cutoff'),
        description: t('cost.budget.cutoff.desc'),
        checked: cutoffOn,
        onChange: (v) => { cutoffOn = v; },
      }),
      h('div', null, Button({
        variant: 'primary', icon: 'check', label: t('cost.budget.save'),
        onClick: () => {
          const raw = Number(input.value);
          if (!Number.isFinite(raw) || raw < 0) {
            Toast({ message: t('toast.error'), type: 'error' });
            return;
          }
          onSave({ monthly_budget_jpy: Math.round(raw), enable_budget_cutoff: cutoffOn });
        },
      })),
    ),
  });
}

// ---------- mount ----------

export default async function mount(slot) {
  slot.replaceChildren(h('div', { class: 'p-8 text-center text-[var(--text-3)]' }, 'Loading…'));

  let usage = {}, audit = [], cfg = {};
  try {
    [usage, audit, cfg] = await Promise.all([
      api.getUsage().catch(() => ({})),
      api.getAuditLog().catch(() => []),
      api.getConfig().catch(() => ({})),
    ]);
  } catch {
    Toast({ message: t('toast.error'), type: 'error' });
  }
  if (!Array.isArray(audit)) audit = [];
  if (!usage || typeof usage !== 'object') usage = {};
  if (!cfg || typeof cfg !== 'object') cfg = {};

  const tk = monthKey(new Date());
  const currentSpend = ENGINES.reduce((s, e) => s + costForEngine(e, usage[tk] || {}), 0);

  const chartBody = h('div', { class: 'w-full' });
  const chartCard = h('section', { class: classes.card }, chartHeader(usage), chartBody);

  const page = h('div', { class: 'space-y-6' },
    h('header', { class: 'mb-2' },
      h('h1', { class: 'text-2xl font-semibold text-[var(--text)]' }, t('page.cost.title'))),
    chartCard,
    renderTable(usage, audit),
    renderBudget(cfg, currentSpend, async ({ monthly_budget_jpy, enable_budget_cutoff }) => {
      try {
        await api.saveConfig({ monthly_budget_jpy, enable_budget_cutoff });
        Toast({ message: t('toast.saved'), type: 'success' });
        await mount(slot);
      } catch {
        Toast({ message: t('toast.error'), type: 'error' });
      }
    }),
    renderAudit(audit),
  );

  slot.replaceChildren(page);

  const draw = () => renderChart(chartBody, build30dSeries(usage, audit));
  draw();
  let raf;
  window.addEventListener('resize', () => {
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(draw);
  });

  if (window.lucide) window.lucide.createIcons();
}
