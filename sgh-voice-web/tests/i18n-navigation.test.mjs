import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../i18n.js', import.meta.url), 'utf8');

function render(search, storage, page = '') {
  let ready;
  const document = {
    body: { dataset: { page } }, documentElement: {},
    querySelectorAll: () => [], getElementById: () => null,
    querySelector: () => ({ setAttribute() {} }),
    addEventListener: (_, callback) => { ready = callback; },
  };
  const context = vm.createContext({
    document, localStorage: storage, URLSearchParams,
    navigator: { language: 'ja-JP' },
    window: { location: { search }, dispatchEvent() {} },
    CustomEvent: class {},
  });
  vm.runInContext(source, context);
  ready();
  return context.window.SGH_LANG;
}

for (const language of ['zh', 'ja', 'en']) {
  test(`query-selected ${language} survives navigation to the update page`, () => {
    const values = new Map();
    const storage = { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value) };
    assert.equal(render(`?lang=${language}`, storage), language);
    assert.equal(render('', storage, 'android-update'), language);
  });
}

test('blocked browser storage does not prevent translations', () => {
  const storage = { getItem() { throw Error('blocked'); }, setItem() { throw Error('blocked'); } };
  assert.equal(render('?lang=zh', storage), 'zh');
  assert.equal(render('', storage, 'android-update'), 'ja');
});
