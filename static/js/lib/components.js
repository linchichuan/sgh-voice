// components.js — shared UI primitives.
// Always return real DOM nodes. Never use innerHTML with untrusted input.

import { t } from './i18n.js';

// ---------- h() factory ----------
/**
 * Hyperscript-style DOM factory.
 * Children may be: string, number, Node, falsy (skipped), or array (flattened).
 * Special attrs: `class` or `className`, `style` (object/string), `dataset` (object),
 * `on<Event>` handlers (e.g. onClick), `ref` (function).
 */
export function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  if (attrs && typeof attrs === 'object') {
    for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === 'class' || k === 'className') {
        el.className = String(v);
      } else if (k === 'style' && typeof v === 'object') {
        Object.assign(el.style, v);
      } else if (k === 'dataset' && typeof v === 'object') {
        Object.assign(el.dataset, v);
      } else if (k === 'ref' && typeof v === 'function') {
        v(el);
      } else if (k.startsWith('on') && typeof v === 'function') {
        el.addEventListener(k.slice(2).toLowerCase(), v);
      } else if (k === 'html' && typeof v === 'string') {
        // Explicit opt-in only when caller has sanitized
        el.innerHTML = v;
      } else if (v === true) {
        el.setAttribute(k, '');
      } else {
        el.setAttribute(k, String(v));
      }
    }
  }
  appendChildren(el, children);
  return el;
}

function appendChildren(parent, children) {
  for (const c of children) {
    if (c === null || c === undefined || c === false) continue;
    if (Array.isArray(c)) { appendChildren(parent, c); continue; }
    if (c instanceof Node) { parent.appendChild(c); continue; }
    parent.appendChild(document.createTextNode(String(c)));
  }
}

// ---------- class tokens ----------
export const classes = {
  card: 'rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6',
  cardHero: 'rounded-2xl bg-gradient-to-br from-brand-blue to-brand-purple text-white p-6',
  btnPrimary: 'inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[var(--brand-blue)] hover:bg-blue-700 text-white font-medium transition focus-visible:ring-4 focus-visible:ring-blue-300 disabled:opacity-50 disabled:cursor-not-allowed',
  btnGhost: 'inline-flex items-center gap-2 px-4 py-2.5 rounded-lg hover:bg-[var(--surface-2)] text-[var(--text)] font-medium transition focus-visible:ring-4 focus-visible:ring-blue-300',
  btnDanger: 'inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[var(--danger)] hover:bg-red-700 text-white font-medium transition focus-visible:ring-4 focus-visible:ring-red-300',
  btnOutline: 'inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-[var(--border)] hover:bg-[var(--surface-2)] text-[var(--text)] font-medium transition focus-visible:ring-4 focus-visible:ring-blue-300',
  input: 'w-full px-4 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-[var(--text)] focus:ring-2 focus:ring-blue-500 focus:border-transparent',
  label: 'block text-sm font-medium text-[var(--text-2)] mb-1.5',
  badge: 'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium',
};

const BADGE_COLORS = {
  default: 'bg-[var(--surface-2)] text-[var(--text-2)]',
  blue:    'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200',
  purple:  'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-200',
  orange:  'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-200',
  green:   'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200',
  red:     'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200',
  yellow:  'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200',
};

// Helper to render a lucide icon element. lucide.createIcons() must run after mount.
function icon(name, cls = 'w-4 h-4') {
  if (!name) return null;
  return h('i', { 'data-lucide': name, class: cls });
}

// ---------- Button ----------
export function Button({ variant = 'primary', icon: ic, label, onClick, ariaLabel, type = 'button', disabled = false }) {
  const cls = variant === 'danger' ? classes.btnDanger
    : variant === 'ghost' ? classes.btnGhost
    : variant === 'outline' ? classes.btnOutline
    : classes.btnPrimary;
  return h('button', {
    type,
    class: cls,
    onClick,
    disabled,
    'aria-label': ariaLabel || (typeof label === 'string' ? label : undefined),
  }, icon(ic), label ? h('span', null, label) : null);
}

// ---------- Card ----------
export function Card({ title, children, footer, className = '' }) {
  return h('section', { class: `${classes.card} ${className}` },
    title ? h('header', { class: 'mb-4 flex items-center justify-between' },
      h('h2', { class: 'text-lg font-semibold text-[var(--text)]' }, title),
    ) : null,
    h('div', null, children),
    footer ? h('footer', { class: 'mt-4 pt-4 border-t border-[var(--border)]' }, footer) : null,
  );
}

