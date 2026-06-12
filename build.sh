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
echo -e "${Y}[0/5] 同步版本字串至 ${VERSION}...${N}"
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

if ! command -v create-dmg &> /dev/null; then
    echo -e "${Y}📦 安裝 create-dmg...${N}"
    brew install create-dmg
fi
echo -e "${G}✓${N} create-dmg"

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

# ── Step 3: Code sign（自簽名）──
echo ""
echo -e "${Y}[3/4] Code signing...${N}"
codesign --force --deep --sign - \
    --entitlements resources/entitlements.plist \
    "dist/${APP_NAME}.app" 2>&1
echo -e "${G}✓${N} 自簽名完成"

# ── Step 4: 製作 DMG ──
echo ""
echo -e "${Y}[4/4] 製作 DMG 安裝檔...${N}"

# 移除舊的 DMG
rm -f "dist/${DMG_NAME}.dmg"

create-dmg \
    --volname "Voice Input" \
    --volicon "resources/icon.icns" \
    --window-pos 200 120 \
    --window-size 660 400 \
    --icon-size 100 \
    --icon "${APP_NAME}.app" 180 190 \
    --hide-extension "${APP_NAME}.app" \
    --app-drop-link 480 190 \
    --no-internet-enable \
    "dist/${DMG_NAME}.dmg" \
    "dist/${APP_NAME}.app" 2>&1

if [ ! -f "dist/${DMG_NAME}.dmg" ]; then
    echo -e "${R}❌ DMG 製作失敗${N}"
    exit 1
fi

DMG_SIZE=$(du -sh "dist/${DMG_NAME}.dmg" | cut -f1)

# ── Step 5: 重置輔助使用權限（重新打包後簽名變更，macOS 會拒絕舊授權）──
echo ""
echo -e "${Y}[5/5] 重置輔助使用權限...${N}"
tccutil reset Accessibility com.shingihou.sghvoice 2>/dev/null && \
    echo -e "${G}✓${N} 已重置 TCC 權限（啟動 App 時會自動彈出授權對話框）" || \
    echo -e "${Y}⚠${N} TCC 重置需要管理員權限，啟動 App 時會自動提示授權"

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
echo "   3. 首次開啟需在「系統設定 → 隱私與安全性」允許"
echo "   4. 在選單列的 🎙 圖示旁開啟 Dashboard 設定 API Key"
echo ""
