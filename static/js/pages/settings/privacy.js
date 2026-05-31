// privacy.js — Settings sub-tab: privacy controls + GDPR wipe-all.
import { h, classes, Card, Switch, Button, ConfirmDialog, Toast } from '../../lib/components.js';
import { t } from '../../lib/i18n.js';
import * as api from '../../lib/api.js';

// Custom gate-on toggle — needed because we must confirm BEFORE enabling app awareness.
function gatedToggle({ id, label, description, checked, onConfirmTurnOn, onTurnOff }) {
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
    if (!state) onConfirmTurnOn(() => apply(true));
    else { apply(false); onTurnOff(); }
  });
  return h('div', { class: 'flex items-start gap-3' },
    track,
    h('div', { class: 'flex-1' },
      h('div', { id: `${id}-label`, class: 'text-sm font-medium text-[var(--text)]' }, label),
      description ? h('div', { class: 'text-xs text-[var(--text-3)] mt-0.5' }, description) : null,
    ),
  );
}

// Custom wipe-all confirm: requires typing DELETE before the danger button enables.
function wipeAllDialog({ onConfirmed }) {
  const backdrop = h('div', {
    class: 'fixed inset-0 z-[90] bg-black/40 flex items-center justify-center p-4',
    role: 'dialog',
    'aria-modal': 'true',
    'aria-labelledby': 'wipe-title',
  });
  const close = () => backdrop.remove();

  const input = h('input', {
    type: 'text',
    class: classes.input + ' font-mono',
    placeholder: t('settings.privacy.wipe.placeholder'),
    'aria-label': t('settings.privacy.wipe.placeholder'),
    spellcheck: 'false',
    autocomplete: 'off',
  });
  const confirmBtn = Button({
    variant: 'danger',
    icon: 'trash-2',
    label: t('settings.privacy.wipe.btn'),
    onClick: async () => {
      if (input.value !== 'DELETE') return;
      confirmBtn.disabled = true;
      try {
        const res = await api.wipeAll();
        close();
        Toast({ message: `${t('settings.privacy.wipe.done')} — ${summarizeWipe(res)}`, type: 'success' });
        if (onConfirmed) onConfirmed();
      } catch (err) {
        Toast({ message: `${t('toast.error')}: ${err.message || err}`, type: 'error' });
        confirmBtn.disabled = false;
      }
    },
  });
  confirmBtn.disabled = true;
  input.addEventListener('input', () => {
    confirmBtn.disabled = (input.value !== 'DELETE');
  });

  const dialog = h('div', { class: 'bg-[var(--surface)] rounded-2xl shadow-2xl max-w-md w-full p-6 border border-[var(--border)]' },
    h('h2', { id: 'wipe-title', class: 'text-lg font-semibold text-[var(--text)] mb-2' }, t('settings.privacy.wipe.confirm.title')),
    h('p', { class: 'text-sm text-[var(--text-2)] mb-4' }, t('settings.privacy.wipe.confirm.msg')),
    input,
    h('div', { class: 'flex justify-end gap-2 mt-6' },
      Button({ variant: 'ghost', label: t('btn.cancel'), onClick: close }),
      confirmBtn,
    ),
  );
  backdrop.appendChild(dialog);
  backdrop.addEventListener('click', (e) => { if (e.target === backdrop) close(); });
  document.body.appendChild(backdrop);
  if (window.lucide) window.lucide.createIcons();
  setTimeout(() => input.focus(), 30);
  const onKey = (e) => { if (e.key === 'Escape') { close(); document.removeEventListener('keydown', onKey); } };
  document.addEventListener('keydown', onKey);
}

function summarizeWipe(res) {
  if (!res || typeof res !== 'object') return '';
  const parts = [];
  for (const [k, v] of Object.entries(res)) {
    if (typeof v === 'number') parts.push(`${k}:${v}`);
  }
  return parts.join(' ');
}

