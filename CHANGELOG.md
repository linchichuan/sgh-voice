# Changelog

## Android v2.7.3 (2026-08-30) — Traditional Chinese Zhuyin & Release Hardening

- 以固定 McBopomofo snapshot 取代只有 2,869 個單字的 Unihan 小表：內建 133,492 組讀音、157,683 個候選、145,332 個詞組與 57,729 個選字後聯想；`ㄕㄢ` 可選「刪」、`ㄕㄢ ㄔㄨˊ` 首選「刪除」，選「刪」後只追加「除」。
- 注音字庫改用未壓縮唯讀映射與稀疏索引，避免把完整候選表載入 IME heap；設定畫面新增最多 200 組、只存本機的自訂「詞彙＋注音」。
- 恢復與公開 2.7.2 相同的 sideload signer，正式 2.7.3 APK 可在不解除安裝的情況下直接覆蓋更新；release 密碼移入 macOS Keychain，keystore 權限收緊為僅擁有者可讀寫。

- Android 退格鍵支援長按連續刪除並在持續按壓後加速；點按仍只刪除一個字元。
- Android 語音辨識來源可由使用者選擇 Auto、繁體中文、日文、英文或韓文；Auto 保留混合語言辨識，指定語言時才送出 STT `language`。
- 鍵盤切換鍵支援點按循環、長按開啟系統鍵盤選擇器；韓文與其他裝置鍵盤由使用者自行啟用與選擇。
- 收斂手機鍵盤外框、功能列與手動輸入列比例，保留既有錄音主按鈕尺寸及至少 44dp 的主要觸控區。
- Android、iOS 與 macOS 翻譯流程新增本機語意守門：問句必須維持問句、請求必須維持請求；合法 JSON 若含代答、已完成動作或極端擴寫，也會 fail closed。
- Android 與 iOS 在實際送往雲端前再次確認版本化同意；即使錄音開始後撤回同意，也會清除記憶體中的錄音並中止上傳。Android 版本升為 2.7.3（versionCode 23）。
- 新增醫療詞庫分階段規劃；本輪未載入完整醫療詞表或新增 runtime 索引。
- 新增 Android RC 實機驗收表、一鍵 preflight 腳本與可持續追加的多語翻譯語意回歸 corpus。
- Android RC 本機自動化驗收已執行並記錄（單元測試 122/122、lint 0 errors；release 簽章金鑰待恢復為唯一 blocker）；驗收文件新增自動化結果表與 31 條實機待驗清單。
- 醫療詞庫 Phase 1 落地：`medical_dictionary.py` 分片/租戶/版本化 bundle 機制＋staged 種子詞庫（39 條，canonical 來自既有 medical 場景清單，`status=staged` 不觸發自動替換）＋`enable_medical_dictionary_bundles` 緊急開關；僅 `medical` 場景生效。
- 新增 Qwen3-ASR 為實驗性、可選的本地 STT 引擎（mlx-audio + `mlx-community/Qwen3-ASR-1.7B-4bit`）；模型未就緒或載入失敗時 fail-safe 回退 whisper-turbo；預設引擎不變；Dashboard 模型下載映射修正並安全遷移舊 repo id。效能與準確度會依裝置及音訊而異，正式比較基準尚待納入可重現報告。
- macOS 貼上防重複：每段錄音的轉錄結果以 recording token 只消費一次，杜絕同段語音被重複貼上；刻意不做內容比對去重，合法的重複口述不受影響。
- PTT 靜音安全網：push-to-talk 連續靜音達 `ptt_silence_autostop_seconds`（預設 120 秒，可設 0 停用）自動停止並及時完成轉錄貼上（發 macOS 通知註明為安全網觸發）；與放鍵/watchdog 競態下保證只 finalize 一次。
- 修正 recorder chunk 計算的浮點截斷（`int(x/0.1)`→`int(round(x/0.1))`）：連續模式最短分段 0.6s 不再被悄悄砍成 0.5s；`start_continuous()` 補 thread 存活守門，比照 `start()` 防 PortAudio 重入 deadlock。
- iOS 補齊 OpenCC s2twp 最終防護層：內嵌上游 OpenCC 詞典資料（與 macOS/Android 同源）之純 Swift 實作，dictate 輸出與幻覺截斷比對均經繁中正規化；translate 輸出因跨語言漢字風險暫不套用（明確標註）。
- Dashboard 新增 `GET /api/latency_summary` 與 Cost & Audit 延遲卡片：近 7/30 天 pipeline p50/p90/p95/p99 與 STT/LLM 分項均值（重用 `scripts/event_summary.py` 同一計算路徑）。
- 測試基準大幅補強：LLM 五引擎 fallback 鏈、連續模式併發/backpressure、貼上 idempotency、PTT 自停競態、latency API、醫療詞庫共 70+ 新測試；全量 468 tests 通過。

