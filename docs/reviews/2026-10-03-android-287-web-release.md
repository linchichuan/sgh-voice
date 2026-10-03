# Android 2.8.7 網站與側載發布

## 範圍與授權

接續 `2026-10-03-android-safe-learning-final.md`。使用者本輪明確要求更新 Landing Page、發布新版並提供下載連結；因此本輪將已驗證的候選 APK 放上 Firebase Hosting。Google Play 已送審／封閉測試軌道與價格設定不變。

首頁繼續招募封閉測試：送出資料只建立 pending 申請，不自動下載、不授予資格、不宣稱邀請已寄出。既有側載使用者另從 `android-update.html` 取得更新，並明示側載不計入 Google Play 測試。更新頁不載入 Firebase、不收集資料、設為 noindex；noindex 並非存取控制，APK 仍是公開檔案。

## 產物

- Android package：`com.shingihou.sghvoice`
- 版本：2.8.7，versionCode 37
- 檔案：`sgh-voice-web/downloads/SGHVoice-Android-v2.8.7.apk`
- 大小：17,581,752 bytes
- SHA-256：`8f1f8ab2a4fea1c27a7bcc7b7826bf64e3b7274222ef8339fca0fbd56229f7dc`
- 唯一 signer SHA-256：`ABAC2DCDA0D728A3C15870E294B26AB1F45274225DD251672EC2A197DE82EDDB`
- 來源：repo 上層 `release-output/android-2.8.7-safe-20261003/`，對應已提交之 Android 程式 `68779a8cda1deb5899696e064a35f058947cf3ac`。APK 在該 commit 之前建置，不能將此 SHA 宣稱為 APK 內嵌 build metadata。
- 網站預覽：該候選版實際 KeyboardView 渲染，1179 × 1116；非手機收音／安裝驗收。

保留舊版 immutable APK，不覆寫舊 URL。新頁沿用靜態 HTML/CSS/三語 i18n，沒有增加 API、OAuth、雲端學習、追蹤器或自動寄信。

## CI 阻擋根因

先前 `68779a8` 的 CI 中，Android、iOS、Web jobs 通過；Python job 的版本一致性測試失敗，原因為 source 2.8.7 與當時仍保留的網站 manifest 2.8.6 不同。此輪同步公開 APK、manifest、RC 文件與版本測試期望，不停用或略過 gate。

## 驗證與限制

- `verify_mobile_rc.sh --artifact-only`：新 APK 版本、大小、SHA-256、APK v2 簽章與唯一 signer 均通過。
- Python 全量：540 passed；網站／Firestore Emulator／招募流程：19 passed。更新頁與首頁翻譯鍵值三語完整、JS 語法檢查通過、production dependency audit 無漏洞。
- Playwright 檢視桌面 1440px 與手機 390px 首頁、更新頁；無橫向溢出，1179 × 1116 預覽維持原比例。畫面在 repo ignored `output/playwright/landing-287/`；未提交真實申請、未寄信或寫入 production Firestore。
- 原 Android 修復：422 個 repo 測試及 13 個獨立探針通過，詳見前述 Android 報告；此輪不更改 Android 原始碼。
- 手機真實收音、外部 AI 準確率與實機覆蓋安裝仍待使用者試用；網站截圖與合成測試不代表這些已驗證。
- Google 官方封閉測試要求於本輪查核：https://support.google.com/googleplay/android-developer/answer/14151465 。網站申請與側載皆不替代 Play opt-in。

最後公開 HTTP、完整 APK hash 與下載續傳檢查須在發布後執行；push 本身不作為發布成功證據。
