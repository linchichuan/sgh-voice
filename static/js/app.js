// app.js — router, theme, language, live recording header.

import * as api from './lib/api.js';
import { t, setLang, getLang, applyI18n } from './lib/i18n.js';
import { Toast } from './lib/components.js';

const THEME_KEY = 'sgh-voice-theme';
const POLL_IDLE_MS = 1000;
const POLL_ACTIVE_MS = 250;

const routes = {
  '#/':            () => import('./pages/dashboard.js'),
  '#/history':     () => import('./pages/history.js'),
  '#/dictionary':  () => import('./pages/dictionary.js'),
  '#/settings':    () => import('./pages/settings.js'),
  '#/voiceprint':  () => import('./pages/voiceprint.js'),
  '#/cost-audit':  () => import('./pages/cost-audit.js'),
  '#/models':      () => import('./pages/models.js'),
  '#/onboarding':  () => import('./pages/onboarding.js'),
};

// ---------- Theme ----------
function applyTheme(theme) {
  // theme: 'light' | 'dark' | 'system'
  let effective = theme;
  if (theme === 'system') {
    effective = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  if (effective === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.removeAttribute('data-theme');
    document.documentElement.classList.remove('dark');
  }
  // Update icon
  const btn = document.getElementById('theme-toggle');
  if (btn) {
    btn.replaceChildren(iconEl(effective === 'dark' ? 'sun' : 'moon'));
    refreshIcons();
  }
}

function iconEl(name) {
  const i = document.createElement('i');
  i.setAttribute('data-lucide', name);
  i.className = 'w-4 h-4';
  return i;
}

function getStoredTheme() {
  try { return localStorage.getItem(THEME_KEY) || 'system'; } catch { return 'system'; }
}

function setStoredTheme(v) {
  try { localStorage.setItem(THEME_KEY, v); } catch { /* ignore */ }
}

function initTheme() {
  applyTheme(getStoredTheme());
  // React to system changes when user chose 'system'
  const mq = window.matchMedia('(prefers-color-scheme: dark)');
  mq.addEventListener('change', () => {
    if (getStoredTheme() === 'system') applyTheme('system');
  });

  const btn = document.getElementById('theme-toggle');
  if (btn) {
    btn.addEventListener('click', () => {
      const current = getStoredTheme();
      const next = current === 'dark' ? 'light' : 'dark';
      setStoredTheme(next);
      applyTheme(next);
    });
  }
}

// ---------- Language ----------
function initLang() {
  const lang = getLang();
  document.documentElement.setAttribute('lang', lang === 'zh' ? 'zh-TW' : lang);
  syncLangLabel(lang);
  applyI18n(document);

  const toggle = document.getElementById('lang-toggle');
  const menu = document.getElementById('lang-menu');
  if (toggle && menu) {
    toggle.addEventListener('click', () => {
      const expanded = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', String(!expanded));
      menu.classList.toggle('hidden', expanded);
    });
    document.addEventListener('click', (e) => {
      if (!toggle.contains(e.target) && !menu.contains(e.target)) {
        toggle.setAttribute('aria-expanded', 'false');
        menu.classList.add('hidden');
      }
    });
    menu.querySelectorAll('[data-lang]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const code = btn.getAttribute('data-lang');
        setLang(code);
        toggle.setAttribute('aria-expanded', 'false');
        menu.classList.add('hidden');
      });
    });
  }

  window.addEventListener('langchange', (e) => {
    syncLangLabel(e.detail?.lang || getLang());
    applyI18n(document);
  });
}

function syncLangLabel(lang) {
  const el = document.getElementById('lang-current');
  if (!el) return;
  el.textContent = lang === 'zh' ? '繁體中文' : lang === 'en' ? 'English' : '日本語';
}

// ---------- Live recording status ----------
let recPollTimer = null;
let recCurrentState = 'idle';

async function tickRecordingStatus() {
  try {
    const data = await api.getRecordingStatus();
    const state = (data && data.state) || 'idle';
    if (state !== recCurrentState) {
      recCurrentState = state;
      renderRecStatus(state, data);
    } else if (state === 'recording') {
      // Update timer label even when state unchanged
      renderRecStatus(state, data);
    }
    scheduleNextPoll(state);
  } catch (e) {
    // silent
    scheduleNextPoll('idle');
  }
}

function scheduleNextPoll(state) {
  clearTimeout(recPollTimer);
  const delay = state === 'recording' ? POLL_ACTIVE_MS : POLL_IDLE_MS;
  recPollTimer = setTimeout(tickRecordingStatus, delay);
}