## Android v2.7.1 (2026-07-27) — Japanese Translation Reliability Hotfix

- 修正 Android 日文翻譯在模型回傳 Markdown JSON fence 或 `ja-JP`／`Japanese` 語言標籤時，被過度嚴格解析直接丟棄、因而無法貼入目前欄位的問題。
- Claude、OpenAI 與 Groq 翻譯請求改用 provider-side Structured Outputs／JSON Schema，本機仍會驗證目標語言、非空內容、重複與額外欄位。
- LLM HTTP／網路／模型／額度／格式錯誤不再被吞掉；輸入法會顯示可採取行動的本地化錯誤原因，同時維持失敗時不插入原文。
- Android 版本升為 2.7.1（versionCode 21）。

## v2.7.0 (2026-07-27) — Safe Dictation, Multi-target Translation & Prompt Management

- macOS、Android、iOS 的聽寫後處理統一為「只整理逐字稿、不得回答或執行內容」；新增疑問／請求的 answer-like output guard，短句也會驗證，異常結果直接退回原逐字稿。
- Android 長按錄音鍵、macOS 獨立翻譯快捷鍵與 iOS App 內長按流程，可從繁中、日文、英文、韓文選擇 1–4 個目標；每段音訊只執行一次 STT 與一次 LLM，並以嚴格 JSON schema 解析。
- 翻譯失敗採 fail-closed：缺少 API key、JSON 格式錯誤、目標缺漏或結果不可信時不會自動貼入；翻譯結果也不會被誤收為人工修正學習資料。
- Dashboard 新增 Prompt 管理頁，顯示目前 provider／model ID、鎖定的 Dictation／Translation／Quick Rewrite 用途，以及只能追加標點與格式偏好的自訂指示。
- 模型選項與 2026-07-27 官方價格基準同步；新增 Claude Opus 5，Sonnet 5／Opus 5 關閉不必要的 thinking，Fable 5 與 Groq GPT OSS 固定 low effort，並為所有翻譯輸出設定 token 上限。
- macOS 新增獨立翻譯快捷鍵與目標語言設定，並阻擋錄音／動作快捷鍵的重疊或前綴衝突。
- Android IME 更新 SGH Voice 品牌與多語模式介面，保留語音、注音、日文、英文輸入，擴充候選與使用者修正學習行為；版本升為 2.7.0（versionCode 20）。
- iOS standalone App 加入短按聽寫、長按翻譯目標選擇與相同輸出守門；受 iOS 系統限制，目前不是可直接收音的第三方鍵盤擴充。
- Firebase 下載頁更新 Android 個人測試版 APK、實機介面截圖、SHA-256 與側載風險揭露；macOS 公開下載仍維持已打包的 v2.6.0。

## v2.6.0 (2026-07-20) — Verified Multilingual Personalization

- Dashboard 手動新增詞彙現在真正進入 STT 與 LLM 共用 vocabulary prompt；統一並自動遷移 `manual_added`／`auto_added` 詞庫 schema，避免 UI 有詞、辨識管線卻沒使用。
- Clipboard correction observer 會把人工修正原子寫回 History，標記 `edited=True`／來源／時間，讓 verified few-shot 在重啟後仍能生效；同時排除 SGH Voice transactional paste／還原所產生的內部 pasteboard generation，避免把舊剪貼簿誤學成修正。設定頁會如實顯示已驗證範例數，0 筆時不再暗示已個人化。
- Dictionary promotion 與 pipeline health 預設只使用人工編輯紀錄；模型自己的 LLM output 僅可 legacy preview，禁止套用，並修正 UI 勾選項目未被 backend 尊重的問題。
- 重寫 STT routing：Groq、OpenAI Cloud、本地引擎各自尊重 primary 選擇；Hybrid 秒數門檻真正生效；長音訊 cloud 失敗仍可回到 local，不再由型別判斷或固定 30 秒規則暗中覆寫。
- Settings 新增中日英混合 Auto／中文／日文／英文語言模式，以及 OpenAI `whisper-1`、`gpt-4o-transcribe`、`gpt-4o-mini-transcribe` 選擇；固定語言時 STT prompt instruction 改用相同語言。
- Dictate validator 新增單字母技術詞、數字、日期、金額、版本號、URL、Email 與檔案路徑保護，避免後處理把 `R`、`v2.5.4`、網址或金額改壞。
- Whisper Turbo 的 Settings／Models／backend ID 統一為 `whisper-turbo`，並遷移舊 ID；已知失效 OpenRouter fallback ID 只針對舊值安全遷移。
- 多語 benchmark 不再硬編碼中文；依 `zh_`／`ja_`／`en_` 檔名選語言，mixed 保持 auto，新增 CLI override、script 保留率與術語保留率。
- History UI 改讀實際 `bundle_id`、`stt_source`、`llm_source`、`audio_duration` 與 scene；自動輸入失敗會明確顯示「已轉寫，輸入失敗」，結果仍保留於 History。

