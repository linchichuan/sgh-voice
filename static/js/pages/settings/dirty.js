// dirty.js — tiny per-tab dirty-tracking helper.
// Holds a Map of changed config keys; consumers read entries() then prune unchanged before submit.

export function createDirty(initialCfg) {
  const initial = { ...initialCfg };
  const dirty = new Map();

  return {
    /** Mark a field as changed with the new value. */
    set(key, value) {
      // Special: '' string for API keys means "unchanged" — never mark dirty.
      // Caller decides — generic helper just stores literally.
      dirty.set(key, value);
    },
    /** Prune entries whose value equals initial (deep eq for primitives only). */
    prune() {
      for (const [k, v] of [...dirty.entries()]) {
        if (initial[k] === v) dirty.delete(k);
      }
    },
    clear() { dirty.clear(); },
    size() { return dirty.size; },
    has(k) { return dirty.has(k); },
    get(k) { return dirty.get(k); },
    /** Returns object of changed entries only. */
    payload() {
      this.prune();
      const out = {};
      for (const [k, v] of dirty.entries()) out[k] = v;
      return out;
    },
    /** Update initial snapshot after a successful save. */
    commit() {
      for (const [k, v] of dirty.entries()) initial[k] = v;
      dirty.clear();
    },
  };
}
