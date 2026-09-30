# Android 淺綠介面：本機待確認預覽

預覽階段狀態：僅本機修改。使用者確認預覽前，不 commit、push、上傳 APK、部署 Firebase 或變更 Google Play。
預覽階段的既有 2.8.5 公開下載與版本資訊保持不變。

後續確認：使用者看過預覽後，要求 Logo 與 SGH 緊鄰為一組，並明確同意「直接上」。
本機預覽階段已結束；核准後的 2.8.6 發布證據另記於 `2026-10-01-android-286-mint-brand.md`。

| Before | After | Why |
| --- | --- | --- |
| 淺綠底色混入深色墨水，收音時另疊灰綠光暈 | 淺綠 #E1F8EA 漸層獨立繪製，移除深色光暈 | 聲音變大時仍清爽，不讓中央變髒、變灰 |
| SGH 17sp、靠左對齊、語音產品圖示 | SGH 正常寬度 22sp，增加品牌區留白、垂直置中，使用公司原始 Logo | 改善品牌可讀性與頂列比例 |
| 固定品牌寬度 | 品牌區依窄螢幕調整 88／96／104dp | 放大品牌時仍保留旁邊語言切換空間 |

Logo 原始來源：`/Volumes/Satechi_SSD/GitHub/shingihou.com/public/images/logo-mark.png`。
直接沿用完整 PNG，未裁切、重繪或改色。

保留：大橢圓、由中間向外淡出的無框漸層、左右小型任務卡、錄音秒數、
真實音量驅動波形、靜音平線、減少動態模式及既有按鍵觸控大小。

預覽由正式 Android View 以 Robolectric native graphics 繪製；音量為合成資料，
不代表實機麥克風或 STT 準確度驗收。APK 僅能在使用者確認後另行版本化、簽章與發布。

## 修改範圍

- `KeyboardView.kt`：移除底色混灰、品牌區響應式寬度。
- `AudioWaveformView.kt`：移除深色光暈，保留真實音量波形。
- `VoicePalette.kt`、`colors.xml`：統一新的淡綠色。
- `keyboard_view.xml`、`drawable-nodpi/shingihou_company_mark.png`：放大並置中品牌、原始公司 Logo。
- `KeyboardGeometryTest.kt`：新增品牌版面與禁止深色光暈回歸測試。
- Debug README 與本文件：同步本機預覽及發布確認門檻。

## 驗證結果

`testDebugUnitTest`（KeyboardGeometryTest、VoicePaletteTest、AudioHaloEnvelopeTest）、
`lintDebug`、`assembleDebug` 全部通過；`git diff --check` 通過。
Logo 與公司官網原始資產 SHA-256 相同，未改動圖片內容。

本機預覽：`/Volumes/Satechi_SSD/voice-input/release-output/android-ui-preview-2026-10-01/`，
含 `voice-recording.png` 與 `voice-idle.png`。
上述預覽階段未提升版本號、未產生新的公開下載、未改動 Firebase／Play。
