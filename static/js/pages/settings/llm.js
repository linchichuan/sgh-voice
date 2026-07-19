// llm.js — Settings sub-tab: LLM engine + fewshot privacy gate.
import { h, classes, Card, Switch, ConfirmDialog } from '../../lib/components.js';
import { t } from '../../lib/i18n.js';

const ENGINES = [
  { id: 'ollama',     label: 'Ollama (local)', modelKey: 'local_llm_model' },
  { id: 'groq',       label: 'Groq',           modelKey: 'groq_model' },
  { id: 'claude',     label: 'Claude',         modelKey: 'claude_model' },
  { id: 'openai',     label: 'OpenAI',         modelKey: 'openai_model' },
  { id: 'openrouter', label: 'OpenRouter',     modelKey: 'openrouter_model' },
];

function radioPanel({ name, options, value, onChange }) {
  const group = h('div', { class: 'grid grid-cols-2 md:grid-cols-5 gap-2', role: 'radiogroup', 'aria-label': t('settings.llm.engine') });
  options.forEach((opt) => {
    const id = `${name}-${opt.id}`;
    const input = h('input', { type: 'radio', id, name, value: opt.id, class: 'sr-only peer', checked: value === opt.id ? '' : null });
    input.addEventListener('change', () => { if (input.checked) onChange(opt.id); });
    const card = h('label', {
      for: id,
      class: 'flex items-center justify-center px-3 py-2 rounded-lg border border-[var(--border)] text-sm font-medium cursor-pointer hover:bg-[var(--surface-2)] peer-checked:border-[var(--brand-blue)] peer-checked:text-[var(--brand-blue)] peer-focus-visible:ring-4 peer-focus-visible:ring-blue-300',
    }, input, h('span', null, opt.label));
    group.appendChild(card);
  });
  return group;
}

function modelInput({ id, key, value, onChange }) {
  const input = h('input', {
    id, type: 'text',
    class: classes.input + ' font-mono text-sm',
    value: value || '',
    placeholder: key,
    'aria-label': `${t('settings.llm.model')} (${key})`,
    spellcheck: 'false',
  });
  input.addEventListener('change', () => onChange(input.value));
  return h('div', { class: 'space-y-1.5' },
    h('label', { class: classes.label, for: id }, `${t('settings.llm.model')} — ${key}`),
    input,
  );
}

function slider({ id, label, min, max, step, value, suffix, onChange, disabled }) {
  const valueLabel = h('span', { class: 'text-xs text-[var(--text-2)] mono' }, `${value}${suffix || ''}`);
  const input = h('input', {
    id, type: 'range', min, max, step, value,
    class: 'w-full accent-[var(--brand-blue)] focus-visible:ring-4 focus-visible:ring-blue-300 rounded',
    'aria-label': label,
    disabled: disabled ? '' : null,
  });
  input.addEventListener('input', () => {
    valueLabel.textContent = `${input.value}${suffix || ''}`;
    onChange(Number(input.value));
  });
  const wrap = h('div', { class: `space-y-1.5 ${disabled ? 'opacity-50' : ''}` },
    h('div', { class: 'flex items-center justify-between' },
      h('label', { class: classes.label, for: id }, label),
      valueLabel,
    ),
    input,
  );
  return { node: wrap, input };
}

// Custom toggle that lets us intercept BEFORE state changes (needed for privacy confirm).
function customToggle({ id, label, description, checked, onConfirmTurnOn, onTurnOff }) {
  let state = !!checked;
  const knob = h('span', { class: 'absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition' });
  knob.style.transform = state ? 'translateX(1rem)' : 'translateX(0)';
  const track = h('button', {
    type: 'button',
    id,
    role: 'switch',
    'aria-checked': state ? 'true' : 'false',
    'aria-labelledby': `${id}-label`,
    class: `inline-block w-10 h-6 rounded-full relative transition border ${state ? 'bg-[var(--brand-blue)] border-[var(--brand-blue)]' : 'bg-[var(--surface-2)] border-[var(--border)]'} focus-visible:ring-4 focus-visible:ring-blue-300 shrink-0 cursor-pointer`,
  }, knob);

  const apply = (next) => {
    state = next;
    track.setAttribute('aria-checked', state ? 'true' : 'false');
    track.classList.toggle('bg-[var(--brand-blue)]', state);
    track.classList.toggle('border-[var(--brand-blue)]', state);
    track.classList.toggle('bg-[var(--surface-2)]', !state);
    track.classList.toggle('border-[var(--border)]', !state);
    knob.style.transform = state ? 'translateX(1rem)' : 'translateX(0)';
  };

  track.addEventListener('click', () => {
    if (!state) {
      // about to turn ON — gate via confirm
      onConfirmTurnOn(() => apply(true));
    } else {
      // turn OFF immediately
      apply(false);
      onTurnOff();
    }
  });

  const labelEl = h('div', { class: 'flex-1' },
    h('div', { id: `${id}-label`, class: 'text-sm font-medium text-[var(--text)]' }, label),
    description ? h('div', { class: 'text-xs text-[var(--text-3)] mt-0.5' }, description) : null,
  );
  return { node: h('div', { class: 'flex items-start gap-3' }, track, labelEl), isOn: () => state };
}

