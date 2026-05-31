// pages/dictionary/util.js — shared helpers for dictionary sub-tabs.

import { h, classes, Button, EmptyState, ConfirmDialog, Toast } from '../../lib/components.js';
import { t } from '../../lib/i18n.js';

/** Section wrapper: card body + heading + optional header-right slot. */
export function Section({ title, headerRight, children }) {
  return h('section', { class: classes.card },
    h('header', { class: 'mb-4 flex items-center justify-between gap-3 flex-wrap' },
      h('h2', { class: 'text-base font-semibold text-[var(--text)]' }, title),
      headerRight ? h('div', { class: 'flex items-center gap-2' }, headerRight) : null,
    ),
    h('div', null, children),
  );
}

/** Build a labelled text input. Label is visually rendered + associated via for/id. */
let _seq = 0;
export function LabeledInput({ label, placeholder = '', value = '', type = 'text', srOnly = false }) {
  const uid = `dict-in-${++_seq}`;
  const input = h('input', {
    id: uid,
    type,
    class: classes.input,
    placeholder,
    value,
    autocomplete: 'off',
    spellcheck: 'false',
  });
  const lab = h('label', {
    for: uid,
    class: srOnly ? 'sr-only' : classes.label,
  }, label);
  const wrap = h('div', { class: 'flex-1 min-w-[8rem]' }, lab, input);
  return { wrap, input };
}

/** Confirm before removing a rule. */
export function confirmRemove({ title, message, onConfirm }) {
  ConfirmDialog({
    title,
    message,
    confirmText: t('btn.delete'),
    danger: true,
    onConfirm,
  });
}

/** Filter a string list by a query (case-insensitive). */
export function filterStrings(list, query) {
  const q = (query || '').trim().toLowerCase();
  if (!q) return list.slice();
  return list.filter((s) => String(s).toLowerCase().includes(q));
}

/** Filter an object {k:v} → array of [k,v] by query against either side. */
export function filterMapEntries(obj, query) {
  const q = (query || '').trim().toLowerCase();
  const entries = Object.entries(obj || {});
  if (!q) return entries;
  return entries.filter(([k, v]) =>
    String(k).toLowerCase().includes(q) ||
    String(v).toLowerCase().includes(q),
  );
}

/** Table renderer for [wrong → right] pairs with row-delete. */
export function PairTable({ entries, leftCol, rightCol, onDelete, emptyTitle, emptyMessage }) {
  if (!entries.length) {
    return EmptyState({ icon: 'book-open', title: emptyTitle, message: emptyMessage });
  }
  const head = h('thead', null,
    h('tr', { class: 'text-left text-xs uppercase tracking-wide text-[var(--text-3)]' },
      h('th', { class: 'py-2 pr-4 font-medium' }, leftCol),
      h('th', { class: 'py-2 pr-4 font-medium' }, rightCol),
      h('th', { class: 'py-2 pr-0 font-medium text-right' }, t('dict.col.actions')),
    ),
  );
  const body = h('tbody', null);
  entries.forEach(([k, v]) => {
    const row = h('tr', { class: 'border-t border-[var(--border)]' },
      h('td', { class: 'py-2 pr-4 mono text-sm text-[var(--text)] break-all' }, String(k)),
      h('td', { class: 'py-2 pr-4 mono text-sm text-[var(--text-2)] break-all' }, String(v)),
      h('td', { class: 'py-2 pr-0 text-right' },
        Button({
          variant: 'ghost',
          icon: 'trash-2',
          ariaLabel: t('btn.delete'),
          onClick: () => onDelete(k),
        }),
      ),
    );
    body.appendChild(row);
  });
  return h('div', { class: 'overflow-x-auto' },
    h('table', { class: 'w-full text-sm' }, head, body),
  );
}

/** Standard success toast. */
export function toastOk(msg = t('toast.saved')) { Toast({ message: msg, type: 'success' }); }
export function toastErr(msg) { Toast({ message: msg || t('toast.error'), type: 'error' }); }
