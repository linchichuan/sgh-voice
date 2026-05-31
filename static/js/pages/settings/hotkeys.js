// hotkeys.js — Settings sub-tab: hotkey overview + mode picker.
import { h, classes, Card, Badge } from '../../lib/components.js';
import { t } from '../../lib/i18n.js';

const ROWS = [
  { key: 'hotkey',            labelKey: 'settings.hotkeys.record' },
  { key: 'rewrite_hotkey',    labelKey: 'settings.hotkeys.rewrite' },
  { key: 'retry_hotkey',      labelKey: 'settings.hotkeys.retry' },
  { key: 'cancel_hotkey',     labelKey: 'settings.hotkeys.cancel' },
  { key: 'continuous_hotkey', labelKey: 'settings.hotkeys.continuous' },
];

function kbd(text) {
  if (!text) return h('span', { class: 'text-xs text-[var(--text-3)] italic' }, '—');
  return h('kbd', { class: 'px-2 py-1 text-xs font-mono rounded border border-[var(--border)] bg-[var(--surface-2)] text-[var(--text)]' }, text);
}

export function mountHotkeysTab(container, cfg, dirty) {
  // Mode picker
  const modeSelectId = 'hotkey_mode';
  const select = h('select', {
    id: modeSelectId,
    class: classes.input,
    'aria-label': t('settings.hotkeys.mode'),
  },
    h('option', { value: 'push_to_talk', selected: cfg.hotkey_mode === 'push_to_talk' ? '' : null }, t('settings.hotkeys.mode.ptt')),
    h('option', { value: 'toggle', selected: cfg.hotkey_mode === 'toggle' ? '' : null }, t('settings.hotkeys.mode.toggle')),
  );
  select.addEventListener('change', () => dirty.set('hotkey_mode', select.value));

  const list = h('div', { class: 'divide-y divide-[var(--border)] border border-[var(--border)] rounded-lg overflow-hidden' });
  ROWS.forEach((row) => {
    list.appendChild(h('div', { class: 'flex items-center justify-between px-4 py-3 bg-[var(--surface)]' },
      h('div', { class: 'text-sm text-[var(--text)]' }, t(row.labelKey)),
      kbd(cfg[row.key]),
    ));
  });

  const notice = h('div', {
    class: 'mt-3 p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 text-xs text-amber-900 dark:text-amber-100',
    role: 'note',
  }, t('settings.hotkeys.notice'));

  container.appendChild(Card({
    title: t('settings.tab.hotkeys'),
    children: h('div', { class: 'space-y-4' },
      h('div', { class: 'space-y-1.5' },
        h('label', { class: classes.label, for: modeSelectId }, t('settings.hotkeys.mode')),
        select,
      ),
      list,
      notice,
    ),
  }));
}
