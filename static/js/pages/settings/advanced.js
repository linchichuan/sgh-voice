// advanced.js — Settings sub-tab: scene, system prompt, typing speed, style profile.
import { h, classes, Card, Button, Toast } from '../../lib/components.js';
import { t } from '../../lib/i18n.js';
import * as api from '../../lib/api.js';

const SCENES = [
  { id: 'general',              labelKey: 'settings.adv.scene.general' },
  { id: 'medical',              labelKey: 'settings.adv.scene.medical' },
  { id: 'medical_consultation', labelKey: 'settings.adv.scene.medical_consultation' },
];

export function mountAdvancedTab(container, cfg, dirty) {
  // Scene picker
  const sceneId = 'active_scene';
  const sceneSelect = h('select', { id: sceneId, class: classes.input, 'aria-label': t('settings.adv.scene') },
    SCENES.map((s) => h('option', { value: s.id, selected: cfg.active_scene === s.id ? '' : null }, t(s.labelKey))),
  );
  sceneSelect.addEventListener('change', () => dirty.set('active_scene', sceneSelect.value));

  // System prompt textarea
  const promptId = 'claude_system_prompt';
  const promptArea = h('textarea', {
    id: promptId,
    rows: 6,
    class: classes.input + ' font-mono text-sm leading-relaxed resize-y',
    placeholder: '(empty = built-in _DICTATE_SYSTEM)',
    'aria-label': t('settings.adv.prompt'),
    spellcheck: 'false',
  }, cfg.claude_system_prompt || '');
  promptArea.addEventListener('change', () => dirty.set('claude_system_prompt', promptArea.value));

  // Typing speed
  const typingId = 'typing_speed_cpm';
  const typingInput = h('input', {
    id: typingId,
    type: 'number',
    min: 10,
    max: 300,
    step: 5,
    value: cfg.typing_speed_cpm ?? 50,
    class: classes.input + ' max-w-[10rem]',
    'aria-label': t('settings.adv.typing'),
  });
  typingInput.addEventListener('change', () => {
    const v = Math.max(10, Math.min(300, Number(typingInput.value) || 50));
    dirty.set('typing_speed_cpm', v);
    typingInput.value = String(v);
  });

  // Style profile section
  const regenBtn = Button({
    variant: 'outline',
    icon: 'refresh-cw',
    label: t('settings.adv.style.regen'),
    onClick: async () => {
      regenBtn.disabled = true;
      try {
        await api.regenerateStyleProfile();
        Toast({ message: t('settings.adv.style.done'), type: 'success' });
      } catch (err) {
        Toast({ message: `${t('toast.error')}: ${err.message || err}`, type: 'error' });
      } finally {
        regenBtn.disabled = false;
      }
    },
  });

  container.appendChild(Card({
    title: t('settings.tab.advanced'),
    children: h('div', { class: 'space-y-6' },
      h('div', { class: 'space-y-1.5' },
        h('label', { class: classes.label, for: sceneId }, t('settings.adv.scene')),
        sceneSelect,
      ),
      h('div', { class: 'space-y-1.5 pt-2 border-t border-[var(--border)]' },
        h('label', { class: classes.label, for: promptId }, t('settings.adv.prompt')),
        promptArea,
      ),
      h('div', { class: 'space-y-1.5 pt-2 border-t border-[var(--border)]' },
        h('label', { class: classes.label, for: typingId }, t('settings.adv.typing')),
        typingInput,
      ),
      h('div', { class: 'pt-2 border-t border-[var(--border)]' },
        h('h3', { class: 'text-sm font-semibold text-[var(--text)] mb-2' }, t('settings.adv.style.title')),
        regenBtn,
      ),
    ),
  }));
}