// ---------- Stat ----------
export function Stat({ label, value, sub, trend, icon: ic, accent = 'blue' }) {
  const accentBg = {
    blue: 'bg-blue-50 text-brand-blue dark:bg-blue-900/30',
    purple: 'bg-purple-50 text-brand-purple dark:bg-purple-900/30',
    orange: 'bg-orange-50 text-brand-orange dark:bg-orange-900/30',
    green: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30',
  }[accent] || '';
  return h('div', { class: classes.card },
    h('div', { class: 'flex items-start justify-between' },
      h('div', null,
        h('div', { class: 'text-sm text-[var(--text-3)]' }, label),
        h('div', { class: 'mt-1 text-2xl font-semibold text-[var(--text)]' }, value),
        sub ? h('div', { class: 'mt-1 text-xs text-[var(--text-3)]' }, sub) : null,
      ),
      ic ? h('div', { class: `w-10 h-10 rounded-xl inline-flex items-center justify-center ${accentBg}` }, icon(ic, 'w-5 h-5')) : null,
    ),
    trend ? h('div', { class: 'mt-3 text-xs text-[var(--text-2)]' }, trend) : null,
  );
}

// ---------- Switch ----------
let switchSeq = 0;
export function Switch({ id, label, checked = false, onChange, description }) {
  const uid = id || `sw-${++switchSeq}`;
  const input = h('input', {
    type: 'checkbox',
    id: uid,
    class: 'sr-only peer',
    checked: checked ? '' : null,
    role: 'switch',
    'aria-checked': checked ? 'true' : 'false',
  });
  input.addEventListener('change', (e) => {
    input.setAttribute('aria-checked', e.target.checked ? 'true' : 'false');
    if (onChange) onChange(e.target.checked);
  });

  const knob = h('span', { class: 'inline-block w-10 h-6 rounded-full bg-[var(--surface-2)] border border-[var(--border)] relative transition peer-checked:bg-[var(--brand-blue)] peer-focus-visible:ring-4 peer-focus-visible:ring-blue-300' },
    h('span', { class: 'absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition peer-checked:translate-x-4', style: { transform: checked ? 'translateX(1rem)' : 'translateX(0)' } }),
  );
  input.addEventListener('change', (e) => {
    const dot = knob.firstElementChild;
    if (dot) dot.style.transform = e.target.checked ? 'translateX(1rem)' : 'translateX(0)';
  });

  return h('label', { class: 'flex items-start gap-3 cursor-pointer select-none', for: uid },
    input,
    knob,
    h('div', null,
      h('div', { class: 'text-sm font-medium text-[var(--text)]' }, label),
      description ? h('div', { class: 'text-xs text-[var(--text-3)] mt-0.5' }, description) : null,
    ),
  );
}

// ---------- Badge ----------
export function Badge({ text, color = 'default' }) {
  const colorCls = BADGE_COLORS[color] || BADGE_COLORS.default;
  return h('span', { class: `${classes.badge} ${colorCls}` }, text);
}

// ---------- Toast ----------
export function Toast({ message, type = 'info', duration = 3000 }) {
  const colorCls = type === 'error' ? 'border-red-300 bg-red-50 text-red-900 dark:bg-red-900/30 dark:text-red-100 dark:border-red-700'
    : type === 'success' ? 'border-emerald-300 bg-emerald-50 text-emerald-900 dark:bg-emerald-900/30 dark:text-emerald-100 dark:border-emerald-700'
    : type === 'warning' ? 'border-amber-300 bg-amber-50 text-amber-900 dark:bg-amber-900/30 dark:text-amber-100 dark:border-amber-700'
    : 'border-[var(--border)] bg-[var(--surface)] text-[var(--text)]';
  const ic = type === 'error' ? 'alert-circle'
    : type === 'success' ? 'check-circle-2'
    : type === 'warning' ? 'alert-triangle'
    : 'info';

  const node = h('div', {
    role: 'status',
    class: `flex items-start gap-2 px-4 py-3 rounded-lg border shadow-lg max-w-sm ${colorCls}`,
  }, icon(ic, 'w-4 h-4 mt-0.5 shrink-0'), h('div', { class: 'text-sm' }, message));

  const root = document.getElementById('toast-root');
  if (root) {
    root.appendChild(node);
    if (window.lucide) window.lucide.createIcons();
    if (duration > 0) {
      setTimeout(() => {
        node.style.transition = 'opacity 0.2s';
        node.style.opacity = '0';
        setTimeout(() => node.remove(), 220);
      }, duration);
    }
  }
  return node;
}

