# 🎤 SGH TTS — 用你自己的聲音朗讀文章

把任何中文文章轉成你本人聲音朗讀檔。**主推 BreezyVoice**（聯發科專為台灣國語），同時支援 Fish Speech S2 Pro、Qwen3-TTS 切換。

---

## 為什麼 BreezyVoice 仍然最佳（即使你有 18 分鐘）

關鍵：所有現代 voice cloning 模型都分兩條路 —

| 路線 | 數據需求 | 你的 18 分鐘 | 推薦模型 |
|------|---------|-------------|---------|
| **Zero-shot clone** | **30 秒**就夠 | 用不到 | BreezyVoice / Fish S2 / Qwen3-TTS |
| **Fine-tune 專屬模型** | **1 小時+** | 不夠 | CosyVoice / GPT-SoVITS fine-tune |

18 分鐘對所有模型都「**zero-shot 太多 / fine-tune 太少**」。決勝點是：**哪個 zero-shot 對台灣國語最準。**

| 模型 | 台灣國語 | 罕用字（林紀全）| Apple Silicon | 備註 |
|------|---------|---------------|--------------|------|
| **🥇 BreezyVoice** | 🟢 專為台灣訓練 | 🟢 注音標記 `紀[:ㄐㄧˋ]` | 🟢 ONNX 可跑 | 同團隊（你已用 Breeze-ASR-25）|
| 🥈 Fish Speech S2 Pro | 🟡 多語含繁中 | 🟡 phoneme 控制 | 🟢 PyTorch MPS | 2026/3/9 release |
| 🥉 Qwen3-TTS | 🟡 偏簡中 | 🔴 無細粒度控制 | 🟢 MLX 加速 | 3 秒 reference |
| ❌ CosyVoice 3 | 🔴 把繁體當粵語 | — | 🟡 | 除非 fine-tune |

---

## 資料夾結構（程式碼 vs 資料分離）

### 內接 SSD — 程式碼與設定
```
/Users/lin/voice-input/tts/
├── README.md
├── setup.sh                # 一次性安裝（會把模型/venv 放外接）
├── prepare_reference.py    # 從 audio_backup 自動挑最佳 30 秒
├── generate.py             # 單篇文章 → wav
├── batch.py                # watcher 模式（電腦跑著就好）
├── lexicon.json            # 個人罕用字注音字典（林紀全等）
├── config.json             # 模型選擇 / reference 路徑
└── scripts/                # 共用工具函數
```

### 外接 SSD — 大檔（模型、venv、音檔）
```
/Volumes/Satechi_SSD/voice-input/tts-data/
├── venv/                   # Python 3.10 venv（避免污染主專案）
├── models/
│   ├── BreezyVoice/        # 1.2 GB（git clone）
│   ├── BreezyVoice-300M/   # 模型權重
│   ├── fish-speech-s2/     # 可選，2-3 GB
│   └── qwen3-tts-1.7b/     # 可選，3.4 GB
├── reference/
│   ├── ref.wav             # 你的 30 秒範本
│   └── ref.txt             # 對應文字稿
├── articles/               # 把要朗讀的 .txt 丟這裡
│   └── done/               # 處理完移到這
└── output/                 # 合成結果 .wav
```

---

## 安裝（一次性）

```bash
cd /Users/lin/voice-input/tts
bash setup.sh
```

`setup.sh` 會：
1. 確認外接 SSD 已掛載 `/Volumes/Satechi_SSD`
2. 建立 `tts-data/` 結構
3. 建 Python 3.10 venv 在外接 SSD（用 `pyenv` 或 `uv`）
4. `git clone` BreezyVoice → 外接 SSD
5. 從 HF 下載模型權重 → 外接 SSD
6. `pip install -r requirements.txt`
7. （可選）下載 Fish Speech S2 / Qwen3-TTS 備用

**首次安裝估時：~10-20 分鐘**（含 1.2GB 模型下載）。

---

## 使用流程

### Step 1 — 準備 reference（一次性）

```bash
python prepare_reference.py
```

自動：
- 掃 `~/.voice-input/audio_backup/` + `/Volumes/Satechi_SSD/voice-input/voice-data-lin/`
- 配對 `~/.voice-input/history.json` 文字稿
- 篩出 15-30 秒 + 純中文 + 高音量穩定的候選
- 列前 5 個讓你 preview，選最自然的
- 寫入外接 SSD `reference/ref.wav` + `ref.txt`

