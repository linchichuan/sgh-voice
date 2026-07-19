# SGH Voice 多語準確度與 Typeless 對標複檢

日期：2026-07-20
範圍：macOS SGH Voice；繁體中文／日本語／English 混講、個人化學習、直接輸入、評測工具

## 結論

- 複檢開始時的已安裝／Release／Firebase 版本均為 **v2.5.4**，不是 v2.5.3。
- 本輪修正收斂為 **v2.6.0**。主要問題不是單一模型，而是個人詞庫、人工修正與評測資料流沒有完整接通。
- Typeless 並非開源 project，官方也沒有公開繁中＋日文＋英文 code-switch WER／CER。SGH Voice 可對標其產品行為，但目前不能客觀宣稱準確率已超越 Typeless。
- v2.6.0 已先把「能正確學、不能學錯、能量測」的基礎補齊；真正比較模型仍需要同一批人工標註音檔。

## 去識別化 Log 觀察

- `events.jsonl`：2,207 筆 metadata event，時間範圍 2026-05-20～2026-07-16；不含逐字稿與音訊。
- STT attempt：449 次，448 次有結果；唯一空結果為 0.12 秒本地音訊。
- LLM attempt：432 次，408 次有結果、24 次空結果；僅 1 次所有 provider 均失敗並落到 regex。
- Paste ledger：445 次 Quartz 成功、3 次未插入；另有 Accessibility 未授權與使用者在 transaction 中重新 copy/cut 的安全取消紀錄。
- 舊 History 在複檢時沒有 `edited=True` 範例，因此即使 few-shot 開啟，實際可用的 verified personalization 仍為 0。

這些數字能說明 availability，不能代表辨識準確度；沒有 ground truth 就不能從成功回傳率推導 CER／WER。

## v2.6.0 已修正

1. Dashboard 手動詞彙接入 STT／LLM 共用 vocabulary prompt；舊 `custom_words` nested／list schema 自動合併到 flat `manual_added`／`auto_added`。
2. Clipboard correction 持久化到 History，寫入 `edited=True`、`correction_source`、`edited_at`，可成為可信 few-shot；SGH Voice 自己的 transactional paste／還原 generation 會被精確排除，不會把舊剪貼簿誤認成人工修正。
3. Dictionary promotion、pipeline health 與 auto-fix 預設只採用人工編輯資料；`auto/both` 僅能 legacy preview，不能 apply。
4. 修正 promotion UI「有勾選但 backend 仍套全部」；後端重新推導、再次驗證，只寫入 exact selected pairs。
5. STT primary routing 改為可預期：Groq、OpenAI Cloud、本地各自先走所選引擎；Hybrid threshold 真正依音檔秒數生效，失敗仍有明確 fallback。
6. STT 設定加入混合 Auto、繁中優先、日文優先、英文優先；固定語言時 prompt instruction 使用相同語言。
7. OpenAI STT 可選 `whisper-1`、`gpt-4o-transcribe`、`gpt-4o-mini-transcribe`，但 production default 未在沒有 corpus 的情況下擅自切換。
8. Dictate validator 保護 Latin／Kana 之外，也保護單字母、數字、日期、金額、版本、URL、Email、路徑。
9. Benchmark 取消 `language="zh"` 硬編碼，依檔名前綴選語言，mixed 保持 auto；新增 CER、script 保留率、術語保留率與 latency。
10. 自動插入失敗會顯示獨立狀態，不再假裝整體成功；結果仍保留在本機 History。

## Typeless 可確認的公開產品行為

- 支援 100+ 語言與句中語言切換，但沒有公開逐語言 benchmark。
- Dictate、Translate、Edit 是明確分開的模式。
- macOS 透過 Accessibility 直接插入；有 Personal Dictionary、修正學習、本機 History 與多組快捷鍵。
- 有 App/context-aware formatting 與可關閉的 personalization／data controls。

官方來源：

- [Typeless 官方首頁](https://www.typeless.com/)
- [Ask Anything／mid-sentence language switching](https://www.typeless.com/ask-anything)
- [macOS Release Notes](https://www.typeless.com/help/release-notes/macos)
- [Key Features](https://www.typeless.com/help/quickstart/key-features)
- [Data Controls](https://www.typeless.com/data-controls)
- [Privacy Policy](https://www.typeless.com/privacy)
- [Installation & Setup](https://www.typeless.com/help/installation-and-setup)

## 尚不能完成的準確率主張

`test/audio/` 與 `test/ground_truth/` 目前沒有可發布的人工標註音檔，因此尚不能回答：

- Groq Whisper large-v3-turbo、Breeze-ASR-25、Whisper Turbo、GPT-4o Transcribe 哪個對此使用者三語混講最好。
- SGH Voice 是否在同一音訊上低於 Typeless 的 CER／WER。
- 日文純漢字片段在 dominant language 被判為中文時的實際誤轉率。

## 下一階段評測資料

建議至少建立下列 7 組，每組 10～20 段、每段 5～30 秒，保留音訊與逐字 ground truth：

1. 純繁中
2. 純日文（平假名、片假名、漢字）
3. 純英文
4. 繁中＋英文
5. 繁中＋日文
6. 日文＋英文
7. 繁中＋日文＋英文，含 SEO／GEO／contact form／お問い合わせフォーム／人名／公司名／版本號／URL

同一 corpus 應比較 CER／WER、專有詞命中率、script 保留率、meaning-change rate、P50／P95 STT latency 與插入成功率。只有這組結果完成後，才適合使用「優於 Typeless」的對外主張。

OpenAI 可用 transcription model 與參數以官方 API reference 為準：
[Audio Transcriptions — Create](https://developers.openai.com/api/reference/resources/audio/subresources/transcriptions/methods/create)。