## v2.5.4 (2026-07-16) — Fn/Globe Hotkey Support

- 錄音快捷鍵新增 macOS Fn／Globe 支援，正確處理 keycode 63 與 `kCGEventFlagMaskSecondaryFn`。
- 接受 `fn+right_shift`、`right_fn+right_shift`、`globe+right_shift` 與 `Right Fn + Right Shift`，並統一正規化為 `fn+right_shift`。
- Dashboard 新增「Fn／地球鍵 + 右 Shift」快速套用，API 回傳正規化結果，避免畫面顯示與 runtime 設定不同步。
- 設定頁以繁中、日文、英文說明 macOS 不區分 Fn 左右；硬體層 Fn 若不送出 macOS 事件則無法監聽。
- pynput fallback 支援 `Key.fn` 與 virtual key 63；新增 parser、native press/release、API normalization 回歸測試。

## v2.5.3 (2026-07-15) — Editable, Conflict-Safe Hotkeys

- 錄音熱鍵預設改為 `right_option+right_shift`，避開 Codex 使用的 `right_cmd`，且純 modifier 組合不會在游標位置輸入額外字元。
- Dashboard 的錄音、Quick-Rewrite、Retry、Cancel、Continuous Mode 五組快捷鍵改為可編輯欄位，並提供一鍵套用推薦鍵。
- Hotkey 與 hotkey mode 儲存後由既有 NSEvent listener 即時載入，不需重開 App，也不會重複註冊 monitor。
- Dashboard API、native NSEvent 與 pynput fallback 共用同一 parser；拒絕未知 token、系統保留鍵、重複鍵與 prefix collision。
- Rewrite／Retry／Cancel 預設改為 `ctrl+option`、`ctrl+shift`、`ctrl+cmd`，標準 MacBook／Apple compact keyboard 都能操作；Cancel 避開 PTT 的 Option／Shift family，在 generic-only KVM 也能可靠辨識。
- 動作快捷鍵由共用 arbiter 在放開組合鍵時觸發；若手勢中加入第三鍵便取消，避免撞到 VoiceOver／一般 App 快捷鍵前綴，且一次手勢最多執行一個動作。
- Cancel 會在事件當下綁定錄音 token；即使與 PTT 幾乎同時放開，仍會在 STT／paste 前攔截該段，不受 background thread 排程順序影響。
- Recorder 的 start／stop／cancel／continuous transition 改為共用序列鎖；快速放開再重按時會先等舊 audio stream 完整釋放，但不會阻塞已開始的 STT。多段轉寫並行時，Cancel 只標記最新一段，不會由其他 pipeline 誤吞。
- Continuous Cancel 使用獨立 session marker，會攔截 stop-time final flush 與已在辨識中的 segment；Continuous 啟用期間也不再把一般 PTT 放鍵誤判為停止串流。
- 新設定拒絕單一 modifier；舊 `right_cmd` 只允許 runtime 載入。獨立 hotkey migration 會在 v1/v2 Keychain 暫不可用時先安全替換已知舊預設，並保留其他自訂鍵。
- `hotkey_mode` 限定為 `push_to_talk`／`toggle`；左右側 Cmd／Ctrl 都會套用 macOS 保留快捷鍵檢查。
- Keychain 拒絕更新 API key 時，Dashboard 會回報儲存失敗並保留原設定，不再靜默沿用舊 key。
- 新增 parser、左右 modifier、Codex 衝突隔離、live reload、API validation 與可編輯 UI 回歸測試。

## v2.5.2 (2026-07-14) — Direct Text Insertion & Icon Refresh

- 一般文字欄位優先透過 `AXSelectedText` 直接插入游標位置，不接觸使用者 Clipboard。
- 不支援 Accessibility direct insertion 的 App 改用 250ms transactional pasteboard，完整保存並還原文字、圖片、檔案、HTML、RTF 等 representation。
- 使用者在 transaction 期間自行 copy/cut 時，以新的 Clipboard 為準，不會被 SGH Voice 覆蓋。
- 送出 synthetic Cmd+V 前再次比對 pasteboard `changeCount`；若使用者剛 copy/cut，取消本次輸入，不會貼錯內容。
- 自動貼上失敗時立即還原原 Clipboard，顯示權限提示，不再把轉錄內容長期占用 Clipboard。
- Build 優先使用固定 Apple signing identity，移除每次 build 自動 `tccutil reset` 的行為。
- 重做為暖黑／米白雙色 App icon，無藍色外框、無螢光與漸層；並新增 light/dark mode 自適應的 menu bar template icons。
- 資料目錄已是安全權限時不再重複 `chmod`，避免 macOS GUI App 在外接 SSD 權限檢查上卡住。
- 新增 Clipboard representation、使用者競態、Accessibility direct insertion 與權限失效回歸測試。

