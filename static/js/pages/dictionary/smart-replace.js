// pages/dictionary/smart-replace.js — trigger→replacement map.

import { h, classes, Button } from '../../lib/components.js';
import { t } from '../../lib/i18n.js';
import * as api from '../../lib/api.js';
import { Section, LabeledInput, PairTable, confirmRemove, filterMapEntries, toastOk, toastErr } from './util.js';

export default async function mount(container) {
  let rules;
  try { rules = await api.getSmartReplace(); }
  catch (e) { container.appendChild(h('div', { class: classes.card }, `Error: ${e.message}`)); return; }
  let map = { ...(rules || {}) };
  let search = '';

  const listHost = h('div', { class: 'mt-4' });

  const persist = async () => {
    try { await api.saveSmartReplace(map); toastOk(); }
    catch (e) { toastErr(e.message); }
  };

  const render = () => {
    listHost.replaceChildren(
      PairTable({
        entries: filterMapEntries(map, search),
        leftCol: t('dict.col.trigger'),
        rightCol: t('dict.col.replacement'),
        emptyTitle: t('dict.empty.smart'),
        onDelete: (key) => {
          confirmRemove({
            title: t('btn.delete'),
            message: `${key} → ${map[key] ?? ''}`,
            onConfirm: async () => {
              delete map[key];
              await persist();
              render();
            },
          });
        },
      }),
    );
    if (window.lucide) window.lucide.createIcons();
  };

  const { wrap: trigWrap, input: trigInput } = LabeledInput({
    label: t('dict.col.trigger'),
    placeholder: t('dict.placeholder.trigger'),
    srOnly: true,
  });
  const { wrap: replWrap, input: replInput } = LabeledInput({
    label: t('dict.col.replacement'),
    placeholder: t('dict.placeholder.replacement'),
    srOnly: true,
  });
  const addBtn = Button({
    variant: 'primary', icon: 'plus', label: t('dict.btn.add'),
    onClick: async () => {
      const k = trigInput.value.trim();
      const v = replInput.value.trim();
      if (!k || !v) return;
      map[k] = v;
      await persist();
      trigInput.value = ''; replInput.value = '';
      render();
    },
  });
  [trigInput, replInput].forEach((el) =>
    el.addEventListener('keydown', (e) => { if (e.key === 'Enter') addBtn.click(); }),
  );

  const { wrap: searchWrap, input: searchInput } = LabeledInput({
    label: t('dict.placeholder.search'),
    placeholder: t('dict.placeholder.search'),
    srOnly: true,
  });
  searchInput.addEventListener('input', () => { search = searchInput.value; render(); });

  container.appendChild(Section({
    title: t('dict.tab.smart'),
    headerRight: h('div', { class: 'min-w-[10rem]' }, searchWrap),
    children: [
      h('div', { class: 'flex gap-2 items-end flex-wrap' }, trigWrap, replWrap, addBtn),
      listHost,
    ],
  }));
  render();
}
