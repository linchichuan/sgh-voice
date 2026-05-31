// store.js — tiny reactive store. No deps.

/**
 * @template T
 * @param {T} initialState
 * @returns {{
 *   get: () => T,
 *   set: (partialOrUpdater: Partial<T> | ((s: T) => Partial<T> | T)) => void,
 *   subscribe: (cb: (state: T) => void) => () => void,
 * }}
 */
export function createStore(initialState) {
  let state = Object.freeze({ ...initialState });
  const listeners = new Set();

  function get() {
    return state;
  }

  function set(partialOrUpdater) {
    const patch = typeof partialOrUpdater === 'function'
      ? partialOrUpdater(state)
      : partialOrUpdater;
    if (!patch || typeof patch !== 'object') return;
    state = Object.freeze({ ...state, ...patch });
    listeners.forEach((cb) => {
      try { cb(state); } catch (e) { console.error('[store] listener error', e); }
    });
  }

  function subscribe(cb) {
    listeners.add(cb);
    return () => listeners.delete(cb);
  }

  return { get, set, subscribe };
}
