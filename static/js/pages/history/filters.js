// filters.js — top bar: search, scene filter, app filter, export menu, clear-all.
// Returns DOM node + reactive accessors via callbacks.

import { h, classes, Button, ConfirmDialog } from '../../lib/components.js';
import { t } from '../../lib/i18n.js';
import { exportHistoryUrl, clearHistory } from '../../lib/api.js';

function Select({ id, value, options, onChange, ariaLabel }) {
  const sel = h('select', {
    id,
    class: classes.input + ' !py-2 text-sm pr-8',
    'aria-label': ariaLabel,
  });
  options.forEach(([v, label]) => {
    const opt = document.createElement('option');
    opt.value = v;
    opt.textContent = label;
    if (v === value) opt.selected = true;
    sel.appendChild(opt);
  });
  sel.addEventListener('change', (e) => onChange(e.target.value));
  return sel;
}

/**
 * @param {{ search, scene, app, scenes: string[], apps: string[],
 *   onSearchChange, onSceneChange, onAppChange, onCleared, count }} opts
 */
export function FiltersBar(opts) {
  const search = h('input', {
    type: 'search',
    class: classes.input + ' !py-2 text-sm',
    placeholder: t('history.search.placeholder'),
    value: opts.search || '',
    'aria-label': t('history.search.placeholder'),
  });
  let debounce;
  search.addEventListener('input', (e) => {
    clearTimeout(debounce);
    const v = e.target.value;
    debounce = setTimeout(() => opts.onSearchChange(v), 250);
  });

  const sceneOpts = [['', t('history.filter.scene.all')], ...opts.scenes.map((s) => [s, s])];
  const appOpts = [['', t('history.filter.app.all')], ...opts.apps.map((a) => [a, a])];

  const sceneSel = Select({
    id: 'history-scene',
    value: opts.scene || '',
    options: sceneOpts,
    onChange: opts.onSceneChange,
    ariaLabel: t('history.filter.scene.all'),
  });
  const appSel = Select({
    id: 'history-app',
    value: opts.app || '',
    options: appOpts,
    onChange: opts.onAppChange,
    ariaLabel: t('history.filter.app.all'),
  });

  // Export menu — details/summary native disclosure (keyboard accessible)
  const exportMenu = h('details', { class: 'relative' },
    h('summary', {
      class: classes.btnOutline + ' cursor-pointer list-none',
      'aria-label': t('history.export.menu'),
    },
      h('i', { 'data-lucide': 'download', class: 'w-4 h-4' }),
      h('span', null, t('history.export.menu')),
    ),
    h('div', { class: 'absolute right-0 mt-1 w-48 rounded-lg border border-[var(--border)] bg-[var(--surface)] shadow-lg z-20 p-1' },
      h('a', {
        href: exportHistoryUrl('csv'),
        download: '',
        class: 'block px-3 py-2 text-sm rounded hover:bg-[var(--surface-2)] text-[var(--text)]',
      }, t('history.export.csv')),
      h('a', {
        href: exportHistoryUrl('txt'),
        download: '',
        class: 'block px-3 py-2 text-sm rounded hover:bg-[var(--surface-2)] text-[var(--text)]',
      }, t('history.export.txt')),
    ),
  );

  const clearBtn = Button({
    variant: 'ghost',
    icon: 'trash-2',
    label: t('history.clear.all'),
    ariaLabel: t('history.clear.all'),
    onClick: () => {
      ConfirmDialog({
        title: t('history.clear.confirm.title'),
        message: t('history.clear.confirm.message'),
        confirmText: t('history.clear.all'),
        danger: true,
        onConfirm: async () => {
          await clearHistory();
          opts.onCleared();
        },
      });
    },
  });

  const countEl = h('div', { class: 'text-xs text-[var(--text-3)] ml-auto' },
    t('history.count', { n: opts.count ?? 0 }),
  );

  return {
    node: h('div', { class: 'flex flex-wrap items-center gap-2 px-4 py-3 border-b border-[var(--border)] bg-[var(--surface)]' },
      h('div', { class: 'flex-1 min-w-[16rem] max-w-md' }, search),
      sceneSel,
      appSel,
      exportMenu,
      clearBtn,
      countEl,
    ),
    setCount(n) { countEl.textContent = t('history.count', { n }); },
  };
}
