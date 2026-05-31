// api.js — single source of truth for all backend calls.
// All 32 endpoints from SPEC §5. Same-origin only (dashboard.py blocks CORS mutating requests).

/**
 * @typedef {Object} ApiError
 * @property {number} status
 * @property {string} message
 * @property {*} body
 */

/**
 * Core request helper. Throws structured ApiError on non-2xx.
 * @param {string} method
 * @param {string} path
 * @param {*} [body]
 * @returns {Promise<*>}
 */
export async function request(method, path, body) {
  const init = {
    method,
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
  };
  if (body !== undefined && body !== null) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }

  let res;
  try {
    res = await fetch(path, init);
  } catch (e) {
    const err = new Error(`Network error: ${e.message}`);
    err.status = 0;
    err.body = null;
    throw err;
  }

  const ct = res.headers.get('content-type') || '';
  let payload = null;
  if (ct.includes('application/json')) {
    payload = await res.json().catch(() => null);
  } else {
    payload = await res.text().catch(() => null);
  }

  if (!res.ok) {
    const msg = (payload && typeof payload === 'object' && payload.error) || `${method} ${path} → ${res.status}`;
    const err = new Error(msg);
    err.status = res.status;
    err.body = payload;
    throw err;
  }
  return payload;
}

// ---------- Config ----------
export const getConfig          = ()           => request('GET',  '/api/config');
export const saveConfig         = (partial)    => request('POST', '/api/config', partial);

// ---------- Stats / Usage / Status ----------
export const getStats           = ()           => request('GET',  '/api/stats');
export const getUsage           = ()           => request('GET',  '/api/usage');
export const getServiceStatus   = ()           => request('GET',  '/api/service-status');

// ---------- History ----------
// backend reads ?n=NN; accept both n and limit for forward compat between page agents
export const getHistory         = (params={})  => {
  const p = { ...params };
  if ('limit' in p && !('n' in p)) { p.n = p.limit; delete p.limit; }
  const qs = new URLSearchParams(p).toString();
  return request('GET', `/api/history${qs ? `?${qs}` : ''}`);
};
export const updateHistory      = (ts, body)   => request('PATCH',  `/api/history/${encodeURIComponent(ts)}`, body);
export const deleteHistory      = (ts)         => request('DELETE', `/api/history/${encodeURIComponent(ts)}`);
export const clearHistory       = ()           => request('POST',   '/api/history/clear');
export const exportHistoryUrl   = (format='csv') => `/api/history/export?format=${encodeURIComponent(format)}`;

// ---------- Dictionary ----------
// backend supports ?layer=global|scene:<key>|app:<bundle_id>
export const getDictionary              = (layer)   => {
  const qs = layer ? `?layer=${encodeURIComponent(layer)}` : '';
  return request('GET', `/api/dictionary${qs}`);
};
export const addDictionaryWord          = (body)    => request('POST',   '/api/dictionary/word', body);
export const removeDictionaryWord       = (body)    => request('DELETE', '/api/dictionary/word', body);
export const addCorrection              = (body)    => request('POST',   '/api/dictionary/correction', body);
export const removeCorrection           = (body)    => request('DELETE', '/api/dictionary/correction', body);
export const addSceneCorrection         = (body)    => request('POST',   '/api/dictionary/scene_correction', body);
export const removeSceneCorrection      = (body)    => request('DELETE', '/api/dictionary/scene_correction', body);
export const addAppCorrection           = (body)    => request('POST',   '/api/dictionary/app_correction', body);
export const removeAppCorrection        = (body)    => request('DELETE', '/api/dictionary/app_correction', body);
export const cleanupDictionary          = ()        => request('POST',   '/api/dictionary/cleanup');
export const promoteFromHistory         = (body)    => request('POST',   '/api/dictionary/promote_from_history', body);

// ---------- Smart Replace ----------
export const getSmartReplace    = ()           => request('GET',  '/api/smart_replace');
export const saveSmartReplace   = (body)       => request('POST', '/api/smart_replace', body);

// ---------- Rewrite / Test LLM ----------
export const rewriteText        = (body)       => request('POST', '/api/rewrite', body);
export const testLlm            = (body)       => request('POST', '/api/test-llm', body);

// ---------- Recording (dashboard-driven) ----------
export const startRecording     = ()           => request('POST', '/api/recording/start');
export const stopRecording      = ()           => request('POST', '/api/recording/stop');
export const getRecordingStatus = ()           => request('GET',  '/api/recording/status');

// ---------- Voiceprint ----------
export const getVoiceprintStatus = ()          => request('GET',  '/api/voiceprint/status');
export const enrollVoiceprint    = ()          => request('POST', '/api/voiceprint/enroll');
export const deleteVoiceprint    = ()          => request('POST', '/api/voiceprint/delete');

// ---------- Models ----------
export const getModelStatus         = (key)    => request('GET', `/api/model/status/${encodeURIComponent(key)}`);
export const getModelDownloadPoll   = ()       => request('GET',  '/api/model/download-progress');
export const triggerModelDownload   = (key)    => request('POST', `/api/model/download/${encodeURIComponent(key)}`);

/**
 * Two-step model download helper.
 * Backend: POST /api/model/download/<key> kicks off (returns immediately),
 *          GET  /api/model/download-progress streams SSE for *any* current download.
 * @param {string} key
 * @param {(evt: MessageEvent) => void} onMessage
 * @param {(err: Event) => void} [onError]
 * @returns {Promise<{ source: EventSource, close: () => void }>}
 */
export async function streamModelDownload(key, onMessage, onError) {
  // 1. fire the POST trigger (returns quickly)
  await triggerModelDownload(key);
  // 2. open SSE on the shared progress endpoint
  const source = new EventSource('/api/model/download-progress');
  if (onMessage) source.onmessage = onMessage;
  if (onError) source.onerror = onError;
  return { source, close: () => source.close() };
}

// ---------- Ollama / Style profile / Audit ----------
export const detectOllama          = ()        => request('POST', '/api/ollama/detect');
export const regenerateStyleProfile = ()       => request('POST', '/api/style_profile/regenerate');
export const getAuditLog            = ()       => request('GET',  '/api/audit-log');

// ---------- GDPR ----------
// v2.4.0：兩步驟 — 先要 token、再帶 token 執行刪除（防 JS 攻擊者直接 wipeAll() bypass UI 守門）
export async function wipeAll() {
  const { token } = await request('POST', '/api/wipe_all/token');
  return request('POST', '/api/wipe_all', { token, confirm: 'DELETE_ALL_MY_DATA' });
}