### Step 2 — 選擇模型（預設 BreezyVoice）

編輯 `config.json`：
```json
{
  "engine": "breezyvoice",   // breezyvoice | fish_speech | qwen3_tts
  "reference_wav": "/Volumes/Satechi_SSD/voice-input/tts-data/reference/ref.wav",
  "reference_text": "/Volumes/Satechi_SSD/voice-input/tts-data/reference/ref.txt",
  "articles_dir": "/Volumes/Satechi_SSD/voice-input/tts-data/articles",
  "output_dir": "/Volumes/Satechi_SSD/voice-input/tts-data/output"
}
```

### Step 3 — 平常使用

#### 即時單篇
```bash
python generate.py path/to/article.txt
# 自動套 lexicon.json → 送 BreezyVoice → 寫 output/article.wav
```

#### 「電腦跑著就好」watcher 模式
```bash
python batch.py
```
丟 `.txt` 到 `articles/` → 自動處理 → 完成 .txt 移到 `articles/done/`、wav 在 `output/`。

背景跑：
```bash
nohup python batch.py > batch.log 2>&1 &
```

---

## 罕用字注音覆蓋（lexicon.json）

```json
{
  "林紀全": "林[:ㄌㄧㄣˊ]紀[:ㄐㄧˋ]全[:ㄑㄩㄢˊ]",
  "新義豊": "新[:ㄒㄧㄣ]義[:ㄧˋ]豊[:ㄈㄥ]",
  "薬機法": "薬[:ㄧㄠˋ]機[:ㄐㄧ]法[:ㄈㄚˇ]",
  "KusuriJapan": "KusuriJapan",
  "Shingihou": "Shingihou"
}
```

`generate.py` / `batch.py` 在送進模型前自動套用 — 這些字永遠讀對。

切換到 Fish Speech / Qwen3-TTS 時用 phoneme 而非注音，自動轉換邏輯寫在 `scripts/lexicon.py`。

---

## 速度預估（M1 Pro / M2 / M3 Mac，跑外接 SSD）

| 模型 | 100 字 | 500 字 | 2000 字 |
|------|-------|--------|---------|
| **BreezyVoice CPU** | ~15s | ~75s | ~5min |
| Fish Speech S2 (MPS) | ~8s | ~40s | ~3min |
| Qwen3-TTS (MLX) | ~5s | ~25s | ~2min |

外接 USB-C SSD（Satechi 通常是 10Gbps）讀模型 = 內接的 1/2 速度，但模型只在啟動時讀一次，後續推理沒影響。

---

## 切換模型的時機

- **預設用 BreezyVoice** — 你目前需求（朗讀文章 + 罕用人名正確）
- **想試 Qwen3-TTS** — 速度最快，適合長文章批次（犧牲部分繁中精度）
- **想試 Fish Speech S2** — 想要表情語氣豐富的朗讀（適合做 podcast / 有聲書）

切換只要改 `config.json` 的 `engine` 欄位，reference 共用。

---

## 你的 18 分鐘語音 — 真正的用途

雖然 zero-shot 只用 30 秒，但 18 分鐘可以：
1. **挑出最佳 30 秒**（preview 多個候選）
2. **未來如果累積到 1 小時 +**，可以做 CosyVoice / Fish Speech 的 LoRA fine-tune，產出真正的「林紀全專屬聲音模型」
3. **做評估資料集** — 比較 BreezyVoice / Fish / Qwen 哪個合成最像你

---

## Troubleshooting

| 問題 | 解法 |
|------|------|
| `pyenv: 3.10` not found | `brew install pyenv && pyenv install 3.10.14` |
| `onnxruntime` import 錯誤 | 確認用 onnxruntime（CPU）非 onnxruntime-gpu |
| 罕用字仍讀錯 | 加進 `lexicon.json`（注音可用 [新酷音](https://chewing.im/) 工具查）|
| 外接 SSD 未掛載 | `setup.sh` 會 fail-fast 提醒 |

---

## Roadmap（按優先級）

- [x] 基本架構 + BreezyVoice 整合
- [ ] `prepare_reference.py` 智慧挑選
- [ ] watcher 模式 + lexicon 自動套用
- [ ] Fish Speech S2 / Qwen3-TTS 切換層
- [ ] Web UI（在 voice-input dashboard 加 TTS tab）
- [ ] 累積 1 小時 + 後試 LoRA fine-tune
