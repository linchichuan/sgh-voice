"""Release gates for the staged Windows download and existing platform flows.

These checks are local only. They never create, upload or advertise an installer.
When the manifest eventually says ``available``, its installer and a Windows
acceptance record bound to the same hash must already exist in the checkout.
"""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "sgh-voice-web"
MANIFEST = WEB / "downloads/windows-release.json"


def node(script):
    executable = shutil.which("node")
    if executable is None:
        pytest.skip("Node is required to exercise the actual download-page JavaScript")
    result = subprocess.run(
        [executable, "--input-type=commonjs", "-e", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


HARNESS = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('sgh-voice-web/windows-download.js', 'utf8');
const good = {
  schemaVersion: 1, status: 'available', version: '0.1.0',
  fileName: 'SGHVoice-Windows-0.1.0-x64.exe', sizeBytes: 1048576,
  sha256: 'a'.repeat(64), architecture: 'x64', installerScope: 'per-user', signing: 'unsigned',
  build: {status: 'passed', platform: 'windows', commit: 'b'.repeat(40)},
  acceptance: {status: 'passed', platform: 'windows', sha256: 'a'.repeat(64),
    record: 'docs/windows-acceptance-0.1.0.md'},
};
function harness({manifest = good, httpOK = true, networkError = false} = {}) {
  const navigations = [], events = {}, requests = [], elements = {};
  for (const id of ['windowsDownloadButton', 'windowsReleaseBadge', 'windowsReleaseStatus',
    'windowsReleaseMetadata', 'windowsReleaseVersion', 'windowsReleaseSize', 'windowsReleaseHash']) {
    elements[id] = {disabled: true, hidden: true, attributes: {}, textContent: '', label: {},
      classList: {toggle() {}}, querySelector() {return this.label;},
      setAttribute(key, value) {this.attributes[key] = value;},
      addEventListener(key, callback) {events[id + ':' + key] = callback;}};
  }
  const context = vm.createContext({
    document: {getElementById: id => elements[id] || null},
    window: {SGH_I18N: {}, addEventListener: (event, callback) => {events[event] = callback;},
      location: {assign: value => navigations.push(value)}},
    fetch: async (url, options) => {
      requests.push({url, options});
      if (networkError) throw new Error('offline');
      return {ok: httpOK, json: async () => structuredClone(manifest)};
    },
  });
  vm.runInContext(source, context);
  return {context, elements, navigations, events, requests,
    ready: () => context.loadWindowsRelease(),
    click: () => events['windowsDownloadButton:click']()};
}
"""


def test_public_manifest_has_verified_artifact_or_no_release_claim():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["status"] in {"pending", "available"}
    if manifest["status"] == "pending":
        for key in ("version", "fileName", "sizeBytes", "sha256"):
            assert manifest[key] is None, f"Pending release must not imply an artifact: {key}"
        assert manifest["build"]["status"] == "pending"
        assert manifest["acceptance"]["status"] == "pending"
        assert manifest["acceptance"]["sha256"] is None
        assert manifest["acceptance"]["record"] is None
        return

    node(HARNESS + "assert.ok(harness().context.validatedWindowsRelease(" + json.dumps(manifest) + "));\n")
    artifact = WEB / "downloads" / manifest["fileName"]
    assert artifact.is_file(), "An available download must have a real local installer"
    assert artifact.stat().st_size == manifest["sizeBytes"]
    with artifact.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == manifest["sha256"]
    record = ROOT / manifest["acceptance"]["record"]
    assert record.is_file(), "Record actual Windows acceptance before making download available"
    evidence = record.read_text(encoding="utf-8")
    assert manifest["sha256"] in evidence
    assert manifest["build"]["commit"] in evidence


@pytest.mark.parametrize("mutation", [
    "manifest = null", "manifest.schemaVersion = 2", "manifest.status = 'pending'",
    "manifest.build.status = 'pending'", "manifest.build.platform = 'darwin'",
    "manifest.build.commit = 'abc123'", "manifest.acceptance.status = 'pending'",
    "manifest.acceptance.platform = 'darwin'", "manifest.acceptance.sha256 = 'c'.repeat(64)",
    "manifest.acceptance.record = null", "manifest.acceptance.record = '../../evidence.md'",
    "manifest.fileName = 'https://other.example/installer.exe'",
    "manifest.fileName = '../installer.exe'", "manifest.fileName = 'SGHVoice-Windows-x64.exe?foo'",
    "manifest.fileName = ['SGHVoice-Windows-x64.exe']", "manifest.sha256 = 'invalid'",
    "manifest.sizeBytes = 0", "manifest.sizeBytes = '123'", "manifest.architecture = 'arm64'",
    "manifest.installerScope = 'machine'", "manifest.signing = 'signed'",
    "manifest.version = '<script>broken</script>'", "manifest.version = ['1.2.3']",
])
def test_unverified_or_unsafe_release_never_enables_a_download(mutation):
    node(HARNESS + "let manifest = structuredClone(good);\n" + mutation + r""";
(async () => {
  const h = harness({manifest}); await h.ready(); h.click();
  assert.equal(h.elements.windowsDownloadButton.disabled, true);
  assert.equal(h.elements.windowsDownloadButton.attributes['aria-disabled'], 'true');
  assert.equal(h.elements.windowsReleaseMetadata.hidden, true);
  assert.deepEqual(h.navigations, []);
})().catch(error => {console.error(error); process.exitCode = 1;});
""")


def test_verified_release_uses_own_downloads_path_and_shows_unsigned_notice():
    node(HARNESS + r"""
(async () => {
  const manifest = {...good, downloadUrl: 'https://unexpected.example/bad.exe'};
  const h = harness({manifest});
  h.click(); assert.deepEqual(h.navigations, []);
  await h.ready(); h.click();
  assert.equal(h.elements.windowsDownloadButton.disabled, false);
  assert.equal(h.elements.windowsReleaseMetadata.hidden, false);
  assert.equal(h.elements.windowsReleaseHash.textContent, good.sha256);
  assert.equal(h.elements.windowsReleaseVersion.textContent, '0.1.0');
  assert.match(h.elements.windowsReleaseStatus.textContent, /未簽章/);
  assert.deepEqual(h.navigations, ['/downloads/' + good.fileName]);
  assert.equal(h.requests[0].options.cache, 'no-store');
})().catch(error => {console.error(error); process.exitCode = 1;});
""")


@pytest.mark.parametrize("options", ["{httpOK: false}", "{networkError: true}"])
def test_manifest_unavailable_keeps_download_disabled(options):
    node(HARNESS + f"const h = harness({options});\n" + r"""
(async () => {
  await h.ready(); h.click();
  assert.equal(h.elements.windowsDownloadButton.disabled, true);
  assert.deepEqual(h.navigations, []);
})().catch(error => {console.error(error); process.exitCode = 1;});
""")


def test_windows_markup_fails_closed_without_javascript():
    from html.parser import HTMLParser

    class Buttons(HTMLParser):
        windows = None

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if attrs.get("id") == "windowsDownloadButton":
                self.windows = tag, attrs

    parser = Buttons()
    parser.feed((WEB / "index.html").read_text(encoding="utf-8"))
    tag, attrs = parser.windows
    assert tag == "button"
    assert "disabled" in attrs
    assert attrs["aria-disabled"] == "true"
    assert "href" not in attrs
    assert "data-download-href" not in attrs


def test_windows_hosting_headers_revalidate_manifest_and_download_installer():
    headers = json.loads((WEB / "firebase.json").read_text(encoding="utf-8"))["hosting"]["headers"]
    headers = {entry["source"]: {item["key"]: item["value"] for item in entry["headers"]}
               for entry in headers}
    assert "no-cache" in headers["/downloads/windows-release.json"]["Cache-Control"]
    assert headers["/downloads/*.exe"]["Content-Disposition"] == "attachment"
    assert headers["/downloads/*.exe"]["Content-Type"] == "application/octet-stream"
    assert headers["/downloads/*.exe"]["X-Content-Type-Options"] == "nosniff"


def test_every_locale_has_windows_copy_and_language_changes_preserve_state():
    node(HARNESS + r"""
const i18nContext = vm.createContext({document: {addEventListener() {}}});
vm.runInContext(fs.readFileSync('sgh-voice-web/i18n.js', 'utf8') +
  '\nglobalThis.copy = translations;', i18nContext);
(async () => {
  for (const lang of ['zh', 'ja', 'en']) {
    const copy = i18nContext.copy[lang];
    for (const key of ['nav', 'badgePending', 'badgeReady', 'title', 'pending', 'target',
      'ctaPending', 'ctaReady', 'ready']) assert.ok(copy['download.windows.' + key], lang + ':' + key);
    const h = harness(); await h.ready();
    h.context.window.SGH_I18N = copy; h.events['sgh:languagechange']();
    assert.equal(h.elements.windowsDownloadButton.disabled, false);
    assert.equal(h.elements.windowsReleaseStatus.textContent, copy['download.windows.ready']);
    assert.equal(h.elements.windowsDownloadButton.label.textContent, copy['download.windows.ctaReady']);
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
""")
