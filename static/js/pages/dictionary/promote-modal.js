// pages/dictionary/promote-modal.js — dry-run preview + selective apply.

import { h, classes, Button } from '../../lib/components.js';
import { t } from '../../lib/i18n.js';
import * as api from '../../lib/api.js';
import { toastOk, toastErr } from './util.js';

/**
 * Open the Promote-from-History dialog.
 * @param {() => void} [onApplied]  Called after successful apply so parent can refresh.
 */
export function openPromoteModal(onApplied) {
  const backdrop = h('div', {
    class: 'fixed inset-0 z-[90] bg-black/40 flex items-center justify-center p-4',
    role: 'dialog',
    'aria-modal': 'true',
    'aria-labelledby': 'promote-title',
  });
  const close = () => backdrop.remove();

  // Controls
  const minFreqId = 'promote-minfreq';
  const sourceId = 'promote-source';

  const minFreq = h('input', {
    id: minFreqId,
    type: 'number',
    min: '1',
    value: '5',
    class: classes.input + ' w-24',
  });
  const sourceSel = h('select', { id: sourceId, class: classes.input + ' w-40' },
    h('option', { value: 'both', selected: '' }, t('dict.promote.source.both')),
    h('option', { value: 'edited' }, t('dict.promote.source.edited')),
    h('option', { value: 'auto' }, t('dict.promote.source.auto')),
  );

  const resultHost = h('div', { class: 'mt-4 min-h-[6rem]' });
  const summary = h('div', { class: 'text-sm text-[var(--text-3)] mt-3' });

  let lastPromoted = []; // [{wrong, right, freq}]
  let selected = new Set();

  const previewBtn = Button({
    variant: 'primary', icon: 'search', label: t('dict.promote.preview'),
    onClick: async () => {
      resultHost.replaceChildren(h('div', { class: 'text-sm text-[var(--text-3)]' }, '…'));
      try {
        const res = await api.promoteFromHistory({
          min_freq: Math.max(1, parseInt(minFreq.value, 10) || 5),
          source: sourceSel.value,
          apply: false,
        });
        lastPromoted = Array.isArray(res?.promoted) ? res.promoted : [];
        selected = new Set(lastPromoted.map((p) => p.wrong));
        renderPromoted(res);
      } catch (e) { toastErr(e.message); }
    },
  });

  const applyBtn = Button({
    variant: 'primary', icon: 'check', label: t('dict.promote.apply'), disabled: true,
    onClick: async () => {
      const items = lastPromoted.filter((p) => selected.has(p.wrong));
      if (!items.length) return;
      try {
        // Backend's apply path re-derives from history; we still pass min_freq to keep the same threshold.
        await api.promoteFromHistory({
          min_freq: Math.max(1, parseInt(minFreq.value, 10) || 5),
          source: sourceSel.value,
          apply: true,
        });
        toastOk(t('dict.promote.applied', { n: items.length }));
        close();
        if (onApplied) onApplied();
      } catch (e) { toastErr(e.message); }
    },
  });

  const renderPromoted = (res) => {
    resultHost.replaceChildren();
    const skippedCounts = res?.skipped_counts || {};
    const totalSkipped = Object.values(skippedCounts).reduce((a, b) => a + b, 0);
    summary.textContent = t('dict.promote.summary', { n: lastPromoted.length, skipped: totalSkipped });

    applyBtn.disabled = lastPromoted.length === 0;

    if (!lastPromoted.length) {
      resultHost.appendChild(h('div', { class: 'text-sm text-[var(--text-3)] text-center py-6' }, t('dict.promote.none')));
      if (window.lucide) window.lucide.createIcons();
      return;
    }

    const head = h('thead', null,
      h('tr', { class: 'text-left text-xs uppercase tracking-wide text-[var(--text-3)]' },
        h('th', { class: 'py-2 pr-3 font-medium w-8' }, ''),
        h('th', { class: 'py-2 pr-3 font-medium' }, t('dict.col.wrong')),
        h('th', { class: 'py-2 pr-3 font-medium' }, t('dict.col.right')),
        h('th', { class: 'py-2 pr-0 font-medium text-right' }, t('dict.col.freq')),
      ),
    );
    const body = h('tbody', null);
    lastPromoted.forEach((p, idx) => {
      const cbId = `promote-cb-${idx}`;
      const cb = h('input', {
        id: cbId, type: 'checkbox', checked: '', class: 'h-4 w-4 accent-[var(--brand-blue)]',
      });
      cb.addEventListener('change', () => {
        if (cb.checked) selected.add(p.wrong); else selected.delete(p.wrong);
        applyBtn.disabled = selected.size === 0;
      });
      body.appendChild(h('tr', { class: 'border-t border-[var(--border)]' },
        h('td', { class: 'py-2 pr-3' }, h('label', { for: cbId, class: 'sr-only' }, `${t('dict.promote.apply')} ${p.wrong}`), cb),
        h('td', { class: 'py-2 pr-3 mono text-sm break-all' }, p.wrong),
        h('td', { class: 'py-2 pr-3 mono text-sm text-[var(--text-2)] break-all' }, p.right),
        h('td', { class: 'py-2 pr-0 text-right mono text-sm tabular-nums' }, String(p.freq)),
      ));
    });
    resultHost.appendChild(h('div', { class: 'max-h-72 overflow-y-auto' },
      h('table', { class: 'w-full text-sm' }, head, body),
    ));
    if (window.lucide) window.lucide.createIcons();
  };

  const dialog = h('div', {
    class: 'bg-[var(--surface)] rounded-2xl shadow-2xl max-w-2xl w-full p-6 border border-[var(--border)]',
  },
    h('h2', { id: 'promote-title', class: 'text-lg font-semibold text-[var(--text)] mb-1' }, t('dict.promote.title')),
    h('p', { class: 'text-sm text-[var(--text-2)] mb-4' }, t('dict.promote.intro')),
    h('div', { class: 'flex gap-4 flex-wrap items-end' },
      h('div', null,
        h('label', { for: minFreqId, class: classes.label }, t('dict.promote.minfreq')),
        minFreq,
      ),
      h('div', null,
        h('label', { for: sourceId, class: classes.label }, t('dict.promote.source')),
        sourceSel,
      ),
      previewBtn,
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
