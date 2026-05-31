// pages/dashboard.js — Bento overview (SPEC §4.1).
// Owns hash route '#/'. Renders Record CTA, Today hero, 4 stat cards,
// 7-day bar chart, personalization progress, last 5 transcriptions.

import * as api from '../lib/api.js';
import { t } from '../lib/i18n.js';
import { h, classes, Stat, Toast } from '../lib/components.js';

const REDUCE_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// ---------- Formatters ----------
const fmtNumber = (n) => new Intl.NumberFormat().format(Math.round(Number(n) || 0));

function fmtMinutes(seconds) {
  const s = Math.max(0, Number(seconds) || 0);
  if (s < 60) return `${Math.round(s)}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const hr = Math.floor(m / 60);
  return `${hr}h ${m % 60}m`;
}

const fmtCostJpy = (n) => `¥${new Intl.NumberFormat().format(Math.round(Math.max(0, Number(n) || 0)))}`;

function relTime(iso) {
  if (!iso) return t('dash.cta.last_never');
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return t('dash.cta.last_never');
  const diff = Math.max(0, (Date.now() - then) / 1000);
  if (diff < 60) return t('dash.time.now');
  if (diff < 3600) return t('dash.time.minutes', { n: Math.floor(diff / 60) });
  if (diff < 86400) return t('dash.time.hours', { n: Math.floor(diff / 3600) });
  return t('dash.time.days', { n: Math.floor(diff / 86400) });
}

// Approx 2026 prices (USD/1M tokens; whisper USD/min). Yen rate ~155.
function estimateMonthCostJpy(m) {
  if (!m || typeof m !== 'object') return 0;
  const v = (k) => Number(m[k]) || 0;
  const usd =
    v('anthropic_input_tokens')   / 1e6 * 1.0 + v('anthropic_output_tokens')   / 1e6 * 5.0 +
    v('openai_input_tokens')      / 1e6 * 2.5 + v('openai_output_tokens')      / 1e6 * 10.0 +
    v('groq_input_tokens')        / 1e6 * 0.3 + v('groq_output_tokens')        / 1e6 * 0.6 +
    v('openrouter_input_tokens')  / 1e6 * 1.0 + v('openrouter_output_tokens')  / 1e6 * 3.0 +
    v('openai_whisper_seconds') / 60 * 0.006 + v('groq_whisper_seconds') / 60 * 0.001;
  return usd * 155;
}

const monthKey = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`; };
const todayKey = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };

// ---------- Hero (Today) ----------
function HeroToday(stats) {
  const today = ((stats && stats.daily) || {})[todayKey()] || {};
  const chars = Number(today.chars) || 0;
  const dictations = Number(today.dictations) || 0;
  const audioSec = Number(today.audio_seconds) || 0;
  return h('section', {
    class: 'col-span-12 md:col-span-7 relative overflow-hidden rounded-2xl bg-gradient-to-br from-brand-blue to-brand-purple text-white p-6 min-h-[180px]',
    'aria-label': t('dash.hero.title'),
  },
    h('i', {
      'data-lucide': 'zap',
      class: 'absolute -right-4 -bottom-4 w-40 h-40 text-white/10 pointer-events-none',
      'aria-hidden': 'true',
    }),
    h('div', { class: 'relative' },
      h('div', { class: 'text-sm font-medium text-white/80' }, t('dash.hero.title')),
      h('div', { class: 'mt-2 text-5xl font-semibold tabular-nums tracking-tight mono' }, fmtNumber(chars)),
      h('div', { class: 'mt-2 text-sm text-white/90' },
        chars === 0
          ? t('dash.hero.empty')
          : t('dash.hero.sub', { dictations: fmtNumber(dictations), audio: fmtMinutes(audioSec) }),
      ),
    ),
  );
}

// ---------- Record CTA ----------
const REC_VARIANTS = {
  recording:  { lblKey: 'dash.cta.stop',       cls: 'bg-[var(--danger)] hover:bg-red-700 focus-visible:ring-red-300',   ic: 'square' },
  processing: { lblKey: 'dash.cta.processing', cls: 'bg-amber-500 hover:bg-amber-600 focus-visible:ring-amber-300',     ic: 'loader' },
  idle:       { lblKey: 'dash.cta.start',      cls: 'bg-[var(--brand-blue)] hover:bg-blue-700 focus-visible:ring-blue-300', ic: 'mic' },
};

