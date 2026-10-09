# Event Translate 對 SGH Voice Android 個人輸入的啟發

查證日：2026-10-09。範圍：官方公開頁面的文件查證；沒有登入、付費 API、音訊上傳或準確率／延遲實測。下列「已證實」只代表官方有該描述，並非獨立測試證明。

Event Translate 的主要用途是活動一對多翻譯、字幕與語音廣播；不是 Android IME。可借用產品原則，不能據此宣稱它可取代 SGH Voice 的輸入引擎，或移植同等辨識表現。[官方首頁](https://eventranslate.com/)

## 五項可用啟發

| 主題 | 官方已披露 | SGH Voice 個人輸入建議（本研究推論） |
| --- | --- | --- |
| 個人背景與詞彙 | 可在開始前設定主題、背景、姓名／公司／產品詞彙及偏好譯名；直播時鎖定，變更須停止再開始。[操作說明](https://eventranslate.com/how-it-works) | 提供使用者主動選擇的「日常／工作」背景及短詞彙表；先用專有名詞測試，不自動讀取其他 App 或敏感上下文。背景與逐字輸入模式分開，避免改寫原意。 |
| 明確定義延遲 | 官方稱通常在自然停頓後約 0.5 秒開始收到翻譯；不是從開始講話算起，完整延遲受語句與連線影響。[首頁 FAQ](https://eventranslate.com/) | 分別量測首次 partial、停講至 final、final 至文字寫入欄位。partial 僅預覽；提交策略必須由自身 IME 狀態機及測試決定。不得以該 0.5 秒宣稱 SGH Voice 速度。 |
| 音質與靜音狀態 | 官方要求乾淨的人聲、正確輸入裝置及不削波的音量；另提供 noise gate 與 voice-detection sensitivity 即時調整。[技術指南](https://eventranslate.com/how-it-works/technical-guides)、[操作說明](https://eventranslate.com/how-it-works) | 顯示目前麥克風、音量與「未收到聲音／音量過低」；區分尚未開口、句中停頓與手動停止。先測手機及藍牙路由，勿把提高增益當成通用修復。 |
| 保存控制需拆層 | 官方不保留處理後音訊；逐字稿／翻譯／摘要預設保存至要求刪除，關閉 Keep event records 才不寫資料庫。STT 供應商防濫用保存仍可能最長 30 天，session／usage logs 為 90 天。[隱私政策](https://eventranslate.com/privacy) | 將錄音、輸入歷史、伺服器日誌、供應商保存分開說明；提供明確刪除及歷史開關。不能把本機不留檔寫成整條鏈零保存。 |
| 有限資源的中斷體驗 | 官方按分鐘×目標語言計 credits；雙麥克風模式為兩倍。餘額歸零停止，操作台有剩餘時間；試用為 20 credits，最多兩種目標語言。[官方繁中價格頁](https://eventranslate.com/zh-TW/pricing) | 個人輸入只開當次所需處理，顯示額度不足與可恢復狀態；錯誤時保留尚未提交的可見文字，避免重試造成重複輸入。此為 UX 啟發，不是採購或價格優勢結論。 |

## 未披露與限制

- 本次頁面沒有可核對的 partial／final API 事件契約、final 修訂規則、IME 提交保證、P50／P95 延遲或 Android 個人輸入實測；不能推定有公開可整合 API。
- 未披露可直接套用的 VAD 閾值、靜音多久結句、靜音是否免計費，以及個人連續輸入的耗電與斷線補送策略。
- 隱私政策要求索取 sub-processors 名單；各語言實際 provider／region 及完整刪除鏈仍需確認。政策第 4 節稱粵語／普通話「可」使用自有 GPU，第 11 節使用更強的 exclusively 說法，因此不能從網頁推定每種模式皆不出站。[隱私政策，2026-09-28 生效](https://eventranslate.com/privacy)
- 英文 [pricing](https://eventranslate.com/pricing) 首次可取得頁面標題，後續讀取兩次 timeout；以上費用限制以官方繁中頁交叉核對，未完整核對方案價格，也未購買試用。
- 官方展示的準確率與語言宣稱，不是本次基準測試。活動 QR、聽眾席次、TTS 廣播與多麥克風不是個人 IME 的優先功能。

## 最小驗證方向

先以 synthetic 語料測「專有名詞／中日英混用／句中停頓／低音量／藍牙切換／斷線／連按停止」，比較 final 文字及重複提交率，再衡量首次預覽與最終可用文字耗時。這是 SGH Voice 的驗收建議，尚未執行，不構成 Event Translate 實測結果。
