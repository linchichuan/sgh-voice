// history.js — History page (#/history)
// Virtualized list of dictations + filters + edit/delete with undo.
// Owns: composition of FiltersBar + virtualized list + per-row state.

import { h, EmptyState, Toast } from '../lib/components.js';
import { t } from '../lib/i18n.js';
import * as api from '../lib/api.js';
import { Row } from './history/row.js';
import { FiltersBar } from './history/filters.js';

const ROW_H = 76;          // estimated row height in px (collapsed)
const OVERSCAN = 10;       // rows above/below viewport
const FETCH_LIMIT = 500;   // initial fetch ceiling

const state = {
  all: [],
  filtered: [],
  search: '',
  scene: '',
  app: '',
  expanded: new Set(),
  editing: new Set(),
  scrollY: 0,
};

let dom = null;
let scrollRaf = 0;

function parseHashQuery() {
  const idx = location.hash.indexOf('?');
  if (idx < 0) return {};
  const qs = new URLSearchParams(location.hash.slice(idx + 1));
  const out = {};
  for (const [k, v] of qs.entries()) out[k] = v;
  return out;
}

function writeHashQuery(params) {
  const base = location.hash.split('?')[0] || '#/history';
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v) qs.set(k, v);
  const str = qs.toString();
  history.replaceState(null, '', str ? `${base}?${str}` : base);
}

function uniqueValues(entries, key) {
  const seen = new Set();
  for (const e of entries) {
    const v = e[key];
    if (v) seen.add(v);
  }
  return Array.from(seen).sort();
}