function RecordCta({ initialState, lastIso, onToggle }) {
  const stateLabel = h('div', { class: 'text-xs uppercase tracking-wider text-[var(--text-3)]' }, t('dash.cta.title'));
  const button = h('button', { type: 'button', class: '', 'aria-label': '', onClick: () => onToggle && onToggle() });
  const hint = h('div', { class: 'text-sm text-[var(--text-2)]' }, t('dash.cta.hint'));
  const last = h('div', { class: 'text-xs text-[var(--text-3)] mono' });

  const setLastIso = (iso) => { last.textContent = t('dash.cta.last', { time: relTime(iso) }); };

  function setState(state) {
    const v = REC_VARIANTS[state] || REC_VARIANTS.idle;
    const label = t(v.lblKey);
    button.className = `w-28 h-28 rounded-full text-white shadow-lg transition flex items-center justify-center focus-visible:ring-4 disabled:opacity-60 disabled:cursor-not-allowed ${v.cls}` +
      (state === 'recording' && !REDUCE_MOTION ? ' animate-pulse' : '');
    button.setAttribute('aria-label', `${label} — ${t('dash.cta.hint')}`);
    button.disabled = state === 'processing';
    button.replaceChildren(h('i', { 'data-lucide': v.ic, class: 'w-10 h-10' }));
    stateLabel.textContent = label;
    if (window.lucide) window.lucide.createIcons();
  }

  setState(initialState || 'idle');
  setLastIso(lastIso);

  const node = h('section', {
    class: 'col-span-12 md:col-span-5 ' + classes.card + ' flex flex-col items-center justify-center gap-4 text-center min-h-[180px]',
  }, stateLabel, button, hint, last);
  node.__setState = setState;
  node.__setLastIso = setLastIso;
  return node;
}

// ---------- Stats grid ----------
function StatsRow(stats, monthJpy) {
  const totalChars = Number((stats && stats.total_characters) || 0);
  const savedSec   = Number((stats && stats.total_seconds_saved) || 0);
  const audioSec   = Number((stats && stats.total_audio_seconds) || 0);
  return h('div', { class: 'col-span-12 grid grid-cols-2 lg:grid-cols-4 gap-4' },
    h('div', null, Stat({ label: t('dash.stat.chars'), value: fmtNumber(totalChars), icon: 'type',   accent: 'blue'   })),
    h('div', null, Stat({ label: t('dash.stat.saved'), value: fmtMinutes(savedSec),  icon: 'clock',  accent: 'green'  })),
    h('div', null, Stat({ label: t('dash.stat.audio'), value: fmtMinutes(audioSec),  icon: 'mic',    accent: 'purple' })),
    h('div', null, Stat({ label: t('dash.stat.cost'),  value: fmtCostJpy(monthJpy),  sub: t('dash.stat.cost_sub'), icon: 'wallet', accent: 'orange' })),
  );
}

// ---------- 7-day Bar Chart ----------
const NS = 'http://www.w3.org/2000/svg';
function svgEl(tag, attrs) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v);
  return el;
}

