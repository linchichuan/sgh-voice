# SGH Voice 多語準確度檢視

日期：2026-07-14
範圍：macOS v2.5.0 實際轉寫管線、640 筆本機 History、445 筆 operational events、可對應之備份音檔，以及 v2.5.1 修正。

## 結論

目前主要風險不是貼上失敗，而是中日英混用內容在 STT 之後被後處理改寫。此次先修正可確定、可回歸驗證的失真；Groq `whisper-large-v3-turbo` 暫時維持預設，因同一批實際音檔 A/B 中，完整 `whisper-large-v3` 雖有部分日文較佳，也會嚴重截短部分中文主導樣本，不能只依一般模型建議直接切換。

## 實際發現

1. 全段 OpenCC `s2twp` 會把正確日文 `画像／動画／台風／参考／来週` 改成中文異體。
2. LLM 曾把 code-switch 片段翻譯或音譯，例如英文詞轉成中文或片假名。
3. 舊 runtime dictionary 有 `Cloud→Claude` 與 `LINE→line`，會破壞 Cloud Run、LINE Bot 等正確詞。
4. 640 筆 History 沒有任何 `edited=true`；舊 few-shot 仍會把模型自己的輸出當成學習範例。
5. History 每 10 筆才寫檔，常駐 App 未關閉時會落後；`paste_debug.log` 亦曾保存本文節錄。
6. 日文真實樣本量明顯不足，現階段不能宣稱具體 CER/WER 改善百分比。

## v2.5.1 已完成

- 日文 clause-aware OpenCC：日文 Han／Kana 保持原字形；同一文節若出現明確簡體中文字仍會繁化，純漢字日文以高可信詞庫保護。
- Code-switch validator：先套用白名單拼字校正，再比較去除 filler／標點後的 Latin 與 kana 序列；可正常加標點，但不可翻譯、音譯或切換 script。
- Canonical vocabulary：同一份詞彙同時進入 STT initial prompt 與 LLM system prompt。
- Deterministic aliases：只針對實際出現且語意明確的誤辨做前置修正。
- Verified few-shot：僅使用人工編輯確認且 Han/Kana/Latin profile 相符的範例。
- Runtime dictionary 清理、History 逐筆原子寫入、metadata-only paste log。
- Ghostty 與 Codex Desktop app mapping；新增 zh/ja/en/mixed script telemetry。

## 模型決策

- 目前保留 Groq `whisper-large-v3-turbo` 作日常預設，理由是本機真實音檔比官方一般性建議更接近實際使用分布。
- `whisper-large-v3` 可作日文優先的 Phase 2 候選，但必須先有分語系 gold corpus 與重跑門檻。
- OpenAI 新一代 transcription model 與 Qwen3-ASR 可列入後續 benchmark，不應在沒有同一音檔 ground truth 的情況下直接替換 production 預設。

官方參考：

- [Groq Speech-to-Text 文件](https://console.groq.com/docs/speech-to-text)
- [OpenAI GPT-4o Transcribe 模型文件](https://developers.openai.com/api/docs/models/gpt-4o-transcribe)
- [Qwen3-ASR 官方 repository](https://github.com/QwenLM/Qwen3-ASR)

## Phase 2 建議

1. 建立至少 60 段人工校對 gold corpus：繁中、日文、英文、中英、中日、日英各 10 段。
2. 分別量 CER/WER、語系保持率、術語保持率、截短率與 P50/P95 latency。
3. 只有在固定 corpus 上勝出後，再考慮 Japanese-first reroute 或候選融合。
4. 日常使用時在 History 修正錯字，讓該筆標記為 verified；不要把未確認輸出自動升格成 few-shot。

## 驗收標準

- 日文新字體不得被 OpenCC 改寫。
- 白名單校正後的 Latin 與非 filler kana 序列不得被 LLM 翻譯、音譯或刪除。
- `Cloud Run`、`LINE Bot` 保持原樣；`cloud code` 可明確修正為 `Claude Code`。
- 未人工確認的 History 不得進入 few-shot。
- 新增測試、完整 pytest、語法檢查與 App bundle smoke test 均須通過後才安裝。