## v2.5.1 (2026-07-14) — Multilingual Accuracy Hardening

- OpenCC 改為日文 clause-aware 正規化，保留 `画像／動画／来週／参考／台風` 等日本語新字體。
- Dictate validator 保護 Latin 與 kana spans，拒絕翻譯、音譯、script switching。
- 三語技術詞庫新增 SEO/AEO/GEO、contact form、お問い合わせフォーム、カタカナ、ひらがな、JSON-LD、hreflang 與實際誤辨別名。
- Few-shot 僅注入人工編輯確認且 Han/Kana/Latin profile 相符的歷史範例。
- 移除高風險 `Cloud→Claude`、`LINE→line` runtime 規則；新增 canonical term 防護。
- History 改為逐筆原子落盤；paste debug 不再記錄逐字稿節錄。
- 新增 Ghostty / Codex Desktop app mapping、語系 telemetry 與多語回歸測試。


## v2.4.0 (2026-06-01) — Hardening & Dashboard Reimagined

**最大規模 release**：全 Dashboard 從 1453 行 monolithic HTML 重寫成 modular SPA、補 macOS Keychain 整合、零測試覆蓋變 55 個 pytest baseline + GitHub Actions CI、完成 APPI / GDPR / PIPL 三重合規 disclosure 重寫。**+9801 / -1561 lines** across 60 files。

### 🏗️ Dashboard 全重寫（從 monolith 變 modular SPA）
- **舊 static/index.html (1453 LOC monolithic) → 拆成 37 個 SPA 檔案**：8 個 page module（lazy load）+ 4 個 shared lib（api / components / i18n / store）+ tokens.css + base.css + app.js router
- **品牌對齊 voice.shingihou.com**：DM Sans + Noto Sans CJK 字體、藍 #2563eb / 紫 #7c3aed / 橘 #f97316 三色、Lucide icon（取代所有 emoji）、Tailwind CDN
- **8 個 page**（4 個全新、4 個重寫）：
  - 🆕 Voiceprint（含 mandatory ConsentDialog 4-section biometric data 揭露）
  - 🆕 Cost & Audit（30 天成本曲線 + 月度 breakdown + 預算 gauge + 一次性 cutoff）
  - 🆕 Models（mlx-whisper / Breeze-ASR-25 三模型 SSE 下載狀態）
  - 🆕 Onboarding（3-step wizard：選引擎 flavor → 貼 key + Test → 試 mic）
  - Dashboard（Bento grid + 即時錄音 CTA + 7 日 bar chart）
  - History（虛擬化 list + edit-to-learn + 5s undo）
  - Dictionary（5 tab：custom_words / corrections / scene / app / smart_replace + promote-from-history modal）
  - Settings（6 tab：API keys / STT / LLM / Hotkeys / Privacy / Advanced，含 wipe-all 需手打 DELETE）
- **a11y 全面修**：WCAG AA 對比度、`:focus-visible` ring、`prefers-reduced-motion` 尊重、所有 input 配 `<label for>`、keyboard 可達

### 🔐 安全 / 合規 hardening
- **macOS Keychain 整合**：5 個 API key（OpenAI / Anthropic / Groq / OpenRouter / ElevenLabs）從 `config.json` 自動遷移到 macOS Keychain。`config.json` 殘留欄位永遠是空字串。iOS / macOS 終於 parity（service=`com.shingihou.voice`）。失敗時 fallback to JSON + 完整錯誤路徑。
- **CSRF**：Dashboard 對 POST/PATCH/DELETE 加 Origin/Referer 同源檢查（防瀏覽器到惡意網站的跨來源觸發）
- **CSP**：baseline `Content-Security-Policy` 含 Tailwind CDN + Lucide CDN + Google Fonts allowlist、`X-Frame-Options: DENY`、`Referrer-Policy: no-referrer`、`X-Content-Type-Options: nosniff`
- **Host hard-pin**：`run_dashboard()` 拒絕綁定到非 loopback host
- **`/api/wipe_all` (GDPR Art. 17)**：一次性 token + magic phrase 雙守門；刪 history / events / dictionary / voiceprint / stats / smart_replace / audit.log / audio_backup + SSD 備份目錄；**清 in-memory state**（防 process 內快取重新 persist）
- **`/api/keychain/delete/<key>`**：個別 Keychain key 刪除 endpoint

### 📋 合規 disclosure（privacy.html × 3 lang × 7 new section）
- **聲紋 / 生體識別資料**（APPI 要配慮個人情報 / GDPR Art. 9 special category）— enroll 改為 opt-in
- **Few-shot 過去發話脈絡傳送** — 預設 OFF，明示揭露
- **醫療模式 + 雲端 LLM 風險警告**（沒 BAA/DPA）
- **音訊備份保留政策**
- **events.jsonl 觀測 metadata 揭露**
- **跨境傳輸**（APPI Art. 28 / PIPL Art. 38）詳列服務商所在國
- **削除權 / Right to Erasure** 程序

