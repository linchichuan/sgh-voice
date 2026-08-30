#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ANDROID_DIR="$PROJECT_DIR/android/SGHVoice"
WEB_DIR="$PROJECT_DIR/sgh-voice-web"
BUILT_APK="$ANDROID_DIR/app/build/outputs/apk/release/app-release.apk"
RELEASE_MANIFEST="$WEB_DIR/downloads/android-release.json"
SWIFT_CONTRACT="$PROJECT_DIR/ios/SGHVoice/SGHVoice/Processing/OutputContracts.swift"
SWIFT_LOCALIZATION="$PROJECT_DIR/ios/SGHVoice/SGHVoice/Support/Localization.swift"
MODE="full"
PYTHON_BIN="${PYTHON_BIN:-python}"

if [[ -x "$PROJECT_DIR/venv/bin/python" ]] && \
    "$PROJECT_DIR/venv/bin/python" -c 'import pytest' >/dev/null 2>&1; then
    PYTHON_BIN="$PROJECT_DIR/venv/bin/python"
fi

usage() {
    cat <<'EOF'
Usage: verify_mobile_rc.sh [--artifact-only | --install]

  no argument       Run source tests, lint, signed release build, artifact checks,
                    then require a connected Android device. Without a device the
                    result is PARTIAL and exits 3.
  --artifact-only   Verify the public release APK, version, SHA-256 and
                    signer certificate. This mode does not satisfy device QA.
  --install         Run the full checks and install the verified release APK on
                    exactly one connected device; manual RC cases still remain.
EOF
}

