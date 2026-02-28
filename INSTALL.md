# 🎙 Voice Input — 完整安裝教學

> 適用對象：Mac 使用者，不需要任何程式經驗。
> 預估安裝時間：10-15 分鐘。

---

## 📋 你需要準備的東西

| 項目 | 說明 | 費用 |
|------|------|------|
| Mac 電腦 | macOS 12 以上 | — |
| OpenAI API Key | Whisper 語音辨識用 | 約 $5/月 |
| Anthropic API Key | Claude 後處理潤稿用（選配但強烈推薦） | 約 $5/月 |

**合計約 $5~10/月**（對比 Typeless $30/月）

---

## 第一步：安裝 Homebrew（Mac 的套件管理工具）

打開「終端機」（Terminal）：
- 方法：按 `Cmd + 空白鍵`，輸入 `Terminal`，按 Enter

在終端機裡，**複製貼上**以下指令，按 Enter：

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

> 過程中可能會要你輸入 Mac 的登入密碼（輸入時畫面不會顯示，正常現象），輸入完按 Enter。
> 安裝大約需要 2-5 分鐘。

裝完後，測試是否成功：
```bash
brew --version
```
如果顯示版本號（例如 `Homebrew 4.x.x`），就成功了。

**⚠️ Apple Silicon Mac（M1/M2/M3/M4）額外步驟：**

如果裝完 brew 後顯示提示要你執行兩行指令，請照做：
```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

---

## 第二步：安裝 Python

在終端機裡執行：

```bash
brew install python3
```

測試：
```bash
python3 --version
```
顯示 `Python 3.x.x` 就成功了。

---

## 第三步：取得 API Key

### 3-A：OpenAI API Key（必要 — Whisper 語音辨識）

1. 打開瀏覽器，前往 https://platform.openai.com/signup
2. 註冊帳號（可以用 Google 登入）
3. 登入後，前往 https://platform.openai.com/api-keys
4. 點「+ Create new secret key」
5. 名稱隨便填（例如 `voice-input`），點 Create
6. **立刻複製顯示的 Key**（sk-proj-... 開頭），存到備忘錄
   > ⚠️ 這個 Key 只會顯示一次！關掉就看不到了！
7. 前往 https://platform.openai.com/settings/organization/billing
8. 點「Add payment method」加入信用卡
9. 建議設定月用量上限 $10（Settings → Limits → Usage limits）

### 3-B：Anthropic API Key（選配但推薦 — Claude 智慧潤稿）

1. 前往 https://console.anthropic.com/
2. 註冊帳號
3. 登入後，前往 https://console.anthropic.com/settings/keys
4. 點「Create Key」
5. 名稱填 `voice-input`，點 Create
6. **立刻複製 Key**（sk-ant-... 開頭），存到備忘錄
7. 前往 https://console.anthropic.com/settings/plans 加入信用卡（或使用預付方案）

> 💡 沒有 Anthropic Key 也能用，只是少了 Claude 的智慧潤稿功能。
> Whisper 會照常辨識，詞庫修正也會正常運作。

---

## 第四步：下載 Voice Input

在終端機裡，**逐行複製貼上**執行：

```bash
cd ~
mkdir -p voice-input
cd voice-input
```

然後把你從 Claude 下載的 voice-input 資料夾裡的**所有檔案**，
用 Finder 拖進 `~/voice-input/` 資料夾。

> 📂 Finder 快速到達：在 Finder 按 `Cmd + Shift + G`，輸入 `~/voice-input`

確認檔案結構正確：
```bash
ls ~/voice-input/
```

你應該看到：
```
README.md    app.py       config.py    dashboard.py
data/        memory.py    recorder.py  requirements.txt
run.sh       static/      transcriber.py
INSTALL.md
```

---

## 第五步：一鍵安裝啟動

```bash
cd ~/voice-input
chmod +x run.sh
./run.sh
```

這個指令會自動做以下事情：
1. ✅ 安裝 portaudio（錄音需要）
2. ✅ 建立 Python 虛擬環境
3. ✅ 安裝所有 Python 套件
4. ✅ 匯入 88 條修正規則 + 70 個自訂詞彙（你的業務術語）
5. ✅ 啟動 Dashboard + 選單列應用

> 第一次安裝大約需要 2-3 分鐘。

---

## 第六步：填入 API Key

瀏覽器會自動開啟 http://localhost:7865

1. 點左邊選單的「⚙️ 設定」
2. 在 **OpenAI API Key** 欄位貼上你的 `sk-proj-...` Key
3. 在 **Anthropic API Key** 欄位貼上你的 `sk-ant-...` Key（如果有的話）
4. 其他設定保持預設即可
5. 點最下面的「💾 儲存設定」

---

## 第七步：macOS 權限授權

啟動後，Mac 會陸續跳出權限請求。**請全部按「允許」/「OK」：**

### 麥克風權限
- 系統設定 → 隱私與安全性 → 麥克風 → 找到 Terminal（或你用的終端機），**打勾** ✅

### 輔助使用權限（自動貼上需要）
- 系統設定 → 隱私與安全性 → 輔助使用 → 點「+」→ 加入 Terminal，**打勾** ✅

### 輸入監控（快捷鍵需要）
- 系統設定 → 隱私與安全性 → 輸入監控 → 找到 Terminal，**打勾** ✅

> 💡 如果你用 iTerm2 或其他終端機，請授權給那個 App 而非 Terminal。
> 授權完後可能需要重新啟動 `./run.sh`。

---

## ✅ 完成！開始使用

### 選單列圖示

螢幕右上角會出現 🎙 圖示，代表 Voice Input 正在背景運行。

### 使用方式：按住 Right Cmd（⌘）說話

1. 把游標放在任何你想輸入文字的地方（Mail、LINE、Slack、備忘錄…任何 App）
2. **按住右邊的 Cmd 鍵（⌘）**
3. 開始說話（中文、日文、英文都可以，可以混著說）
4. **放開 Cmd 鍵**
5. 等 1-3 秒，辨識結果會自動貼上

選單列圖示會變化：
- 🎙 = 待命中
- 🔴 = 錄音中
- ⏳ = 辨識處理中

### Dashboard

隨時可以點選單列的「📊 開啟 Dashboard」，或瀏覽器開 http://localhost:7865

- **總覽**：看你節省了多少時間
- **歷史紀錄**：搜尋查看過去的辨識結果
- **詞庫記憶**：新增/刪除專業術語
- **設定**：調整各種參數

---

## 🔄 之後要啟動怎麼做？

每次重開機或關掉終端機後，需要重新啟動：

```bash
cd ~/voice-input
./run.sh
```

> 💡 如果你想開機自動啟動，在終端機執行以下指令（只需執行一次）：

```bash
cd ~/voice-input
source venv/bin/activate