### 🛡️ Production correctness 修
- **CLI mode crash**：`run_cli` 印 `result['corrected']` 不存在欄位 → 每次 KeyError → 修
- **Continuous mode race conditions**：start/stop 寫 `is_recording` 沒鎖 + 繞過 PortAudio thread liveness check → 補 `_state_lock` 守門 + thread join timeout
- **PortAudio lifecycle**（v2.3.0 修了 push-to-talk 路徑，但 continuous mode 沒涵蓋）→ 補
- **`retry_last_llm` event_ledger 黑洞**：retry 路徑沒寫 `llm_attempt` → 補完整觀測
- **Voice command stripping edge case**：「請問怎麼把『早安』翻成英文」會被誤判翻譯 → 強制 LEADER pattern（pause 標記 或「以上 / 這段」）+ 12 字門檻
- **Ollama backoff** 成功時不重置 → 一次暫掛把 backoff 推到 120s 永遠回不來 → 修
- **`_graceful_shutdown`** 不 flush memory → Ctrl+C 最多 lose 9 筆 history → 補
- **app awareness gating**：`_get_system_prompt` 尊重 `enable_app_awareness` 預設 False（防 bundle id 洩漏給 LLM）

### ⚙️ Config schema migration
- **CONFIG_VERSION = 3**（v2 → Keychain migration、v1 → v2 修錯誤 qwen 模型名）
- 預設值修：`enable_fewshot: False`（合規）、`enable_app_awareness: False`（合規）、`local_llm_model: qwen3:latest`（從不存在的 qwen3.5）、`openrouter_model: qwen/qwen3-30b-a3b:free`（從不存在的 qwen3.6-plus）
- 新增：`monthly_budget_jpy`、`enable_budget_cutoff`

### 🧪 測試 infrastructure（從 0 變 55）
- **`tests/` 完整 baseline**：55 pytest（memory / config / transcriber validators / voice command / few-shot / event_ledger / Keychain migration）
- **`.github/workflows/ci.yml`**：macOS-latest × Python 3.11 + 3.12 matrix，含 ruff + pytest --cov
- **`pytest.ini` + `requirements-dev.txt`**

### 🤖 開發品質
- **Agent team workflow**：1 個 SPEC.md → 1 個 Skeleton agent → 8 個 page agent 並行 + 2 個 backend agent 並行 → integration phase 收尾 → Codex round 1 fast review → P1 修補
- **Codex review** 抓出 7 個 P1（CSP CDN block、wipe in-memory 殘留、Keychain data-loss 路徑、Origin 邏輯漏洞、wipe magic-phrase 可 bypass、wipe 漏 audit.log），全修

### 📦 平台版本
- macOS: v2.4.0
- iOS: 2.2.0（未動）
- Android: 2.2.0（未動）

---

## v2.3.0 (2026-05-27) — Speed Wins

把「實際很慢」也修了。Local Breeze 在實際使用下 cold-start 每次 10–15s，預設改走 Groq Cloud Whisper（avg 1–2s），總處理時間從 ~15s 降到 ~3s。同時補 5/20 之後累積的可靠性修復。

### ⚡ STT 預設切換（macOS）
- **預設 `stt_engine = groq`**，`enable_hybrid_mode = false`：實測 26 次 local Breeze 平均 STT latency = 11.18s，4 次 Groq 平均 = 2.43s（70s 音檔僅 1.7s）。Local Breeze fp16 / 4bit 的「3.5× faster than whisper-turbo」是 warmed-up benchmark，production cold path 達不到。Groq 跑 H100 + LPU 對 Whisper 優化，差距結構性。
- **Local 仍保留**：Dashboard 可切回 `mlx-whisper` 供無網路 / 隱私場景使用，舊 config 自動備份在 `~/.voice-input/config.json.bak.*`。
- **Fallback 鏈不變**：Groq 失敗 → OpenAI Whisper API → 視 stt_engine 設定走 local。

### 🛡️ 可靠性修復（macOS）
- **PortAudio stream lifecycle**：`recorder.py` 新增 thread liveness 檢查 + 5s join timeout + `try/finally` 保證 `is_recording=False`。修復連續按熱鍵造成 `Pa_OpenStream` 與 `FinishStoppingStream` 競爭、整個 audio 子系統 deadlock 的情況（症狀：app 還活著但每按熱鍵只印 🔴錄音中… 沒下文）。
- **Few-shot 防退化複誦**（`transcriber.py` + `config.py`）：當 Whisper raw text 短於 `fewshot_min_input_chars`（預設 8）時不注入 few-shot；另在 `_is_llm_hallucination` 加 echo detection — LLM 直接複誦 example 的 `final_text` 視為幻覺丟棄。修復 0.1s 誤觸錄音時 Claude 把前一段 150 字整段吐出來的 bug。
- **Event ledger production observability**：純 metadata 寫 `~/.voice-input/events.jsonl`（不寫文字內容），串接 audio_gate / voiceprint / stt_attempt / llm_attempt / validator_action / paste_method / pipeline_complete 七種事件 + thread-local session ID，未來 silent failure 可直接溯源。50MB 自動 rotate。
- **TLS / session 競態修復**：4 輪 codex review attack 拆出 ledger TLS 在 thread-reuse 場景下會 leak session_id 給後續 event 的問題 → 改用 `_active_list` newest-at-end 設計 + `try/finally end_session()`。

