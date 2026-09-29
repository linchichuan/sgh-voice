import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";

const source = await readFile(new URL("../main.js", import.meta.url), "utf8");
const html = await readFile(new URL("../index.html", import.meta.url), "utf8");
const i18n = await readFile(new URL("../i18n.js", import.meta.url), "utf8");
function harness({ fail = false, pending = false } = {}) {
  const calls = [], navigations = [], listeners = {};
  const noop = () => {};
  const elements = Object.fromEntries([
    "downloadRegistrationForm", "downloadName", "downloadEmail", "downloadPrivacyConsent",
    "downloadRegistrationStatus", "riskAck", "apkDownloadButton", "macDownloadButton",
  ].map(id => [id, {
    tagName: id === "apkDownloadButton" ? "BUTTON" : "A", value: "", checked: true,
    validity: { valid: true }, dataset: {}, textContent: "", label: { textContent: "" },
    classList: { toggle: noop }, setAttribute: noop, focus: noop, reportValidity: noop,
    addEventListener: noop, querySelector() { return this.label; },
  }]));
  elements.downloadName.value = " Synthetic Tester ";
  elements.downloadEmail.value = " SYNTHETIC@example.invalid ";
  elements.apkDownloadButton.dataset = { platform: "android" };
  elements.macDownloadButton.dataset = {
    platform: "macos", version: "2.6.0", filename: "SGH.Voice-2.6.0-apple-silicon.dmg",
    downloadHref: "https://example.invalid/synthetic.dmg",
  };
  let finish;
  const firestore = {
    db: {}, collection: (_, name) => name, serverTimestamp: () => "SERVER_TIMESTAMP",
    addDoc: async (collection, data) => {
      calls.push({ collection, data });
      if (fail) throw { code: "permission-denied" };
      if (pending) await new Promise(resolve => { finish = resolve; });
    },
  };
  const context = vm.createContext({
    document: { getElementById: id => elements[id] || null, querySelectorAll: () => [],
      addEventListener: noop, documentElement: { lang: "zh-Hant" } },
    window: { SGH_FIRESTORE_READY: Promise.resolve(firestore), SGH_LANG: "zh",
      addEventListener: (event, callback) => { listeners[event] = callback; },
      location: { assign: url => navigations.push(url) } },
    console: { error: noop },
  });
  vm.runInContext(source, context);
  return { calls, navigations, elements, listeners, finish: () => finish(),
    click: id => context.handleDownload({ preventDefault: noop, currentTarget: elements[id] }) };
}

test("Android creates pending application and never downloads or claims invitation", async () => {
  const h = harness();
  await h.click("apkDownloadButton");
  assert.equal(h.calls.length, 1);
  assert.equal(h.calls[0].collection, "sgh-voice-alpha-applications");
  assert.equal(h.calls[0].data.status, "pending");
  assert.equal(h.calls[0].data.track, "alpha");
  assert.equal(h.calls[0].data.email, "synthetic@example.invalid");
  assert.equal(h.calls[0].data.testingCommitment, true);
  assert.deepEqual(h.navigations, []);
  assert.match(h.elements.downloadRegistrationStatus.textContent, /尚未寄出/);
  assert.equal(h.elements.apkDownloadButton.disabled, true);
  await h.click("apkDownloadButton");
  assert.equal(h.calls.length, 1);
});

test("Android needs both privacy consent and testing commitment", async () => {
  for (const id of ["downloadPrivacyConsent", "riskAck"]) {
    const h = harness(); h.elements[id].checked = false;
    await h.click("apkDownloadButton");
    assert.equal(h.calls.length, 0);
    assert.deepEqual(h.navigations, []);
  }
});

test("failed application is honest, does not download and permits a retry", async () => {
  const h = harness({ fail: true });
  await h.click("apkDownloadButton");
  assert.deepEqual(h.navigations, []);
  assert.equal(h.elements.downloadRegistrationStatus.dataset.state, "error");
  assert.equal(h.elements.apkDownloadButton.disabled, false);
});

test("double click while saving cannot create duplicate submissions", async () => {
  const h = harness({ pending: true });
  const first = h.click("apkDownloadButton");
  await Promise.resolve();
  await h.click("apkDownloadButton");
  assert.equal(h.calls.length, 1);
  h.finish(); await first;
  assert.deepEqual(h.navigations, []);
});

test("macOS registers before navigation and never needs Android commitment", async () => {
  const h = harness(); h.elements.riskAck.checked = false;
  await h.click("macDownloadButton");
  assert.equal(h.calls[0].collection, "sgh-voice-downloads");
  assert.equal(h.calls[0].data.platform, "macos");
  assert.deepEqual(h.navigations, ["https://example.invalid/synthetic.dmg"]);
});

test("failed macOS registration never starts a download", async () => {
  const h = harness({ fail: true });
  await h.click("macDownloadButton");
  assert.deepEqual(h.navigations, []);
});

test("public Android markup has no APK link or download metadata", () => {
  assert.doesNotMatch(html, /\.apk|apkHash|copyHashButton|data-download-href="\/downloads/);
  assert.match(html, /id="apkDownloadButton"[\s\S]*?data-platform="android"/);
  assert.match(html, /"price": "10.00"/);
  assert.match(html, /"priceCurrency": "USD"/);
});

test("all locales disclose pending recruitment, testing commitment and one-time price", () => {
  const context = vm.createContext({ document: { addEventListener() {} } });
  vm.runInContext(i18n + "\nglobalThis.copy = translations;", context);
  for (const lang of ["zh", "ja", "en"]) {
    assert.ok(context.copy[lang]["download.android.success"]);
    assert.match(context.copy[lang]["download.android.price"], /US\$10/);
    assert.match(context.copy[lang]["download.consent"], /14/);
  }
});