export function mountLlmTab(container, cfg, dirty) {
  const engineGroup = radioPanel({
    name: 'llm_engine',
    options: ENGINES,
    value: cfg.llm_engine,
    onChange: (v) => dirty.set('llm_engine', v),
  });

  const modelInputs = h('div', { class: 'grid gap-3' });
  ENGINES.forEach((eng) => {
    modelInputs.appendChild(modelInput({
      id: `model-${eng.modelKey}`,
      key: eng.modelKey,
      value: cfg[eng.modelKey],
      onChange: (v) => dirty.set(eng.modelKey, v),
    }));
  });

  const polishSwitch = Switch({
    id: 'enable_claude_polish',
    label: t('settings.llm.polish'),
    checked: !!cfg.enable_claude_polish,
    onChange: (v) => dirty.set('enable_claude_polish', v),
  });
  const fillerSwitch = Switch({
    id: 'enable_filler_removal',
    label: t('settings.llm.filler'),
    checked: !!cfg.enable_filler_removal,
    onChange: (v) => dirty.set('enable_filler_removal', v),
  });

  // Privacy: fewshot — use custom toggle so we can confirm BEFORE state flips
  const fewshotInitial = !!cfg.enable_fewshot;
  const fewshotCountSlider = slider({
    id: 'fewshot_count',
    label: t('settings.llm.fewshot.count'),
    min: 0, max: 5, step: 1,
    value: cfg.fewshot_count ?? 3,
    suffix: '',
    onChange: (v) => dirty.set('fewshot_count', v),
    disabled: !fewshotInitial,
  });
  const setSliderDisabled = (off) => {
    fewshotCountSlider.input.disabled = off;
    fewshotCountSlider.node.classList.toggle('opacity-50', off);
  };
  const fewshotToggle = customToggle({
    id: 'enable_fewshot',
    label: t('settings.llm.fewshot.label'),
    description: t('settings.llm.fewshot.desc'),
    checked: fewshotInitial,
    onConfirmTurnOn: (applyOn) => {
      ConfirmDialog({
        title: t('settings.llm.fewshot.confirm.title'),
        message: t('settings.llm.fewshot.confirm.msg', { n: cfg.fewshot_count ?? 3 }),
        confirmText: t('btn.confirm'),
        onConfirm: () => {
          applyOn();
          dirty.set('enable_fewshot', true);
          setSliderDisabled(false);
        },
      });
    },
    onTurnOff: () => {
      dirty.set('enable_fewshot', false);
      setSliderDisabled(true);
    },
  });
  const verifiedCount = Number(cfg.personalization_verified_count || 0);
  const fewshotStatus = h('div', {
    class: `rounded-lg border p-3 text-sm ${verifiedCount > 0 ? 'border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-100' : 'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-100'}`,
  },
    h('div', { class: 'font-medium' }, verifiedCount > 0
      ? t('settings.llm.fewshot.ready', { n: verifiedCount })
      : t('settings.llm.fewshot.empty')),
    h('a', { href: '#/history', class: 'inline-block mt-1 underline underline-offset-2' },
      t('settings.llm.fewshot.history.link')),
  );

  container.appendChild(Card({
    title: t('settings.llm.engine'),
    children: h('div', { class: 'space-y-6' },
      engineGroup,
      h('div', { class: 'pt-2 border-t border-[var(--border)]' }, modelInputs),
      h('div', { class: 'space-y-4 pt-2 border-t border-[var(--border)]' },
        polishSwitch,
        fillerSwitch,
      ),
      h('div', { class: 'space-y-4 pt-2 border-t border-[var(--border)]' },
        fewshotToggle.node,
        fewshotCountSlider.node,
        fewshotStatus,
      ),
    ),
  }));
}