### 📦 平台版本
- macOS: v2.3.0
- iOS: 2.2.0（不變）
- Android: 2.2.0（不變）

---

## v2.2.0 (2026-05-20) — Perceived Responsiveness & Production Trust

跨平台 Release：macOS / iOS / Android 三平台同步升版。針對「實際很快但感覺不夠快」做整體優化，10 個 bug 透過 4 輪 codex review loop 被攔下，沒一個 ship 出去。

### ⚡ 感知速度提升（macOS）
- **5 處固定 sleep → polling**：`paste_text` 的 `sleep(0.6)` 等修飾鍵 → Quartz `CGEventSourceFlagsState` 輪詢（典型 50-150ms 解除）。Quick-Rewrite 的 `sleep(0.25)` + `sleep(0.2)` 同樣改 polling。Overlay 過場 `sleep(0.4)` 移除。
- **AXValue 補刀邏輯修復**：原本長文 Quartz 成功後還補一次 AXValue 會把編輯器既有內容清空只剩貼上的字。現在只在 Quartz + osascript 都失敗才走 AXValue。
- **剪貼簿還原 3s → 1.5s + NSPasteboard.changeCount() race-free 守門**：使用者期間動過剪貼簿（即使內容碰巧相同）也不會被誤覆蓋。

### 🎮 工作流摩擦解除（macOS）
- **Retry hotkey** `right_option+y`：用 cache 的 raw STT 重跑 LLM，跳過 STT 階段（省 1.5s），不用重錄就能換一版輸出。
- **Cancel hotkey** `right_option+x`：錄音中按下 = 立刻丟棄音訊；處理中按下 = paste 階段自動跳過。Pipeline 已開始的 LLM call 會跑完但結果不貼。

### 👀 處理視覺化（macOS）
- **Overlay 階段化**：原本只有一個「處理中…」label，現在會依管線進度切換 `🎧 辨識中` → `✨ 整理中` → `📋 貼上中`，三語都有。
- 多 race 防護：`_pending_stage_prefix` 在 init / done / idle / recording / show_transcript 都會清，避免異步主執行緒排程跟背景 stage 設定的 race。

### 🛡️ 生產級信任修復（三平台）
- **LLM 尾部幻覺截斷**（macOS + iOS + Android）：偵測「raw 內容完整保留 + LLM 在結尾自己接話加新句子」的補寫型幻覺，自動截斷而非整段捨棄。例：raw 結尾「色色名稱不用到這麼大」，LLM 加上「，所以你看能不能調整。而且你仔細看，從」→ 自動截到「不用到這麼大。」
  - macOS 用 `difflib.SequenceMatcher` + OpenCC `s2twp` 雙向正規化，處理簡體 raw + LLM 繁化 + 擴寫的混合 case。
  - iOS 用 `String.range(of:options:.backwards)` 簡化版（暫無 OpenCC 依賴）。
  - Android 用 `String.lastIndexOf` + opencc4j `ZhConverterUtil.toTraditional` 同樣雙向正規化。
- **Mode gating**：只在 dictate mode 套用截斷，edit mode（Quick-Rewrite / 翻譯 / Email 草稿 / 語音指令改寫）跳過 — 改寫本來就是 LLM 應該加內容，截斷會誤毀正常輸出。

### 🔧 內部優化
- HTTP client cache（macOS）：5 個雲端 LLM/STT client 連線重用，每次省 200-500ms TCP/TLS handshake。
- Signal handler（macOS）：SIGINT/SIGTERM/atexit 乾淨關閉 PortAudio 串流，不再殘留 leaked semaphore。
- Anthropic 連線預熱（macOS）：啟動時背景送 1 token ping，第一次正式錄音不付握手成本。
- `_should_skip_llm` 邏輯保留（不放寬，避免犧牲品質）。

### 📦 平台版本
- macOS: v2.2.0 (app.py + Dashboard footer)
- iOS: MARKETING_VERSION 2.2.0
- Android: versionName 2.2.0, versionCode 15

