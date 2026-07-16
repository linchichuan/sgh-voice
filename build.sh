#!/bin/bash
# ═══════════════════════════════════════════
# 🎙 Voice Input — 一鍵打包 DMG
# ═══════════════════════════════════════════
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

G='\033[0;32m'
Y='\033[1;33m'
R='\033[0;31m'
C='\033[0;36m'
N='\033[0m'

APP_NAME="SGH Voice"
DMG_APP_NAME="SGH.Voice"
ARCH=$(uname -m)
VERSION=""
RELEASE=false
RELEASE_TAG=""
TARGET_ARCH=""

# ── 參數支援：可自定版本與是否直接上傳 Release
while [[ $# -gt 0 ]]; do
    case "$1" in
        --version)
            VERSION="$2"
            shift 2
            ;;
        --tag)
            RELEASE_TAG="$2"
            shift 2
            ;;
        --arch)
            TARGET_ARCH="$2"
            shift 2
            ;;
        --release)
            RELEASE=true
            shift
            ;;
        -h|--help)
            echo "用法: ./build.sh [--version <version>] [--tag <tag>] [--release]"
            echo "範例: ./build.sh --version 2.5.0 --release --tag v2.5.0"
            exit 0
            ;;
        *)
            if [[ -z "$VERSION" ]]; then
                VERSION="$1"
                shift
            else
                echo -e "${R}❌ 未知參數: $1${N}"
                exit 1
            fi
            ;;
    esac
done

