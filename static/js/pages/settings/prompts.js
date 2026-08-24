// prompts.js — Truthful prompt management for dictation, translation and rewrite.
import { h, classes, Card, Button } from '../../lib/components.js';
import { t } from '../../lib/i18n.js';

const ENGINE_MODEL_KEYS = {
  ollama: 'local_llm_model',
  groq: 'groq_model',
  claude: 'claude_model',
  openai: 'openai_model',
  openrouter: 'openrouter_model',
};

const MODEL_COST_AND_POLICY = {
  'claude-haiku-4-5-20251001': 'US$1 / US$5 per MTok · no thinking',
  'claude-sonnet-5': 'US$2 / US$10 per MTok through 2026-08-31, then US$3 / US$15 · thinking disabled',
  'claude-opus-5': 'US$5 / US$25 per MTok · thinking disabled',
  'claude-opus-4-8': 'US$5 / US$25 per MTok · thinking disabled',
  'claude-fable-5': 'US$10 / US$50 per MTok · required thinking at low effort · 30-day data retention',
  'openai/gpt-oss-20b': 'US$0.075 / US$0.30 per MTok · low reasoning effort',
  'openai/gpt-oss-120b': 'US$0.15 / US$0.60 per MTok · low reasoning effort',
  'llama-3.3-70b-versatile': 'US$0.59 / US$0.79 per MTok',
  'gpt-4o-mini': 'US$0.15 / US$0.60 per MTok',
  'gpt-4o': 'US$2.50 / US$10 per MTok',
};

function modeRow(icon, titleKey, descriptionKey, badgeKey) {
  return h('div', {
    class: 'flex items-start gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] p-4',
  },
    h('div', {
      class: 'mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[var(--surface)] text-[var(--brand-blue)]',
      'aria-hidden': 'true',
    }, h('i', { 'data-lucide': icon, class: 'w-5 h-5' })),
    h('div', { class: 'min-w-0 flex-1' },
      h('div', { class: 'flex flex-wrap items-center gap-2' },
        h('h3', { class: 'text-sm font-semibold text-[var(--text)]' }, t(titleKey)),
        h('span', {
          class: 'rounded-full border border-emerald-300 bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200',
        }, t(badgeKey)),
      ),
      h('p', { class: 'mt-1 text-sm leading-relaxed text-[var(--text-2)]' }, t(descriptionKey)),
    ),
  );
}

export function mountPromptsTab(container, cfg, dirty) {
  const engine = cfg.llm_engine || 'groq';
  const modelKey = ENGINE_MODEL_KEYS[engine] || '';
  const model = modelKey ? (cfg[modelKey] || t('settings.prompts.model.unset')) : t('settings.prompts.model.unset');
  const costAndPolicy = engine === 'ollama'
    ? t('settings.prompts.cost.local')
    : (MODEL_COST_AND_POLICY[model] || t('settings.prompts.cost.unknown'));

  const routeTruth = h('div', {
    class: 'grid gap-3 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm dark:border-blue-900 dark:bg-blue-950/30 md:grid-cols-2',
  },
    h('div', null,
      h('div', { class: 'text-xs font-medium uppercase tracking-wide text-[var(--text-3)]' }, t('settings.prompts.provider')),
      h('div', { class: 'mt-1 font-semibold text-[var(--text)]' }, engine),
    ),
    h('div', null,
      h('div', { class: 'text-xs font-medium uppercase tracking-wide text-[var(--text-3)]' }, t('settings.prompts.model')),
      h('div', { class: 'mt-1 break-all font-mono text-[var(--text)]' }, model),
    ),
    h('div', { class: 'md:col-span-2' },
      h('div', { class: 'text-xs font-medium uppercase tracking-wide text-[var(--text-3)]' }, t('settings.prompts.cost')),
      h('div', { class: 'mt-1 text-[var(--text)]' }, costAndPolicy),
      h('div', { class: 'mt-1 text-xs text-[var(--text-3)]' }, t('settings.prompts.pricing.date')),
    ),
  );

  const promptId = 'claude_system_prompt';
  const promptArea = h('textarea', {
    id: promptId,
    rows: 7,
    maxlength: 4000,
    class: `${classes.input} font-mono text-sm leading-relaxed resize-y`,
    placeholder: t('settings.prompts.custom.placeholder'),
    'aria-label': t('settings.prompts.custom.title'),
    spellcheck: 'false',
  }, cfg.claude_system_prompt || '');
  promptArea.addEventListener('input', () => {
    dirty.set('claude_system_prompt', promptArea.value);
    count.textContent = `${promptArea.value.length}/4000`;
  });

  const count = h('span', {
    class: 'text-xs tabular-nums text-[var(--text-3)]',
    'aria-live': 'polite',
  }, `${promptArea.value.length}/4000`);
  const resetButton = Button({
    variant: 'outline',
    icon: 'rotate-ccw',
    label: t('settings.prompts.custom.reset'),
    onClick: () => {
      promptArea.value = '';
      count.textContent = '0/4000';
      dirty.set('claude_system_prompt', '');
      promptArea.focus();
    },
  });

  container.appendChild(Card({
    title: t('settings.prompts.title'),
    children: h('div', { class: 'space-y-6' },
      h('p', { class: 'text-sm leading-relaxed text-[var(--text-2)]' }, t('settings.prompts.intro')),
      routeTruth,
      h('div', { class: 'grid gap-3' },
        modeRow('mic', 'settings.prompts.dictate.title', 'settings.prompts.dictate.desc', 'settings.prompts.locked'),
        modeRow('languages', 'settings.prompts.translate.title', 'settings.prompts.translate.desc', 'settings.prompts.locked'),
        modeRow('wand-sparkles', 'settings.prompts.rewrite.title', 'settings.prompts.rewrite.desc', 'settings.prompts.command.only'),
      ),
      h('div', { class: 'space-y-2 border-t border-[var(--border)] pt-5' },
        h('div', { class: 'flex flex-wrap items-center justify-between gap-2' },
          h('label', { class: classes.label, for: promptId }, t('settings.prompts.custom.title')),
          count,
        ),
        h('p', { class: 'text-xs leading-relaxed text-[var(--text-3)]' }, t('settings.prompts.custom.desc')),
        promptArea,
        h('div', { class: 'flex justify-end' }, resetButton),
      ),
    ),
  }));
}
