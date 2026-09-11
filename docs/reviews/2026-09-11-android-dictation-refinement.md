# Android 2.7.6 聽寫與收音介面改善

日期：2026-09-11

版本：2.7.6（versionCode 26）

狀態：個人測試候選版；實機驗收未完成。

## 1. 本輪變更

| 使用者遇到的問題 | 本輪處理 | 邊界 |
|---|---|---|
| 短句、前後文與口吃輸出不通順 | 短句也交由既有所選 AI 做一次整理，使用本段完整逐字稿處理標點、明確口吃與句子連貫 | 不讀取前景 App 的其他文章作為上下文；不新增供應商或額外第二次修句呼叫 |
| 模型出現無關內容或助手回覆 | 加強無關改寫、數字／版本、否定語意與助手前言守門；拒絕結果回退逐字稿並提示 | 仍可能出現 STT 本身的誤辨；不能保證每句都正確 |
| GitHub 等常用詞經常辨識錯 | 加入 GitHub、GitHub Actions、Actions、CI/CD、git push／GitPush；自訂詞與人工確認的短修正詞優先進入受限詞彙提示 | 詞彙是拼寫參考，不是可執行指令；一般 action／push 不硬換成產品名稱 |
| 上下跳動波形太躁動 | 使用淺綠圓形光暈，隨實際收音小幅變化；靜音時固定、停止後重設 | 模擬器畫面不能證明真實手機麥克風與噪音環境表現 |
| 上方切換太大、Enter 符號太小 | 上方改為較小的模式膠囊；Enter 改為置中的 24dp 向量圖示，保留 48dp 觸控範圍 | 仍需實機較大系統字體、橫向與觸控檢查 |

Android 本輪沿用現有 STT／LLM 選項，沒有加入 macOS 的 Qwen3 引擎。網站既有示意圖也不是 2.7.6 的實機截圖。

## 2. 個人詞彙與雲端處理

- 自訂詞彙與人工確認的短修正詞可作為後續 STT／LLM 的詞彙提示；整筆修正紀錄、候選頻率與錄音歷史不因此上傳。
- AI 自己的輸出不會自動記成已確認詞；本輪不建立 Android 完整聽寫歷史檔案。
- 在禁止個人化的輸入欄位，不使用已學習詞彙；密碼欄位仍停用語音與學習。
- 雲端處理同意升為版本 3。升級後請在 App 設定閱讀新說明並重新同意，即使曾同意版本 2 亦同。
- 官網日文、繁中、英文隱私說明同步揭露詞彙提示會送至所選 STT／LLM。

## 3. 驗證紀錄

以下為本輪本機測試與產物驗證結果。舊版測試數不視為本版證據。

| 檢查 | 本輪結果 |
|---|---|
| Android 單元測試、Debug Lint | 164 個單元測試通過，0 failures／0 errors／0 skipped；Debug Lint 0 errors／88 warnings |
| 簽署 Release APK／AAB | BUILD SUCCESSFUL；Release Lint 0 errors／76 warnings；AAB jarsigner 驗證通過（Android 自簽憑證警告，不作 CA 驗證）；Release APK manifest 不含 Debug KeyboardPreviewActivity；artifact-only 結果為 ARTIFACT VERIFIED，版本、大小、hash 與 signer 均符合 metadata |
| Python 迴歸 | `venv/bin/python -m pytest tests/ -o addopts='' -q`：534 passed in 6.11s；新 APK 產生後完整重跑通過 |
| Firestore Rules | Emulator 3／3 通過 |
| 網站 JavaScript／依賴檢查 | 3 個 JavaScript 檔語法通過；production npm audit 0 vulnerabilities |
| iOS source preflight／Python 靜態檢查 | source-only preflight 與 release-critical Ruff 通過 |
| Android 模擬器安裝與畫面 | Debug APK 2.7.6／26 安裝成功；5 張最新實際 View 合成截圖已檢視，靜音／0.6 音量與語音／注音／日文／英文正常，無重疊爆版，Enter 清楚置中；SGH crash buffer 無 crash，動畫設定已恢復。不能取代實機收音或準確度測試 |
| 真實 Android 手機 | 未執行：31 個基礎案例，另 7 個注音案例仍待實測 |
| Firebase live APK／metadata | 由 main 的 CI 通過後觸發 Firebase workflow 發布；須另核對該提交、workflow 與 live APK hash，部署回執另存於本輪產物目錄 |
| Google Play 2.7.6 | 未提交；目前 Mac 鎖定，無法操作 Console，不沿用 2.7.5 已發布狀態 |

## 4. 本輪新增實機案例

以下均使用合成句子，輸入到本機草稿，不對外送出訊息。另需完成 [Android RC 驗收](../ANDROID_RC_ACCEPTANCE.md) 的既有案例。

- [ ] DICT-01：口述短句「我我明天再確認」，確認保留原意並處理明確口吃；「哈哈哈」等合法重複不被刪光。
- [ ] DICT-02：口述「GitHub Actions 的 CI/CD 失敗，先不要 git push」，檢查技術詞、順序及「不要」都保留。
- [ ] DICT-03：口述「版本 2.7.6，有 12 個案例，明天 14 點再確認」，檢查版本、數字、時間未被改動。
- [ ] DICT-04：口述問句與命令句，確認只有原意文字，沒有「身為 AI」或代答。
- [ ] DICT-05：使用測試設定讓 AI 整理失敗，確認顯示回退提示且沒有把錯誤訊息當逐字稿插入。
- [ ] WORD-01：在個人詞庫新增一筆非敏感合成產品詞，後續口述檢查拼寫；移除後不再作為自訂提示。
- [ ] WORD-02：手動確認一筆短修正後再口述，檢查可撤銷／清除；未確認的 AI 輸出不自動變成已確認詞。
- [ ] HALO-01：安靜、一般說話、較大聲、再安靜，光暈只隨收到音量輕柔變化，靜音固定；取消／停止後不殘留動畫。
- [ ] UI-06：上方 Auto／注音／日文／英文在正常與較大字體均可切換；Enter 符號可辨識且觸控行為不變。
- [ ] CONSENT-03：由舊版覆蓋更新，金鑰、詞庫保留；未重新同意版本 3 前不送出音訊，重新同意後才恢復。

## 5. 安裝與產物

- 網站：`https://voice.shingihou.com/`
- APK：`https://voice.shingihou.com/downloads/SGHVoice-Android-v2.7.6.apk`
- Manifest：`sgh-voice-web/downloads/android-release.json`
- APK SHA-256：`9440f2eb170a7bd93510e14aa38e219b47617ef8c598be5c08093ed608a49168`
- APK 大小：17,339,573 bytes（16.54 MiB）。
- 簽署 AAB：`/Volumes/Satechi_SSD/voice-input/release-output/android-2.7.6/SGHVoice-Android-v2.7.6.aab`
- AAB SHA-256：`8215d6fe0ccbae2cf2f72fff8da7a6b15ca1cf6ceb371e3b3b1ac487c404aca4`
- 本輪模擬器畫面：`/Volumes/Satechi_SSD/voice-input/release-output/android-2.7.6/screenshots/synthetic-{voice-active,voice-silent,zhuyin,english,japanese}.png`。這些是使用合成音量的實際 View，並非真實手機錄音截圖。

從官方側載版更新時保留原 App，不先解除安裝。Google Play 安裝版沿原管道更新，以避免簽章差異造成資料遺失。正式商店上架與 12 人封閉測試不列為本輪手機功能改善的完成證據。
