// latency.js — pipeline latency benchmark card (SGH Phone 教訓：沒有 runtime 證據
// 就不能判定變更生效。過去 p95 只能靠離線 scripts/event_summary.py 算，這裡把同一份
// 數字搬進 Dashboard，讓每次調參有基準線可比).
// Data source: api.getLatencySummary() → GET /api/latency_summary (dashboard.py),
// which reuses scripts/event_summary.py's load_events()/percentile() — no separate math here.

import { t } from '../../lib/i18n.js';
import { h, classes, Card } from '../../lib/components.js';

function fmtMs(ms) {
  const n = Number(ms) || 0;
  return n >= 1000 ? `${(n / 1000).toFixed(2)}s` : `${Math.round(n)}ms`;
}

function statTile(label, value) {
  return h('div', { class: classes.card + ' p-3' },
    h('div', { class: 'text-xs text-[var(--text-3)] uppercase tracking-wide' }, label),
    h('div', { class: 'mt-1 text-lg font-semibold mono tabular-nums text-[var(--text)]' }, fmtMs(value)),
  );
}

function windowBlock(label, w) {
  w = w && typeof w === 'object' ? w : {};
  const n = Number(w.sample_count) || 0;
  if (!n) {
    return h('div', { class: 'space-y-2' },
      h('div', { class: 'text-sm font-medium text-[var(--text-2)]' }, label),
      h('div', { class: 'py-6 text-center text-sm text-[var(--text-3)]' }, t('cost.latency.empty')),
    );
  }
  return h('div', { class: 'space-y-3' },
    h('div', { class: 'flex items-center justify-between' },
      h('div', { class: 'text-sm font-medium text-[var(--text-2)]' }, label),
      h('div', { class: 'text-xs text-[var(--text-3)] mono' }, t('cost.latency.samples', { n })),
    ),
    h('div', { class: 'grid grid-cols-2 sm:grid-cols-4 gap-3' },
      statTile('p50', w.pipeline_p50_ms),
      statTile('p90', w.pipeline_p90_ms),
      statTile('p95', w.pipeline_p95_ms),
      statTile('p99', w.pipeline_p99_ms),
    ),
    h('div', { class: 'flex flex-wrap gap-x-6 gap-y-1 text-sm text-[var(--text-2)]' },
      h('div', null, `${t('cost.latency.sttAvg')}: `,
        h('span', { class: 'mono tabular-nums font-medium text-[var(--text)]' }, fmtMs(w.stt_avg_ms))),
      h('div', null, `${t('cost.latency.llmAvg')}: `,
        h('span', { class: 'mono tabular-nums font-medium text-[var(--text)]' }, fmtMs(w.llm_avg_ms))),
    ),
  );
}

export function renderLatency(summary) {
  summary = summary && typeof summary === 'object' ? summary : {};
  return Card({
    title: t('cost.latency.title'),
    children: h('div', { class: 'grid grid-cols-1 md:grid-cols-2 gap-6' },
      windowBlock(t('cost.latency.window.7d'), summary['7d']),
      windowBlock(t('cost.latency.window.30d'), summary['30d']),
    ),
  });
}
