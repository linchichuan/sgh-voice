# Android 2.8.10 側載發布檢查

使用者授權 commit、push、deployment 與下載連結。此次只發布 Android 側載 APK 與網站更新；不提交 Google Play、不變更測試招募／付款設定。

## 產物

- versionName 2.8.10、versionCode 40。
- `sgh-voice-web/downloads/SGHVoice-Android-v2.8.10.apk`：17,923,139 bytes。
- SHA-256：`c5a5ff162623043b20e2d6ecf07a6ccddf96a24b0e0873a0b82b2586c510ce15`。
- 沿用既有側載簽章；舊 immutable APK 保留原檔。
- 網站更新頁：`https://voice.shingihou.com/android-update.html?lang=zh`。
- 新首頁圖片為原生 View 測試預覽，不是真實手機收音驗證。

## 修改範圍

注音候選出現時保持按鍵位置、英文數字列、日文十二鍵左右功能列與滑動／連按、場景詞庫、連續草稿整理與代寫預覽、標點及否定邊界保護。細節見同日 stable-layout-context 與 japanese-phone-layout 報告。

網站繁中／日文／英文版本資訊及更新說明同步。公開 Android 表單仍是申請測試，不觸發 APK 下載、不宣稱已加入 Play 測試。

## 發布前證據

- Android：518 tests，0 failures/errors/skipped。
- Signed Release build：SUCCESS；Release Lint 0 errors、100 warnings。
- Python：667 passed。
- Firestore Emulator／網站：23 passed；JavaScript 語法檢查通過。
- production npm audit：0 vulnerabilities；release-critical Ruff 通過。
- `verify_mobile_rc.sh --artifact-only`：版本、檔案大小、SHA-256、唯一簽章與 metadata 一致。

本文件是提交前本機證據；CI、Firebase 部署及 live GET/hash/Range 須在推送後另外核對，不能由本機通過推定。

## 未驗範圍

未連接 Android 實機；手機手感、更新後資料保留、實際收音、供應商準確率與延遲仍待驗。沒有呼叫付費 AI API；沒有新增雲端個人詞彙同步。Google Play 安裝者應沿用 Play 更新，不假設 Play 簽章與側載版相同。
