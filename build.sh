#!/bin/bash
# SGH Voice macOS packaging entrypoint.
# Default mode creates a local test DMG. --release creates a Developer ID signed,
# notarized, stapled artifact but never publishes or overwrites a remote release.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
umask 077

G='\033[0;32m'
Y='\033[1;33m'
R='\033[0;31m'
C='\033[0;36m'
N='\033[0m'

APP_NAME="SGH Voice"
DMG_APP_NAME="SGH.Voice"
HOST_ARCH="$(uname -m)"
VERSION=""
TARGET_ARCH=""
RELEASE=false
PREFLIGHT_ONLY=false
BUILD_VENV="${SGH_BUILD_VENV:-$SCRIPT_DIR/venv}"

fail() {
    echo -e "${R}❌ $*${N}" >&2
    exit 1
}

usage() {
    cat <<'EOF'
用法: ./build.sh [--version <version>] [--arch <arm64|x86_64|universal2>] [--release] [--preflight]

一般模式：建立本機測試 DMG；找不到 Apple 憑證時允許 ad-hoc 簽章。
正式模式：--release 僅建立本機正式產物，不會建立或覆蓋 GitHub Release。

正式模式必要條件：
  CODE_SIGN_IDENTITY         Developer ID Application 憑證名稱（可省略並自動尋找）
  NOTARY_KEYCHAIN_PROFILE    已由 notarytool store-credentials 建立的 Keychain profile
  乾淨 Git tree，且 HEAD 必須有與版本一致的 v<version> tag

所有模式固定使用 Python 3.12 與 requirements-dev.lock。若環境不在 ./venv，
請以 SGH_BUILD_VENV 指向已由 lock 建立的虛擬環境。

範例：
  ./build.sh --preflight
  ./build.sh --version 2.7.0
  NOTARY_KEYCHAIN_PROFILE=SGH_NOTARY ./build.sh --version 2.7.0 --release --preflight
  NOTARY_KEYCHAIN_PROFILE=SGH_NOTARY ./build.sh --version 2.7.0 --release
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --version)
            [[ $# -ge 2 ]] || fail "--version 缺少值"
            VERSION="$2"
            shift 2
            ;;
        --arch)
            [[ $# -ge 2 ]] || fail "--arch 缺少值"
            TARGET_ARCH="$2"
            shift 2
            ;;
        --release)
            RELEASE=true
            shift
            ;;
        --preflight)
            PREFLIGHT_ONLY=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            fail "未知參數: $1"
            ;;
    esac
done

APP_SOURCE_VERSION="$(sed -n 's/.*self.version = "\([^"]*\)"/\1/p' app.py | head -n 1)"
DASHBOARD_SOURCE_VERSION="$(sed -n 's/.*>v\([0-9][0-9.]*\)<.*/\1/p' static/index.html | head -n 1)"
VERSION="${VERSION:-$APP_SOURCE_VERSION}"

[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail "版本必須是 x.y.z 格式"
[[ "$APP_SOURCE_VERSION" == "$VERSION" ]] || fail "app.py 版本 ${APP_SOURCE_VERSION:-unknown} 與建置版本 $VERSION 不一致"
[[ "$DASHBOARD_SOURCE_VERSION" == "$VERSION" ]] || fail "Dashboard 版本 ${DASHBOARD_SOURCE_VERSION:-unknown} 與建置版本 $VERSION 不一致"

ARCH="${TARGET_ARCH:-$HOST_ARCH}"
case "$ARCH" in
    arm64|apple-silicon|apple_silicon)
        PYI_TARGET_ARCH="arm64"
        DMG_NAME="${DMG_APP_NAME}-${VERSION}-apple-silicon"
        ;;
    x86_64|intel)
        PYI_TARGET_ARCH="x86_64"
        DMG_NAME="${DMG_APP_NAME}-${VERSION}-intel"
        ;;
    universal2)
        PYI_TARGET_ARCH="universal2"
        DMG_NAME="${DMG_APP_NAME}-${VERSION}-universal2"
        ;;
    *)
        fail "不支援的架構: $ARCH"
        ;;
esac

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "缺少必要工具: $1"
}

release_require_developer_id() {
    local identity="$1"
    local identities
    identities="$(security find-identity -v -p codesigning 2>/dev/null || true)"
    if [[ "$identity" != Developer\ ID\ Application:* ]] \
        && ! printf '%s\n' "$identities" | grep -F "$identity" | grep -q "Developer ID Application:"; then
        fail "正式建置只接受 Developer ID Application 憑證"
    fi
}

