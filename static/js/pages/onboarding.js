// onboarding.js — first-time setup wizard (3 steps). Spec §4.8.

import { t } from '../lib/i18n.js';
import { h, classes, Button, Toast } from '../lib/components.js';
import * as api from '../lib/api.js';

const FLAVORS = {
  local:   { iconChar: '🆓', tk: 'onb.flavor.local.title',   dk: 'onb.flavor.local.desc',   rk: 'onb.flavor.local.req',   needsKeys: [],                       config: { stt_engine: 'mlx-whisper', llm_engine: 'ollama' } },
  fast:    { iconChar: '⚡', tk: 'onb.flavor.fast.title',    dk: 'onb.flavor.fast.desc',    rk: 'onb.flavor.fast.req',    needsKeys: ['groq'],                  config: { stt_engine: 'groq',        llm_engine: 'groq'   }, recommended: true },
  premium: { iconChar: '💎', tk: 'onb.flavor.premium.title', dk: 'onb.flavor.premium.desc', rk: 'onb.flavor.premium.req', needsKeys: ['anthropic', 'openai'],   config: { stt_engine: 'groq',        llm_engine: 'claude' } },
};

const KEY_SPECS = {
  groq:      { configKey: 'groq_api_key',      prefix: 'gsk_',    engine: 'groq',   url: 'https://console.groq.com/keys',                lk: 'onb.keys.groq.label',      hk: 'onb.keys.groq.help' },
  openai:    { configKey: 'openai_api_key',    prefix: 'sk-',     engine: 'openai', url: 'https://platform.openai.com/api-keys',         lk: 'onb.keys.openai.label',    hk: 'onb.keys.openai.help' },
  anthropic: { configKey: 'anthropic_api_key', prefix: 'sk-ant-', engine: 'claude', url: 'https://console.anthropic.com/settings/keys',  lk: 'onb.keys.anthropic.label', hk: 'onb.keys.anthropic.help' },
};

