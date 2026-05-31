// pages/dictionary/scene-corrections.js — scene-scoped corrections selector.

import { h, classes, Button, EmptyState } from '../../lib/components.js';
import { t } from '../../lib/i18n.js';
import * as api from '../../lib/api.js';
import { Section, LabeledInput, PairTable, confirmRemove, filterMapEntries, toastOk, toastErr } from './util.js';

const KNOWN_SCENES = ['general', 'medical'];

export default async function mount(container) {
  // Fetch global view first so we know which scene keys already have entries.
  let globalPayload;
  try { globalPayload = await api.getDictionary(); }
  catch (e) { container.appendChild(h('div', { class: classes.card }, `Error: ${e.message}`)); return; }

  const existingScenes = Array.from(new Set([
    ...KNOWN_SCENES,
    ...(globalPayload.scene_keys || []),
  ]));

  let activeScene = existingScenes[0] || 'general';
  let map = {};
  let search = '';

  // Scene selector — labelled <select>.
  const selectId = 'dict-scene-select';
  const select = h('select', {
    id: selectId,
    class: classes.input,
    'aria-label': t('dict.scene.select'),
  });
  const renderOptions = () => {
    select.replaceChildren();
    existingScenes.forEach((k) => {
      const opt = h('option', { value: k, selected: k === activeScene ? '' : null }, k);
      select.appendChild(opt);
    });
  };
  renderOptions();
  const selectorLabel = h('label', { for: selectId, class: classes.label }, t('dict.scene.select'));

  // Add new scene inline.
  const { wrap: newSceneWrap, input: newSceneInput } = LabeledInput({
    label: t('dict.col.scene'),
    placeholder: t('dict.placeholder.scene'),
    srOnly: true,
  });
  const addSceneBtn = Button({
    variant: 'outline', icon: 'plus', label: t('dict.col.scene'),
    onClick: () => {
      const v = newSceneInput.value.trim();
      if (!v || existingScenes.includes(v)) return;
      existingScenes.push(v);
      activeScene = v;
      newSceneInput.value = '';
      renderOptions();
      loadActive();
    },
  });

  // Pair add row.
  const { wrap: wrongWrap, input: wrongInput } = LabeledInput({ label: t('dict.col.wrong'), placeholder: t('dict.placeholder.wrong'), srOnly: true });
  const { wrap: rightWrap, input: rightInput } = LabeledInput({ label: t('dict.col.right'), placeholder: t('dict.placeholder.right'), srOnly: true });
  const addPairBtn = Button({
    variant: 'primary', icon: 'plus', label: t('dict.btn.add'),
    onClick: async () => {
      const w = wrongInput.value.trim();
      const r = rightInput.value.trim();
      if (!w || !r || !activeScene) return;
      try {
        const res = await api.addSceneCorrection({ scene: activeScene, wrong: w, right: r });
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

  // Search input.
  const { wrap: searchWrap, input: searchInput } = LabeledInput({
    label: t('dict.placeholder.search'),
    placeholder: t('dict.placeholder.search'),
    srOnly: true,
  });
  searchInput.addEventListener('input', () => { search = searchInput.value; render(); });

  const listHost = h('div', { class: 'mt-4' });

  const render = () => {
    if (!activeScene) {
      listHost.replaceChildren(EmptyState({ icon: 'layers', title: t('dict.scene.none') }));
      if (window.lucide) window.lucide.createIcons();
      return;
    }
    listHost.replaceChildren(
      PairTable({
        entries: filterMapEntries(map, search),
        leftCol: t('dict.col.wrong'),
        rightCol: t('dict.col.right'),
        emptyTitle: t('dict.empty.scene'),
        onDelete: (wrong) => {
          confirmRemove({
            title: t('btn.delete'),
            message: `[${activeScene}] ${wrong} → ${map[wrong] ?? ''}`,
            onConfirm: async () => {
              try {
                await api.removeSceneCorrection({ scene: activeScene, wrong });
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
    if (!activeScene) { map = {}; render(); return; }
    try {
      const res = await api.getDictionary();
      // We need scene-specific: re-fetch via layer param.
      const resp = await fetch(`/api/dictionary?layer=${encodeURIComponent(`scene:${activeScene}`)}`, { credentials: 'same-origin' });
      const data = await resp.json();
      map = { ...(data.corrections || {}) };
    } catch (e) { map = {}; toastErr(e.message); }
    render();
  };

  select.addEventListener('change', () => { activeScene = select.value; loadActive(); });

  container.appendChild(Section({
    title: t('dict.tab.scene'),
    headerRight: h('div', { class: 'min-w-[10rem]' }, searchWrap),
    children: [
      h('div', { class: 'grid grid-cols-1 md:grid-cols-[1fr_auto] gap-3 items-end' },
        h('div', null, selectorLabel, select),
        h('div', { class: 'flex gap-2 items-end' }, newSceneWrap, addSceneBtn),
      ),
      h('div', { class: 'flex gap-2 items-end flex-wrap mt-3' }, wrongWrap, rightWrap, addPairBtn),
      listHost,
    ],
  }));
  await loadActive();
}