function BarChart7d(stats) {
  const daily = (stats && stats.daily) || {};
  const days = [], labels = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    days.push(Number((daily[key] || {}).chars) || 0);
    labels.push(`${d.getMonth() + 1}/${d.getDate()}`);
  }
  const max = Math.max(1, ...days);
  const W = 560, H = 200, PAD = 28, BW = (W - PAD * 2) / 7;

  const svg = svgEl('svg', {
    viewBox: `0 0 ${W} ${H}`, class: 'w-full h-48', role: 'img',
    'aria-label': t('dash.chart.title'),
  });
  svg.appendChild(svgEl('line', {
    x1: PAD, x2: W - PAD, y1: H - PAD, y2: H - PAD,
    stroke: 'currentColor', 'stroke-opacity': '0.15',
  }));

  days.forEach((v, i) => {
    const hBar = ((H - PAD * 2) * v) / max;
    const x = PAD + i * BW + BW * 0.18;
    const w = BW * 0.64;
    const yFinal = H - PAD - hBar;
    const rect = svgEl('rect', {
      x, width: w, rx: '4',
      fill: i === 6 ? 'var(--brand-purple)' : 'var(--brand-blue)',
      opacity: v === 0 ? '0.25' : '1',
      y: REDUCE_MOTION ? yFinal : H - PAD,
      height: REDUCE_MOTION ? hBar : 0,
    });
    if (!REDUCE_MOTION) {
      requestAnimationFrame(() => {
        rect.style.transition = `y 600ms cubic-bezier(.2,.7,.2,1) ${i * 60}ms, height 600ms cubic-bezier(.2,.7,.2,1) ${i * 60}ms`;
        rect.setAttribute('y', yFinal);
        rect.setAttribute('height', hBar);
      });
    }
    svg.appendChild(rect);
    if (v > 0) {
      const valTxt = svgEl('text', {
        x: x + w / 2, y: yFinal - 6, 'text-anchor': 'middle',
        'font-size': '11', fill: 'currentColor', opacity: '0.7',
      });
      valTxt.textContent = fmtNumber(v);
      svg.appendChild(valTxt);
    }
    const lbl = svgEl('text', {
      x: x + w / 2, y: H - PAD + 16, 'text-anchor': 'middle',
      'font-size': '11', fill: 'currentColor', opacity: '0.55',
    });
    lbl.textContent = labels[i];
    svg.appendChild(lbl);
  });

  return h('section', { class: 'col-span-12 lg:col-span-7 ' + classes.card },
    h('header', { class: 'mb-4 flex items-center justify-between' },
      h('h2', { class: 'text-lg font-semibold text-[var(--text)]' }, t('dash.chart.title')),
      h('span', { class: 'text-xs text-[var(--text-3)] mono' }, t('dash.chart.unit')),
    ),
    days.every((v) => v === 0)
      ? h('div', { class: 'py-12 text-center text-sm text-[var(--text-3)]' }, t('dash.chart.empty'))
      : svg,
  );
}

// ---------- Personalization ----------
function PersonalizationCard(p) {
  p = p || {};
  const rows = [
    { label: t('dash.personalization.dict'),   score: p.dict_score   || 0, max: p.dict_max   || 25, color: 'bg-brand-blue' },
    { label: t('dash.personalization.vocab'),  score: p.vocab_score  || 0, max: p.vocab_max  || 20, color: 'bg-brand-purple' },
    { label: t('dash.personalization.usage'),  score: p.usage_score  || 0, max: p.usage_max  || 25, color: 'bg-brand-orange' },
    { label: t('dash.personalization.active'), score: p.active_score || 0, max: p.active_max || 30, color: 'bg-emerald-500' },
  ];
  const total = Math.max(0, Math.min(100, Number(p.total) || 0));
  return h('section', { class: 'col-span-12 lg:col-span-5 ' + classes.card },
    h('header', { class: 'mb-4 flex items-end justify-between' },
      h('h2', { class: 'text-lg font-semibold text-[var(--text)]' }, t('dash.personalization.title')),
      h('div', { class: 'text-2xl font-semibold mono tabular-nums text-[var(--text)]' }, `${total} / 100`),
    ),
    h('div', { class: 'space-y-3' },
      rows.map((r) => {
        const pct = r.max > 0 ? Math.min(100, Math.round((r.score / r.max) * 100)) : 0;
        return h('div', { class: 'space-y-1' },
          h('div', { class: 'flex items-center justify-between text-xs text-[var(--text-2)]' },
            h('span', null, r.label),
            h('span', { class: 'mono' }, `${r.score} / ${r.max}`),
          ),
          h('div', { class: 'h-2 rounded-full overflow-hidden bg-[var(--surface-2)]' },
            h('div', {
              class: `h-full ${r.color} ${REDUCE_MOTION ? '' : 'transition-all duration-700 ease-out'}`,
              style: { width: REDUCE_MOTION ? `${pct}%` : '0%' },
              ref: (el) => {
                if (REDUCE_MOTION) return;
                requestAnimationFrame(() => { el.style.width = `${pct}%`; });
              },
            }),
          ),
        );
      }),
    ),
  );
}

// ---------- Recent transcriptions ----------
async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text || '');
    Toast({ message: t('toast.copied'), type: 'success' });
  } catch { Toast({ message: t('toast.error'), type: 'error' }); }
}