if [ -z "$VERSION" ]; then
    # 預設改用 app.py 內部版本，避免硬編碼遺漏
    VERSION="$(sed -n 's/.*self.version = "\([^"]*\)"/\1/p' app.py | head -n 1)"
fi

if [ -z "$VERSION" ]; then
    echo -e "${R}❌ 無法自動取得版本，請用 --version 指定${N}"
    exit 1
fi

ARCH=${TARGET_ARCH:-$ARCH}
if [ "$ARCH" = "x86_64" ] || [ "$ARCH" = "intel" ]; then
    PYI_TARGET_ARCH="x86_64"
    DMG_NAME="${DMG_APP_NAME}-${VERSION}-intel"
elif [ "$ARCH" = "universal2" ]; then
    PYI_TARGET_ARCH="universal2"
    DMG_NAME="${DMG_APP_NAME}-${VERSION}-universal2"
elif [ "$ARCH" = "arm64" ] || [ "$ARCH" = "apple-silicon" ] || [ "$ARCH" = "apple_silicon" ]; then
    PYI_TARGET_ARCH="arm64"
    DMG_NAME="${DMG_APP_NAME}-${VERSION}-apple-silicon"
else
    PYI_TARGET_ARCH="auto"
    DMG_NAME="${DMG_APP_NAME}-${VERSION}-${ARCH}"
fi

# Normalized architecture label used for status output
ARCH_LABEL="$ARCH"

echo ""
echo -e "${C}🎙 Voice Input — Build DMG${N}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── 自動同步版本字串到所有檔案（避免三處不同步）──
echo -e "${Y}[0/4] 同步版本字串至 ${VERSION}...${N}"
# voiceinput.spec — Info.plist 版本
sed -i '' "s/'CFBundleVersion': '[^']*'/'CFBundleVersion': '${VERSION}'/" voiceinput.spec
sed -i '' "s/'CFBundleShortVersionString': '[^']*'/'CFBundleShortVersionString': '${VERSION}'/" voiceinput.spec
# static/index.html — Dashboard 左下角顯示
sed -i '' "s|>v[0-9]\\.[0-9]\\.[0-9]<|>v${VERSION}<|" static/index.html
# app.py — engine.version
sed -i '' "s/self\\.version = \"[^\"]*\"/self.version = \"${VERSION}\"/" app.py
echo -e "${G}✓${N} 已同步 voiceinput.spec / static/index.html / app.py"
echo ""

# ── 啟動 venv ──
if [ -d "venv" ]; then
    source venv/bin/activate
    echo -e "${G}✓${N} 虛擬環境已啟動"
else
    echo -e "${R}❌ venv 不存在，請先執行 run.sh${N}"
    exit 1
fi

# ── 檢查工具 ──
if ! command -v pyinstaller &> /dev/null; then
    echo -e "${Y}📦 安裝 PyInstaller...${N}"
    pip install -q pyinstaller
fi
echo -e "${G}✓${N} PyInstaller $(pyinstaller --version)"

if ! command -v hdiutil &> /dev/null; then
    echo -e "${R}❌ 找不到 macOS hdiutil${N}"
    exit 1
fi
echo -e "${G}✓${N} hdiutil"

# ── Step 1: 清理 ──
echo ""
echo -e "${Y}[1/4] 清理舊的建構產物...${N}"
rm -rf build/ dist/
echo -e "${G}✓${N} 清理完成"

# ── Step 2: PyInstaller 打包 ──
echo ""
echo -e "${Y}[2/4] PyInstaller 打包中（需要幾分鐘）...${N}"
if [ "$PYI_TARGET_ARCH" = "x86_64" ]; then
    PYI_CMD="arch -x86_64 pyinstaller"
else
    PYI_CMD="pyinstaller"
fi

eval "${PYI_CMD} voiceinput.spec --noconfirm" 2>&1 | while IFS= read -r line; do
    # 只顯示關鍵訊息
    if echo "$line" | grep -qE "(ERROR|WARNING|Building|Completed)"; then
        echo "   $line"
    fi
done

if [ ! -d "dist/${APP_NAME}.app" ]; then
    echo -e "${R}❌ 打包失敗，請查看上方錯誤訊息${N}"
    exit 1
fi
echo -e "${G}✓${N} .app bundle 建構完成"

# 顯示體積
APP_SIZE=$(du -sh "dist/${APP_NAME}.app" | cut -f1)
echo "   體積: ${APP_SIZE}"

# ── Step 3: Code sign ──
echo ""
echo -e "${Y}[3/4] Code signing...${N}"
SIGN_IDENTITY="${CODE_SIGN_IDENTITY:-}"
if [ -z "$SIGN_IDENTITY" ]; then
    SIGN_IDENTITY="$(security find-identity -v -p codesigning 2>/dev/null \
        | awk -F'"' '/Developer ID Application:|Apple Development:/ { print $2; exit }')"
fi

if [ -n "$SIGN_IDENTITY" ]; then
    # 固定 Team ID + bundle id 讓 macOS TCC 可跨版本沿用輔助使用權限。
    codesign --force --deep --options runtime --timestamp=none \
        --sign "$SIGN_IDENTITY" \
        --entitlements resources/entitlements.plist \
        "dist/${APP_NAME}.app" 2>&1
    echo -e "${G}✓${N} 已使用穩定 Apple signing identity"
else
    # 沒有憑證的開發機仍可 build，但每次 ad-hoc signature 都可能需要重新授權。
    codesign --force --deep --sign - \
        --entitlements resources/entitlements.plist \
        "dist/${APP_NAME}.app" 2>&1
    echo -e "${Y}⚠${N} 未找到 Apple signing identity，已使用 ad-hoc signature"
fi

codesign --verify --deep --strict "dist/${APP_NAME}.app"
echo -e "${G}✓${N} Code signature 驗證通過"

# ── Step 4: 製作 DMG ──
echo ""
echo -e "${Y}[4/4] 製作 DMG 安裝檔...${N}"

# create-dmg 依賴 Finder AppleScript，CI、無 Dock session 或權限對話框存在時
# 可能永久卡住。改用 headless hdiutil，內容仍包含 App + Applications 捷徑。
DMG_STAGE="build/dmg-staging"
rm -rf "$DMG_STAGE"
mkdir -p "$DMG_STAGE"
ditto "dist/${APP_NAME}.app" "$DMG_STAGE/${APP_NAME}.app"
ln -s /Applications "$DMG_STAGE/Applications"
cp resources/icon.icns "$DMG_STAGE/.VolumeIcon.icns"
SetFile -a C "$DMG_STAGE" 2>/dev/null || true

rm -f "dist/${DMG_NAME}.dmg"
hdiutil create \
    -volname "SGH Voice" \
    -srcfolder "$DMG_STAGE" \
    -format UDZO \
    -imagekey zlib-level=9 \
    -ov "dist/${DMG_NAME}.dmg"

if [ ! -f "dist/${DMG_NAME}.dmg" ]; then
    echo -e "${R}❌ DMG 製作失敗${N}"
    exit 1
fi

DMG_SIZE=$(du -sh "dist/${DMG_NAME}.dmg" | cut -f1)

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${G}✅ 打包完成！${N}"
echo ""
echo -e "   📦 App:  dist/${APP_NAME}.app (${APP_SIZE})"
echo -e "   💿 DMG:  dist/${DMG_NAME}.dmg (${DMG_SIZE})"
if [ "$RELEASE" = true ]; then
    RELEASE_TAG_CLEAN="${RELEASE_TAG:-v${VERSION}}"
    if [[ "${RELEASE_TAG_CLEAN}" != v* ]]; then
        RELEASE_TAG_CLEAN="v${RELEASE_TAG_CLEAN}"
    fi
    echo -e "${Y}[6/6] 上傳 DMG 到 GitHub Release ${RELEASE_TAG_CLEAN}...${N}"
    if ! command -v gh &> /dev/null; then
        echo -e "${R}❌ 缺少 gh CLI，請先安裝或先行手動上傳${N}"
        exit 1
    fi
    if ! gh release view "${RELEASE_TAG_CLEAN}" >/dev/null 2>&1; then
        gh release create "${RELEASE_TAG_CLEAN}" --title "SGH Voice ${VERSION}" --notes "Release ${VERSION}"
    fi
    gh release upload "${RELEASE_TAG_CLEAN}" "dist/${DMG_NAME}.dmg" --clobber
    echo -e "${G}✅ Release 已更新：${RELEASE_TAG_CLEAN}${N}"
fi
echo ""
echo -e "${C}安裝方式：${N}"
echo "   1. 雙擊 .dmg 檔案"
echo "   2. 將 Voice Input 拖入 Applications 資料夾"
echo "   3. 第一次安裝時需在「系統設定 → 隱私與安全性」允許；後續同一簽章版本會沿用"
echo "   4. 從選單列的 SGH Voice 圖示開啟 Dashboard 設定 API Key"
echo ""
