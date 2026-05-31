// pages/models.js — Local Whisper model manager (SPEC §4.7).
// Lists known local models, shows download status + SSE progress, lets user set default.

import * as api from '../lib/api.js';
import { h, Card, Button, Badge, Toast } from '../lib/components.js';
import { t, STRINGS } from '../lib/i18n.js';

// ---------- i18n extensions ----------
const I18N = {
  ja: {
    'models.subtitle': 'デバイス上の音声認識用 Whisper モデル',
    'models.status.downloaded': 'ダウンロード済み', 'models.status.missing': '未ダウンロード',
    'models.status.downloading': 'ダウンロード中 {pct}%', 'models.status.unknown': '不明',
    'models.action.download': 'ダウンロード', 'models.action.cancel': 'キャンセル',
    'models.action.setdefault': 'デフォルトに設定', 'models.action.isdefault': '現在のデフォルト',
    'models.size.disk': 'ディスク使用量 約 {size}', 'models.size.unknown': 'サイズ不明',
    'models.progress.eta': '残り {eta}', 'models.progress.speed': '{speed}/秒',
    'models.toast.busy': '同時に 1 件のみダウンロード可能です',
    'models.toast.started': 'ダウンロードを開始しました',
    'models.toast.done': 'ダウンロードが完了しました',
    'models.toast.setdefault': 'デフォルトに設定しました',
    'models.toast.canceled': 'ダウンロードを中止しました',
    'models.toast.error': 'ダウンロード中にエラーが発生しました',
    'models.desc.turbo': '多言語対応・軽量で高速。非 CJK のデフォルト',
    'models.desc.breeze4bit': 'MediaTek Breeze ASR 25 — 繁体字中国語に最適化・0.82GB・Turbo の 3.5 倍高速・v1.4.0+',
    'models.desc.breezefp16': '4bit と同モデルだが fp16 で精度優先・2.87GB',
  },
  zh: {
    'models.subtitle': '裝置端語音辨識用 Whisper 模型',
    'models.status.downloaded': '已下載', 'models.status.missing': '未下載',
    'models.status.downloading': '下載中 {pct}%', 'models.status.unknown': '未知',
    'models.action.download': '下載', 'models.action.cancel': '取消',
    'models.action.setdefault': '設為預設', 'models.action.isdefault': '目前預設',
    'models.size.disk': '磁碟佔用約 {size}', 'models.size.unknown': '大小未知',
    'models.progress.eta': '剩餘 {eta}', 'models.progress.speed': '{speed}/秒',
    'models.toast.busy': '同時只能下載一個模型', 'models.toast.started': '已開始下載',
    'models.toast.done': '下載完成', 'models.toast.setdefault': '已設為預設',
    'models.toast.canceled': '已取消下載', 'models.toast.error': '下載發生錯誤',
    'models.desc.turbo': '多語通用、體積較小、速度快；非 CJK 預設',
    'models.desc.breeze4bit': 'MediaTek Breeze ASR 25 — 繁中專用、0.82GB、比 turbo 快 3.5×、v1.4.0+',
    'models.desc.breezefp16': '與 4bit 同模型但全精度，品質更佳、2.87GB',
  },
  en: {
    'models.subtitle': 'Local Whisper models for on-device transcription',
    'models.status.downloaded': 'Downloaded', 'models.status.missing': 'Not downloaded',
    'models.status.downloading': 'Downloading {pct}%', 'models.status.unknown': 'Unknown',
    'models.action.download': 'Download', 'models.action.cancel': 'Cancel',
    'models.action.setdefault': 'Set as default', 'models.action.isdefault': 'Current default',
    'models.size.disk': '~{size} on disk', 'models.size.unknown': 'Size unknown',
    'models.progress.eta': '{eta} left', 'models.progress.speed': '{speed}/s',
    'models.toast.busy': 'One download at a time', 'models.toast.started': 'Download started',
    'models.toast.done': 'Download complete', 'models.toast.setdefault': 'Default model updated',
    'models.toast.canceled': 'Download canceled', 'models.toast.error': 'Download failed',
    'models.desc.turbo': 'Multi-lingual; lighter / faster. Default for non-CJK',
    'models.desc.breeze4bit': 'MediaTek Breeze ASR 25 — Traditional Chinese specialized; 0.82GB; 3.5× faster than turbo; v1.4.0+',
    'models.desc.breezefp16': 'Same as 4bit but full precision; better quality, 2.87GB',
  },
};
for (const lang of Object.keys(I18N)) Object.assign(STRINGS[lang], I18N[lang]);

