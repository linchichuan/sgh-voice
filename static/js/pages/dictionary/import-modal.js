// pages/dictionary/import-modal.js — B1: batch dictionary import (.txt / .csv).
// Two-step: preview (no write) → apply (writes through memory.add_custom_word(),
// the exact same path as the single-word "+ Add" button).

import { h, classes, Button } from '../../lib/components.js';
import { t } from '../../lib/i18n.js';
import * as api from '../../lib/api.js';
import { toastOk, toastErr } from './util.js';

/**
 * Open the batch-import dialog.
 * @param {() => void} [onImported]  Called after a successful apply so the parent can refresh.
 */
export function openImportModal(onImported) {
  const backdrop = h('div', {
    class: 'fixed inset-0 z-[90] bg-black/40 flex items-center justify-center p-4',
    role: 'dialog',
    'aria-modal': 'true',
    'aria-labelledby': 'import-title',
  });
  const close = () => backdrop.remove();

  let selectedFile = null;
  let lastPreview = null; // { importable, duplicates, counts }
  // Words the user has actively *unchecked* among the visible preview rows.
  // Everything else importable — including anything past the 500-row preview
  // cap the user could never see or check — is included by default. This is
  // an exclusion list, not a selection list: preview only ever shows/lets you
  // check the first 500 rows (dashboard.py:api_dictionary_import truncates
  // `importable` there), so a selection list could never represent row 501+
  // and would silently cap a large import at whatever was visible, even after
  // fixing the "select all visible" case — deselecting even one visible word
  // still forced every unseen word to be dropped too (2026-09 second-pass fix).
  let excluded = new Set();
  // Bumped on every file change and every preview click; a preview response
  // is only applied if it's still the most recent request in flight. Without
  // this, picking a new file (or re-clicking Preview) while a slow preview
  // request for an earlier file is still in flight lets that stale response
  // land later and silently overwrite the state for the file the user
  // actually wants — wrong preview shown, excluded-set built from the wrong
  // file's words.
  let previewGeneration = 0;

  const fileInput = h('input', {
    type: 'file', accept: '.txt,.csv,text/csv,text/plain', class: 'sr-only', id: 'dict-import-file',
  });
  const chosenLabel = h('span', { class: 'text-sm text-[var(--text-2)]' }, '');
  const chooseBtn = Button({
    variant: 'outline', icon: 'upload', label: t('dict.import.choose'),
    onClick: () => fileInput.click(),
  });
  fileInput.addEventListener('change', () => {
    selectedFile = fileInput.files && fileInput.files[0] ? fileInput.files[0] : null;
    chosenLabel.textContent = selectedFile ? t('dict.import.chosen', { name: selectedFile.name }) : '';
    lastPreview = null;
    excluded = new Set();
    previewGeneration += 1; // invalidate any in-flight preview for the old file
    applyBtn.disabled = true;
    resultHost.replaceChildren();
    summary.textContent = '';
  });

  const resultHost = h('div', { class: 'mt-4 min-h-[6rem]' });
  const summary = h('div', { class: 'text-sm text-[var(--text-3)] mt-3' });

  const previewBtn = Button({
    variant: 'primary', icon: 'search', label: t('dict.import.preview'),
    onClick: async () => {
      if (!selectedFile) { toastErr(t('dict.import.error.no_file')); return; }
      const myGeneration = ++previewGeneration;
      resultHost.replaceChildren(h('div', { class: 'text-sm text-[var(--text-3)]' }, '…'));
      try {
        const res = await api.previewDictionaryImport(selectedFile);
        if (myGeneration !== previewGeneration) return; // superseded by a newer file/preview
        lastPreview = res;
        excluded = new Set(); // fresh preview → nothing deselected yet
        renderPreview(res);
      } catch (e) {
        if (myGeneration !== previewGeneration) return;
        resultHost.replaceChildren();
        toastErr(e.message);
      }
    },
  });

  // Disable Apply only when there is truly nothing that could be imported:
  // either the preview found zero importable words, or (when the preview
  // wasn't truncated, i.e. every importable word is visible) the user has
  // unchecked every single one of them. When the preview *is* truncated we
  // can never know that from the checkboxes alone — there could always be
  // more importable words past row 500 — so Apply stays enabled.
  const updateApplyDisabled = () => {
    const counts = lastPreview?.counts || {};
    const shownImportable = Array.isArray(lastPreview?.importable) ? lastPreview.importable : [];
    const totalImportable = Number(counts.importable ?? shownImportable.length);
    const truncated = totalImportable > shownImportable.length;
    applyBtn.disabled = shownImportable.length === 0
      || (!truncated && excluded.size >= shownImportable.length);
  };

  const applyBtn = Button({
    variant: 'primary', icon: 'check', label: t('dict.import.apply'), disabled: true,
    onClick: async () => {
      if (!selectedFile || !lastPreview) return;
      try {
        // Always re-upload + re-parse the full file; `excluded` is the (small)
        // set of words the user unchecked. Omitting/empty-ing it imports
        // everything importable, including words beyond the preview's
        // 500-row cap that the user never had a chance to see or exclude.
        const res = await api.applyDictionaryImport(selectedFile, Array.from(excluded));
        const n = Array.isArray(res?.imported) ? res.imported.length : 0;
        toastOk(t('dict.import.applied', { n }));
        close();
        if (onImported) onImported();
      } catch (e) { toastErr(e.message); }
    },
  });

  const renderPreview = (res) => {
    resultHost.replaceChildren();
    const counts = res?.counts || {};
    summary.textContent = t('dict.import.summary', {
      importable: counts.importable ?? 0,
      duplicates: counts.duplicates ?? 0,
      invalid: counts.invalid ?? 0,
    });

    const importable = Array.isArray(res?.importable) ? res.importable : [];
    const duplicates = Array.isArray(res?.duplicates) ? res.duplicates : [];
    updateApplyDisabled();

    if (!importable.length && !duplicates.length) {
      resultHost.appendChild(h('div', { class: 'text-sm text-[var(--text-3)] text-center py-6' }, t('dict.import.none')));
      return;
    }

    // Preview truncates to 500 rows; tell the user the real total so a large
    // file's word count isn't silently understated in the UI. Apply always
    // processes the full re-parsed file regardless of this truncation (see
    // applyBtn's onClick) — only explicitly unchecked words are excluded.
    const totalImportable = Number(counts.importable ?? importable.length);
    if (totalImportable > importable.length) {
      resultHost.appendChild(h('div', { class: 'text-xs text-[var(--text-3)] mb-2' },
        t('dict.import.truncated', { shown: importable.length, total: totalImportable })));
    }

    const rows = h('tbody', null);
    importable.forEach((word, idx) => {
      const cbId = `import-cb-${idx}`;
      const cb = h('input', {
        id: cbId, type: 'checkbox', checked: '', class: 'h-4 w-4 accent-[var(--brand-blue)]',
      });
      cb.addEventListener('change', () => {
        if (cb.checked) excluded.delete(word); else excluded.add(word);
        updateApplyDisabled();
      });
      rows.appendChild(h('tr', { class: 'border-t border-[var(--border)]' },
        h('td', { class: 'py-2 pr-3' }, h('label', { for: cbId, class: 'sr-only' }, `${t('dict.import.apply')} ${word}`), cb),
        h('td', { class: 'py-2 pr-3 mono text-sm break-all' }, word),
        h('td', { class: 'py-2 pr-0 text-xs text-[var(--text-3)]' }, t('dict.import.status.importable')),
      ));
    });
    duplicates.slice(0, 50).forEach((word) => {
      rows.appendChild(h('tr', { class: 'border-t border-[var(--border)] opacity-50' },
        h('td', { class: 'py-2 pr-3' }),
        h('td', { class: 'py-2 pr-3 mono text-sm break-all' }, word),
        h('td', { class: 'py-2 pr-0 text-xs text-[var(--text-3)]' }, t('dict.import.status.duplicate')),
      ));
    });

    resultHost.appendChild(h('div', { class: 'max-h-72 overflow-y-auto' },
      h('table', { class: 'w-full text-sm' }, rows),
    ));
  };

  const dialog = h('div', {
    class: 'bg-[var(--surface)] rounded-2xl shadow-2xl max-w-2xl w-full p-6 border border-[var(--border)]',
  },
    h('h2', { id: 'import-title', class: 'text-lg font-semibold text-[var(--text)] mb-1' }, t('dict.import.title')),
    h('p', { class: 'text-sm text-[var(--text-2)] mb-4' }, t('dict.import.intro')),
    h('div', { class: 'flex gap-3 flex-wrap items-center' },
      fileInput, chooseBtn, chosenLabel, previewBtn,
    ),
    summary,
    resultHost,
    h('div', { class: 'mt-6 flex justify-end gap-2' },
      Button({ variant: 'ghost', label: t('btn.cancel'), onClick: close }),
      applyBtn,
    ),
  );
  backdrop.appendChild(dialog);
  backdrop.addEventListener('click', (e) => { if (e.target === backdrop) close(); });
  document.body.appendChild(backdrop);
  if (window.lucide) window.lucide.createIcons();
  const onKey = (e) => { if (e.key === 'Escape') { close(); document.removeEventListener('keydown', onKey); } };
  document.addEventListener('keydown', onKey);
}