// ---------- KeyInput ----------
let keySeq = 0;
export function KeyInput({ id, label, value = '', placeholder = '', onTest, onSave, helpText }) {
  const uid = id || `key-${++keySeq}`;
  let revealed = false;

  const input = h('input', {
    id: uid,
    type: 'password',
    class: classes.input + ' pr-24 mono text-sm',
    value,
    placeholder,
    autocomplete: 'off',
    spellcheck: 'false',
  });

  const revealBtn = h('button', {
    type: 'button',
    class: 'absolute right-2 top-1/2 -translate-y-1/2 px-2 py-1 text-xs text-[var(--text-2)] hover:text-[var(--text)]',
    'aria-label': 'Toggle visibility',
    onClick: () => {
      revealed = !revealed;
      input.type = revealed ? 'text' : 'password';
      revealBtn.replaceChildren(icon(revealed ? 'eye-off' : 'eye', 'w-4 h-4'));
      if (window.lucide) window.lucide.createIcons();
    },
  }, icon('eye', 'w-4 h-4'));

  const wrap = h('div', { class: 'space-y-1.5' },
    h('label', { class: classes.label, for: uid }, label),
    h('div', { class: 'relative' }, input, revealBtn),
    helpText ? h('div', { class: 'text-xs text-[var(--text-3)]' }, helpText) : null,
    h('div', { class: 'flex gap-2 pt-1' },
      onTest ? Button({ variant: 'outline', label: t('btn.test'), icon: 'zap', onClick: () => onTest(input.value) }) : null,
      onSave ? Button({ variant: 'primary', label: t('btn.save'), icon: 'check', onClick: () => onSave(input.value) }) : null,
    ),
  );
  return wrap;
}

// ---------- Tabs ----------
export function Tabs({ tabs, active, onChange }) {
  const list = h('div', { class: 'flex gap-1 border-b border-[var(--border)] mb-4', role: 'tablist' });
  tabs.forEach((tab) => {
    const isActive = tab.id === active;
    const btn = h('button', {
      type: 'button',
      role: 'tab',
      'aria-selected': isActive ? 'true' : 'false',
      class: `px-4 py-2 text-sm font-medium border-b-2 transition ${isActive ? 'border-[var(--brand-blue)] text-[var(--brand-blue)]' : 'border-transparent text-[var(--text-3)] hover:text-[var(--text)]'}`,
      onClick: () => { if (onChange) onChange(tab.id); },
    }, tab.label);
    list.appendChild(btn);
  });
  return list;
}

// ---------- EmptyState ----------
export function EmptyState({ icon: ic = 'inbox', title, message, action }) {
  return h('div', { class: 'flex flex-col items-center justify-center py-16 text-center' },
    h('div', { class: 'w-14 h-14 rounded-2xl bg-[var(--surface-2)] flex items-center justify-center text-[var(--text-3)] mb-4' }, icon(ic, 'w-7 h-7')),
    h('h3', { class: 'text-base font-semibold text-[var(--text)] mb-1' }, title || t('empty.generic')),
    message ? h('p', { class: 'text-sm text-[var(--text-3)] max-w-sm mb-4' }, message) : null,
    action || null,
  );
}

// ---------- ConfirmDialog ----------
export function ConfirmDialog({ title, message, confirmText, cancelText, onConfirm, danger = false }) {
  const backdrop = h('div', {
    class: 'fixed inset-0 z-[90] bg-black/40 flex items-center justify-center p-4',
    role: 'dialog',
    'aria-modal': 'true',
    'aria-labelledby': 'confirm-title',
  });

  const close = () => backdrop.remove();

  const dialog = h('div', { class: 'bg-[var(--surface)] rounded-2xl shadow-2xl max-w-md w-full p-6 border border-[var(--border)]' },
    h('h2', { id: 'confirm-title', class: 'text-lg font-semibold text-[var(--text)] mb-2' }, title),
    h('p', { class: 'text-sm text-[var(--text-2)] mb-6' }, message),
    h('div', { class: 'flex justify-end gap-2' },
      Button({ variant: 'ghost', label: cancelText || t('btn.cancel'), onClick: close }),
      Button({
        variant: danger ? 'danger' : 'primary',
        label: confirmText || t('btn.confirm'),
        onClick: async () => {
          try { if (onConfirm) await onConfirm(); } finally { close(); }
        },
      }),
    ),
  );
  backdrop.appendChild(dialog);
  backdrop.addEventListener('click', (e) => { if (e.target === backdrop) close(); });
  document.body.appendChild(backdrop);
  if (window.lucide) window.lucide.createIcons();
  // ESC to close
  const onKey = (e) => { if (e.key === 'Escape') { close(); document.removeEventListener('keydown', onKey); } };
  document.addEventListener('keydown', onKey);
  return backdrop;
}
