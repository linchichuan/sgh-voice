# Android 2.7.8 單一圓形錄音控制

日期：2026-09-12

版本：2.7.8（versionCode 28）

狀態：本輪自動化、簽署產物及 synthetic UI 驗證已完成；發布收據另行記錄，Google Play 與實機驗收未執行。不以先前版本結果作為本版完成證據。

## 1. 本版範圍

| 項目 | 變更 |
|---|---|
| 錄音控制 | 使用單一淺綠大圓，開始、錄音中、結束使用同一個控制位置 |
| 收音呈現 | 聲音進入時只在圓內顯示柔和波紋；沒有聲音時保持平靜 |
| 語音底列標點 | 原本的 `@` 快速鍵改為頓號 `、`，逗號 `，`、句號 `。` 保留；三個快速鍵皆可用 |
| 較大字體 | 200% 字體檢查發現上方狀態列固定高度裁字，改為隨內容增高並保留 28dp 最小高度；新增實際 View 幾何檢查 |
| 既有功能 | 保留既有聽寫、長按翻譯、語言模式與輸入流程 |

本版沒有更換 STT 或 AI 供應商，沒有改動語音辨識、句子整理、隱私與資料傳送範圍，不宣稱辨識率因此提高。雲端處理同意維持版本 3；已同意者不需再次同意。

網站的舊功能示意圖不是 2.7.8 實機截圖。先前功能與相容性修補歷史保留於 [2.7.6／2.7.7 改善紀錄](2026-09-11-android-dictation-refinement.md)。

## 2. 驗證結果

| 檢查 | 本版證據 |
|---|---|
| Firestore 下載登記規則 | 既有公開 client 測試更新為 2.7.8 後，舊規則拒絕合法登記（1 fail／2 pass）；更新版號與檔名白名單後，Emulator 3／3 通過 |
| 公開 APK／manifest／版號一致性 | 測試先改為 2.7.8／28，在舊 manifest 下取得 2 項失敗；字體裁字修正後以最終 APK 完整重跑：Python 535 passed in 5.88s，artifact-only PASS |
| JavaScript 語法與網站三語 | JavaScript 語法與三語 key 一致性通過；release-critical Ruff 通過；production npm audit 0 vulnerabilities |
| Android 單元測試、Lint | 167 tests 通過；Debug Lint 0 errors／95 warnings，Release Lint 0 errors／78 warnings |
| 簽署 APK／AAB 與 artifact-only | 字體裁字修正後最後組建 BUILD SUCCESSFUL（2m50s），最終 APK／AAB hash 已更新；APK `8bef8543…93809049` 的 artifact-only PASS。AAB 有 Android 自簽與 ZIP entry-order 警告，不代表 Google Play 驗證通過 |
| 模擬器／畫面 | active／silent／processing 大圓三圖已目視檢視；最終 `ui-final-contract.xml` PASS，200% zh-TW 截圖確認狀態列與圓內文字無裁切。這是 synthetic UI 驗證，不等同實機收音通過 |
| 實際 Android 手機 | 未執行；[RC 驗收](../ANDROID_RC_ACCEPTANCE.md) 的 31 個基礎＋7 個注音案例及下列新增案例仍待驗 |
| Firebase／Google Play | Firebase 由本版 main CI 通過後發布；須另核對提交、workflow 與 live APK hash，實際發布回執另存於本版產物目錄。Google Play 本輪未操作 |

本文件只記錄取得證據的結果，不把組建成功、模擬器截圖或網站原始碼修改視為手機實測通過或商店發布完成。

## 3. 本版新增驗收案例

- [ ] CIRCLE-01：待機時只顯示一個主要淺綠圓形；開始錄音後可在同一位置結束，沒有額外分離的開始／停止控制。
- [ ] CIRCLE-02：安靜 → 一般說話 → 安靜，圓內波紋只在實際收到聲音時變化，靜音後回復平靜。
- [ ] CIRCLE-03：短按完成錄音只插入一次；取消或停止後，圓內沒有殘留動畫；既有長按翻譯入口仍可使用。
- [ ] PUNCT-01：語音底列分別點頓號 `、`、逗號 `，`、句號 `。`，各只插入一個對應標點；頓號鍵不再插入 `@`。
- [ ] UI-07：正常／較大系統字體、直向／橫向切換後，大圓、模式列與底列標點皆可見且可操作。

全部使用非敏感合成句子，結果只留在草稿，不對外傳送。

## 4. 當前產物

- 網站：`https://voice.shingihou.com/`
- APK：`https://voice.shingihou.com/downloads/SGHVoice-Android-v2.7.8.apk`
- APK SHA-256：`8bef85433723474ea017de1b45a4af29777631d2e3730e95a27ce7dc93809049`
- APK 大小：17,340,997 bytes（16.54 MiB）。
- Manifest：`sgh-voice-web/downloads/android-release.json`（由主 agent 依實際產物更新）。
- AAB：`/Volumes/Satechi_SSD/voice-input/release-output/android-2.7.8/SGHVoice-Android-v2.7.8.aab`
- AAB SHA-256：`2c0fec71013e465cd20537148d6a5f7b672775e5c555cca4aca2713cb33c61e0`
- Git／部署／live APK 驗證收據：`/Volumes/Satechi_SSD/voice-input/release-output/android-2.7.8/RELEASE_RECEIPT.md`（發布完成後另行記錄）。

官方側載版使用相同 package name 與 signer 驗證通過後可直接覆蓋更新；保留原 App 以保留設定和詞庫。Google Play 安裝版沿原安裝管道更新。舊 2.7.6、2.7.7 APK 不覆寫，歷史檔案與 hash 保留。
