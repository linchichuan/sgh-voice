// pricing.js — display-only JPY estimates and helpers.
// Backend doesn't expose pricing; these are approximate 2026 rates per 1k tokens / per audio sec.

export const PRICING_JPY = {
  groq_stt:   { audio_sec: 0.00065 },
  openai_stt: { audio_sec: 0.0009 },
  groq:       { in_1k: 0.06, out_1k: 0.09 },
  openai:     { in_1k: 0.38, out_1k: 1.50 },
  anthropic:  { in_1k: 0.12, out_1k: 0.60 },
  openrouter: { in_1k: 0.00, out_1k: 0.00 },
};

export const ENGINE_COLORS = {
  groq:       'var(--brand-blue)',
  anthropic:  'var(--brand-purple)',
  openai:     'var(--brand-orange)',
  openrouter: 'var(--success)',
  local:      'var(--text-3)',
};

export const ENGINE_LABEL = {
  groq: 'Groq', anthropic: 'Claude', openai: 'OpenAI',
  openrouter: 'OpenRouter', local: 'Local',
};

export const ENGINES = ['groq', 'anthropic', 'openai', 'openrouter'];

export const monthKey = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
export const dayKey   = (d) => `${monthKey(d)}-${String(d.getDate()).padStart(2, '0')}`;
export const fmtJpy   = (n) => `¥${Math.round(Number(n) || 0).toLocaleString('en-US')}`;
export const fmtInt   = (n) => Math.round(Number(n) || 0).toLocaleString('en-US');

export function costForEngine(engine, row) {
  const r = row || {};
  if (engine === 'groq') {
    return (r.groq_input_tokens || 0) / 1000 * PRICING_JPY.groq.in_1k
         + (r.groq_output_tokens || 0) / 1000 * PRICING_JPY.groq.out_1k
         + (r.groq_whisper_seconds || 0) * PRICING_JPY.groq_stt.audio_sec;
  }
  if (engine === 'openai') {
    return (r.openai_input_tokens || 0) / 1000 * PRICING_JPY.openai.in_1k
         + (r.openai_output_tokens || 0) / 1000 * PRICING_JPY.openai.out_1k
         + (r.openai_whisper_seconds || 0) * PRICING_JPY.openai_stt.audio_sec;
  }
  if (engine === 'anthropic') {
    return (r.anthropic_input_tokens || 0) / 1000 * PRICING_JPY.anthropic.in_1k
         + (r.anthropic_output_tokens || 0) / 1000 * PRICING_JPY.anthropic.out_1k;
  }
  if (engine === 'openrouter') {
    return (r.openrouter_input_tokens || 0) / 1000 * PRICING_JPY.openrouter.in_1k
         + (r.openrouter_output_tokens || 0) / 1000 * PRICING_JPY.openrouter.out_1k;
  }
  return 0;
}

export function engineCallStats(audit, engine, sinceMs) {
  let calls = 0;
  for (const e of audit) {
    if (!e || !e.ts) continue;
    const ts = new Date(e.ts).getTime();
    if (sinceMs && ts < sinceMs) continue;
    if (e.stt === engine || e.llm === engine) calls += 1;
  }
  return calls;
}

// Distribute monthly per-engine cost across audit-log calls to derive 30-day series.
export function build30dSeries(usage, audit) {
  const today = new Date();
  const days = [];
  for (let i = 29; i >= 0; i--) {
    days.push(new Date(today.getFullYear(), today.getMonth(), today.getDate() - i));
  }
  const series = {};
  for (const eng of ENGINES) series[eng] = new Array(30).fill(0);

  const callsByEngineMonth = {};
  for (const e of (audit || [])) {
    if (!e || !e.ts) continue;
    const d = new Date(e.ts);
    if (isNaN(d.getTime())) continue;
    const mk = monthKey(d);
    const dayIdx = days.findIndex((x) => dayKey(x) === dayKey(d));
    for (const role of ['stt', 'llm']) {
      const eng = e[role];
      if (!ENGINES.includes(eng)) continue;
      if (!callsByEngineMonth[eng]) callsByEngineMonth[eng] = {};
      if (!callsByEngineMonth[eng][mk]) callsByEngineMonth[eng][mk] = { total: 0, perDay: {} };
      callsByEngineMonth[eng][mk].total += 1;
      if (dayIdx >= 0) callsByEngineMonth[eng][mk].perDay[dayIdx] = (callsByEngineMonth[eng][mk].perDay[dayIdx] || 0) + 1;
    }
  }

  for (const eng of ENGINES) {
    const byMonth = callsByEngineMonth[eng] || {};
    for (const [mk, info] of Object.entries(byMonth)) {
      const monthCost = costForEngine(eng, usage[mk] || {});
      if (!info.total || monthCost <= 0) continue;
      for (const [idx, n] of Object.entries(info.perDay)) {
        series[eng][Number(idx)] += monthCost * (n / info.total);
      }
    }
  }
  return { days, series };
}
