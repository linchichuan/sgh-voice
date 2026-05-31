// api-keys.js — Settings sub-tab: API keys.
// Each key is rendered via KeyInput. Empty input on save = "unchanged" — we never round-trip masked values.

import { h, classes, Button, Card, Toast } from '../../lib/components.js';
import { t } from '../../lib/i18n.js';
import * as api from '../../lib/api.js';

// Engines we test against /api/test-llm. Whisper key (openai) and elevenlabs tested as raw LLM call too.
const KEYS = [
  { field: 'groq_api_key',       label: 'settings.key.groq',       engine: 'groq',       model: 'groq_model' },
  { field: 'openai_api_key',     label: 'settings.key.openai',     engine: 'openai',     model: 'openai_model' },
  { field: 'anthropic_api_key',  label: 'settings.key.anthropic',  engine: 'claude',     model: 'claude_model' },
  { field: 'openrouter_api_key', label: 'settings.key.openrouter', engine: 'openrouter', model: 'openrouter_model' },
  { field: 'elevenlabs_api_key', label: 'settings.key.elevenlabs', engine: null,         model: null },
];

function isMasked(v) {
  return typeof v === 'string' && /^[•*]{2,}/.test(v.trim());
}

function makeKeyRow(spec, cfg, dirty) {
  const inputId = `apikey-${spec.field}`;
  const has = !!cfg[spec.field];
  // Backend masks present keys as "sk-...xxxx" or similar.
  // Show user a clear placeholder; never inject masked value into the textbox.
  const placeholder = has ? t('settings.key.placeholder.set') : t('settings.key.placeholder.empty');

  const input = h('input', {
    id: inputId,
    type: 'password',
    class: classes.input + ' pr-28 font-mono text-sm',
    value: '', // CRITICAL — never put masked value here
    placeholder,
    autocomplete: 'off',
    spellcheck: 'false',
    'aria-label': t(spec.label),
  });

  let revealed = false;
  const eyeBtn = h('button', {
    type: 'button',
    class: 'absolute right-2 top-1/2 -translate-y-1/2 px-2 py-1 text-xs text-[var(--text-2)] hover:text-[var(--text)] rounded',
    'aria-label': 'Toggle visibility',
    onClick: () => {
      revealed = !revealed;
      input.type = revealed ? 'text' : 'password';
      eyeBtn.replaceChildren(iconNode(revealed ? 'eye-off' : 'eye'));
      if (window.lucide) window.lucide.createIcons();
    },
  }, iconNode('eye'));

  // Status badge area
  const status = h('div', {
    class: 'mt-2 text-xs text-[var(--text-3)] min-h-[1.25rem]',
    role: 'status',
    'aria-live': 'polite',
  });
  const setStatus = (cls, text) => {
    status.className = `mt-2 text-xs min-h-[1.25rem] ${cls}`;
    status.textContent = text;
  };

  // Test button
  const testBtn = Button({
    variant: 'outline',
    icon: 'zap',
    label: t('btn.test'),
    ariaLabel: `${t('btn.test')} — ${t(spec.label)}`,
    onClick: async () => {
      if (!spec.engine) {
        Toast({ message: t('settings.key.test.fail'), type: 'warning' });
        return;
      }
      setStatus('mt-2 text-xs text-[var(--text-2)]', t('settings.key.test.run'));
      testBtn.disabled = true;
      const started = performance.now();
      try {
        const body = { engine: spec.engine };
        // If user typed a new key in the box, include it so backend tests *that* key
        // instead of the saved one. (Falls back to stored key if input is empty.)
        if (input.value && !isMasked(input.value)) body.api_key = input.value;
        if (spec.model && cfg[spec.model]) body.model = cfg[spec.model];

        const res = await api.testLlm(body);
        const latency = Math.round(performance.now() - started);
        const ok = res && (res.ok === true || res.success === true || res.status === 'ok' || res.latency != null);
        if (ok) {
          setStatus('mt-2 text-xs text-emerald-600 dark:text-emerald-400', t('settings.key.test.ok', { ms: res.latency_ms ?? res.latency ?? latency }));
        } else {
          const msg = (res && (res.error || res.message)) || t('settings.key.test.fail');
          setStatus('mt-2 text-xs text-red-600 dark:text-red-400', `${t('settings.key.test.fail')} — ${msg}`);
        }
      } catch (err) {
        setStatus('mt-2 text-xs text-red-600 dark:text-red-400', `${t('settings.key.test.fail')} — ${err.message || err}`);
      } finally {
        testBtn.disabled = false;
      }
    },
  });

  input.addEventListener('input', () => {
    const v = input.value;
    // Empty or masked → not dirty (means unchanged on save)
    if (!v || isMasked(v)) {
      dirty.set(spec.field, undefined);
      if (dirty.has(spec.field) && dirty.get(spec.field) === undefined) {
        // remove undefined entries so payload() doesn't ship them
        dirty.payload(); // triggers prune; undefined !== initial so it stays — explicitly delete
      }
      return;
    }
    dirty.set(spec.field, v);
  });

  return h('div', { class: 'space-y-1.5' },
    h('label', { class: classes.label, for: inputId }, t(spec.label)),
    h('div', { class: 'relative' }, input, eyeBtn),
    h('div', { class: 'flex items-center gap-2 mt-2' }, testBtn),
    status,
  );
}

function iconNode(name) {
  return h('i', { 'data-lucide': name, class: 'w-4 h-4 inline-block' });
}

export function mountApiKeysTab(container, cfg, dirty) {
  const hint = h('p', { class: 'text-sm text-[var(--text-3)] mb-4' }, t('settings.key.unchanged.hint'));
  const grid = h('div', { class: 'grid gap-6' });
  KEYS.forEach((spec) => grid.appendChild(makeKeyRow(spec, cfg, dirty)));
  container.appendChild(Card({ title: t('settings.tab.keys'), children: h('div', null, hint, grid) }));
}