case "${1:-}" in
    "") ;;
    --artifact-only) MODE="artifact-only" ;;
    --install) MODE="install" ;;
    --help|-h)
        usage
        exit 0
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac
[[ $# -le 1 ]] || { usage >&2; exit 2; }

fail() {
    echo "[RC] BLOCKED: $*" >&2
    exit 1
}

json_value() {
    local key="$1"
    "$PYTHON_BIN" - "$RELEASE_MANIFEST" "$key" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    value = json.load(handle)[sys.argv[2]]
print(value)
PY
}

find_android_build_tool() {
    local tool="$1"
    local sdk_root="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}"

    if command -v "$tool" >/dev/null 2>&1; then
        command -v "$tool"
        return 0
    fi
    if [[ -z "$sdk_root" && -d "$HOME/Library/Android/sdk" ]]; then
        sdk_root="$HOME/Library/Android/sdk"
    fi
    if [[ -n "$sdk_root" && -d "$sdk_root/build-tools" ]]; then
        find "$sdk_root/build-tools" -type f -name "$tool" -perm -u+x -print 2>/dev/null |
            sort -V |
            tail -n 1
        return 0
    fi
    return 1
}

normalize_fingerprint() {
    # POSIX character classes are locale-sensitive and produced divergent
    # output between macOS and the Ubuntu Actions runner.  Fingerprints are
    # ASCII by definition, so normalize them with an explicit ASCII regex.
    "$PYTHON_BIN" -c 'import re, sys; print(re.sub(r"[^0-9A-Fa-f]", "", sys.stdin.read()).upper(), end="")'
}

sha256_file() {
    local path="$1"
    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$path" | awk '{print $1}'
    elif command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$path" | awk '{print $1}'
    else
        fail "A SHA-256 command (shasum or sha256sum) is required"
    fi
}

[[ -f "$RELEASE_MANIFEST" ]] || fail "Release manifest is missing: sgh-voice-web/downloads/android-release.json"

EXPECTED_VERSION_NAME="$(json_value versionName)"
EXPECTED_VERSION_CODE="$(json_value versionCode)"
EXPECTED_FILE_NAME="$(json_value fileName)"
EXPECTED_SHA256="$(json_value sha256 | tr '[:upper:]' '[:lower:]')"
EXPECTED_CERT_SHA256="$(json_value certificateSha256 | normalize_fingerprint)"
EXPECTED_SIZE="$(json_value sizeBytes)"
PUBLISHED_APK="$WEB_DIR/downloads/$EXPECTED_FILE_NAME"

[[ "$EXPECTED_VERSION_NAME" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail "Invalid versionName in release manifest"
[[ "$EXPECTED_VERSION_CODE" =~ ^[1-9][0-9]*$ ]] || fail "Invalid versionCode in release manifest"
[[ "$EXPECTED_FILE_NAME" == "SGHVoice-Android-v${EXPECTED_VERSION_NAME}.apk" ]] || fail "Release filename is not versioned consistently"
[[ "$EXPECTED_SHA256" =~ ^[0-9a-f]{64}$ ]] || fail "Invalid APK SHA-256 in release manifest"
[[ "$EXPECTED_CERT_SHA256" =~ ^[0-9A-F]{64}$ ]] || fail "Invalid signer certificate SHA-256 in release manifest"
[[ "$EXPECTED_SIZE" =~ ^[1-9][0-9]*$ ]] || fail "Invalid APK size in release manifest"

APKSIGNER_BIN="$(find_android_build_tool apksigner || true)"
AAPT_BIN="$(find_android_build_tool aapt || true)"
[[ -n "$APKSIGNER_BIN" ]] || fail "apksigner is required to verify the release artifact"
[[ -n "$AAPT_BIN" ]] || fail "aapt is required to verify the release artifact version"
command -v openssl >/dev/null 2>&1 || fail "openssl is required to verify the signer certificate"

verify_release_apk() {
    local apk="$1"
    local actual_sha actual_size badging actual_version_code actual_version_name
    local signer_report signer_pem_report signer_pem actual_cert

    [[ -f "$apk" ]] || fail "Expected release APK is missing"

    actual_sha="$(sha256_file "$apk")"
    if stat --version >/dev/null 2>&1; then
        actual_size="$(stat -c '%s' "$apk")"
    else
        actual_size="$(stat -f '%z' "$apk")"
    fi
    [[ "$actual_sha" == "$EXPECTED_SHA256" ]] || fail "Release APK SHA-256 does not match the manifest"
    [[ "$actual_size" == "$EXPECTED_SIZE" ]] || fail "Release APK size does not match the manifest"

    badging="$("$AAPT_BIN" dump badging "$apk")"
    actual_version_code="$(printf '%s\n' "$badging" | sed -n "s/^package:.*versionCode='\([^']*\)'.*/\1/p" | head -n 1)"
    actual_version_name="$(printf '%s\n' "$badging" | sed -n "s/^package:.*versionName='\([^']*\)'.*/\1/p" | head -n 1)"
    [[ "$actual_version_code" == "$EXPECTED_VERSION_CODE" ]] || fail "Release APK versionCode does not match the manifest"
    [[ "$actual_version_name" == "$EXPECTED_VERSION_NAME" ]] || fail "Release APK versionName does not match the manifest"

    signer_report="$("$APKSIGNER_BIN" verify --verbose --print-certs "$apk")"
    printf '%s\n' "$signer_report" | grep -Eq '^Verified using v2 scheme .*: true$' || fail "Release APK is not verified with APK Signature Scheme v2"
    printf '%s\n' "$signer_report" | grep -Eq '^Number of signers: 1$' || fail "Release APK must have exactly one signer"

    # Derive the fingerprint from the certificate bytes instead of parsing
    # apksigner's human-readable digest label, which differs across SDK hosts.
    signer_pem_report="$("$APKSIGNER_BIN" verify --print-certs-pem "$apk")"
    signer_pem="$(
        printf '%s\n' "$signer_pem_report" |
            awk '/-----BEGIN CERTIFICATE-----/{capture=1} capture{print} /-----END CERTIFICATE-----/{exit}'
    )"
    [[ "$signer_pem" == *"-----BEGIN CERTIFICATE-----"* ]] || fail "Release APK signer certificate PEM is missing"
    actual_cert="$(
        printf '%s\n' "$signer_pem" |
            openssl x509 -outform DER 2>/dev/null |
            "$PYTHON_BIN" -c 'import hashlib, sys; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())' |
            normalize_fingerprint
    )"
    if [[ "$actual_cert" != "$EXPECTED_CERT_SHA256" ]]; then
        echo "[RC] expected signer: $EXPECTED_CERT_SHA256" >&2
        echo "[RC] actual signer:   ${actual_cert:-<missing>}" >&2
        fail "Release APK signer certificate does not match the approved fingerprint"
    fi
}

