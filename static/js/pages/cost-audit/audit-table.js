// audit-table.js — virtualized audit log card with engine + range filters.

import { t } from '../../lib/i18n.js';
import { h, classes, Card, Badge, EmptyState } from '../../lib/components.js';
import { ENGINE_LABEL, fmtInt } from './pricing.js';

export function renderAudit(audit) {
  const engineOpts = ['all', 'groq', 'anthropic', 'openai', 'openrouter', 'local'];
  let filterEngine = 'all';
  let filterRange = '7d';

  const countEl = h('div', { class: 'text-xs text-[var(--text-3)]' });
  const listEl = h('div', { class: 'border border-[var(--border)] rounded-xl overflow-hidden' });

  function rangeSince() {
    const now = Date.now();
    if (filterRange === '24h') return now - 24 * 3600e3;
    if (filterRange === '7d')  return now - 7  * 86400e3;
    if (filterRange === '30d') return now - 30 * 86400e3;
    return 0;
  }

  function paint() {
    const since = rangeSince();
    const filtered = (audit || []).filter((e) => {
      if (!e || !e.ts) return false;
      const ts = new Date(e.ts).getTime();
      if (Number.isNaN(ts)) return false;
      if (since && ts < since) return false;
      if (filterEngine !== 'all' && e.stt !== filterEngine && e.llm !== filterEngine) return false;
      return true;
    });
    countEl.textContent = t('cost.audit.count', { n: filtered.length });
    if (!filtered.length) {
      listEl.replaceChildren(EmptyState({ icon: 'list', title: t('cost.audit.empty') }));
      return;
    }
    // Virtualize: cap render at 200 rows (endpoint defaults to last 100).
    const rows = filtered.slice(0, 200).map((e) =>
      h('div', { class: 'grid grid-cols-12 gap-2 px-3 py-2 text-sm border-b border-[var(--border)] last:border-b-0 items-center' },
        h('span', { class: 'col-span-3 mono text-xs text-[var(--text-2)]' }, new Date(e.ts).toLocaleString()),
        h('span', { class: 'col-span-2' }, Badge({ text: e.stt || '—', color: 'blue' })),
        h('span', { class: 'col-span-2' }, Badge({ text: e.llm || '—', color: 'purple' })),
        h('span', { class: 'col-span-2 text-xs text-[var(--text-3)]' }, e.mode || '—'),
        h('span', { class: 'col-span-2 mono tabular-nums text-right text-[var(--text-2)]' }, fmtInt(e.latency_ms)),
        h('span', { class: 'col-span-1 mono tabular-nums text-right text-[var(--text-2)]' }, fmtInt(e.chars)),
      ));
    const header = h('div', { class: 'grid grid-cols-12 gap-2 px-3 py-2 bg-[var(--surface-2)] text-xs uppercase tracking-wide text-[var(--text-3)] font-semibold' },
      h('span', { class: 'col-span-3' }, t('cost.audit.col.time')),
      h('span', { class: 'col-span-2' }, t('cost.audit.col.stt')),
      h('span', { class: 'col-span-2' }, t('cost.audit.col.llm')),
      h('span', { class: 'col-span-2' }, t('cost.audit.col.mode')),
      h('span', { class: 'col-span-2 text-right' }, t('cost.audit.col.latency')),
      h('span', { class: 'col-span-1 text-right' }, t('cost.audit.col.chars')),
    );
    listEl.replaceChildren(header, ...rows);
  }

  const engineSel = h('select', {
    class: classes.input + ' max-w-xs',
    'aria-label': t('cost.audit.filter.engine'),
    onChange: (e) => { filterEngine = e.target.value; paint(); },
  }, ...engineOpts.map((e) =>
    h('option', { value: e, selected: e === filterEngine ? '' : null },
      e === 'all' ? t('cost.audit.range.all') : (ENGINE_LABEL[e] || e))));

  const rangeSel = h('select', {
    class: classes.input + ' max-w-xs',
    'aria-label': t('cost.audit.filter.range'),
    onChange: (e) => { filterRange = e.target.value; paint(); },
  },
    h('option', { value: '24h' }, t('cost.audit.range.24h')),
    h('option', { value: '7d', selected: '' }, t('cost.audit.range.7d')),
    h('option', { value: '30d' }, t('cost.audit.range.30d')),
    h('option', { value: 'all' }, t('cost.audit.range.all')),
  );

  const controls = h('div', { class: 'flex flex-wrap gap-3 items-end' },
    h('div', null, h('label', { class: classes.label }, t('cost.audit.filter.engine')), engineSel),
    h('div', null, h('label', { class: classes.label }, t('cost.audit.filter.range')), rangeSel),
    h('div', { class: 'ml-auto' }, countEl),
  );

  paint();
  return Card({
    title: t('cost.audit.title'),
    children: h('div', { class: 'space-y-3' }, controls, listEl),
  });
}