release_require_clean_tree() {
    require_command git
    [[ -z "$(git status --porcelain --untracked-files=normal)" ]] \
        || fail "正式建置要求乾淨 Git tree；請先審核並提交變更"
    git tag --points-at HEAD | grep -Fxq "v${VERSION}" \
        || fail "正式建置要求 HEAD 具有 v${VERSION} tag"
}

find_signing_identity() {
    if [[ -n "${CODE_SIGN_IDENTITY:-}" ]]; then
        printf '%s\n' "$CODE_SIGN_IDENTITY"
        return
    fi

    if [[ "$RELEASE" == true ]]; then
        security find-identity -v -p codesigning 2>/dev/null \
            | awk -F'"' '/Developer ID Application:/ { print $2; exit }'
    else
        security find-identity -v -p codesigning 2>/dev/null \
            | awk -F'"' '/Developer ID Application:|Apple Development:/ { print $2; exit }'
    fi
}

echo ""
echo -e "${C}SGH Voice macOS build ${VERSION} (${PYI_TARGET_ARCH})${N}"

[[ -f requirements-dev.lock ]] || fail "requirements-dev.lock 不存在"
[[ -d "$BUILD_VENV" ]] || fail "建置環境不存在：$BUILD_VENV；請依 requirements-dev.lock 建立"
# shellcheck disable=SC1091
source "$BUILD_VENV/bin/activate"

PYTHON_MINOR="$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
[[ "$PYTHON_MINOR" == "3.12" ]] \
    || fail "建置固定要求 Python 3.12；目前為 $PYTHON_MINOR（環境：$BUILD_VENV）"

require_command pyinstaller
require_command pyi-archive_viewer
require_command hdiutil
require_command codesign
require_command ditto
require_command shasum

SIGN_IDENTITY="$(find_signing_identity)"
if [[ "$RELEASE" == true ]]; then
    require_command security
    require_command xcrun
    require_command spctl
    [[ -n "$SIGN_IDENTITY" ]] || fail "找不到 Developer ID Application 憑證"
    release_require_developer_id "$SIGN_IDENTITY"
    [[ -n "${NOTARY_KEYCHAIN_PROFILE:-}" ]] || fail "正式建置需要 NOTARY_KEYCHAIN_PROFILE"
    release_require_clean_tree
    xcrun notarytool history --keychain-profile "$NOTARY_KEYCHAIN_PROFILE" >/dev/null \
        || fail "notarytool Keychain profile 驗證失敗"
fi

echo -e "${G}✓${N} PyInstaller $(pyinstaller --version)"
echo -e "${G}✓${N} 建置來源版本一致"
if [[ "$RELEASE" == true ]]; then
    echo -e "${G}✓${N} Developer ID、notary profile、Git tag preflight 通過"
elif [[ -z "$SIGN_IDENTITY" ]]; then
    echo -e "${Y}⚠${N} 本機測試模式將使用 ad-hoc 簽章"
fi

if [[ "$PREFLIGHT_ONLY" == true ]]; then
    echo -e "${G}✅ Preflight 完成，未建立或發布任何產物${N}"
    exit 0
fi

echo -e "${Y}[1/5] 清理舊建置產物...${N}"
rm -rf build/ dist/
mkdir -p build/ dist/
touch build/.metadata_never_index dist/.metadata_never_index

echo -e "${Y}[2/5] PyInstaller 打包...${N}"
export SGH_BUILD_VERSION="$VERSION"
export SGH_PYI_TARGET_ARCH="$PYI_TARGET_ARCH"
if [[ "$PYI_TARGET_ARCH" == "x86_64" && "$HOST_ARCH" == "arm64" ]]; then
    arch -x86_64 pyinstaller voiceinput.spec --noconfirm
else
    pyinstaller voiceinput.spec --noconfirm
fi

APP_PATH="dist/${APP_NAME}.app"
[[ -d "$APP_PATH" ]] || fail "PyInstaller 未建立 $APP_PATH"

BUILT_VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$APP_PATH/Contents/Info.plist")"
[[ "$BUILT_VERSION" == "$VERSION" ]] || fail "App bundle 版本 $BUILT_VERSION 與 $VERSION 不一致"

# PyInstaller can complete while reporting a newly added top-level module as
# missing. Gate the actual embedded PYZ, not only the build exit code.
ARCHIVE_LIST="$(pyi-archive_viewer "$APP_PATH/Contents/MacOS/${APP_NAME}" -r -b)"
REQUIRED_PYTHON_MODULES=(
    app config dashboard event_ledger memory transcriber translation
    mlx mlx.nn mlx_whisper
)
for required_module in "${REQUIRED_PYTHON_MODULES[@]}"; do
    grep -Eq "^[[:space:]]*${required_module}$" <<< "$ARCHIVE_LIST" \
        || fail "App bundle 缺少必要 Python 模組: $required_module"
