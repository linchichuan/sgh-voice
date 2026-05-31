// pages/dictionary/corrections.js — user-scope wrong→right rules.

import { h, classes, Button } from '../../lib/components.js';
import { t } from '../../lib/i18n.js';
import * as api from '../../lib/api.js';
import { Section, LabeledInput, PairTable, confirmRemove, filterMapEntries, toastOk, toastErr } from './util.js';

export default async function mount(container) {
  let payload;
  try { payload = await api.getDictionary(); }
  catch (e) { container.appendChild(h('div', { class: classes.card }, `Error: ${e.message}`)); return; }

  // /api/dictionary?layer=global returns corrections = memory.get_all_corrections() (the user dict).
  let map = { ...(payload.corrections || {}) };

  let search = '';
  const listHost = h('div', { class: 'mt-4' });

  const render = () => {
    listHost.replaceChildren(
      PairTable({
        entries: filterMapEntries(map, search),
        leftCol: t('dict.col.wrong'),
        rightCol: t('dict.col.right'),
        emptyTitle: t('dict.empty.corrections'),
        onDelete: (wrong) => {
          confirmRemove({
            title: t('btn.delete'),
            message: `${wrong} → ${map[wrong] ?? ''}`,
            onConfirm: async () => {
              try {
                await api.removeCorrection({ wrong });
                delete map[wrong];
                render();
                toastOk();
              } catch (e) { toastErr(e.message); }
            },
          });
        },
      }),
    );
    if (window.lucide) window.lucide.createIcons();
  };

  const { wrap: wrongWrap, input: wrongInput } = LabeledInput({
    label: t('dict.col.wrong'),
    placeholder: t('dict.placeholder.wrong'),
    srOnly: true,
  });
  const { wrap: rightWrap, input: rightInput } = LabeledInput({
    label: t('dict.col.right'),
    placeholder: t('dict.placeholder.right'),
    srOnly: true,
  });
  const addBtn = Button({
    variant: 'primary',
    icon: 'plus',
    label: t('dict.btn.add'),
    onClick: async () => {
      const w = wrongInput.value.trim();
      const r = rightInput.value.trim();
      if (!w || !r) return;
      try {
        await api.addCorrection({ wrong: w, right: r });
        map[w] = r;
        wrongInput.value = ''; rightInput.value = '';
        render();
        toastOk();
      } catch (e) {
        // Backend returns 400 with rejected:true when gatekeeper blocks.
        toastErr(e.body?.rejected ? t('dict.rejected') : e.message);
      }
    },
  });
  [wrongInput, rightInput].forEach((el) =>
    el.addEventListener('keydown', (e) => { if (e.key === 'Enter') addBtn.click(); }),
  );

  const { wrap: searchWrap, input: searchInput } = LabeledInput({
    label: t('dict.placeholder.search'),
    placeholder: t('dict.placeholder.search'),
    srOnly: true,
  });
  searchInput.addEventListener('input', () => { search = searchInput.value; render(); });

  container.appendChild(Section({
    title: t('dict.tab.corrections'),
    headerRight: h('div', { class: 'min-w-[10rem]' }, searchWrap),
    children: [
      h('div', { class: 'flex gap-2 items-end flex-wrap' },
        wrongWrap, rightWrap, addBtn,
      ),
      listHost,
    ],
  }));
  render();
}
