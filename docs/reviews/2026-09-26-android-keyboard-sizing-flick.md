# Android 共用鍵盤高度與日文 flick

日期：2026-09-26。範圍：本機程式修正與驗證；不是新版 Play／Firebase 發布證明。

## 問題重現

Robolectric 直接建立 production `KeyboardView`，在 393×852dp、3× density
切換模式，修正前注音為 1116px（372dp），語音為 1271px（約424dp）。
`KeyboardGeometryTest` 原始 1 個測試確實失敗，不是複製尺寸公式的假測試。

根因：`onMeasure` 依當前模式的自然內容高度決定鍵盤高度；手動模式又有不同
列數與每列高度。即使螢幕相同，切換模式仍移動主 App 的輸入區。

## 實作與介面檢查

| Before | After | Why |
| --- | --- | --- |
| 語音較高、英文突然縮小 | 所有模式共用 372dp 基準與螢幕上限 | 模式切換不改變主 App 的可用高度 |
| 無尺寸設定 | 設定頁 90%–125%，每5%一格，可還原100% | 使用者能調整；偏好會儲存，下次開啟 IME 套用 |
| QWERTY 固定48dp列高 | 四列平均填滿與五列注音相同的按鍵區 | 不是只補一片空白湊高度 |
| 日文連按輪替 | 點／左／上／右／下 flick，放開只輸出一次 | 符合使用者要求；連點「な」為「なな」 |
| 日文滑動中第二指可能各打出一字 | 只在 Kana flick 模式不分割事件，第二指取消當次 | 防止誤輸入，同時保留 QWERTY 快速交疊打字 |
| 手勢沒有無障礙替代 | TalkBack 中央點擊及方向動作 | 不要求所有人都能做精準滑動 |

- 372dp 不含裝置的 navigation inset；inset 另外加入，四種模式一致。
- 共同上限為可用螢幕高度80%；極短視窗保留至少44dp按鍵並允許內容區捲動。
- 錄音狀態、草稿、候選展開與符號層不改變外框高度。語音圓保留原有淺色／漸淡風格。
- `な`：中央な、左に、上ぬ、右ね、下の。`や`：中央や、上ゆ、下よ。
  `わ`：中央わ、左を、上ん、右ー。未配置方向不輸出。
- 保留既有 Romaji／12鍵切換與 composer；flick 走既有 `InsertText → appendKana`，
  不再走 legacy multi-tap。沒有新增雲端請求或保存個人輸入。

## 驗證產物

`./gradlew :app:testDebugUnitTest :app:lintDebug :app:assembleDebug --console=plain`
最終完成256個測試（0 skipped／failure／error）、Lint 0 errors／107既有warnings，Debug APK 建置成功。
另 `venv/bin/python -m pytest tests/test_mobile_release_gates.py -q`：16項通過。
Lint 阻塞的 custom View 相容性已修正為 AppCompatTextView；未加入 suppress 或 baseline 隱藏錯誤。

- `android/SGHVoice/app/build/reports/tests/testDebugUnitTest/index.html`
- `android/SGHVoice/app/build/reports/lint-results-debug.html`
- `android/SGHVoice/app/build/reports/keyboard-preview/*-100.png`
  為 production View 的 synthetic native rendering，不是實機或辨識準確度證明。
- Debug APK：`android/SGHVoice/app/build/outputs/apk/debug/app-debug.apk`。
  不是正式同簽章更新檔，不應拿來覆蓋使用者既有正式安裝。

測試涵蓋共用高度、比例還原、橫向／大字、navigation inset、候選／符號／錄音狀態，
以及 MotionEvent 經整個 KeyboardView dispatch 到實際 listener 的方向、重複、取消和多指行為。

## 發布邊界

本輪不覆寫已發布的2.8.2 APK，也不把來源修正稱為手機已更新。下一版需分配新 versionCode、
簽章建置、實機驗收，再依管道發布。Google Play 版與側載版須分別確認 signer；不可要求先解除安裝。
目前付費 Alpha 招募仍需新版發行與測試資格設定；不把公開免費 APK 當成付費 Play 計畫已完成。
實機仍需確認手指滑動距離、TalkBack 語音、LINE等主 App 與橫向螢幕行為。