export function mountPrivacyTab(container, cfg, dirty) {
  // fewshot mirror (read-only display) — link user to LLM tab for real toggle.
  const fewshotMirror = h('div', { class: 'flex items-center justify-between p-3 rounded-lg bg-[var(--surface-2)] border border-[var(--border)]' },
    h('div', null,
      h('div', { class: 'text-sm font-medium text-[var(--text)]' }, t('settings.llm.fewshot.label')),
      h('div', { class: 'text-xs text-[var(--text-3)] mt-0.5' }, t('settings.llm.fewshot.desc')),
    ),
    h('span', { class: `inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cfg.enable_fewshot ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200' : 'bg-[var(--surface)] text-[var(--text-3)] border border-[var(--border)]'}` }, cfg.enable_fewshot ? 'ON' : 'OFF'),
  );

  // App awareness — gated toggle
  const appAware = gatedToggle({
    id: 'enable_app_awareness',
    label: t('settings.privacy.appaware.label'),
    description: t('settings.privacy.appaware.desc'),
    checked: !!cfg.enable_app_awareness,
    onConfirmTurnOn: (applyOn) => {
      ConfirmDialog({
        title: t('settings.privacy.appaware.confirm.title'),
        message: t('settings.privacy.appaware.confirm.msg'),
        confirmText: t('btn.confirm'),
        onConfirm: () => { applyOn(); dirty.set('enable_app_awareness', true); },
      });
    },
    onTurnOff: () => dirty.set('enable_app_awareness', false),
  });

  // Voiceprint — normal switch (just toggles; setup happens on voiceprint page)
  const voiceprintSwitch = Switch({
    id: 'enable_voiceprint',
    label: t('settings.privacy.voiceprint.label'),
    checked: !!cfg.enable_voiceprint,
    onChange: (v) => dirty.set('enable_voiceprint', v),
  });
  const voiceprintLink = h('a', {
    href: '#/voiceprint',
    class: 'text-sm text-[var(--brand-blue)] hover:underline inline-flex items-center gap-1',
  }, t('settings.privacy.voiceprint.link'), ' →');

  // Audio backup dir
  const dirId = 'backup_audio_dir';
  const dirInput = h('input', {
    id: dirId,
    type: 'text',
    class: classes.input + ' font-mono text-sm',
    value: cfg.backup_audio_dir || '',
    placeholder: '/Volumes/Satechi_SSD/voice-input/audio_backup',
    spellcheck: 'false',
    autocomplete: 'off',
  });
  dirInput.addEventListener('change', () => dirty.set('backup_audio_dir', dirInput.value));

  // Wipe-all
  const wipeBtn = Button({
    variant: 'danger',
    icon: 'trash-2',
    label: t('settings.privacy.wipe.btn'),
    onClick: () => wipeAllDialog({
      onConfirmed: () => { setTimeout(() => location.reload(), 800); },
    }),
  });

  container.appendChild(Card({
    title: t('settings.privacy.title'),
    children: h('div', { class: 'space-y-6' },
      fewshotMirror,
      h('div', { class: 'pt-2 border-t border-[var(--border)] space-y-4' },
        appAware,
        h('div', { class: 'space-y-1.5' },
          voiceprintSwitch,
          h('div', { class: 'ml-13' }, voiceprintLink),
        ),
      ),
      h('div', { class: 'pt-2 border-t border-[var(--border)] space-y-1.5' },
        h('label', { class: classes.label, for: dirId }, t('settings.privacy.audio.dir')),
        dirInput,
        h('div', { class: 'text-xs text-[var(--text-3)]' }, t('settings.privacy.audio.hint')),
      ),
      h('div', {
        class: 'pt-4 mt-2 border-t border-red-200 dark:border-red-800/40 rounded-lg bg-red-50/40 dark:bg-red-900/10 p-4 -mx-2',
      },
        h('h3', { class: 'text-sm font-semibold text-red-900 dark:text-red-200 mb-2' }, t('settings.privacy.wipe.title')),
        h('p', { class: 'text-xs text-red-800 dark:text-red-300 mb-3' }, t('settings.privacy.wipe.confirm.msg')),
        wipeBtn,
      ),
    ),
  }));
}