done

# mlx.core is a native extension and therefore lives beside the PYZ instead of
# appearing as a pure-Python archive entry. Gate the complete Metal runtime.
MLX_CORE_MODULE="$(
    find "$APP_PATH/Contents/Frameworks/mlx" \
        -maxdepth 1 -type f -name 'core*.so' -print -quit 2>/dev/null
)"
[[ -n "$MLX_CORE_MODULE" ]] || fail "App bundle 缺少必要 native 模組: mlx.core"
[[ -f "$APP_PATH/Contents/Frameworks/mlx/lib/libmlx.dylib" ]] \
    || fail "App bundle 缺少 libmlx.dylib"
[[ -f "$APP_PATH/Contents/Resources/mlx/lib/mlx.metallib" ]] \
    || fail "App bundle 缺少 mlx.metallib"

echo -e "${Y}[3/5] Code signing...${N}"
if [[ -n "$SIGN_IDENTITY" ]]; then
    codesign --force --deep --options runtime --timestamp \
        --sign "$SIGN_IDENTITY" \
        --entitlements resources/entitlements.plist \
        "$APP_PATH"
else
    codesign --force --deep --sign - \
        --entitlements resources/entitlements.plist \
        "$APP_PATH"
fi
codesign --verify --deep --strict --verbose=2 "$APP_PATH"

ACTUAL_ARCHS="$(lipo -archs "$APP_PATH/Contents/MacOS/${APP_NAME}")"
if [[ "$PYI_TARGET_ARCH" == "universal2" ]]; then
    [[ "$ACTUAL_ARCHS" == *arm64* && "$ACTUAL_ARCHS" == *x86_64* ]] \
        || fail "預期 universal2，實際架構為: $ACTUAL_ARCHS"
else
    [[ " $ACTUAL_ARCHS " == *" $PYI_TARGET_ARCH "* ]] \
        || fail "預期 $PYI_TARGET_ARCH，實際架構為: $ACTUAL_ARCHS"
fi

echo -e "${Y}[4/5] 建立 DMG...${N}"
DMG_STAGE="build/dmg-staging"
DMG_PATH="dist/${DMG_NAME}.dmg"
rm -rf "$DMG_STAGE"
mkdir -p "$DMG_STAGE"
ditto "$APP_PATH" "$DMG_STAGE/${APP_NAME}.app"
ln -s /Applications "$DMG_STAGE/Applications"
cp resources/icon.icns "$DMG_STAGE/.VolumeIcon.icns"
SetFile -a C "$DMG_STAGE" 2>/dev/null || true

hdiutil create \
    -volname "SGH Voice" \
    -srcfolder "$DMG_STAGE" \
    -format UDZO \
    -imagekey zlib-level=9 \
    -ov "$DMG_PATH"
rm -rf "$DMG_STAGE"
[[ -f "$DMG_PATH" ]] || fail "DMG 建立失敗"

if [[ "$RELEASE" == true ]]; then
    echo -e "${Y}[5/5] DMG 簽章、公證與 Gatekeeper 驗證...${N}"
    codesign --force --options runtime --timestamp --sign "$SIGN_IDENTITY" "$DMG_PATH"
    codesign --verify --verbose=2 "$DMG_PATH"
    xcrun notarytool submit "$DMG_PATH" \
        --keychain-profile "$NOTARY_KEYCHAIN_PROFILE" \
        --wait
    xcrun stapler staple "$DMG_PATH"
    xcrun stapler validate "$DMG_PATH"
    spctl --assess --type open --context context:primary-signature --verbose=2 "$DMG_PATH"
else
    echo -e "${Y}[5/5] 本機測試產物驗證...${N}"
    hdiutil verify "$DMG_PATH"
fi

CHECKSUM_PATH="${DMG_PATH}.sha256"
shasum -a 256 "$DMG_PATH" > "$CHECKSUM_PATH"
chmod 600 "$DMG_PATH" "$CHECKSUM_PATH"

APP_SIZE="$(du -sh "$APP_PATH" | cut -f1)"
DMG_SIZE="$(du -sh "$DMG_PATH" | cut -f1)"
echo ""
echo -e "${G}✅ 建置完成${N}"
echo "   App:      $APP_PATH ($APP_SIZE)"
echo "   DMG:      $DMG_PATH ($DMG_SIZE)"
echo "   SHA-256:  $CHECKSUM_PATH"
if [[ "$RELEASE" == true ]]; then
    echo "   狀態:     Developer ID signed + notarized + stapled"
    echo "   發布:     未執行；遠端 Release 必須另行審核並使用不可覆寫流程"
else
    echo "   狀態:     local test artifact（未公證，不可當正式公開版）"
fi
