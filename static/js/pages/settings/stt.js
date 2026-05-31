// stt.js — Settings sub-tab: STT engine.
import { h, classes, Card, Switch, Badge } from '../../lib/components.js';
import { t } from '../../lib/i18n.js';

const ENGINES = [
  { id: 'mlx-whisper', labelKey: 'settings.stt.local' },
  { id: 'groq',        labelKey: 'settings.stt.groq' },
  { id: 'cloud-only',  labelKey: 'settings.stt.cloud' },
];

const LOCAL_MODELS = [
  { id: 'whisper-turbo',        label: 'whisper-turbo (1.5GB, multilingual)' },
  { id: 'breeze-asr-25-4bit',   label: 'Breeze-ASR-25 4bit (0.82GB, 繁中最強)' },
  { id: 'breeze-asr-25',        label: 'Breeze-ASR-25 fp16 (2.87GB, 繁中最強)' },
];

function radioGroup({ name, options, value, onChange, ariaLabel }) {
  const group = h('div', { class: 'space-y-2', role: 'radiogroup', 'aria-label': ariaLabel });
  options.forEach((opt) => {
    const id = `${name}-${opt.id}`;
    const input = h('input', {
      type: 'radio',
      id,
      name,
      value: opt.id,
      class: 'sr-only peer',
      checked: value === opt.id ? '' : null,
    });
    input.addEventListener('change', () => { if (input.checked) onChange(opt.id); });
    const card = h('label', {
      for: id,
      class: 'flex items-center gap-3 p-3 rounded-lg border border-[var(--border)] cursor-pointer hover:bg-[var(--surface-2)] transition peer-checked:border-[var(--brand-blue)] peer-focus-visible:ring-4 peer-focus-visible:ring-blue-300',
    },
      input,
      h('span', { class: `w-4 h-4 rounded-full border-2 ${value === opt.id ? 'border-[var(--brand-blue)] bg-[var(--brand-blue)]' : 'border-[var(--border)]'}` }),
      h('span', { class: 'text-sm font-medium text-[var(--text)]' }, opt.label || t(opt.labelKey)),
    );
    group.appendChild(card);
  });
  return group;
}

function slider({ id, label, min, max, step, value, suffix, onChange }) {
  const valueLabel = h('span', { class: 'text-xs text-[var(--text-2)] mono' }, `${value}${suffix || ''}`);
  const input = h('input', {
    id, type: 'range', min, max, step, value,
    class: 'w-full accent-[var(--brand-blue)] focus-visible:ring-4 focus-visible:ring-blue-300 rounded',
    'aria-label': label,
  });
  input.addEventListener('input', () => {
    valueLabel.textContent = `${input.value}${suffix || ''}`;
    onChange(Number(input.value));
  });
  return h('div', { class: 'space-y-1.5' },
    h('div', { class: 'flex items-center justify-between' },
      h('label', { class: classes.label, for: id }, label),
      valueLabel,
    ),
    input,
  );
}

export function mountSttTab(container, cfg, dirty) {
  // Engine radio
  const enginePicker = radioGroup({
    name: 'stt_engine',
    options: ENGINES,
    value: cfg.stt_engine,
    ariaLabel: t('settings.stt.engine'),
    onChange: (v) => dirty.set('stt_engine', v),
  });

  // Local model picker — only meaningful when stt_engine === 'mlx-whisper'
  const modelSelectId = 'local-whisper-model';
  const modelSelect = h('select', {
    id: modelSelectId,
    class: classes.input,
    'aria-label': t('settings.stt.local.model'),
  }, LOCAL_MODELS.map((m) => h('option', { value: m.id, selected: cfg.local_whisper_model === m.id ? '' : null }, m.label)));
  modelSelect.addEventListener('change', () => dirty.set('local_whisper_model', modelSelect.value));

  const modelLink = h('a', {
    href: '#/models',
    class: 'text-sm text-[var(--brand-blue)] hover:underline inline-flex items-center gap-1',
  }, t('settings.stt.model.link'), ' →');

  // Hybrid + audio gate switches
  const hybridSwitch = Switch({
    id: 'enable_hybrid_mode',
    label: t('settings.stt.hybrid'),
    checked: !!cfg.enable_hybrid_mode,
    onChange: (v) => dirty.set('enable_hybrid_mode', v),
  });
  const hybridThreshold = slider({
    id: 'hybrid_audio_threshold',
    label: t('settings.stt.hybrid.threshold'),
    min: 1, max: 30, step: 1,
    value: cfg.hybrid_audio_threshold ?? 15,
    suffix: 's',
    onChange: (v) => dirty.set('hybrid_audio_threshold', v),
  });
  const gateSwitch = Switch({
    id: 'enable_audio_gate',
    label: t('settings.stt.gate'),
    checked: !!cfg.enable_audio_gate,
    onChange: (v) => dirty.set('enable_audio_gate', v),
  });

  container.appendChild(Card({
    title: t('settings.stt.engine'),
    children: h('div', { class: 'space-y-6' },
      enginePicker,
      h('div', { class: 'space-y-2 pt-2 border-t border-[var(--border)]' },
        h('label', { class: classes.label, for: modelSelectId }, t('settings.stt.local.model')),
        modelSelect,
        modelLink,
      ),
      h('div', { class: 'space-y-4 pt-2 border-t border-[var(--border)]' },
        hybridSwitch,
        hybridThreshold,
        gateSwitch,
      ),
    ),
  }));
}
