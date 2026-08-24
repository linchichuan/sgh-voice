#!/usr/bin/env bash

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
IOS_DIR="$PROJECT_DIR/ios/SGHVoice"
APP_DIR="$IOS_DIR/SGHVoice"
PROJECT_FILE="$IOS_DIR/SGHVoice.xcodeproj/project.pbxproj"
PRIVACY_FILE="$APP_DIR/PrivacyInfo.xcprivacy"
ICON_FILE="$APP_DIR/Assets.xcassets/AppIcon.appiconset/AppIcon-1024.png"
ICON_JSON="$APP_DIR/Assets.xcassets/AppIcon.appiconset/Contents.json"
METADATA_DIR="$IOS_DIR/AppStore/Metadata/ja-JP"
REVIEW_DIR="$IOS_DIR/AppStore/Review"
LIVE_PRIVACY_URL="https://voice.shingihou.com/privacy.html"
QUICK=false
SOURCE_ONLY=false
ISSUES=()

case "${1:-}" in
    "") ;;
    --quick) QUICK=true ;;
    --source-only) SOURCE_ONLY=true ;;
    --help|-h)
        echo "Usage: $0 [--quick | --source-only]"
        echo "  --source-only validates repository-owned source/metadata without live App Store gates."
        exit 0
        ;;
    *)
        echo "Usage: $0 [--quick | --source-only]" >&2
        exit 2
        ;;
