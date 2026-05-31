// row.js — single history row renderer (collapsed/expanded/edit states).
// Returns a DOM node. Callers wire onCopy/onEdit/onDelete/onSave.

import { h, classes, Badge, Button } from '../../lib/components.js';
import { t } from '../../lib/i18n.js';

function fmtTs(ts) {
  // ts is "YYYY-MM-DD HH:MM:SS" or ISO-ish. Render compact mono.
  if (!ts) return '';
  return String(ts).replace('T', ' ').slice(0, 19);
}

function fmtDuration(sec) {
  if (sec === undefined || sec === null) return '—';
  const n = Number(sec);
  if (!Number.isFinite(n)) return '—';
  if (n < 60) return `${n.toFixed(1)}s`;
  const m = Math.floor(n / 60);
  const s = Math.round(n % 60);
  return `${m}m${s.toString().padStart(2, '0')}s`;
}

/**
 * @param {object} entry
 * @param {{ expanded: boolean, editing: boolean, onToggle, onCopy, onEdit, onDelete, onSave, onCancel }} ctx
 */
export function Row(entry, ctx) {
  const ts = entry.timestamp || entry.ts || '';
  const finalText = entry.final_text || entry.text || '';
  const rawText = entry.whisper_raw || entry.raw || '';
  const app = entry.app_id || entry.app || '';
  const scene = entry.scene || '';
  const stt = entry.stt_engine || entry.stt || '';
  const llm = entry.llm_engine || entry.llm || '';

  if (ctx.editing) return EditRow(entry, ctx);

  const tsCell = h('div', { class: 'shrink-0 w-44 text-xs mono text-[var(--text-3)] pt-1' },
    fmtTs(ts),
    app ? h('div', { class: 'mt-1' }, Badge({ text: app, color: 'blue' })) : null,
  );

  const truncCls = ctx.expanded
    ? 'text-sm text-[var(--text)] whitespace-pre-wrap break-words'
    : 'text-sm text-[var(--text)] line-clamp-2 break-words';

  const middle = h('div', { class: 'flex-1 min-w-0 cursor-pointer', onClick: ctx.onToggle },
    h('div', { class: truncCls }, finalText || h('span', { class: 'text-[var(--text-3)] italic' }, '(empty)')),
    ctx.expanded ? ExpandedDetails({ rawText, entry, scene, stt, llm }) : null,
  );

  const actions = h('div', { class: 'shrink-0 flex items-start gap-1' },
    h('button', {
      type: 'button',
      class: classes.btnGhost + ' !px-2 !py-1.5',
      'aria-label': t('btn.copy'),
      title: t('btn.copy'),
      onClick: (e) => { e.stopPropagation(); ctx.onCopy(); },
    }, h('i', { 'data-lucide': 'copy', class: 'w-4 h-4' })),
    h('button', {
      type: 'button',
      class: classes.btnGhost + ' !px-2 !py-1.5',
      'aria-label': t('btn.edit'),
      title: t('btn.edit'),
      onClick: (e) => { e.stopPropagation(); ctx.onEdit(); },
    }, h('i', { 'data-lucide': 'pencil', class: 'w-4 h-4' })),
    h('button', {
      type: 'button',
      class: classes.btnGhost + ' !px-2 !py-1.5 text-[var(--danger)]',
      'aria-label': t('btn.delete'),
      title: t('btn.delete'),
      onClick: (e) => { e.stopPropagation(); ctx.onDelete(); },
    }, h('i', { 'data-lucide': 'trash-2', class: 'w-4 h-4' })),
  );

  return h('article', {
    class: 'flex gap-3 px-4 py-3 border-b border-[var(--border)] hover:bg-[var(--surface-2)] transition',
    dataset: { ts },
  }, tsCell, middle, actions);
}

function ExpandedDetails({ rawText, entry, scene, stt, llm }) {
  const meta = [];
  if (entry.duration !== undefined) meta.push([t('history.row.duration'), fmtDuration(entry.duration)]);
  if (scene) meta.push([t('history.row.scene'), scene]);
  if (stt) meta.push([t('history.row.stt'), stt]);
  if (llm) meta.push([t('history.row.llm'), llm]);

  return h('div', { class: 'mt-3 space-y-2 text-xs' },
    rawText && rawText !== (entry.final_text || '')
      ? h('div', null,
          h('div', { class: 'text-[var(--text-3)] mb-0.5' }, t('history.row.raw')),
          h('div', { class: 'mono text-[var(--text-2)] whitespace-pre-wrap break-words bg-[var(--surface-2)] rounded p-2' }, rawText),
        )
      : null,
    meta.length
      ? h('div', { class: 'flex flex-wrap gap-3 text-[var(--text-2)]' },
          ...meta.map(([k, v]) => h('span', null, h('span', { class: 'text-[var(--text-3)]' }, `${k}: `), v)),
        )
      : null,
  );
}

function EditRow(entry, ctx) {
  const ts = entry.timestamp || entry.ts || '';
  const initial = entry.final_text || entry.text || '';

  const ta = h('textarea', {
    class: classes.input + ' resize-none text-sm leading-relaxed',
    rows: '2',
    'aria-label': t('history.edit.save'),
  });
  ta.value = initial;

  const grow = () => {
    ta.style.height = 'auto';
    const max = parseFloat(getComputedStyle(ta).lineHeight) * 8 + 24;
    ta.style.height = Math.min(ta.scrollHeight, max) + 'px';
    ta.style.overflowY = ta.scrollHeight > max ? 'auto' : 'hidden';
  };
  ta.addEventListener('input', grow);
  queueMicrotask(grow);

  const tsCell = h('div', { class: 'shrink-0 w-44 text-xs mono text-[var(--text-3)] pt-1' }, fmtTs(ts));
  const middle = h('div', { class: 'flex-1 min-w-0 space-y-2' },
    ta,
    h('div', { class: 'flex gap-2' },
      Button({ variant: 'primary', icon: 'check', label: t('history.edit.save'), onClick: () => ctx.onSave(ta.value) }),
      Button({ variant: 'ghost', label: t('history.edit.cancel'), onClick: ctx.onCancel }),
    ),
  );

  return h('article', {
    class: 'flex gap-3 px-4 py-3 border-b border-[var(--border)] bg-[var(--surface-2)]',
    dataset: { ts },
  }, tsCell, middle);
}