function RecentList(items) {
  const head = h('header', { class: 'mb-2 flex items-center justify-between' },
    h('h2', { class: 'text-lg font-semibold text-[var(--text)]' }, t('dash.recent.title')),
    h('a', { href: '#/history', class: 'text-sm text-[var(--brand-blue)] hover:underline rounded focus-visible:ring-4 focus-visible:ring-blue-300' }, t('nav.history')),
  );
  if (!items || items.length === 0) {
    return h('section', { class: 'col-span-12 ' + classes.card }, head,
      h('div', { class: 'py-10 text-center text-sm text-[var(--text-3)]' }, t('dash.recent.empty')));
  }
  const rows = items.slice(-5).reverse().map((it) => {
    const text = (it && (it.final_text || it.text)) || '';
    return h('li', { class: 'flex items-start gap-3 py-3 border-t border-[var(--border)] first:border-t-0' },
      h('div', { class: 'flex-1 min-w-0' },
        h('p', { class: 'text-sm text-[var(--text)] line-clamp-2 break-words' }, text || '—'),
        h('div', { class: 'mt-1 text-xs text-[var(--text-3)] mono' }, relTime(it && it.timestamp)),
      ),
      h('button', {
        type: 'button',
        class: 'shrink-0 inline-flex items-center justify-center w-9 h-9 rounded-lg hover:bg-[var(--surface-2)] text-[var(--text-2)] hover:text-[var(--text)] transition focus-visible:ring-4 focus-visible:ring-blue-300',
        'aria-label': t('btn.copy'),
        onClick: () => copyText(text),
      }, h('i', { 'data-lucide': 'copy', class: 'w-4 h-4' })),
    );
  });
  return h('section', { class: 'col-span-12 ' + classes.card }, head, h('ul', null, rows));
}

// ---------- Mount ----------
export default async function mount(slot) {
  const grid = h('div', { class: 'grid grid-cols-12 gap-4 p-6 max-w-7xl mx-auto' });
  slot.appendChild(grid);

  const [statsRes, recRes, histRes] = await Promise.allSettled([
    api.getStats(),
    api.getRecordingStatus(),
    api.getHistory({ n: 5 }),
  ]);

  const statsPayload   = statsRes.status === 'fulfilled' ? (statsRes.value || {}) : {};
  const stats          = statsPayload.stats || {};
  const personalization = statsPayload.personalization || {};
  const usageMonth     = (stats.usage && stats.usage[monthKey()]) || null;
  const monthJpy       = estimateMonthCostJpy(usageMonth);

  const initialRecState = (recRes.status === 'fulfilled' && recRes.value && recRes.value.state) || 'idle';
  const history        = histRes.status === 'fulfilled' && Array.isArray(histRes.value) ? histRes.value : [];
  const lastIso        = history.length ? (history[history.length - 1].timestamp || null) : null;

  let currentState = initialRecState;
  let cta;

  const onToggle = async () => {
    try {
      if (currentState === 'recording') {
        cta.__setState('processing');
        currentState = 'processing';
        await api.stopRecording();
      } else if (currentState === 'idle') {
        cta.__setState('recording');
        currentState = 'recording';
        await api.startRecording();
      }
    } catch (e) {
      Toast({ message: e.message || t('toast.error'), type: 'error' });
      // Revert UI on failure
      try {
        const s = await api.getRecordingStatus();
        currentState = (s && s.state) || 'idle';
        cta.__setState(currentState);
      } catch { /* silent */ }
    }
  };

  cta = RecordCta({ initialState: initialRecState, lastIso, onToggle });

  grid.appendChild(cta);
  grid.appendChild(HeroToday(stats));
  grid.appendChild(StatsRow(stats, monthJpy));
  grid.appendChild(BarChart7d(stats));
  grid.appendChild(PersonalizationCard(personalization));
  grid.appendChild(RecentList(history));

  // Sync CTA with global recording state.
  const localPoll = setInterval(async () => {
    if (!document.body.contains(grid)) { clearInterval(localPoll); return; }
    try {
      const s = await api.getRecordingStatus();
      const next = (s && s.state) || 'idle';
      if (next !== currentState) {
        currentState = next;
        cta.__setState(next);
      }
    } catch { /* silent */ }
  }, 1500);

  if (window.lucide) window.lucide.createIcons();
}
