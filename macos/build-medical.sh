#!/usr/bin/env bash
# Build, verify and package the macOS offline (Japanese, medical) edition.
# Apple Silicon only. Ad-hoc signed (no Apple Developer ID / notarization yet).
set -euo pipefail
cd "$(dirname "$0")/.."
[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]] || { echo "macOS arm64 required"; exit 1; }
export PYTHONIOENCODING=utf-8
VERSION=$(python3 -c "import ast,pathlib;t=ast.parse(pathlib.Path('config.py').read_text(encoding='utf-8'));print(next(ast.literal_eval(n.value) for n in t.body if isinstance(n,ast.Assign) and any(getattr(x,'id','')=='APP_VERSION' for x in n.targets)))")
DIST=dist/macos
BUILD=build/macos
rm -rf "$DIST" "$BUILD"
mkdir -p "$DIST" "$BUILD"
step() { echo "::group::$1"; }
end() { echo "::endgroup::"; }

step "Install dependencies"
python3 -m pip install --only-binary=:all: -r macos/requirements-mac.txt
end

step "Source tests"
python3 -m pytest tests/test_windows_soap.py tests/test_windows_controller.py tests/test_windows_ui.py \
  tests/test_windows_audio_import.py tests/test_windows_llm_fetch.py tests/test_windows_models.py \
  tests/test_mac_medical.py -q -o addopts=
end

step "PyInstaller"
python3 -m PyInstaller --noconfirm --clean --workpath "$BUILD/pyinstaller" --distpath "$DIST" macos/sghvoice-mac.spec
APP="$DIST/SGH Voice Medical.app"
EXE="$APP/Contents/MacOS/SGH Voice"
RES="$APP/Contents/Resources"
[[ -x "$EXE" ]]
end

step "Bundle pinned models (speech + SOAP)"
python3 scripts/fetch_windows_model.py --dest "$RES/models"
python3 scripts/fetch_windows_llm.py --dest "$RES/llm" --platform macos
end

step "Ad-hoc sign"
# Apple Silicon requires a code signature; this is not a Developer ID signature.
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"
end

step "Frozen self-test"
"$EXE" --self-test "$DIST/mac-smoke.json" || { cat "$DIST/mac-smoke.json"; exit 1; }
cat "$DIST/mac-smoke.json"
end

step "Offline recognition + SOAP with the bundled models"
FIX="$BUILD/speech"
python3 scripts/prepare_windows_speech_fixture.py --out "$FIX" --count 5 --skip 40 --phone-mp3
export SGHVOICE_SOAP_STDERR="$BUILD/soap-runtime.log"
"$EXE" --offline-self-test bundled "$DIST/mac-offline-test.json" --speech-set "$FIX/clips.json" \
  --max-cer 0.15 --soap-transcript scripts/fixtures/consultation-ja-fictional.txt || true
unset SGHVOICE_SOAP_STDERR
python3 - "$DIST/mac-offline-test.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
for c in r.get("speech", []):
    print(("IMPORTED " + c.get("format", "") if c.get("imported") else "WAV"), "CER", c["cer"], "in", c["seconds"], "s")
print("overall CER", r.get("cer"), "network attempts", r.get("python_network_attempts"), "error", r.get("error"), r.get("error_code"))
ok = (r.get("ok") and r.get("python_network_attempts") == 0 and r.get("soap_tested")
      and any(c.get("imported") for c in r.get("speech", [])))
sys.exit(0 if ok else 1)
PY
if [[ -f "$BUILD/soap-runtime.log" ]]; then tail -20 "$BUILD/soap-runtime.log" || true; fi
python3 scripts/check_soap_report.py "$DIST/mac-offline-test.json"
end

step "DMG"
STAGE="$BUILD/dmg"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
cp docs/ja/mac-offline-install-guide.md "$STAGE/はじめにお読みください.md"
DMG="$DIST/SGHVoice-macOS-$VERSION-arm64-unsigned.dmg"
hdiutil create -volname "SGH Voice Medical" -srcfolder "$STAGE" -fs HFS+ -format UDZO -ov "$DMG"
rm -rf "$STAGE"
end

step "Checksums"
(
  cd "$DIST"
  shasum -a 256 "$(basename "$DMG")"
  cd "SGH Voice Medical.app/Contents/Resources"
  find models llm -type f \( -name '*.gguf' -o -name 'model.bin' -o -name 'llama-completion' \) -print0 | sort -z | xargs -0 shasum -a 256
) > "$DIST/SHA256SUMS.txt"
cat "$DIST/SHA256SUMS.txt"
ls -l "$DIST"
end
echo "PASS macOS offline edition (ad-hoc signed, not notarized). Microphone and Gatekeeper acceptance NOT RUN."
