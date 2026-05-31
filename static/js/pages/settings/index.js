// pages/settings/index.js — mount + tab orchestration for #/settings.
// Each tab module owns its own DOM + dirty-tracking; index merges payloads on Save.
import { h, classes, Tabs, Button, Toast } from '../../lib/components.js';
import { t } from '../../lib/i18n.js';
import * as api from '../../lib/api.js';
import { registerSettingsStrings } from './i18n-strings.js';
import { createDirty } from './dirty.js';
import { mountApiKeysTab } from './api-keys.js';
import { mountSttTab } from './stt.js';
import { mountLlmTab } from './llm.js';
import { mountHotkeysTab } from './hotkeys.js';
import { mountPrivacyTab } from './privacy.js';
import { mountAdvancedTab } from './advanced.js';

const TABS = [
  { id: 'keys',     i18n: 'settings.tab.keys',     mounter: mountApiKeysTab },
  { id: 'stt',      i18n: 'settings.tab.stt',      mounter: mountSttTab },
  { id: 'llm',      i18n: 'settings.tab.llm',      mounter: mountLlmTab },
  { id: 'hotkeys',  i18n: 'settings.tab.hotkeys',  mounter: mountHotkeysTab },
  { id: 'privacy',  i18n: 'settings.tab.privacy',  mounter: mountPrivacyTab },
  { id: 'advanced', i18n: 'settings.tab.advanced', mounter: mountAdvancedTab },
];

function getActiveTabFromHash() {
  const m = /[?&]tab=([^&]+)/.exec(location.hash);
  if (!m) return 'keys';
  const id = decodeURIComponent(m[1]);
  return TABS.some((t) => t.id === id) ? id : 'keys';
}

function setActiveTabInHash(id) {
  // Preserve base #/settings, swap ?tab= query
  const base = location.hash.split('?')[0] || '#/settings';
  history.replaceState(null, '', `${base}?tab=${encodeURIComponent(id)}`);
}

function buildPayload(dirty) {
  const raw = dirty.payload();
  // Strip undefined and empty-string keys for *_api_key fields (empty=unchanged).
  const out = {};
  for (const [k, v] of Object.entries(raw)) {
    if (v === undefined) continue;
    if (k.endsWith('_api_key') && (v === '' || v == null)) continue;
    // Extra paranoia: never ship a value that looks like a masked key
    if (k.endsWith('_api_key') && typeof v === 'string' && /^[•*]{2,}/.test(v.trim())) continue;
    out[k] = v;
  }
  return out;
}

export default async function mount(slot) {
  registerSettingsStrings();

  // Initial config snapshot — single source of truth for all tabs.
  let cfg;
  try {
    cfg = await api.getConfig();
  } catch (err) {
    slot.replaceChildren(h('div', { class: 'p-8 text-[var(--text-3)]' }, `${t('toast.error')}: ${err.message || err}`));
    return;
  }

  // One dirty store shared across tabs — keys are config field names.
  const dirty = createDirty(cfg);

  // Page chrome
  const header = h('header', { class: 'mb-6' },
    h('h1', { class: 'text-2xl font-semibold text-[var(--text)]' }, t('page.settings.title')),
  );

  const tabBar = h('div');
  const tabContent = h('div', { class: 'space-y-6' });

  // Sticky save bar
  const savedHint = h('span', { class: 'text-xs text-[var(--text-3)]', role: 'status', 'aria-live': 'polite' }, '');
  const saveBtn = Button({
    variant: 'primary',
    icon: 'save',
    label: t('settings.save'),
    onClick: async () => {
      const payload = buildPayload(dirty);
      if (Object.keys(payload).length === 0) {
        Toast({ message: t('settings.no.changes'), type: 'info' });
        return;
      }
      saveBtn.disabled = true;
      savedHint.textContent = '…';
      try {
        await api.saveConfig(payload);
        dirty.commit();
        // refresh cfg snapshot so subsequent dirty tracking compares against new baseline
        Object.assign(cfg, payload);
        Toast({ message: t('settings.saved.notice'), type: 'success' });
        savedHint.textContent = '';
      } catch (err) {
        Toast({ message: `${t('toast.error')}: ${err.message || err}`, type: 'error' });
        savedHint.textContent = '';
      } finally {
        saveBtn.disabled = false;
      }
    },
  });
  const saveBar = h('div', {
    class: 'sticky bottom-0 mt-8 -mx-2 px-2 py-3 bg-[var(--surface)]/95 backdrop-blur border-t border-[var(--border)] flex items-center justify-end gap-3',
  }, savedHint, saveBtn);

  const renderTab = (activeId) => {
    tabContent.replaceChildren();
    tabBar.replaceChildren(Tabs({
      tabs: TABS.map((tab) => ({ id: tab.id, label: t(tab.i18n) })),
      active: activeId,
      onChange: (next) => {
        setActiveTabInHash(next);
        renderTab(next);
      },
    }));
    const def = TABS.find((tab) => tab.id === activeId) || TABS[0];
    try {
      def.mounter(tabContent, cfg, dirty);
    } catch (err) {
      tabContent.appendChild(h('div', { class: 'p-4 text-red-600 dark:text-red-400' }, `Failed to mount tab: ${err.message || err}`));
    }
    if (window.lucide) window.lucide.createIcons();
  };

  slot.replaceChildren(h('div', { class: 'p-6 max-w-4xl mx-auto' }, header, tabBar, tabContent, saveBar));
  renderTab(getActiveTabFromHash());
  if (window.lucide) window.lucide.createIcons();
}
