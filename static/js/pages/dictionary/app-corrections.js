// pages/dictionary/app-corrections.js — app-scoped corrections selector.

import { h, classes, Button, EmptyState } from '../../lib/components.js';
import { t } from '../../lib/i18n.js';
import * as api from '../../lib/api.js';
import { Section, LabeledInput, PairTable, confirmRemove, filterMapEntries, toastOk, toastErr } from './util.js';

export default async function mount(container) {
  let globalPayload;
  try { globalPayload = await api.getDictionary(); }
  catch (e) { container.appendChild(h('div', { class: classes.card }, `Error: ${e.message}`)); return; }

  const existingApps = Array.from(new Set(globalPayload.app_ids || []));
  let activeApp = existingApps[0] || '';
  let map = {};
  let search = '';

  const selectId = 'dict-app-select';
  const select = h('select', {
    id: selectId,
    class: classes.input,
    'aria-label': t('dict.app.select'),
  });
  const renderOptions = () => {
    select.replaceChildren();
    if (!existingApps.length) {
      select.appendChild(h('option', { value: '' }, t('dict.app.none')));
      return;
    }
    existingApps.forEach((k) => {
      const opt = h('option', { value: k, selected: k === activeApp ? '' : null }, k);
      select.appendChild(opt);
    });
  };
  renderOptions();
  const selectorLabel = h('label', { for: selectId, class: classes.label }, t('dict.app.select'));

  const { wrap: newAppWrap, input: newAppInput } = LabeledInput({
    label: t('dict.col.app'),
    placeholder: t('dict.placeholder.app'),
    srOnly: true,
  });
  const addAppBtn = Button({
    variant: 'outline', icon: 'plus', label: t('dict.col.app'),
    onClick: () => {
      const v = newAppInput.value.trim();
      if (!v || existingApps.includes(v)) return;
      existingApps.push(v);
      activeApp = v;
      newAppInput.value = '';
      renderOptions();
      loadActive();
    },
  });

  const { wrap: wrongWrap, input: wrongInput } = LabeledInput({ label: t('dict.col.wrong'), placeholder: t('dict.placeholder.wrong'), srOnly: true });
  const { wrap: rightWrap, input: rightInput } = LabeledInput({ label: t('dict.col.right'), placeholder: t('dict.placeholder.right'), srOnly: true });
  const addPairBtn = Button({
    variant: 'primary', icon: 'plus', label: t('dict.btn.add'),
    onClick: async () => {
      const w = wrongInput.value.trim();
      const r = rightInput.value.trim();
      if (!w || !r || !activeApp) return;
      try {
        const res = await api.addAppCorrection({ app_id: activeApp, wrong: w, right: r });
        if (res && res.ok === false) { toastErr(t('dict.rejected')); return; }
        map[w] = r;
        wrongInput.value = ''; rightInput.value = '';
        render();
        toastOk();
      } catch (e) { toastErr(e.message); }
    },
  });
  [wrongInput, rightInput].forEach((el) =>
    el.addEventListener('keydown', (e) => { if (e.key === 'Enter') addPairBtn.click(); }),
  );

  const { wrap: searchWrap, input: searchInput } = LabeledInput({
    label: t('dict.placeholder.search'),
    placeholder: t('dict.placeholder.search'),
    srOnly: true,
  });
  searchInput.addEventListener('input', () => { search = searchInput.value; render(); });

  const listHost = h('div', { class: 'mt-4' });

  const render = () => {
    if (!activeApp) {
      listHost.replaceChildren(EmptyState({ icon: 'app-window', title: t('dict.app.none') }));
      if (window.lucide) window.lucide.createIcons();
      return;
    }
    listHost.replaceChildren(
      PairTable({
        entries: filterMapEntries(map, search),
        leftCol: t('dict.col.wrong'),
        rightCol: t('dict.col.right'),
        emptyTitle: t('dict.empty.app'),
        onDelete: (wrong) => {
          confirmRemove({
            title: t('btn.delete'),
            message: `[${activeApp}] ${wrong} → ${map[wrong] ?? ''}`,
            onConfirm: async () => {
              try {
                await api.removeAppCorrection({ app_id: activeApp, wrong });
                delete map[wrong]; render(); toastOk();
              } catch (e) { toastErr(e.message); }
            },
          });
        },
      }),
    );
    if (window.lucide) window.lucide.createIcons();
  };

  const loadActive = async () => {
    if (!activeApp) { map = {}; render(); return; }
    try {
      const resp = await fetch(`/api/dictionary?layer=${encodeURIComponent(`app:${activeApp}`)}`, { credentials: 'same-origin' });
      const data = await resp.json();
      map = { ...(data.corrections || {}) };
    } catch (e) { map = {}; toastErr(e.message); }
    render();
  };

  select.addEventListener('change', () => { activeApp = select.value; loadActive(); });

  container.appendChild(Section({
    title: t('dict.tab.app'),
    headerRight: h('div', { class: 'min-w-[10rem]' }, searchWrap),
    children: [
      h('div', { class: 'grid grid-cols-1 md:grid-cols-[1fr_auto] gap-3 items-end' },
        h('div', null, selectorLabel, select),
        h('div', { class: 'flex gap-2 items-end' }, newAppWrap, addAppBtn),
      ),
      h('div', { class: 'flex gap-2 items-end flex-wrap mt-3' }, wrongWrap, rightWrap, addPairBtn),
      listHost,
    ],
  }));
  await loadActive();
}