function applyFilters() {
  const q = state.search.trim().toLowerCase();
  state.filtered = state.all.filter((e) => {
    if (state.scene && (e.scene || '') !== state.scene) return false;
    if (state.app) {
      const appValues = [e.bundle_id, e.app_name, e.app_id, e.app].filter(Boolean);
      if (!appValues.includes(state.app)) return false;
    }
    if (q) {
      const hay = `${e.final_text || ''}\n${e.whisper_raw || ''}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  if (dom?.filtersApi) dom.filtersApi.setCount(state.filtered.length);
}

function renderVirtual() {
  if (!dom) return;
  const { viewport, spacer } = dom;
  const total = state.filtered.length;

  if (total === 0) {
    spacer.style.height = '0px';
    viewport.replaceChildren(EmptyState({
      icon: 'inbox',
      title: t('empty.history'),
      message: (state.search || state.scene || state.app) ? t('empty.generic') : null,
    }));
    if (window.lucide) window.lucide.createIcons();
    return;
  }

  const containerH = dom.container.clientHeight || 600;
  const scrollY = state.scrollY;

  const heights = state.filtered.map((e) => {
    const ts = e.timestamp || e.ts;
    if (state.editing.has(ts)) return ROW_H * 4;
    if (state.expanded.has(ts)) return ROW_H * 3;
    return ROW_H;
  });

  const offsets = [];
  let acc = 0;
  for (let i = 0; i < heights.length; i++) { offsets.push(acc); acc += heights[i]; }
  spacer.style.height = `${acc}px`;

  let start = 0;
  while (start < total - 1 && offsets[start + 1] < scrollY) start++;
  start = Math.max(0, start - OVERSCAN);
  let end = start;
  while (end < total && offsets[end] < scrollY + containerH) end++;
  end = Math.min(total, end + OVERSCAN);

  const slice = h('div', {
    style: { position: 'absolute', top: `${offsets[start]}px`, left: '0', right: '0' },
  });
  for (let i = start; i < end; i++) {
    slice.appendChild(buildRow(state.filtered[i]));
  }
  viewport.replaceChildren(slice);
  if (window.lucide) window.lucide.createIcons();
}

function buildRow(entry) {
  const ts = entry.timestamp || entry.ts;
  return Row(entry, {
    expanded: state.expanded.has(ts),
    editing: state.editing.has(ts),
    onToggle: () => {
      if (state.expanded.has(ts)) state.expanded.delete(ts);
      else state.expanded.add(ts);
      renderVirtual();
    },
    onCopy: async () => {
      try {
        await navigator.clipboard.writeText(entry.final_text || '');
        Toast({ message: t('toast.copied'), type: 'success', duration: 1500 });
      } catch {
        Toast({ message: t('toast.error'), type: 'error' });
      }
    },
    onEdit: () => { state.editing.add(ts); renderVirtual(); },
    onCancel: () => { state.editing.delete(ts); renderVirtual(); },
    onSave: async (newText) => {
      try {
        await api.updateHistory(ts, { final_text: newText });
        entry.final_text = newText;
        entry.edited = true;
        state.editing.delete(ts);
        applyFilters();
        renderVirtual();
        Toast({ message: t('history.learned'), type: 'success' });
      } catch (err) {
        Toast({ message: err.message || t('toast.error'), type: 'error' });
      }
    },
    onDelete: () => deleteWithUndo(entry),
  });
}

function deleteWithUndo(entry) {
  const ts = entry.timestamp || entry.ts;
  const idx = state.all.indexOf(entry);
  if (idx < 0) return;
  state.all.splice(idx, 1);
  applyFilters();
  renderVirtual();

  let undone = false;
  let committed = false;
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  const toast = Toast({ message: '', type: 'warning', duration: 0 });
  toast.replaceChildren(
    h('i', { 'data-lucide': 'trash-2', class: 'w-4 h-4 mt-0.5 shrink-0' }),
    h('div', { class: 'text-sm flex-1' }, t('history.delete.undo')),
    h('button', {
      type: 'button',
      class: 'text-sm font-medium underline ml-2',
      onClick: () => {
        if (committed) return;
        undone = true;
        state.all.splice(idx, 0, entry);
        applyFilters();
        renderVirtual();
        toast.remove();
        Toast({ message: t('history.delete.undone'), type: 'success', duration: 1500 });
      },
    }, t('btn.cancel')),
  );
  if (window.lucide) window.lucide.createIcons();

  setTimeout(() => {
    if (undone) return;
    committed = true;
    api.deleteHistory(ts).catch((err) => {
      Toast({ message: err.message || t('toast.error'), type: 'error' });
    });
    if (reducedMotion) {
      toast.remove();
    } else {
      toast.style.transition = 'opacity 0.2s';
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 220);
    }
  }, 5000);
}

function onScroll() {
  if (scrollRaf) cancelAnimationFrame(scrollRaf);
  scrollRaf = requestAnimationFrame(() => {
    state.scrollY = dom.container.scrollTop;
    renderVirtual();
  });
}

async function loadEntries() {
  const data = await api.getHistory({ limit: FETCH_LIMIT });
  const entries = Array.isArray(data) ? data : (data?.entries || data?.history || []);
  state.all = entries;
}

export default async function mount(slot) {
  const q = parseHashQuery();
  state.search = q.q || '';
  state.scene = q.scene || '';
  state.app = q.app || '';
  state.expanded = new Set();
  state.editing = new Set();
  state.scrollY = 0;

  slot.replaceChildren(h('div', { class: 'p-8 text-center text-[var(--text-3)]' }, t('rec.processing') + '…'));

  try {
    await loadEntries();
  } catch (err) {
    slot.replaceChildren(h('div', { class: 'p-8' },
      h('h1', { class: 'text-2xl font-semibold mb-2' }, t('page.history.title')),
      h('p', { class: 'text-[var(--danger)]' }, err.message || t('toast.error')),
    ));
    return;
  }

  const scenes = uniqueValues(state.all, 'scene');
  const appFields = ['bundle_id', 'app_name', 'app_id', 'app'];
  const apps = Array.from(new Set(appFields.flatMap((field) => uniqueValues(state.all, field)))).sort();

  applyFilters();

  const container = h('div', {
    class: 'relative overflow-y-auto',
    style: { height: 'calc(100vh - 11rem)' },
    role: 'list',
    'aria-label': t('page.history.title'),
  });
  const spacer = h('div', { class: 'relative', style: { height: '0px' } });
  const viewport = h('div', { class: 'absolute inset-0' });
  spacer.appendChild(viewport);
  container.appendChild(spacer);
  container.addEventListener('scroll', onScroll, { passive: true });

  const filtersApi = FiltersBar({
    search: state.search,
    scene: state.scene,
    app: state.app,
    scenes,
    apps,
    count: state.filtered.length,
    onSearchChange: (v) => {
      state.search = v;
      writeHashQuery({ q: v, scene: state.scene, app: state.app });
      applyFilters();
      container.scrollTop = 0;
      state.scrollY = 0;
      renderVirtual();
    },
    onSceneChange: (v) => {
      state.scene = v;
      writeHashQuery({ q: state.search, scene: v, app: state.app });
      applyFilters();
      renderVirtual();
    },
    onAppChange: (v) => {
      state.app = v;
      writeHashQuery({ q: state.search, scene: state.scene, app: v });
      applyFilters();
      renderVirtual();
    },
    onCleared: () => {
      state.all = [];
      applyFilters();
      renderVirtual();
      Toast({ message: t('toast.saved'), type: 'success' });
    },
  });

  dom = { container, viewport, spacer, filtersApi };

  const page = h('div', { class: 'h-full flex flex-col' },
    h('header', { class: 'px-4 pt-6 pb-3' },
      h('h1', { class: 'text-2xl font-semibold text-[var(--text)]' }, t('page.history.title')),
    ),
    filtersApi.node,
    container,
  );

  slot.replaceChildren(page);
  requestAnimationFrame(renderVirtual);
}