esac
[[ $# -le 1 ]] || { echo "Usage: $0 [--quick | --source-only]" >&2; exit 2; }

add_issue() {
    ISSUES+=("$1")
}

require_file() {
    local path="$1"
    if [[ ! -f "$path" ]]; then
        add_issue "Missing required file: ${path#$PROJECT_DIR/}"
    fi
}

echo "[iOS] Checking required source and submission files"
REQUIRED_FILES=(
    "$PROJECT_FILE"
    "$PRIVACY_FILE"
    "$ICON_FILE"
    "$ICON_JSON"
    "$APP_DIR/Processing/OutputContracts.swift"
    "$APP_DIR/Support/Localization.swift"
    "$APP_DIR/en.lproj/InfoPlist.strings"
    "$APP_DIR/ja.lproj/InfoPlist.strings"
    "$APP_DIR/zh-Hant.lproj/InfoPlist.strings"
    "$APP_DIR/en.lproj/Localizable.strings"
    "$APP_DIR/ja.lproj/Localizable.strings"
    "$APP_DIR/zh-Hant.lproj/Localizable.strings"
    "$METADATA_DIR/name.txt"
    "$METADATA_DIR/subtitle.txt"
    "$METADATA_DIR/promotional_text.txt"
    "$METADATA_DIR/description.txt"
    "$METADATA_DIR/keywords.txt"
    "$METADATA_DIR/support_url.txt"
    "$METADATA_DIR/privacy_url.txt"
    "$METADATA_DIR/marketing_url.txt"
    "$REVIEW_DIR/beta_description.txt"
    "$REVIEW_DIR/what_to_test.txt"
    "$REVIEW_DIR/review_notes.template.txt"
)
for path in "${REQUIRED_FILES[@]}"; do
    require_file "$path"
done

echo "[iOS] Checking release-critical files are tracked by the outer repository"
for path in "${REQUIRED_FILES[@]}"; do
    [[ -f "$path" ]] || continue
    relative="${path#$PROJECT_DIR/}"
    if ! git -C "$PROJECT_DIR" ls-files --error-unmatch "$relative" >/dev/null 2>&1; then
        add_issue "Release-critical file is not tracked: $relative"
    fi
done

if [[ -d "$IOS_DIR/.git" ]]; then
    add_issue "Nested repository exists at ios/SGHVoice/.git; use the outer repository as the release source of truth"
fi

echo "[iOS] Validating project, privacy manifest and localized purpose strings"
PLIST_FILES=(
    "$PROJECT_FILE"
    "$PRIVACY_FILE"
    "$APP_DIR/en.lproj/InfoPlist.strings"
    "$APP_DIR/ja.lproj/InfoPlist.strings"
    "$APP_DIR/zh-Hant.lproj/InfoPlist.strings"
    "$APP_DIR/en.lproj/Localizable.strings"
    "$APP_DIR/ja.lproj/Localizable.strings"
    "$APP_DIR/zh-Hant.lproj/Localizable.strings"
)
for path in "${PLIST_FILES[@]}"; do
    [[ -f "$path" ]] || continue
    if ! plutil -lint "$path" >/dev/null; then
        add_issue "plutil validation failed: ${path#$PROJECT_DIR/}"
    fi
done

echo "[iOS] Checking localization key parity"
if command -v jq >/dev/null 2>&1; then
    localization_key_files=()
    localization_keys_match=true
    for locale in en ja zh-Hant; do
        path="$APP_DIR/$locale.lproj/Localizable.strings"
        [[ -f "$path" ]] || continue
        key_file="$(mktemp)"
        localization_key_files+=("$key_file")
        if ! plutil -convert json -o - "$path" \
            | jq -r 'keys[]' \
            | LC_ALL=C sort > "$key_file"; then
            add_issue "Could not read localization keys: ${path#$PROJECT_DIR/}"
            localization_keys_match=false
        fi
    done
    if [[ ${#localization_key_files[@]} -eq 3 ]]; then
        if ! cmp -s "${localization_key_files[0]}" "${localization_key_files[1]}" \
            || ! cmp -s "${localization_key_files[0]}" "${localization_key_files[2]}"; then
            add_issue "English, Japanese and Traditional Chinese localization key sets do not match"
            localization_keys_match=false
        fi
        if [[ "$localization_keys_match" == true ]]; then
            localization_key_count="$(wc -l < "${localization_key_files[0]}" | tr -d ' ')"
            if (( localization_key_count < 130 )); then
                add_issue "Localization coverage unexpectedly dropped below 130 keys (${localization_key_count})"
            fi
        fi
    fi
    for key_file in "${localization_key_files[@]}"; do
        rm -f "$key_file"
    done
else
    add_issue "jq is unavailable; localization key parity was not checked"
fi

if ! git -C "$PROJECT_DIR" diff --check -- ios/SGHVoice sgh-voice-web/privacy.html README.md README.ja.md README.en.md; then
    add_issue "git diff --check failed for the iOS release surface"
fi

echo "[iOS] Checking build settings"
if [[ -f "$PROJECT_FILE" ]]; then
    rg -q 'PRODUCT_BUNDLE_IDENTIFIER = com\.shingihou\.SGHVoice;' "$PROJECT_FILE" \
        || add_issue "Unexpected or missing production bundle identifier"
    rg -q 'IPHONEOS_DEPLOYMENT_TARGET = 17\.0;' "$PROJECT_FILE" \
        || add_issue "Expected iOS 17 deployment target is missing"
    rg -q 'INFOPLIST_KEY_ITSAppUsesNonExemptEncryption = NO;' "$PROJECT_FILE" \
        || add_issue "Export-compliance Info.plist key is missing"
    rg -q 'SUPPORTED_PLATFORMS = "iphoneos iphonesimulator";' "$PROJECT_FILE" \
        || add_issue "Unexpected supported platform configuration"
fi

echo "[iOS] Checking App Icon"
if [[ -f "$ICON_FILE" ]]; then
    width="$(sips -g pixelWidth "$ICON_FILE" 2>/dev/null | awk '/pixelWidth/ {print $2}')"
    height="$(sips -g pixelHeight "$ICON_FILE" 2>/dev/null | awk '/pixelHeight/ {print $2}')"
    alpha="$(sips -g hasAlpha "$ICON_FILE" 2>/dev/null | awk '/hasAlpha/ {print $2}')"
    [[ "$width" == "1024" && "$height" == "1024" ]] \
        || add_issue "App Icon must be 1024x1024; found ${width:-unknown}x${height:-unknown}"
    [[ "$alpha" == "no" ]] || add_issue "App Icon must not contain an alpha channel"
fi

echo "[iOS] Checking privacy and provider-boundary invariants"
rg -q 'currentCloudProcessingConsentVersion = 2' "$APP_DIR/API/ApiConfig.swift" \
    || add_issue "Cloud-processing consent must be v2 or newer"
if rg -q 'URLSession\.shared' "$APP_DIR/API"; then
    add_issue "Provider API clients must not use URLSession.shared"
fi
rg -q '詞庫與場景提示' "$APP_DIR/UI/MainView.swift" \
    || add_issue "Dictionary and scene-prompt disclosure is missing from consent UI"
rg -q 'NSPrivacyCollectedDataTypeAudioData' "$PRIVACY_FILE" \
    || add_issue "Privacy manifest does not declare Audio Data"
rg -q 'NSPrivacyCollectedDataTypeOtherUserContent' "$PRIVACY_FILE" \
    || add_issue "Privacy manifest does not declare Other User Content"
if rg -q --hidden --glob '!**/.git/**' --glob '!**/build/**' \
    '(sk-ant-[A-Za-z0-9_-]{16,}|sk-[A-Za-z0-9]{16,}|gsk_[A-Za-z0-9]{16,}|Bearer [A-Za-z0-9_-]{20,})' "$IOS_DIR"; then
    add_issue "Possible provider secret is present in the iOS source tree"
fi
if rg -q 'http://' "$APP_DIR" --glob '*.swift'; then
    add_issue "Insecure HTTP endpoint is present in the iOS application source"
fi

echo "[iOS] Checking local and live privacy policy"
if command -v tidy >/dev/null 2>&1; then
    tidy_output="$(mktemp)"
    tidy -errors -quiet -utf8 "$PROJECT_DIR/sgh-voice-web/privacy.html" >"$tidy_output" 2>&1
    tidy_result=$?
    # HTML Tidy uses exit 1 for warnings and exit 2 for actual errors.  Newer
    # macOS runners emit additional HTML5 warnings; warnings must stay visible
    # without turning an otherwise valid privacy page into a false blocker.
    if (( tidy_result >= 2 )); then
        sed -n '1,80p' "$tidy_output" >&2
        add_issue "Local privacy.html failed tidy validation"
    elif (( tidy_result == 1 )); then
        echo "[iOS] privacy.html tidy warnings (non-blocking)"
        sed -n '1,40p' "$tidy_output"
    fi
    rm -f "$tidy_output"
fi
if [[ "$SOURCE_ONLY" == false ]]; then
    live_privacy="$(curl -fsSL --max-time 20 "$LIVE_PRIVACY_URL" 2>/dev/null || true)"
    if [[ -z "$live_privacy" ]]; then
        add_issue "Live privacy policy is unreachable: $LIVE_PRIVACY_URL"
    else
        [[ "$live_privacy" == *"2026年8月24日"* ]] \
            || add_issue "Live privacy policy is not the 2026-08-24 mobile release version"
        [[ "$live_privacy" == *"Claude Fable 5"* ]] \
            || add_issue "Live privacy policy does not disclose Fable 5 model-specific retention"
        [[ "$live_privacy" == *"platform.claude.com/docs/en/manage-claude/api-and-data-retention"* ]] \
            || add_issue "Live privacy policy does not link the current Anthropic retention terms"
    fi
fi

echo "[iOS] Checking App Store artifacts"
metadata_character_count() {
    local count
    count="$(LC_CTYPE=UTF-8 wc -m < "$1" | tr -d ' ')"
    if [[ -s "$1" && "$(tail -c 1 "$1" | od -An -t u1 | tr -d ' ')" == "10" ]]; then
        count=$((count - 1))
    fi
    printf '%s\n' "$count"
}

metadata_byte_count() {
    local count
    count="$(wc -c < "$1" | tr -d ' ')"
    if [[ -s "$1" && "$(tail -c 1 "$1" | od -An -t u1 | tr -d ' ')" == "10" ]]; then
        count=$((count - 1))
    fi
    printf '%s\n' "$count"
}

check_character_limit() {
    local path="$1"
    local limit="$2"
    local count
    [[ -f "$path" ]] || return
    count="$(metadata_character_count "$path")"
    if (( count > limit )); then
        add_issue "${path#$PROJECT_DIR/} exceeds ${limit} characters (${count})"
    fi
}

check_character_limit "$METADATA_DIR/name.txt" 30
check_character_limit "$METADATA_DIR/subtitle.txt" 30
check_character_limit "$METADATA_DIR/promotional_text.txt" 170
check_character_limit "$METADATA_DIR/description.txt" 4000

if [[ -f "$METADATA_DIR/keywords.txt" ]]; then
    keyword_bytes="$(metadata_byte_count "$METADATA_DIR/keywords.txt")"
    if (( keyword_bytes > 100 )); then
        add_issue "App Store keywords exceed 100 bytes (${keyword_bytes})"
    fi
fi

for url_file in support_url.txt privacy_url.txt marketing_url.txt; do
    path="$METADATA_DIR/$url_file"
    [[ -f "$path" ]] || continue
    value="$(tr -d '\r\n' < "$path")"
    [[ "$value" == https://* ]] || add_issue "App Store URL must use HTTPS: ${path#$PROJECT_DIR/}"
done

if [[ -f "$REVIEW_DIR/review_notes.template.txt" ]]; then
    template_bytes="$(metadata_byte_count "$REVIEW_DIR/review_notes.template.txt")"
    if (( template_bytes > 4000 )); then
        add_issue "Review Notes template exceeds 4000 bytes (${template_bytes})"
    fi
fi

if [[ "$SOURCE_ONLY" == false ]]; then
    final_review_notes="$REVIEW_DIR/review_notes.txt"
    if [[ ! -f "$final_review_notes" ]]; then
        add_issue "Final Review Notes are missing; copy the template only after Evaluation Access is implemented and replace every placeholder"
    else
        final_notes_bytes="$(metadata_byte_count "$final_review_notes")"
        if (( final_notes_bytes > 4000 )); then
            add_issue "Final Review Notes exceed 4000 bytes (${final_notes_bytes})"
        fi
        if rg -q '［提出前入力|<ADD|PLACEHOLDER|TODO' "$final_review_notes"; then
            add_issue "Final Review Notes still contain a placeholder"
        fi
    fi

    if ! rg -q 'Evaluation Access' "$APP_DIR" --glob '*.swift'; then
        add_issue "Evaluation Access is described in submission artifacts but is not implemented in the iOS client"
    fi

    if [[ ! -d "$IOS_DIR/AppStore/Screenshots" ]] \
        || ! find "$IOS_DIR/AppStore/Screenshots" -type f \( -name '*.png' -o -name '*.jpg' -o -name '*.jpeg' \) -print -quit 2>/dev/null | grep -q .; then
        add_issue "App Store screenshots are missing"
    fi
fi

if [[ "$QUICK" == false ]]; then
    echo "[iOS] Type-checking all Swift application sources"
    if command -v swiftc >/dev/null 2>&1; then
        swift_sources=()
        while IFS= read -r source; do
            swift_sources+=("$source")
        done < <(find "$APP_DIR" -name '*.swift' -print | sort)
        if ! swiftc -typecheck -parse-as-library -module-name SGHVoice "${swift_sources[@]}"; then
            add_issue "Swift source type-check failed"
        fi
    else
        add_issue "swiftc is unavailable"
    fi
fi

echo "[iOS] Checking Xcode and iOS SDK upload requirements"
if [[ "$SOURCE_ONLY" == false ]]; then
    if ! command -v xcodebuild >/dev/null 2>&1 || ! xcode_version="$(xcodebuild -version 2>/dev/null)"; then
        add_issue "Full Xcode 26+ is not selected; archive and upload cannot be verified"
    else
        xcode_major="$(printf '%s\n' "$xcode_version" | awk '/^Xcode / {split($2, parts, "."); print parts[1]; exit}')"
        if [[ -z "$xcode_major" || "$xcode_major" -lt 26 ]]; then
            add_issue "Xcode 26+ is required; found ${xcode_major:-unknown}"
        fi
        if ! xcodebuild -showsdks 2>/dev/null | rg -q 'iphoneos26'; then
            add_issue "iOS 26+ SDK is required for App Store uploads"
        fi
    fi
fi

echo
if [[ ${#ISSUES[@]} -gt 0 ]]; then
    echo "[iOS] PRE-FLIGHT BLOCKED (${#ISSUES[@]} issue(s))"
    for issue in "${ISSUES[@]}"; do
        echo "  - $issue"
    done
    echo
    echo "Manual gates not automated here: Apple membership Active, agreements accepted, reviewer access, App Privacy answers, signing, Archive/Validate, and TestFlight smoke."
    exit 1
fi

if [[ "$SOURCE_ONLY" == true ]]; then
    echo "[iOS] Repository-owned source and metadata checks passed"
    echo "Live policy, screenshots, Evaluation Access, Xcode upload requirements, signing and App Store account gates were not evaluated."
else
    echo "[iOS] Automated pre-flight checks passed"
    echo "Manual gates remain: Apple membership Active, agreements accepted, reviewer access, App Privacy answers, signing, Archive/Validate, and TestFlight smoke."
fi
