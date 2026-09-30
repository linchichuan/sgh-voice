# Android 2.8.6：淡綠收音介面與一體品牌

使用者已看過本機預覽，要求 Logo 與 SGH 靠在一起並確認直接發布。
versionCode 36；此輪為個人同簽章 APK 更新與 Firebase Hosting 發布，
不更換已送審的 Google Play Alpha bundle，不宣稱 Play 已核准。

| Before | After | Why |
| --- | --- | --- |
| 中央疊加深色光暈，收音時發灰 | #E1F8EA 淡綠漸層，不疊深色底；真實波形保持獨立 | 清爽、淡雅，避免聲音越大畫面越髒 |
| 小型語音圖示與 17sp SGH | 新義豊原始公司 Logo 與正常寬度 22sp SGH | 增強品牌辨識，維持原始資產 |
| Logo 與置中文字之間有空隙 | Logo 與 SGH 緊鄰、整組置中 | 品牌是一組，不拆開兩段 |
| 放大品牌可能擠壓模式列 | 280／320／393／480dp 與字體 1／1.5 倍檢查 | 保留各模式操作空間 |

保留大橢圓、中心向四周漸淡、左右小任務卡、錄音秒數及原本觸控高度。
靜音平線、減少動態模式、四種鍵盤共用高度不變。

Logo 直接沿用公司官網 `public/images/logo-mark.png`，未裁切或重繪。
公開網站仍是封閉測試申請導線，不連結 APK；側載更新不授予 Play 測試資格。

## 驗證與限制

Android 269 tests 全過；Debug／Release Lint、APK／AAB 組建通過；
網站 Firestore rules／招募導線 18 tests 全過，production dependencies audit 0 vulnerabilities。
Python 538 tests 全過；artifact-only 版本／大小／SHA-256／唯一同簽章 signer 驗證通過。
AAB jarsigner 驗證成功（Android 自簽憑證會有 PKIX／自簽警告，不是簽章失敗）。

- APK：`sgh-voice-web/downloads/SGHVoice-Android-v2.8.6.apk`。
- versionCode：36；size：17,526,324 bytes。
- SHA-256：`480e8bb71a9791a1aefdcef3b5d5012378c3159c98959f7a269c11f8d5d8f65b`。
- Signer：`ABAC2DCDA0D728A3C15870E294B26AB1F45274225DD251672EC2A197DE82EDDB`；唯一 APK v2 signer 與 2.8.5 一致。
- 個人更新連結：`https://voice.shingihou.com/downloads/SGHVoice-Android-v2.8.6.apk`。

發布後另記 Git commit、Firebase workflow、下載 HTTP 200、完整檔案雜湊、
Range 206 及 release manifest 實際驗證結果於 repo 上層 `release-output/android-2.8.6/RELEASE_RECEIPT.md`。

合成預覽使用正式 KeyboardView 的 native graphics，不代表實機麥克風或 STT 驗收。
手機安裝與常用 App 錄音仍須實機確認；同簽章側載請直接更新，不要先解除安裝。
