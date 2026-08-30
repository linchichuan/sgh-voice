#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ANDROID_ROOT="$REPO_ROOT/android/SGHVoice"
RELEASE_MANIFEST="$REPO_ROOT/sgh-voice-web/downloads/android-release.json"
KEYCHAIN_SERVICE="${SGH_ANDROID_SIGNING_KEYCHAIN_SERVICE:-com.shingihou.sghvoice.android-release}"

read_keychain_secret() {
    local account="$1"
    if ! command -v security >/dev/null 2>&1; then
        echo "macOS Keychain is unavailable; set the SGH_RELEASE_* environment variables." >&2
        return 1
    fi
    security find-generic-password \
        -s "$KEYCHAIN_SERVICE" \
        -a "$account" \
        -w 2>/dev/null
}

if [[ -z "${SGH_RELEASE_STORE_FILE:-}" ]]; then
    SGH_RELEASE_STORE_FILE="${HOME}/.android/sgh-voice.jks"
fi
if [[ -z "${SGH_RELEASE_STORE_PASSWORD:-}" ]]; then
    SGH_RELEASE_STORE_PASSWORD="$(read_keychain_secret store-password)"
fi
if [[ -z "${SGH_RELEASE_KEY_ALIAS:-}" ]]; then
    SGH_RELEASE_KEY_ALIAS="$(read_keychain_secret key-alias)"
fi
if [[ -z "${SGH_RELEASE_KEY_PASSWORD:-}" ]]; then
    SGH_RELEASE_KEY_PASSWORD="$(read_keychain_secret key-password)"
fi
if [[ -z "${SGH_RELEASE_CERT_SHA256:-}" ]]; then
    SGH_RELEASE_CERT_SHA256="$(python3 -c \
        'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["certificateSha256"])' \
        "$RELEASE_MANIFEST")"
fi

if [[ ! -f "$SGH_RELEASE_STORE_FILE" ]]; then
    echo "Android release keystore is missing." >&2
    exit 1
fi

export SGH_RELEASE_STORE_FILE
export SGH_RELEASE_STORE_PASSWORD
export SGH_RELEASE_KEY_ALIAS
export SGH_RELEASE_KEY_PASSWORD
export SGH_RELEASE_CERT_SHA256

cd "$ANDROID_ROOT"
if (($#)); then
    exec ./gradlew "$@"
fi
exec ./gradlew lintRelease assembleRelease --no-daemon