function renderRecStatus(state, data) {
  const wrap = document.getElementById('rec-status');
  if (!wrap) return;
  wrap.setAttribute('data-state', state);
  const label = wrap.querySelector('.rec-label');
  if (!label) return;
  if (state === 'recording') {
    const sec = Math.floor((data && data.elapsed_seconds) || 0);
    const mm = String(Math.floor(sec / 60)).padStart(2, '0');
    const ss = String(sec % 60).padStart(2, '0');
    label.textContent = `${t('rec.recording')} ${mm}:${ss}`;
  } else if (state === 'processing') {
    label.textContent = t('rec.processing');
  } else {
    label.textContent = t('rec.idle');
  }
}

function initRecordingPolling() {
  renderRecStatus('idle', null);
  tickRecordingStatus();
}

// ---------- Service status pills ----------
async function loadServiceStatus() {
  const wrap = document.getElementById('service-status-pills');
  if (!wrap) return;
  try {
    const status = await api.getServiceStatus();
    wrap.replaceChildren();
    const items = [];
    if (status) {
      if ('ollama_running' in status) items.push({ label: 'Ollama', ok: !!status.ollama_running });
      if ('has_anthropic_key' in status) items.push({ label: 'Claude', ok: !!status.has_anthropic_key });
      if ('has_openai_key' in status) items.push({ label: 'OpenAI', ok: !!status.has_openai_key });
      if ('has_groq_key' in status) items.push({ label: 'Groq', ok: !!status.has_groq_key });
      if ('has_openrouter_key' in status) items.push({ label: 'OpenRouter', ok: !!status.has_openrouter_key });
    }
    items.forEach((it) => {
      const pill = document.createElement('span');
      pill.className = `inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${it.ok ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200' : 'bg-[var(--surface-2)] text-[var(--text-3)]'}`;
      const dot = document.createElement('span');
      dot.className = `w-1.5 h-1.5 rounded-full ${it.ok ? 'bg-emerald-500' : 'bg-[var(--text-3)]'}`;
      pill.appendChild(dot);
      pill.appendChild(document.createTextNode(it.label));
      wrap.appendChild(pill);
    });
  } catch {
    // ignore
  }
}

// ---------- Router ----------
function refreshIcons() {
  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }
}

function highlightActiveNav() {
  const hash = location.hash || '#/';
  document.querySelectorAll('[data-route]').forEach((a) => {
    if (a.getAttribute('data-route') === hash) {
      a.setAttribute('aria-current', 'page');
    } else {
      a.removeAttribute('aria-current');
    }
  });
}

async function mount() {
  const hash = location.hash || '#/';
  const slot = document.getElementById('page-slot');
  if (!slot) return;
  slot.innerHTML = '';
  const loading = document.createElement('div');
  loading.className = 'p-8 text-center text-[var(--text-3)]';
  loading.textContent = 'Loading…';
  slot.appendChild(loading);

  const route = routes[hash] || routes['#/'];
  try {
    const mod = await route();
    slot.innerHTML = '';
    await mod.default(slot);
  } catch (e) {
    console.error('[router] mount failed', e);
    slot.innerHTML = '';
    const err = document.createElement('div');
    err.className = 'p-8 text-center';
    err.innerHTML = `<h1 class="text-lg font-semibold text-[var(--danger)] mb-2">Failed to load page</h1><p class="text-sm text-[var(--text-3)]"></p>`;
    err.querySelector('p').textContent = e.message;
    slot.appendChild(err);
  }
  refreshIcons();
  highlightActiveNav();
  applyI18n(slot);
}

// ---------- Onboarding redirect ----------
async function shouldRedirectToOnboarding() {
  if (location.hash === '#/onboarding') return false;
  try {
    const cfg = await api.getConfig();
    const keys = ['groq_api_key', 'openai_api_key', 'anthropic_api_key', 'openrouter_api_key'];
    return !keys.some((k) => !!(cfg && cfg[k]));
  } catch {
    return false;
  }
}

// ---------- Boot ----------
window.addEventListener('hashchange', mount);
window.addEventListener('load', async () => {
  initTheme();
  initLang();
  refreshIcons();

  if (await shouldRedirectToOnboarding()) {
    location.hash = '#/onboarding';
  }

  await mount();
  initRecordingPolling();
  loadServiceStatus();
  // refresh service status every 30s
  setInterval(loadServiceStatus, 30000);
});

// Expose for debugging
window.__sghVoice = { api, Toast };