### 🤖 開發品質
- 4 輪 codex auto-review loop 攔下 10 個 bug（含 4 個 UI race、3 個 LLM 截斷 edge case、1 個 cancel flag 殘留、1 個 retry cache 時機、1 個 clipboard race）。沒一個 ship。
- 約 +494 行 / 4 個檔案（macOS app/transcriber/overlay/config）+ iOS/Android LlmClient 各 ~80 行。

## v2.1.0 (2026-04-29) — Personalization & Productivity Release

- **個人化 Few-shot 後處理**：LLM 後處理會注入最近 3 筆 `whisper_raw → final_text` 歷史範例，5 個引擎統一支援，rewrite API 會自動跳過。
- **Dictionary 從歷史學習**：新增 `scripts/dictionary_promote_from_history.py` 與 `POST /api/dictionary/promote_from_history`，支援 dry-run / apply 兩段式流程與多重守門。
- **全域 Quick-Rewrite 熱鍵**：選取任意 App 文字後按 `right_option+r`，走 LLM fallback 鏈改寫並自動貼回。
- **連續錄音模式 + VAD 自動分段**：新增連續錄音 hotkey、voice/silence 邊界偵測、片段長度保護與尾端靜音裁切。
- **發布前穩定化**：修正連續模式切片呼叫 `transcribe()`；新增音訊品質前置守門、個人語氣 profile 生成 API/UI，以及場景/App 分層詞庫管理。
- **錄音檔搬離隱藏目錄**：`backup_audio_dir` 預設改為 `/Volumes/Satechi_SSD/voice-input/audio_backup`，SSD 未掛載時自動略過備份。

## v2.0.0 (2026-04-25) — Cross-Platform Release Sync

- **三平台版本同步**：macOS App/DMG、iOS project、Android Gradle、README、Firebase Landing Page 全部升級至 `2.0.0`。
- **GitHub Release asset 命名統一**：DMG 產物改為 `SGH.Voice-2.0.0-apple-silicon.dmg`，與 Release 下載 URL 格式一致。
- **RVC/TTS 工具鏈整合**：加入 RVC 推論工作區、批次 TTS、Spotify post-copy、長篇語音生成與提示文字正規化腳本。
- **iOS Release build 修正**：SwiftUI `#Preview` 僅在 Debug 編譯，避免 production build 被 preview macro 擋住。
- **延續反幻覺管線**：保留 Claude Haiku 4.5 預設、Whisper prompt 注入、重複幻覺 sanitizer、短指令 skip LLM 等 v1.9.9 安全策略。

## v1.9.9 (2026-04-19) — Anti-Hallucination Overhaul

基於 762 筆真實歷史的差異分析（`whisper_raw` vs `final_text`），定位並修復了 LLM 後處理把指令當成對話回答的根本原因。

### 🎯 主因（已修復）
- **預設 LLM 從 Groq + `gpt-oss-120b` 切回 Claude Haiku 4.5**：歷史數據顯示 Groq 上跑 OpenAI 的開源 reasoning 模型 `gpt-oss-120b` 幻覺率 11.9%（35/295 筆），而 Claude Haiku 4.5 僅 2.5%（6/239 筆），差距 **4.7 倍**。reasoning 模型本質會「主動思考並重寫」輸入，不適合做純 transcoding。
- **Groq fallback 模型改回 `llama-3.3-70b-versatile`**：傳統 instruct 模型，服從性比 reasoning 模型穩定。

### 🛡️ 幻覺防護全面升級（`transcriber.py`）
- **Whisper STT 注入個人詞庫**：原本 `_local_stt` / `_groq_stt` / `_whisper_api_fallback` 三函數都用固定 prompt，**完全沒有調用 `memory.build_whisper_prompt()`**。現在會把 `custom_words` + 當前場景詞彙 + `BASE_CUSTOM_WORDS` 一起餵給 Whisper（≤20 詞、≤200 字元）。
- **三層幻覺檢測**：
  - 66 個對話起手詞（請提供／我來幫／您可以／Sure／Here is…）
  - 9 個中段助理句型（…，請提供…）
  - 字元 bigram 重疊率：< 30% 嚴判 / < 50% 配合 < 70% 縮減 / < 55% 配合 > 120% 擴寫
  - 統計樣本：幻覺平均重疊 37%，正常平均 76%，分離度極佳
- **Whisper 重複幻覺 Sanitizer**：正則 `(.{1,15}?)\1{4,}` 偵測連續重複片段，截斷到第一次出現（解決「11.11.11×30」、「財務所×16」類災難）。
- **短指令自動 Skip LLM**：≤60 字 + 全中日文 + 含動作詞（請繼續｜幫我｜你幫｜麻煩｜執行｜處理一下｜懂嗎…）→ 直接跳過 LLM，避免被誤當對話回答。
- **`_DICTATE_SYSTEM` 完全重寫**：1600 chars，移除舊版「條列呈現／長文整理」等誘導改寫字眼，改成嚴格 transcoder 風格 + 雙語明確示範 + 短文 ≤20 字「return as-is」規則。