export default async function mount(slot) {
  const state = {
    step: 1, flavor: null,
    keys: { groq: '', openai: '', anthropic: '' },
    keyResults: {}, recording: false, processing: false, result: null,
  };
  const root = h('div', { class: 'max-w-2xl mx-auto p-6 sm:p-10 space-y-8' });
  slot.replaceChildren(root);
  render();

  function render() {
    root.replaceChildren(StepIndicator(state.step), StepBody());
    if (window.lucide) window.lucide.createIcons();
  }

  function StepIndicator(active) {
    const labels = [t('onb.step.flavor'), t('onb.step.keys'), t('onb.step.try')];
    const segs = labels.map((label, i) => {
      const idx = i + 1, done = idx < active, cur = idx === active;
      const dotCls = cur ? 'bg-[var(--brand-blue)] text-white' : done ? 'bg-emerald-500 text-white' : 'bg-[var(--surface-2)] text-[var(--text-3)]';
      const barCls = idx < active ? 'bg-emerald-500' : 'bg-[var(--border)]';
      return h('div', { class: 'flex items-center flex-1 last:flex-initial' },
        h('div', { class: `w-8 h-8 rounded-full inline-flex items-center justify-center text-sm font-semibold ${dotCls}` }, String(idx)),
        h('span', { class: `ml-2 text-sm ${cur ? 'text-[var(--text)] font-medium' : 'text-[var(--text-3)]'}` }, label),
        idx < labels.length ? h('div', { class: `flex-1 h-px mx-3 ${barCls}` }) : null,
      );
    });
    return h('nav', { 'aria-label': t('onb.step.indicator', { current: active, total: 3 }), class: 'flex items-center' }, segs);
  }

  function StepBody() {
    if (state.step === 1) return Step1();
    if (state.step === 2) return Step2();
    return Step3();
  }

  function Step1() {
    const cards = Object.entries(FLAVORS).map(([id, f]) => {
      const sel = state.flavor === id;
      const border = sel ? 'border-[var(--brand-blue)] ring-2 ring-blue-300' : 'border-[var(--border)] hover:border-[var(--brand-blue)]';
      return h('button', {
        type: 'button', role: 'radio', 'aria-checked': sel ? 'true' : 'false',
        class: `relative w-full text-left rounded-2xl border ${border} bg-[var(--surface)] p-5 transition focus-visible:ring-4 focus-visible:ring-blue-300`,
        onClick: () => { state.flavor = id; render(); },
      },
        f.recommended ? h('span', { class: 'absolute top-3 right-3 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-200' }, t('onb.flavor.recommended')) : null,
        h('div', { class: 'flex items-start gap-3' },
          h('div', { class: 'text-2xl select-none', 'aria-hidden': 'true' }, f.iconChar),
          h('div', { class: 'flex-1' },
            h('div', { class: 'text-base font-semibold text-[var(--text)]' }, t(f.tk)),
            h('div', { class: 'mt-1 text-sm text-[var(--text-2)]' }, t(f.dk)),
            h('div', { class: 'mt-2 text-xs text-[var(--text-3)]' }, t(f.rk)),
          ),
        ),
      );
    });
    return h('section', { class: 'space-y-6' },
      h('header', null,
        h('h1', { class: 'text-2xl font-semibold text-[var(--text)]' }, t('onb.flavor.title')),
        h('p', { class: 'mt-1 text-sm text-[var(--text-3)]' }, t('onb.flavor.sub')),
      ),
      h('div', { role: 'radiogroup', 'aria-label': t('onb.flavor.title'), class: 'space-y-3' }, cards),
      h('div', { class: 'flex justify-end' },
        Button({
          variant: 'primary', label: t('onb.btn.continue'), icon: 'arrow-right',
          disabled: !state.flavor,
          onClick: () => {
            if (!state.flavor) return;
            state.step = FLAVORS[state.flavor].needsKeys.length === 0 ? 3 : 2;
            render();
          },
        }),
      ),
    );
  }

  function Step2() {
    const flavor = FLAVORS[state.flavor];
    const form = h('form', { class: 'space-y-6', onSubmit: (e) => e.preventDefault() });
    flavor.needsKeys.forEach((id) => form.appendChild(KeyField(id)));
    const continueBtn = Button({
      variant: 'primary', label: t('onb.btn.continue'), icon: 'arrow-right',
      disabled: !canAdvanceFromKeys(),
      onClick: () => { state.step = 3; render(); },
    });
    return h('section', { class: 'space-y-6' },
      h('header', null,
        h('h1', { class: 'text-2xl font-semibold text-[var(--text)]' }, t('onb.keys.title')),
        h('p', { class: 'mt-1 text-sm text-[var(--text-3)]' }, t('onb.keys.sub')),
      ),
      form,
      h('div', { class: 'flex justify-between' },
        Button({ variant: 'ghost', label: t('onb.btn.back'), icon: 'arrow-left', onClick: () => { state.step = 1; render(); } }),
        continueBtn,
      ),
    );
  }

  function KeyField(id) {
    const spec = KEY_SPECS[id];
    const inputId = `onb-key-${id}`, helpId = `onb-help-${id}`, statusId = `onb-status-${id}`;
    const status = h('div', { id: statusId, class: 'min-h-5 text-xs', 'aria-live': 'polite' });
    const refresh = () => {
      const r = state.keyResults[id];
      status.replaceChildren();
      if (!r) return;
      if (r.pending) {
        status.className = 'min-h-5 text-xs text-[var(--text-3)]';
        status.textContent = t('onb.keys.test.pending');
      } else if (r.ok) {
        status.className = 'min-h-5 text-xs text-emerald-600 dark:text-emerald-400';
        status.textContent = t('onb.keys.test.ok', { model: r.model || spec.engine, ms: r.ms ?? '?' });
      } else {
        status.className = 'min-h-5 text-xs text-red-600 dark:text-red-400';
        status.textContent = r.formatBad ? t('onb.keys.format.bad') : t('onb.keys.test.fail', { msg: r.msg || 'unknown' });
      }
    };
    const input = h('input', {
      id: inputId, type: 'password', autocomplete: 'off', spellcheck: 'false',
      'aria-describedby': helpId, class: classes.input + ' mono text-sm',
      placeholder: spec.prefix + '…', value: state.keys[id],
    });
    input.addEventListener('input', () => {
      state.keys[id] = input.value;
      if (state.keyResults[id]?.ok) { state.keyResults[id] = null; refresh(); }
      const val = input.value.trim();
      if (val && !val.startsWith(spec.prefix)) {
        state.keyResults[id] = { ok: false, formatBad: true }; refresh();
      } else if (state.keyResults[id]?.formatBad) {
        state.keyResults[id] = null; refresh();
      }
      updateContinue();
    });
    const testBtn = Button({ variant: 'outline', label: t('btn.test'), icon: 'zap', onClick: () => doTest(id, input, refresh) });
    refresh();
    return h('div', { class: 'space-y-1.5' },
      h('label', { class: classes.label, for: inputId }, t(spec.lk)),
      input,
      h('div', { id: helpId, class: 'text-xs text-[var(--text-3)]' },
        h('a', { href: spec.url, target: '_blank', rel: 'noopener noreferrer', class: 'underline hover:text-[var(--brand-blue)]' }, t(spec.hk)),
      ),
      h('div', { class: 'flex items-center gap-3' }, testBtn, status),
    );
  }

  async function doTest(id, input, refresh) {
    const spec = KEY_SPECS[id];
    const val = (input.value || '').trim();
    if (!val) return;
    if (!val.startsWith(spec.prefix)) {
      state.keyResults[id] = { ok: false, formatBad: true }; refresh(); updateContinue(); return;
    }
    state.keyResults[id] = { pending: true }; refresh();
    try { await api.saveConfig({ [spec.configKey]: val }); }
    catch (e) { state.keyResults[id] = { ok: false, msg: e.message }; refresh(); updateContinue(); return; }
    const t0 = performance.now();
    try {
      const r = await api.testLlm({ engine: spec.engine });
      const ms = Math.round(performance.now() - t0);
      const ok = r && (r.ok === true || r.success === true || r.status === 'ok' || !r.error);
      state.keyResults[id] = ok
        ? { ok: true, model: r.model || r.model_name || spec.engine, ms: r.latency_ms ?? r.latency ?? ms }
        : { ok: false, msg: r?.error || r?.message || 'failed' };
    } catch (e) { state.keyResults[id] = { ok: false, msg: e.message }; }
    refresh(); updateContinue();
  }

  function canAdvanceFromKeys() {
    const flavor = FLAVORS[state.flavor];
    return !!flavor && flavor.needsKeys.every((id) => state.keyResults[id]?.ok === true);
  }

  function updateContinue() {
    if (state.step !== 2) return;
    const btn = root.querySelector('section .flex.justify-between > button:last-child');
    if (btn) btn.disabled = !canAdvanceFromKeys();
  }

  function Step3() {
    const resultBox = h('div', { class: 'rounded-xl border border-[var(--border)] bg-[var(--surface-2)] p-5 min-h-32', 'aria-live': 'polite' });
    const renderResult = () => {
      resultBox.replaceChildren();
      if (state.processing) {
        resultBox.appendChild(h('div', { class: 'text-sm text-[var(--text-3)] italic' }, t('onb.try.processing')));
      } else if (state.result?.final) {
        resultBox.appendChild(h('div', { class: 'text-lg font-medium text-[var(--text)] whitespace-pre-wrap' }, state.result.final));
        if (state.result.raw && state.result.raw !== state.result.final) {
          resultBox.appendChild(h('div', { class: 'mt-3 pt-3 border-t border-[var(--border)] text-xs text-[var(--text-3)]' },
            h('span', { class: 'font-medium' }, t('onb.try.result.raw') + ': '),
            h('span', { class: 'mono' }, state.result.raw),
          ));
        }
      } else {
        resultBox.appendChild(h('div', { class: 'text-sm text-[var(--text-3)]' }, t('onb.try.result.empty')));
      }
    };
    const recBtn = h('button', {
      type: 'button',
      class: 'w-28 h-28 rounded-full inline-flex items-center justify-center text-white shadow-lg transition focus-visible:ring-4 focus-visible:ring-blue-300',
      'aria-label': state.recording ? t('onb.try.stop') : t('onb.try.start'),
      onClick: () => toggleRecord(renderResult, recBtn),
    });
    paintRecBtn(recBtn);
    renderResult();
    return h('section', { class: 'space-y-6' },
      h('header', null,
        h('h1', { class: 'text-2xl font-semibold text-[var(--text)]' }, t('onb.try.title')),
        h('p', { class: 'mt-1 text-sm text-[var(--text-3)]' }, t('onb.try.hint')),
      ),
      h('div', { class: 'flex flex-col items-center gap-3' }, recBtn,
        h('div', { class: 'text-sm text-[var(--text-2)]' }, state.recording ? t('onb.try.stop') : t('onb.try.start')),
      ),
      resultBox,
      h('div', { class: 'flex justify-between' },
        Button({ variant: 'ghost', label: t('onb.try.skip'), onClick: () => finish(true) }),
        Button({ variant: 'primary', label: t('onb.try.done'), icon: 'check', onClick: () => finish(false) }),
      ),
    );
  }

  function paintRecBtn(btn) {
    const motionOk = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    btn.replaceChildren();
    if (state.recording) {
      btn.className = `w-28 h-28 rounded-full inline-flex items-center justify-center text-white shadow-lg bg-red-600 transition focus-visible:ring-4 focus-visible:ring-red-300 ${motionOk ? 'animate-pulse' : ''}`;
      btn.appendChild(h('i', { 'data-lucide': 'square', class: 'w-10 h-10' }));
      btn.disabled = false;
    } else if (state.processing) {
      btn.className = 'w-28 h-28 rounded-full inline-flex items-center justify-center text-white shadow-lg bg-[var(--brand-purple)] transition';
      btn.appendChild(h('i', { 'data-lucide': 'loader-2', class: `w-10 h-10 ${motionOk ? 'animate-spin' : ''}` }));
      btn.disabled = true;
    } else {
      btn.className = 'w-28 h-28 rounded-full inline-flex items-center justify-center text-white shadow-lg bg-[var(--brand-blue)] hover:bg-blue-700 transition focus-visible:ring-4 focus-visible:ring-blue-300';
      btn.appendChild(h('i', { 'data-lucide': 'mic', class: 'w-10 h-10' }));
      btn.disabled = false;
    }
    if (window.lucide) window.lucide.createIcons();
  }

  async function toggleRecord(renderResult, recBtn) {
    if (state.processing) return;
    if (!state.recording) {
      try { await api.startRecording(); state.recording = true; paintRecBtn(recBtn); }
      catch (e) { Toast({ message: e.message, type: 'error' }); }
      return;
    }
    try { await api.stopRecording(); } catch (e) { Toast({ message: e.message, type: 'error' }); }
    state.recording = false; state.processing = true; paintRecBtn(recBtn); renderResult();
    await pollUntilDone();
    state.processing = false;
    try {
      const hist = await api.getHistory({ limit: 1 });
      const items = Array.isArray(hist) ? hist : (hist?.items || hist?.history || []);
      const latest = items[0];
      if (latest) state.result = { final: latest.final_text || latest.text || '', raw: latest.whisper_raw || latest.raw || '' };
    } catch { /* ignore */ }
    paintRecBtn(recBtn); renderResult();
  }

  async function pollUntilDone() {
    for (let i = 0; i < 60; i++) {
      try {
        const s = await api.getRecordingStatus();
        const st = s?.state || s?.status;
        if (st && st !== 'recording' && st !== 'processing') return;
      } catch { /* ignore */ }
      await new Promise((r) => setTimeout(r, 500));
    }
  }

  async function finish(skip) {
    if (skip) { location.hash = '#/'; return; }
    const flavor = FLAVORS[state.flavor];
    if (!flavor) { location.hash = '#/'; return; }
    const partial = { ...flavor.config };
    flavor.needsKeys.forEach((id) => {
      const spec = KEY_SPECS[id];
      const val = (state.keys[id] || '').trim();
      if (val) partial[spec.configKey] = val;
    });
    try {
      await api.saveConfig(partial);
      Toast({ message: t('onb.toast.saved'), type: 'success' });
    } catch (e) {
      Toast({ message: t('onb.toast.save.fail') + ': ' + e.message, type: 'error' });
    }
    location.hash = '#/';
  }
}