verify_public_copy() {
    verify_release_apk "$PUBLISHED_APK"
    grep -Fq "$EXPECTED_FILE_NAME" "$WEB_DIR/index.html" || fail "Website does not reference the release filename"
    grep -Fq "$EXPECTED_SHA256" "$WEB_DIR/index.html" || fail "Website does not show the release SHA-256"
    grep -Fq "$EXPECTED_VERSION_NAME ($EXPECTED_VERSION_CODE)" "$WEB_DIR/index.html" || fail "Website version does not match the release manifest"
    grep -Fq "$EXPECTED_FILE_NAME" "$WEB_DIR/llms.txt" || fail "llms.txt does not reference the release filename"
    grep -Fq "$EXPECTED_SHA256" "$WEB_DIR/llms.txt" || fail "llms.txt SHA-256 does not match the release manifest"
}

if [[ "$MODE" == "artifact-only" ]]; then
    echo "[RC] Verifying public Android release artifact"
    verify_public_copy
    echo "[RC] ARTIFACT VERIFIED — physical-device QA is not included in --artifact-only mode"
    exit 0
fi

echo "[RC] Checking workspace diff formatting"
git -C "$PROJECT_DIR" diff --check

echo "[RC] Running Python regression suite"
(
    cd "$PROJECT_DIR"
    "$PYTHON_BIN" -m pytest -q
)

if command -v swiftc >/dev/null 2>&1; then
    echo "[RC] Type-checking the iOS translation contract with localization support"
    swiftc -typecheck -parse-as-library -module-name SGHVoice \
        "$SWIFT_LOCALIZATION" \
        "$SWIFT_CONTRACT"
else
    fail "swiftc is required for the iOS translation contract gate"
fi

echo "[RC] Running Android tests, release lint and signed release assembly"
"$PROJECT_DIR/scripts/build_android_sideload_release.sh" \
    testDebugUnitTest lintRelease assembleRelease --no-daemon

verify_release_apk "$BUILT_APK"
verify_public_copy
cmp -s "$BUILT_APK" "$PUBLISHED_APK" || fail "Built release APK differs from the published artifact"

ADB_BIN=""
if command -v adb >/dev/null 2>&1; then
    ADB_BIN="$(command -v adb)"
elif [[ -n "${ANDROID_SDK_ROOT:-}" && -x "$ANDROID_SDK_ROOT/platform-tools/adb" ]]; then
    ADB_BIN="$ANDROID_SDK_ROOT/platform-tools/adb"
elif [[ -x "$HOME/Library/Android/sdk/platform-tools/adb" ]]; then
    ADB_BIN="$HOME/Library/Android/sdk/platform-tools/adb"
fi

if [[ -z "$ADB_BIN" ]]; then
    echo "[RC] PARTIAL: release artifact passed, but adb is unavailable and physical-device QA remains pending" >&2
    exit 3
fi

DEVICE_COUNT="$(
    "$ADB_BIN" devices |
        awk 'NR > 1 && $2 == "device" { count += 1 } END { print count + 0 }'
)"

if [[ "$DEVICE_COUNT" -eq 0 ]]; then
    echo "[RC] PARTIAL: release artifact passed, but no authorized Android device is connected" >&2
    exit 3
fi

if [[ "$MODE" != "install" ]]; then
    echo "[RC] PARTIAL: $DEVICE_COUNT device(s) detected; rerun with --install, then complete docs/ANDROID_RC_ACCEPTANCE.md" >&2
    exit 3
fi

if [[ "$DEVICE_COUNT" -ne 1 ]]; then
    fail "--install requires exactly one authorized Android device"
fi

echo "[RC] Installing the verified release APK on the connected device"
"$ADB_BIN" install -r "$BUILT_APK"
echo "[RC] RELEASE INSTALLED — complete and record every manual case in docs/ANDROID_RC_ACCEPTANCE.md"
