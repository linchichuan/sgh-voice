// pages/dictionary.js — Dictionary page (5 tabs + top actions).
// Tabs: Custom words / Corrections / Scene / App / Smart Replace.
// Top actions: Promote from history / Cleanup bad rules.

import { h, classes, Button, Tabs, ConfirmDialog } from '../lib/components.js';
import { t } from '../lib/i18n.js';
import * as api from '../lib/api.js';

import mountWords from './dictionary/custom-words.js';
import mountCorrections from './dictionary/corrections.js';
import mountSceneCorrections from './dictionary/scene-corrections.js';
import mountAppCorrections from './dictionary/app-corrections.js';
import mountSmartReplace from './dictionary/smart-replace.js';
import { openPromoteModal } from './dictionary/promote-modal.js';
import { toastOk, toastErr } from './dictionary/util.js';

const TABS = [
  { id: 'words',       labelKey: 'dict.tab.words',       mount: mountWords },
  { id: 'corrections', labelKey: 'dict.tab.corrections', mount: mountCorrections },
  { id: 'scene',       labelKey: 'dict.tab.scene',       mount: mountSceneCorrections },
  { id: 'app',         labelKey: 'dict.tab.app',         mount: mountAppCorrections },
  { id: 'smart',       labelKey: 'dict.tab.smart',       mount: mountSmartReplace },
];

export default async function mount(slot) {
  let activeId = readActiveTabFromHash();
  if (!TABS.some((t2) => t2.id === activeId)) activeId = TABS[0].id;

  const root = h('div', { class: 'space-y-4' });
  slot.replaceChildren(root);

  // ── Header: title + top action buttons ────────────────────────────────
  const tabBarHost = h('div');
  const tabBodyHost = h('div', { id: 'dict-tab-body' });

  const promoteBtn = Button({
    variant: 'outline',
    icon: 'sparkles',
    label: t('dict.action.promote'),
    onClick: () => openPromoteModal(() => rerenderActive()),
  });
  const cleanupBtn = Button({
    variant: 'outline',
    icon: 'broom',
    label: t('dict.action.cleanup'),
    onClick: () => {
      ConfirmDialog({
        title: t('dict.cleanup.title'),
        message: t('dict.cleanup.message'),
        confirmText: t('btn.confirm'),
        danger: true,
        onConfirm: async () => {
          try {
            const res = await api.cleanupDictionary();
            toastOk(t('dict.cleanup.done', { n: res?.removed_count ?? 0 }));
            rerenderActive();
          } catch (e) { toastErr(e.message); }
        },
      });
    },
  });

  const header = h('header', { class: 'flex items-center justify-between gap-3 flex-wrap' },
    h('div', null,
      h('h1', { class: 'text-2xl font-semibold text-[var(--text)]' }, t('page.dictionary.title')),
    ),
    h('div', { class: 'flex items-center gap-2 flex-wrap' }, promoteBtn, cleanupBtn),
  );

  root.appendChild(header);
  root.appendChild(tabBarHost);
  root.appendChild(tabBodyHost);

  const renderTabs = () => {
    const tabs = TABS.map((tab) => ({ id: tab.id, label: t(tab.labelKey) }));
    const bar = Tabs({
      tabs,
      active: activeId,
      onChange: (id) => {
        if (id === activeId) return;
        activeId = id;
        writeActiveTabToHash(id);
        renderTabs();
        renderActiveBody();
      },
    });
    tabBarHost.replaceChildren(bar);
  };

  const renderActiveBody = async () => {
    tabBodyHost.replaceChildren(
      h('div', { class: 'p-8 text-center text-[var(--text-3)]' }, '…'),
    );
    const tab = TABS.find((t2) => t2.id === activeId) || TABS[0];
    const slotEl = h('div', { class: 'space-y-4' });
    tabBodyHost.replaceChildren(slotEl);
    try {
      await tab.mount(slotEl);
    } catch (e) {
      slotEl.appendChild(h('div', { class: `${classes.card} text-[var(--danger)]` }, `Error: ${e.message}`));
    }
    if (window.lucide) window.lucide.createIcons();
  };

  const rerenderActive = () => { renderActiveBody(); };

  // Re-render tab labels on language change so they stay localised.
  window.addEventListener('langchange', renderTabs);

  renderTabs();
  await renderActiveBody();
}

// ── Hash sub-route helpers ────────────────────────────────────────────────
function readActiveTabFromHash() {
  const m = (location.hash || '').match(/^#\/dictionary\/([\w-]+)/);
  return m ? m[1] : '';
}
function writeActiveTabToHash(id) {
  // Use history.replaceState to avoid triggering hashchange → re-mount.
  const next = `#/dictionary/${id}`;
  if (location.hash !== next) {
    history.replaceState(null, '', next);
  }
}
