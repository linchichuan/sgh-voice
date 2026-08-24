// hotkeys.js — Settings sub-tab: editable hotkeys + mode picker.
import { h, classes, Card, Badge, Button } from '../../lib/components.js';
import { t } from '../../lib/i18n.js';

const RECOMMENDED_RECORD_HOTKEY = 'right_option+right_shift';
const FN_RECORD_HOTKEY = 'fn+right_shift';
const RECOMMENDED_TRANSLATION_HOTKEY = 'fn+right_option+right_shift';

const ROWS = [
  { key: 'hotkey',            labelKey: 'settings.hotkeys.record', recommended: true, fnPreset: true },
  { key: 'translation_hotkey', labelKey: 'settings.hotkeys.translate', translationPreset: true },
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

  const presetButtons = row.recommended || row.fnPreset || row.translationPreset
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
      row.translationPreset ? Button({
        variant: 'outline',
        icon: 'languages',
        label: t('settings.hotkeys.apply.translation'),
        onClick: () => {
          input.value = RECOMMENDED_TRANSLATION_HOTKEY;
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

function translationTargets(cfg, dirty) {
  const options = [
    { code: 'zh-Hant', labelKey: 'settings.translation.language.zh' },
    { code: 'ja', labelKey: 'settings.translation.language.ja' },
    { code: 'en', labelKey: 'settings.translation.language.en' },
    { code: 'ko', labelKey: 'settings.translation.language.ko' },
  ];
  const initial = Array.isArray(cfg.translation_target_languages)
    ? cfg.translation_target_languages
    : ['ja'];
  const selected = new Set(initial.filter((code) => options.some((option) => option.code === code)));
  if (selected.size === 0) selected.add('ja');

  const rows = options.map((option) => {
    const id = `translation-target-${option.code.replace(/[^a-z0-9]/gi, '-')}`;
    const input = h('input', {
      id,
      type: 'checkbox',
      value: option.code,
      checked: selected.has(option.code) ? '' : null,
      class: 'h-5 w-5 rounded border-[var(--border)] text-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]',
    });
    input.addEventListener('change', () => {
      if (input.checked) {
        selected.add(option.code);
      } else if (selected.size === 1) {
        input.checked = true;
        return;
      } else {
        selected.delete(option.code);
      }
      const ordered = options
        .map((candidate) => candidate.code)
        .filter((code) => selected.has(code));
      dirty.set('translation_target_languages', ordered);
    });
    return h('label', {
      for: id,
      class: 'flex min-h-11 cursor-pointer items-center gap-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)]',
    }, input, h('span', {}, t(option.labelKey)));
  });

  return Card({
    title: t('settings.translation.title'),
    children: h('fieldset', { class: 'space-y-3' },
      h('legend', { class: 'sr-only' }, t('settings.translation.title')),
      h('p', { class: 'text-sm leading-6 text-[var(--text-2)]' }, t('settings.translation.desc')),
      h('div', { class: 'grid gap-2 sm:grid-cols-2' }, ...rows),
      h('p', {
        class: 'rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-950 dark:border-amber-700 dark:bg-amber-900/20 dark:text-amber-100',
        role: 'note',
      }, t('settings.translation.cost')),
    ),
  });
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
  container.appendChild(translationTargets(cfg, dirty));
}