### 💾 設定變更
- `~/.voice-input/config.json`：
  - `llm_engine`: `groq` → `claude`
  - `groq_model`: `openai/gpt-oss-120b` → `llama-3.3-70b-versatile`
  - `claude_system_prompt`: 用戶自訂 616 字版本（含自相矛盾規則）→ `""`（fallback 至新版 `_DICTATE_SYSTEM`）
  - `backup_audio_dir`: `""` → `~/.voice-input/audio_backup/`（為將來 CER 趨勢分析累積素材）
- 舊 config 自動備份至 `~/.voice-input/config.json.bak.<timestamp>`

### 📊 預期效益（基於 762 筆歷史回算）
| 指標 | 之前 | 現在 |
|------|------|------|
| LLM 幻覺率 | 11.9% (Groq+GPT-OSS) | 2.5% (Claude Haiku) |
| 已知 23 筆對話洩漏 | — | 攔截 21+/23 (markers) + bigram 補強 |
| Whisper 重複幻覺（3 筆/2 月）| 直接輸出 | Sanitizer 截斷 → 0 |
| 短指令誤判為對話 | 經常 | Skip 邏輯阻擋 |
| 體感速度 | 中位 1.46s | 中位 4.05s（trade-off）|

### 🚧 注意
- Claude 比 Groq 慢約 2.5 秒，但正確性大幅提升 — 對「頭痛」級的幻覺問題是值得的 trade-off。
- 若想恢復速度，可改回 `llm_engine=groq`，**但保持 `groq_model=llama-3.3-70b-versatile`**，千萬別再用任何 reasoning 模型（gpt-oss / qwen-qwq / deepseek-r1）做 transcoding。

## v1.4.0 (2026-03-17)

- **整合 MediaTek Breeze-ASR-25**：專為繁體中文 + 中英混用優化，Apple Silicon 上的推理速度比 Whisper-turbo 快 3.5 倍。
- **本地離線模型優化**：新增 4-bit 量化模型支援 (0.82 GB)，大幅降低記憶體占用並維持優異辨識率。
- **自動化監控與測試體系**：
  - `scripts/benchmark_models.py`：支援批次測試各模型的 CER (Character Error Rate) 與耗時。
  - `scripts/hf-model-watch.sh`：每日監控 HuggingFace 新 ASR 模型並推送通知。
  - `scripts/dict-update.py`：每週自動從 PMDA/MHLW 擷取最新醫療術語更新至個人詞庫。
- **系統任務管理**：新增 `scripts/install-launchd.sh` 方便一鍵安裝/卸載 macOS 背景監控任務。
- **三平台版本號同步**：將 macOS、iOS、Android 版本號一致升級至 `1.4.0`，Landing Page 補齊各平台下載連結。

## v1.3.0 (2026-03-17)

- **聲紋辨識 (Speaker Verification)**：新增純本地聲紋驗證模組，可有效過濾背景噪音與非本人的語音輸入。
- **LLM 引擎動態切換**：Dashboard 新增引擎選擇器，支援在 Ollama (本地)、Claude、OpenAI 之間快速切換。
- **聲紋前置過濾 (Step 0.5)**：在辨識前先比對音訊特徵，非本人聲音直接丟棄，防止 Whisper 產生重複字元幻覺。
- **UI 強化與狀態顯示**：Dashboard 設定頁加入聲紋狀態指示（維度、檔案大小）、相似度閾值滑桿與聲紋重置功能。
- **基礎架構優化**：修復 `config.py` 中的路徑映射邏輯，並強化 LLM 超時處理機制。

## v1.2.1 (2026-03-03)

- 新增 Dashboard「詞庫學習懸浮提示」：新增詞彙、新增/更新修正規則時，右上角即時浮窗提示使用者。
- 懸浮提示支援多語系（zh-TW / ja / en / ko / th / vi）並加入短時間去重，避免重複洗版。
- 更新 macOS App / DMG 版本號至 `1.3.0`（`build.sh` / `voiceinput.spec` / README / Firebase 下載頁）。
- iOS / Android 不新增此懸浮提示（維持現有行為）。

## v1.2.0 (2026-03-03)

- 修復 Dashboard `static/index.html` 內的 JavaScript 語法錯誤，避免頁面因 i18n 區塊錯置而無法載入。
- 補齊越南語 (`vi`) i18n 字串到正確語言物件，避免翻譯鍵缺失。
- 調整本地 Ollama LLM timeout 策略：從固定短超時改為可配置（`local_llm_timeout_sec`，預設 6 秒）。
- 新增 Ollama timeout 退避與警告節流，降低連續 fallback 造成的重複錯誤訊息。
- 升級 macOS App/DMG 版本號至 `1.2.0`（`build.sh` / `voiceinput.spec` / README 下載指引）。
