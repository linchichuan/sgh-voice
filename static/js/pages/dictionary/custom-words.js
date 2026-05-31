// pages/dictionary/custom-words.js — flat list of custom words with add/remove/search.

import { h, classes, Button, EmptyState } from '../../lib/components.js';
import { t } from '../../lib/i18n.js';
import * as api from '../../lib/api.js';
import { Section, LabeledInput, confirmRemove, filterStrings, toastOk, toastErr } from './util.js';

export default async function mount(container) {
  // Fetch fresh data so this tab reflects latest server state.
  let payload;
  try { payload = await api.getDictionary(); }
  catch (e) { container.appendChild(errorBox(e.message)); return; }

  // Backend returns { auto_added: [...], manual_added: [...] }
  const words = payload.custom_words || { auto_added: [], manual_added: [] };
  let manual = (words.manual_added || []).slice();
  const auto = (words.auto_added || []).slice();

  let search = '';
  const listHost = h('div', { class: 'mt-4' });

  const render = () => {
    listHost.replaceChildren();
    const filteredManual = filterStrings(manual, search);
    const filteredAuto = filterStrings(auto, search);

    if (!filteredManual.length && !filteredAuto.length) {
      listHost.appendChild(EmptyState({
        icon: 'book-open',
        title: t('dict.empty.words'),
      }));
      if (window.lucide) window.lucide.createIcons();
      return;
    }

    if (filteredManual.length) {
      listHost.appendChild(
        h('div', { class: 'mb-4' },
          h('div', { class: 'text-xs uppercase tracking-wide text-[var(--text-3)] mb-2' },
            `${t('dict.col.word')} · manual (${filteredManual.length})`),
          chipList(filteredManual, (w) => removeWord(w)),
        ),
      );
    }
    if (filteredAuto.length) {
      listHost.appendChild(
        h('div', null,
          h('div', { class: 'text-xs uppercase tracking-wide text-[var(--text-3)] mb-2' },
            `${t('dict.col.word')} · auto (${filteredAuto.length})`),
          chipList(filteredAuto, (w) => removeWord(w)),
        ),
      );
    }
    if (window.lucide) window.lucide.createIcons();
  };

  const removeWord = (word) => {
    confirmRemove({
      title: t('btn.delete'),
      message: `${t('dict.col.word')}: ${word}`,
      onConfirm: async () => {
        try {
          await api.removeDictionaryWord({ word });
          manual = manual.filter((w) => w !== word);
          // auto_added is server-managed; we leave it alone in local state and just re-fetch.
          render();
          toastOk();
        } catch (e) { toastErr(e.message); }
      },
    });
  };

  // Add row.
  const { wrap: wordWrap, input: wordInput } = LabeledInput({
    label: t('dict.col.word'),
    placeholder: t('dict.placeholder.word'),
    srOnly: true,
  });
  const addBtn = Button({
    variant: 'primary',
    icon: 'plus',
    label: t('dict.btn.add'),
    onClick: async () => {
      const w = wordInput.value.trim();
      if (!w) return;
      try {
        await api.addDictionaryWord({ word: w });
        if (!manual.includes(w)) manual.unshift(w);
        wordInput.value = '';
        render();
        toastOk();
      } catch (e) { toastErr(e.message); }
    },
  });
  wordInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') addBtn.click(); });

  // Search row.
  const { wrap: searchWrap, input: searchInput } = LabeledInput({
    label: t('dict.placeholder.search'),
    placeholder: t('dict.placeholder.search'),
    srOnly: true,
  });
  searchInput.addEventListener('input', () => { search = searchInput.value; render(); });

  const section = Section({
    title: t('dict.tab.words'),
    headerRight: h('div', { class: 'min-w-[10rem]' }, searchWrap),
    children: [
      h('div', { class: 'flex gap-2 items-end' }, wordWrap, addBtn),
      listHost,
    ],
  });

  container.appendChild(section);
  render();
}

function chipList(words, onRemove) {
  const wrap = h('div', { class: 'flex flex-wrap gap-2' });
  words.forEach((w) => {
    const chip = h('span', {
      class: 'inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[var(--surface-2)] text-sm text-[var(--text)] border border-[var(--border)]',
    },
      h('span', { class: 'mono break-all' }, w),
      h('button', {
        type: 'button',
        class: 'text-[var(--text-3)] hover:text-[var(--danger)] focus-visible:ring-2 focus-visible:ring-red-300 rounded',
        'aria-label': `${t('btn.delete')}: ${w}`,
        onClick: () => onRemove(w),
      }, h('i', { 'data-lucide': 'x', class: 'w-3.5 h-3.5' })),
    );
    wrap.appendChild(chip);
  });
  return wrap;
}

function errorBox(msg) {
  return h('div', { class: `${classes.card} text-[var(--danger)]` }, `Error: ${msg}`);
}