cat > ~/Library/LaunchAgents/com.voice-input.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.voice-input</string>
    <key>ProgramArguments</key>
    <array>
        <string>$HOME/voice-input/venv/bin/python3</string>
        <string>$HOME/voice-input/app.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$HOME/voice-input</string>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
EOF

launchctl load ~/Library/LaunchAgents/com.voice-input.plist
echo "✅ 已設定開機自動啟動"
```

要取消開機啟動：
```bash
launchctl unload ~/Library/LaunchAgents/com.voice-input.plist
rm ~/Library/LaunchAgents/com.voice-input.plist
```

---

## ❓ 常見問題

### Q：按住 Right Cmd 沒反應？
→ 確認「輸入監控」權限已授權給 Terminal
→ 試試重新啟動 `./run.sh`

### Q：辨識結果沒有自動貼上？
→ 確認「輔助使用」權限已授權給 Terminal

### Q：辨識很慢（超過 5 秒）？
→ 檢查網路連線（需要連上 OpenAI 和 Anthropic 的 API）
→ 可以在設定中把 Claude 模型改為 Haiku（較快較便宜）
→ 或關閉 Claude 後處理（只用 Whisper + 詞庫修正）

### Q：某個專業術語一直辨識錯？
→ 到 Dashboard「詞庫記憶」→ 新增修正規則
→ 例如：錯誤詞 `新义丰` → 正確詞 `新義豊`

### Q：怎麼完全停止？
→ 點選單列 🎙 → 退出
→ 或在終端機按 `Ctrl + C`

### Q：想重裝或重設所有資料？
```bash
rm -rf ~/.voice-input    # 刪除所有本地資料
./run.sh                 # 重新安裝，會匯入預設詞庫
```

### Q：API 費用怎麼控制？
→ OpenAI: https://platform.openai.com/usage 查看用量
→ Anthropic: https://console.anthropic.com/settings/usage 查看用量
→ 建議兩邊都設定月用量上限 $10

---

## 💰 已預裝的你的業務詞庫

首次安裝自動匯入的內容：

**修正規則（88 條）** — 各種常見語音辨識錯誤的自動修正：
- 新义丰/新义豊/しんぎほう → 新義豊
- kusuri japan → KusuriJapan
- medical supporter → MedicalSupporter
- 个人输入 → 個人輸入
- やっきほう → 薬機法
- ...等 88 條

**自訂詞彙（70 個）** — 注入 Whisper 提高辨識率：
- 公司品牌：新義豊、KusuriJapan、MedicalSupporter、SGH Phone、TWT
- 法規術語：薬機法、PMD Act、個人輸入、衛福部、TFDA、關務署
- 技術工具：n8n、Twilio、Ultravox、Claude Code、MCP Server、LINE Bot
- 個人資訊：林 紀全、代表取締役、福岡、博多駅南、早稲田大学
- 業務用語：醫療旅遊、跨國就醫、醫療協調、復健機器人、按摩機器人

**Claude 系統提示詞** — 已客製化為你的專屬助手：
- 知道你是新義豊 CEO
- 熟悉你的所有品牌名稱和業務術語
- 保持直接專業的語氣
- 支援中/日/英三語混合
