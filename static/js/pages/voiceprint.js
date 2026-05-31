// voiceprint.js — Voiceprint enrollment / verification settings page.
// Privacy posture: biometric data ("要配慮個人情報" APPI, GDPR Art. 9 special category).
// HARD RULE: never call api.enrollVoiceprint() without explicit ConsentDialog → ack checkbox.

import * as api from '../lib/api.js';
import { t } from '../lib/i18n.js';
import { h, Button, Card, Switch, Badge, Toast, ConfirmDialog, classes } from '../lib/components.js';

function fmtBytes(n) {
  if (!Number.isFinite(n) || n <= 0) return '—';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(2)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

function fmtTs(ts) {
  if (!ts) return '—';
  try {
    const d = typeof ts === 'number' ? new Date(ts * (ts < 1e12 ? 1000 : 1)) : new Date(ts);
    if (Number.isNaN(d.getTime())) return String(ts);
    return d.toLocaleString();
  } catch { return String(ts); }
}

// ---------- modal helper (shared by consent + typed-delete) ----------
function openModal({ titleId, maxW = 'max-w-md', body, footer }) {
  const backdrop = h('div', {
    class: `fixed inset-0 z-[95] bg-black/50 flex items-center justify-center p-4 overflow-y-auto`,
    role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': titleId,
  });
  const onKey = (e) => { if (e.key === 'Escape') close(); };
  const close = () => { backdrop.remove(); document.removeEventListener('keydown', onKey); };
  document.addEventListener('keydown', onKey);
  const dialog = h('div', {
    class: `bg-[var(--surface)] rounded-2xl shadow-2xl ${maxW} w-full p-6 border border-[var(--border)] my-8`,
  }, body, footer);
  backdrop.appendChild(dialog);
  backdrop.addEventListener('click', (e) => { if (e.target === backdrop) close(); });
  document.body.appendChild(backdrop);
  if (window.lucide) window.lucide.createIcons();
  return { close, dialog };
}

// ---------- ConsentDialog (multi-section, ack-gated) ----------
function openConsentDialog({ onConsent }) {
  const ackId = 'vp-consent-ack';
  const ackInput = h('input', {
    type: 'checkbox', id: ackId,
    class: 'mt-1 w-4 h-4 accent-[var(--brand-blue)] focus-visible:ring-4 focus-visible:ring-blue-300',
  });
  const section = (titleKey, bodyKey, extra) =>
    h('section', { class: 'rounded-xl border border-[var(--border)] bg-[var(--surface-2)] p-4' },
      h('h3', { class: 'text-sm font-semibold text-[var(--text)] mb-1' }, t(titleKey)),
      h('p', { class: 'text-sm text-[var(--text-2)] leading-relaxed' }, t(bodyKey)),
      extra ? h('div', { class: 'mt-2 mono text-xs text-[var(--text-3)] break-all' }, extra) : null,
    );
  const body = h('div', null,
    h('div', { class: 'flex items-center gap-2 mb-4' },
      h('i', { 'data-lucide': 'shield-alert', class: 'w-6 h-6 text-[var(--brand-orange)]' }),
      h('h2', { id: 'vp-consent-title', class: 'text-xl font-semibold text-[var(--text)]' }, t('vp.consent.title')),
    ),
    h('div', { class: 'space-y-3 mb-5' },
      section('vp.consent.s1.title', 'vp.consent.s1.body', t('vp.consent.s1.example')),
      section('vp.consent.s2.title', 'vp.consent.s2.body', t('vp.consent.s2.path')),
      section('vp.consent.s3.title', 'vp.consent.s3.body'),
      section('vp.consent.s4.title', 'vp.consent.s4.body'),
    ),
    h('label', { class: 'flex items-start gap-2 p-3 rounded-lg border border-[var(--border)] bg-[var(--surface-2)] cursor-pointer mb-4', for: ackId },
      ackInput,
      h('span', { class: 'text-sm text-[var(--text)] leading-relaxed' }, t('vp.consent.ack')),
    ),
  );
  let ctl;
  const confirmBtn = Button({
    variant: 'primary', icon: 'shield-check', label: t('vp.consent.confirm'), disabled: true,
    onClick: async () => { ctl.close(); if (onConsent) await onConsent(); },
  });
  ackInput.addEventListener('change', () => { confirmBtn.disabled = !ackInput.checked; });
  const footer = h('div', { class: 'flex justify-end gap-2' },
    Button({ variant: 'ghost', label: t('btn.cancel'), onClick: () => ctl.close() }),
    confirmBtn,
  );
  ctl = openModal({ titleId: 'vp-consent-title', maxW: 'max-w-2xl', body, footer });
}

// ---------- Typed-confirm delete dialog ----------
function openTypedDeleteDialog({ onConfirm }) {
  const input = h('input', {
    type: 'text', class: classes.input + ' mono',
    placeholder: t('vp.delete.confirm.placeholder'),
    'aria-label': t('vp.delete.confirm.placeholder'),
    autocomplete: 'off', spellcheck: 'false',
  });
  let ctl;
  const confirmBtn = Button({
    variant: 'danger', icon: 'trash-2', label: t('btn.delete'), disabled: true,
    onClick: async () => { ctl.close(); if (onConfirm) await onConfirm(); },
  });
  input.addEventListener('input', () => { confirmBtn.disabled = input.value.trim() !== 'DELETE'; });
  const body = h('div', null,
    h('h2', { id: 'vp-del-title', class: 'text-lg font-semibold text-[var(--text)] mb-2' }, t('vp.delete.confirm.title')),
    h('p', { class: 'text-sm text-[var(--text-2)] mb-4' }, t('vp.delete.confirm.msg')),
    input,
  );
  const footer = h('div', { class: 'flex justify-end gap-2 mt-5' },
    Button({ variant: 'ghost', label: t('btn.cancel'), onClick: () => ctl.close() }),
    confirmBtn,
  );
  ctl = openModal({ titleId: 'vp-del-title', body, footer });
  setTimeout(() => input.focus(), 0);
}

// ---------- Renderers ----------
function renderEnrolled(status, cfg, refresh) {
  const enabled = cfg?.enable_voiceprint !== false;
  const threshold = Number(cfg?.voiceprint_threshold ?? 0.97);

  const tEl = h('span', { class: 'mono text-sm tabular-nums text-[var(--text)] min-w-[3rem] text-right' }, threshold.toFixed(2));
  const slider = h('input', {
    type: 'range',
    id: 'vp-threshold',
    min: '0.85', max: '0.99', step: '0.01',
    value: String(threshold),
    class: 'w-full accent-[var(--brand-blue)] focus-visible:ring-4 focus-visible:ring-blue-300',
    'aria-label': t('vp.threshold.label'),
    'aria-valuemin': '0.85', 'aria-valuemax': '0.99', 'aria-valuenow': String(threshold),
  });
  let debounceId = 0;
  slider.addEventListener('input', () => {
    const v = Number(slider.value);
    tEl.textContent = v.toFixed(2);
    slider.setAttribute('aria-valuenow', String(v));
    clearTimeout(debounceId);
    debounceId = setTimeout(async () => {
      try {
        await api.saveConfig({ voiceprint_threshold: v });
        Toast({ message: t('vp.threshold.saved'), type: 'success' });
      } catch (e) { Toast({ message: e.message || t('toast.error'), type: 'error' }); }
    }, 400);
  });

  const detailRow = (label, value, mono = false) =>
    h('div', { class: 'flex justify-between items-baseline gap-4 py-1.5' },
      h('span', { class: 'text-sm text-[var(--text-3)]' }, label),
      h('span', { class: `text-sm ${mono ? 'mono' : ''} text-[var(--text)] text-right break-all` }, value),
    );

  return [
    Card({
      title: h('span', { class: 'flex items-center gap-2' },
        h('i', { 'data-lucide': 'fingerprint', class: 'w-5 h-5 text-[var(--brand-blue)]' }),
        h('span', null, t('vp.header.title')),
        h('span', { class: 'ml-2' }, Badge({ text: `● ${t('vp.status.enrolled')}`, color: 'green' })),
      ),
      children: [
        h('p', { class: 'text-sm text-[var(--text-2)] leading-relaxed mb-4' }, t('vp.header.desc')),
        h('div', { class: 'border-t border-[var(--border)] pt-4' },
          h('h3', { class: 'text-sm font-semibold text-[var(--text)] mb-2' }, t('vp.detail.title')),
          detailRow(t('vp.detail.dim'), String(status.dim ?? '—'), true),
          detailRow(t('vp.detail.size'), fmtBytes(status.file_size), true),
          detailRow(t('vp.detail.enrolledAt'), fmtTs(status.enrolled_at)),
          detailRow(t('vp.detail.path'), '~/.voice-input/voiceprint.npy', true),
        ),
      ],
    }),
    Card({
      title: t('vp.threshold.label'),
      children: [
        h('div', { class: 'flex items-center gap-3 mb-2' },
          h('label', { for: 'vp-threshold', class: 'sr-only' }, t('vp.threshold.label')),
          slider, tEl,
        ),
        h('p', { class: 'text-xs text-[var(--text-3)]' }, t('vp.threshold.help')),
        h('div', { class: 'mt-4 pt-4 border-t border-[var(--border)]' },
          Switch({
            id: 'vp-enable',
            label: t('vp.toggle.label'),
            description: t('vp.toggle.desc'),
            checked: enabled,
            onChange: async (v) => {
              try {
                await api.saveConfig({ enable_voiceprint: v });
                Toast({ message: t('toast.saved'), type: 'success' });
              } catch (e) { Toast({ message: e.message || t('toast.error'), type: 'error' }); }
            },
          }),
        ),
      ],
    }),
    h('div', { class: 'flex flex-wrap gap-3 justify-end' },
      Button({
        variant: 'outline',
        icon: 'refresh-cw',
        label: t('vp.reenroll.btn'),
        onClick: () => {
          ConfirmDialog({
            title: t('vp.reenroll.confirm.title'),
            message: t('vp.reenroll.confirm.msg'),
            confirmText: t('vp.reenroll.btn'),
            // Re-enroll is destructive → still requires consent dialog (acknowledge biometric).
            onConfirm: () => openConsentDialog({ onConsent: () => doEnroll(refresh) }),
          });
        },
      }),
      Button({
        variant: 'danger',
        icon: 'trash-2',
        label: t('vp.delete.btn'),
        onClick: () => openTypedDeleteDialog({ onConfirm: () => doDelete(refresh) }),
      }),
    ),
  ];
}

function renderNotEnrolled(refresh) {
  const enrollBtn = Button({
    variant: 'primary',
    icon: 'shield-plus',
    label: t('vp.enroll.btn'),
    // BLOCKING: enroll ONLY through consent dialog. Do NOT bypass.
    onClick: () => openConsentDialog({ onConsent: () => doEnroll(refresh) }),
  });
  return [
    Card({
      title: h('span', { class: 'flex items-center gap-2' },
        h('i', { 'data-lucide': 'fingerprint', class: 'w-5 h-5 text-[var(--brand-blue)]' }),
        h('span', null, t('vp.header.title')),
        h('span', { class: 'ml-2' }, Badge({ text: t('vp.status.notEnrolled'), color: 'default' })),
      ),
      children: [
        h('p', { class: 'text-sm text-[var(--text-2)] leading-relaxed mb-4' }, t('vp.header.desc')),
        h('div', { class: 'flex flex-col items-center justify-center py-10 text-center border-t border-[var(--border)]' },
          h('div', { class: 'w-14 h-14 rounded-2xl bg-[var(--surface-2)] flex items-center justify-center text-[var(--text-3)] mb-4' },
            h('i', { 'data-lucide': 'user-plus', class: 'w-7 h-7' }),
          ),
          h('h3', { class: 'text-base font-semibold text-[var(--text)] mb-2' }, t('vp.empty.title')),
          h('p', { class: 'text-sm text-[var(--text-3)] max-w-md mb-5 leading-relaxed' }, t('vp.empty.msg')),
          enrollBtn,
        ),
      ],
    }),
  ];
}

// ---------- Mutators ----------
async function doEnroll(refresh) {
  const toast = Toast({ message: t('vp.enrolling'), type: 'info', duration: 0 });
  try {
    const res = await api.enrollVoiceprint();
    toast.remove();
    if (res && res.ok === false) {
      Toast({ message: t('vp.enroll.fail', { msg: res.message || res.error || '' }), type: 'error' });
    } else {
      Toast({ message: t('vp.enroll.success', { dim: res?.dim ?? '?' }), type: 'success' });
    }
  } catch (e) {
    toast.remove();
    Toast({ message: t('vp.enroll.fail', { msg: e.message || t('toast.error') }), type: 'error' });
  }
  await refresh();
}

async function doDelete(refresh) {
  try {
    await api.deleteVoiceprint();
    Toast({ message: t('vp.delete.success'), type: 'success' });
  } catch (e) {
    Toast({ message: e.message || t('toast.error'), type: 'error' });
  }
  await refresh();
}

// ---------- mount ----------
export default async function mount(slot) {
  slot.replaceChildren();
  const wrap = h('div', { class: 'max-w-2xl mx-auto space-y-5 p-6' });
  slot.appendChild(wrap);

  async function refresh() {
    wrap.replaceChildren(h('div', { class: 'text-center text-[var(--text-3)] py-10' }, '…'));
    let status, cfg;
    try {
      [status, cfg] = await Promise.all([api.getVoiceprintStatus(), api.getConfig()]);
    } catch (e) {
      wrap.replaceChildren(h('div', { class: `${classes.card} text-[var(--danger)]` }, e.message || t('toast.error')));
      return;
    }
    const enrolled = !!(status && status.enrolled);
    const children = enrolled
      ? renderEnrolled(status, cfg || {}, refresh)
      : renderNotEnrolled(refresh);
    wrap.replaceChildren(...children);
    if (window.lucide) window.lucide.createIcons();
  }

  await refresh();
}
