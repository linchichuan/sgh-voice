// hotkeys.js — Settings sub-tab: editable hotkeys + mode picker.
import { h, classes, Card, Badge, Button } from '../../lib/components.js';
import { t } from '../../lib/i18n.js';

const RECOMMENDED_RECORD_HOTKEY = 'right_option+right_shift';
const FN_RECORD_HOTKEY = 'fn+right_shift';

const ROWS = [
  { key: 'hotkey',            labelKey: 'settings.hotkeys.record', recommended: true, fnPreset: true },
  { key: 'rewrite_hotkey',    labelKey: 'settings.hotkeys.rewrite', optional: true },
  { key: 'retry_hotkey',      labelKey: 'settings.hotkeys.retry', optional: true },
  { key: 'cancel_hotkey',     labelKey: 'settings.hotkeys.cancel', optional: true },
  { key: 'continuous_hotkey', labelKey: 'settings.hotkeys.continuous', optional: true },
];

function usesRightCommand(value) {
  const keys = String(value || '').toLowerCase().replaceAll('+', ' ').trim().split(/\s+/);
  return keys.includes('right_cmd') || keys.includes('right_command');
}

function hotkeyRow(row, cfg, dirty, syntaxHintId) {
  const inputId = `hotkey-input-${row.key}`;
  const conflictId = `${inputId}-conflict`;
  const input = h('input', {
    id: inputId,
    name: row.key,
    type: 'text',
    class: `${classes.input} font-mono text-sm`,
    value: cfg[row.key] || '',
    placeholder: t(row.optional ? 'settings.hotkeys.placeholder.optional' : 'settings.hotkeys.placeholder'),
    autocomplete: 'off',
    autocapitalize: 'none',
    spellcheck: 'false',
    'aria-describedby': `${syntaxHintId} ${conflictId}`,
  });

  const conflict = h('div', {
    id: conflictId,
    class: 'mt-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-950 dark:border-amber-700 dark:bg-amber-900/20 dark:text-amber-100',
    role: 'alert',
    'aria-live': 'polite',
  }, t('settings.hotkeys.conflict.right_cmd'));

  const syncValue = () => {
    dirty.set(row.key, input.value.trim());
    conflict.hidden = !usesRightCommand(input.value);
  };
  input.addEventListener('input', syncValue);
  conflict.hidden = !usesRightCommand(input.value);

  const presetButtons = row.recommended || row.fnPreset
    ? h('div', { class: 'flex flex-col gap-2 sm:flex-row sm:justify-end' },
      row.recommended ? Button({
        variant: 'outline',
        icon: 'keyboard',
        label: t('settings.hotkeys.apply.recommended'),
        onClick: () => {
          input.value = RECOMMENDED_RECORD_HOTKEY;
          syncValue();
          input.focus();
        },
      }) : null,
      row.fnPreset ? Button({
        variant: 'outline',
        icon: 'globe-2',
        label: t('settings.hotkeys.apply.fn'),
        onClick: () => {
          input.value = FN_RECORD_HOTKEY;
          syncValue();
          input.focus();
        },
      }) : null,
    )
    : null;

  const field = h('div', { class: 'min-w-0' },
    h('div', { class: 'space-y-2' },
      input,
      presetButtons,
    ),
    conflict,
  );

  return h('div', {
    class: 'grid gap-3 bg-[var(--surface)] px-4 py-4 md:grid-cols-[minmax(10rem,0.7fr)_minmax(0,1.3fr)] md:items-start',
  },
    h('label', { class: 'flex flex-wrap items-center gap-2 pt-2 text-sm font-medium text-[var(--text)]', for: inputId },
      t(row.labelKey),
      row.recommended ? Badge({ text: t('settings.hotkeys.recommended'), color: 'green' }) : null,
      row.optional ? Badge({ text: t('settings.hotkeys.optional') }) : null,
    ),
    field,
  );
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

  const syntaxHintId = 'hotkey-syntax-hint';
  const syntaxHint = h('p', {
    id: syntaxHintId,
    class: 'text-xs leading-5 text-[var(--text-3)]',
  }, t('settings.hotkeys.syntax'));
  const fnHint = h('p', {
    class: 'text-xs leading-5 text-[var(--text-3)]',
    role: 'note',
  }, t('settings.hotkeys.fn.note'));

  const list = h('div', { class: 'divide-y divide-[var(--border)] overflow-hidden rounded-lg border border-[var(--border)]' });
  ROWS.forEach((row) => {
    list.appendChild(hotkeyRow(row, cfg, dirty, syntaxHintId));
  });

  const notice = h('div', {
    class: 'mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-3 text-xs text-[var(--text-2)]',
    role: 'note',
  }, Badge({ text: t('settings.hotkeys.immediate'), color: 'green' }), t('settings.hotkeys.notice'));

  container.appendChild(Card({
    title: t('settings.tab.hotkeys'),
    children: h('div', { class: 'space-y-4' },
      h('div', { class: 'space-y-1.5' },
        h('label', { class: classes.label, for: modeSelectId }, t('settings.hotkeys.mode')),
        select,
      ),
      syntaxHint,
      fnHint,
      list,
      notice,
    ),
  }));
}