// Mirrors config.py LOCAL_MODEL_PATHS + default turbo model
const MODELS = [
  { key: 'mlx-community/whisper-turbo', name: 'Whisper Turbo', descKey: 'models.desc.turbo', sizeBytes: 1610612736 },
  { key: 'breeze-asr-25-4bit', name: 'Breeze ASR 25 (4-bit)', descKey: 'models.desc.breeze4bit', sizeBytes: 880803840 },
  { key: 'breeze-asr-25', name: 'Breeze ASR 25 (fp16)', descKey: 'models.desc.breezefp16', sizeBytes: 3082277683 },
];

function fmtBytes(n) {
  if (!n || n <= 0) return '—';
  const u = ['B', 'KB', 'MB', 'GB', 'TB']; let v = n; let i = 0;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i += 1; }
  return `${v.toFixed(v >= 10 ? 0 : 2)} ${u[i]}`;
}
function fmtEta(s) {
  if (!isFinite(s) || s <= 0) return '—';
  if (s < 60) return `${Math.round(s)}s`;
  const m = Math.floor(s / 60); const ss = Math.round(s % 60);
  if (m < 60) return `${m}m ${ss}s`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

let state = null;

function cleanupStream() {
  if (state && state.stream) { try { state.stream.close(); } catch { /* ignore */ } state.stream = null; }
}
window.addEventListener('hashchange', cleanupStream);
window.addEventListener('beforeunload', cleanupStream);

function renderProgress() {
  const pct = Math.max(0, Math.min(100, state.progressPct));
  const speedText = state.speedBps > 0 ? t('models.progress.speed', { speed: fmtBytes(state.speedBps) }) : '—';
  const etaText = t('models.progress.eta', { eta: fmtEta(state.etaSeconds) });
  return h('div', { class: 'mt-4 space-y-1.5' },
    h('div', {
      class: 'h-2 rounded-full bg-[var(--surface-2)] overflow-hidden',
      role: 'progressbar', 'aria-valuemin': '0', 'aria-valuemax': '100', 'aria-valuenow': String(Math.round(pct)),
    }, h('div', { class: 'h-full bg-[var(--brand-blue)] transition-all', style: { width: `${pct}%` } })),
    h('div', { class: 'flex justify-between text-xs text-[var(--text-3)] mono' },
      h('span', null, `${fmtBytes(state.downloadedBytes)} / ${fmtBytes(state.totalBytes)}`),
      h('span', null, `${speedText}  ·  ${etaText}`),
    ),
  );
}

function renderCard(model) {
  const isDefault = state.currentDefault === model.key;
  const downloading = state.activeKey === model.key;
  const status = state.statuses[model.key] || { downloaded: false, unknown: true };

  const badge = downloading
    ? Badge({ text: t('models.status.downloading', { pct: state.progressPct.toFixed(0) }), color: 'blue' })
    : status.downloaded ? Badge({ text: t('models.status.downloaded'), color: 'green' })
      : status.unknown ? Badge({ text: t('models.status.unknown'), color: 'default' })
        : Badge({ text: t('models.status.missing'), color: 'default' });

  let action;
  if (downloading) {
    action = Button({ variant: 'outline', icon: 'x', label: t('models.action.cancel'), onClick: cancelDownload });
  } else if (status.downloaded) {
    action = Button({
      variant: isDefault ? 'ghost' : 'primary',
      icon: isDefault ? 'check' : 'star',
      label: isDefault ? t('models.action.isdefault') : t('models.action.setdefault'),
      disabled: isDefault || state.savingDefault,
      onClick: () => setDefault(model.key),
    });
  } else {
    action = Button({
      variant: 'primary', icon: 'download', label: t('models.action.download'),
      disabled: state.activeKey !== null,
      onClick: () => startDownload(model.key),
    });
  }

  const sizeText = model.sizeBytes ? t('models.size.disk', { size: fmtBytes(model.sizeBytes) }) : t('models.size.unknown');
  const highlight = isDefault ? ' ring-2 ring-[var(--brand-blue)] border-transparent' : '';

  const body = h('div', { class: 'flex flex-col gap-3 md:flex-row md:items-start md:justify-between' },
    h('div', { class: 'flex-1 min-w-0' },
      h('div', { class: 'flex items-center gap-2 flex-wrap' },
        h('h3', { class: 'text-base font-semibold text-[var(--text)]' }, model.name),
        badge,
        isDefault ? Badge({ text: t('models.action.isdefault'), color: 'blue' }) : null,
      ),
      h('p', { class: 'mt-1 text-sm text-[var(--text-2)]' }, t(model.descKey)),
      h('div', { class: 'mt-2 text-xs text-[var(--text-3)] mono' }, `${model.key}  ·  ${sizeText}`),
      downloading ? renderProgress() : null,
    ),
    h('div', { class: 'shrink-0 flex items-center' }, action),
  );
  return Card({ children: body, className: highlight });
}

function repaint() {
  if (!state || !state.root) return;
  const list = state.root.querySelector('#models-list');
  if (!list) return;
  list.replaceChildren(...MODELS.map(renderCard));
  if (window.lucide) window.lucide.createIcons();
}

async function startDownload(key) {
  if (state.activeKey) { Toast({ message: t('models.toast.busy'), type: 'warning' }); return; }
  state.activeKey = key;
  Object.assign(state, { progressPct: 0, downloadedBytes: 0, totalBytes: 0, speedBps: 0, etaSeconds: Infinity, speedSamples: [] });
  repaint();
  try {
    await api.request('POST', `/api/model/download/${encodeURIComponent(key)}`);
    Toast({ message: t('models.toast.started'), type: 'info', duration: 2000 });
  } catch (err) {
    state.activeKey = null; repaint();
    Toast({ message: err.message || t('models.toast.error'), type: 'error' });
    return;
  }
  openStream(key);
}

function openStream(key) {
  // Backend exposes a single global SSE at /api/model/download-progress
  cleanupStream();
  const source = new EventSource('/api/model/download-progress');
  state.stream = source;

  source.onmessage = (evt) => {
    let data; try { data = JSON.parse(evt.data); } catch { return; }
    const downloaded = Number(data.progress || data.downloaded_bytes || 0);
    const total = Number(data.total || data.total_bytes || 0);
    const pct = typeof data.percent === 'number'
      ? data.percent : (total > 0 ? (downloaded / total) * 100 : 0);

    const now = Date.now();
    state.speedSamples.push({ t: now, bytes: downloaded });
    while (state.speedSamples.length > 1 && (now - state.speedSamples[0].t) > 2000) state.speedSamples.shift();
    if (state.speedSamples.length >= 2) {
      const a = state.speedSamples[0];
      const b = state.speedSamples[state.speedSamples.length - 1];
      const dt = Math.max(0.001, (b.t - a.t) / 1000);
      state.speedBps = Math.max(0, (b.bytes - a.bytes) / dt);
    }
    state.downloadedBytes = downloaded;
    state.totalBytes = total;
    state.progressPct = pct;
    const remaining = Math.max(0, total - downloaded);
    state.etaSeconds = state.speedBps > 0 ? remaining / state.speedBps : Infinity;
    repaint();

    if (data.error) {
      cleanupStream(); state.activeKey = null;
      Toast({ message: String(data.error) || t('models.toast.error'), type: 'error' });
      refreshStatuses();
    } else if (data.done) {
      cleanupStream(); state.activeKey = null;
      Toast({ message: t('models.toast.done'), type: 'success' });
      refreshStatuses();
    }
  };
  source.onerror = () => {
    cleanupStream();
    if (state.activeKey === key) {
      state.activeKey = null;
      Toast({ message: t('models.toast.error'), type: 'error' });
      repaint(); refreshStatuses();
    }
  };
}

function cancelDownload() {
  cleanupStream(); state.activeKey = null;
  Toast({ message: t('models.toast.canceled'), type: 'info' });
  repaint();
}

async function refreshStatuses() {
  const res = await Promise.allSettled(MODELS.map((m) => api.getModelStatus(m.key)));
  res.forEach((r, idx) => {
    const key = MODELS[idx].key;
    state.statuses[key] = (r.status === 'fulfilled' && r.value && typeof r.value === 'object')
      ? { downloaded: !!r.value.downloaded, unknown: false }
      : { downloaded: false, unknown: true };
  });
  repaint();
}

async function setDefault(key) {
  state.savingDefault = true; repaint();
  try {
    await api.saveConfig({ local_whisper_model: key });
    state.currentDefault = key;
    Toast({ message: t('models.toast.setdefault'), type: 'success' });
  } catch (err) {
    Toast({ message: err.message || t('toast.error'), type: 'error' });
  } finally {
    state.savingDefault = false; repaint();
  }
}

export default async function mount(slot) {
  cleanupStream();
  state = {
    root: null, stream: null, activeKey: null, currentDefault: '', savingDefault: false,
    statuses: {}, progressPct: 0, downloadedBytes: 0, totalBytes: 0,
    speedBps: 0, etaSeconds: Infinity, speedSamples: [],
  };
  const root = h('div', { class: 'max-w-3xl mx-auto p-6 md:p-8 space-y-6' },
    h('header', null,
      h('h1', { class: 'text-2xl font-semibold text-[var(--text)]' }, t('page.models.title')),
      h('p', { class: 'mt-1 text-sm text-[var(--text-3)]' }, t('models.subtitle')),
    ),
    h('div', { id: 'models-list', class: 'space-y-4' }),
  );
  state.root = root;
  slot.replaceChildren(root);
  MODELS.forEach((m) => { state.statuses[m.key] = { downloaded: false, unknown: true }; });
  repaint();
  const [cfgRes] = await Promise.all([api.getConfig().catch(() => ({})), refreshStatuses()]);
  state.currentDefault = (cfgRes && cfgRes.local_whisper_model) || '';
  repaint();
}
