#!/bin/bash
# Upload an already verified macOS artifact to an existing draft GitHub release.
# This is intentionally separate from build.sh and is a no-op without --execute.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

TAG=""
ARTIFACT=""
EXECUTE=false

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

usage() {
    cat <<'EOF'
Usage: scripts/publish_macos_release.sh --tag vX.Y.Z --artifact dist/file.dmg [--execute]

Without --execute this performs read-only preflight only. The target release must
already exist as a draft. Existing asset names are immutable and cause failure.
This script never creates or publishes a GitHub Release.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tag)
            [[ $# -ge 2 ]] || fail "--tag requires a value"
            TAG="$2"
            shift 2
            ;;
        --artifact)
            [[ $# -ge 2 ]] || fail "--artifact requires a value"
            ARTIFACT="$2"
            shift 2
            ;;
        --execute)
            EXECUTE=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            fail "unknown argument: $1"
            ;;
    esac
done

[[ "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail "tag must use vX.Y.Z"
[[ -n "$ARTIFACT" ]] || fail "--artifact is required"
[[ "$ARTIFACT" == *.dmg ]] || fail "artifact must be a DMG"
[[ -f "$ARTIFACT" ]] || fail "artifact not found: $ARTIFACT"

CHECKSUM="${ARTIFACT}.sha256"
[[ -f "$CHECKSUM" ]] || fail "checksum not found: $CHECKSUM"

command -v gh >/dev/null 2>&1 || fail "gh CLI is required"
command -v codesign >/dev/null 2>&1 || fail "codesign is required"
command -v xcrun >/dev/null 2>&1 || fail "xcrun is required"
command -v spctl >/dev/null 2>&1 || fail "spctl is required"

[[ -z "$(git status --porcelain --untracked-files=normal)" ]] \
    || fail "publishing requires a clean Git tree"
git tag --points-at HEAD | grep -Fxq "$TAG" \
    || fail "HEAD is not tagged $TAG"

REMOTE_TAG_LINES="$(
    git ls-remote --tags origin "refs/tags/$TAG" "refs/tags/$TAG^{}"
)" || fail "could not resolve remote tag $TAG"
REMOTE_TAG_SHA="$(
    printf '%s\n' "$REMOTE_TAG_LINES" \
        | awk '$2 ~ /\^\{\}$/ { print $1; found=1 } END { if (!found) exit 1 }'
)" || REMOTE_TAG_SHA="$(
    printf '%s\n' "$REMOTE_TAG_LINES" \
        | awk -v ref="refs/tags/$TAG" '$2 == ref { print $1; exit }'
)"
[[ -n "$REMOTE_TAG_SHA" ]] || fail "remote tag $TAG does not exist on origin"
[[ "$REMOTE_TAG_SHA" == "$(git rev-parse HEAD)" ]] \
    || fail "remote tag $TAG does not resolve to local HEAD"

VERSION="${TAG#v}"
[[ "$(basename "$ARTIFACT")" == *"$VERSION"* ]] \
    || fail "artifact filename does not contain release version $VERSION"

EXPECTED_SHA="$(awk 'NR == 1 { print $1 }' "$CHECKSUM")"
ACTUAL_SHA="$(shasum -a 256 "$ARTIFACT" | awk '{ print $1 }')"
[[ "$EXPECTED_SHA" =~ ^[0-9a-fA-F]{64}$ && "$EXPECTED_SHA" == "$ACTUAL_SHA" ]] \
    || fail "artifact checksum mismatch"

codesign --verify --verbose=2 "$ARTIFACT"
xcrun stapler validate "$ARTIFACT"
spctl --assess --type open --context context:primary-signature --verbose=2 "$ARTIFACT"

RELEASE_JSON="$(gh release view "$TAG" --json isDraft,assets,url)" \
    || fail "target release does not exist"
printf '%s' "$RELEASE_JSON" | grep -q '"isDraft":true' \
    || fail "target release must remain a draft during upload"

for asset_name in "$(basename "$ARTIFACT")" "$(basename "$CHECKSUM")"; do
    if printf '%s' "$RELEASE_JSON" | grep -Fq "\"name\":\"$asset_name\""; then
        fail "existing remote asset is immutable: $asset_name"
    fi
done

if [[ "$EXECUTE" != true ]]; then
    echo "Preflight passed. No files uploaded; rerun with --execute after approval."
    exit 0
fi

gh release upload "$TAG" "$ARTIFACT" "$CHECKSUM"
echo "Upload complete. Release remains draft and was not published."
