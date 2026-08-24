# SGH Voice iOS Production Review（2026-08-09）

## Verdict

目前判定為 **NO-GO：不可直接送 TestFlight / App Review**。應用程式的 Swift 靜態檢查、隱私基礎、跨平台回歸與網站測試已通過，但 Apple 會員、完整 Xcode、正式 archive、審核員測試路徑與正式隱私頁部署仍未完成。

## Apple Developer 進度

- 2026-08-09 瀏覽器實際狀態：`登録がキャンセルされました`（註冊已取消）。
- 先前組織申請：SHINGIHOU CO., LTD.，D-U-N-S `692744025`，Enrollment ID `XGM6Z5L366`。
- Apple Developer Program 登入本身免費；App Store 發佈所需會員為每年 99 美元或當地等值金額。
- 若要繼續，必須重新開始 organization enrollment、完成 Apple 驗證、接受合約並支付年費。付款前不會進入完整 App Store Connect 發佈流程。

## 本輪已修正

1. STT readiness 改為依實際選定的 OpenAI / Groq 引擎檢查對應 API key，不再錄完才失敗，也不再暗中切換供應商。
2. 移除 iOS 預載詞庫中的個人姓名與姓名修正規則。
3. 首次外部 AI 同意新增「詞庫與場景提示」外送說明，並將 consent version 升為 v2，既有使用者會重新確認。
4. 清除資料功能現在也會清除自訂詞庫、修正規則與場景設定。
5. OpenAI / Groq / Anthropic request 改用 ephemeral `URLSession`，停用 URL cache 與 Cookie storage，補齊網路錯誤分類。
6. 錄音加入 10 分鐘自動停止與 24 MB 上傳防線；啟動時清除 crash / force-quit 遺留的 `sgh-voice-*.wav` 暫存檔；WAV 讀取移出主執行緒。
7. 三語隱私政策補齊 iOS 詞庫 prompt、provider retention、BYOK 刪除責任、same/equal protection 與下載登記資料保存邊界。
8. README 移除「100% 自主管理」與「只送 OpenAI/Anthropic」等不精確主張，改為實際 BYOK 資料流。
9. iOS 主要 UI、狀態、錯誤、VoiceOver 與隱私同意補齊日文、英文、繁體中文 130 組 localization；錯誤狀態不再依繁中文字面判斷，錄音錯誤也改為可正確顯示原因的 `LocalizedError`。
10. 建立日文 App Store metadata、TestFlight／Review Notes template、reviewer flow 與安全 Evaluation Access 架構文件；preflight 會驗證欄位限制、三語鍵集合與未替換 placeholder。
11. 設定頁移除「精確／極速」等未量化比較，以及容易過期的硬編模型價格；保留模型選擇、Fable 5 的 30 天資料留存警示，並導向供應商最新公告。

## 驗證結果

- `git diff --check`：通過。
- 全部 iOS Swift source `swiftc -typecheck`：通過。
- Xcode project、Privacy Manifest、三語 `InfoPlist.strings`：`plutil` 通過。
- App Icon JSON：通過；既有檢查確認 1024×1024、無 alpha。
- 三語 `Localizable.strings`：`plutil` 通過；各 130 keys 且鍵集合一致。
- 日文 metadata：Name 18 字、Subtitle 16 字、Promotional Text 81 字、Description 1,094 字、Keywords 98 bytes；均在 Apple 欄位限制內。
- Python regression：296 passed。
- Web targeted tests：5 passed。
- Android unit test + lint + debug assembly：通過，Gradle build successful。
- `xcodebuild` / simulator / archive / signing / Organizer validation：未執行，因本機只有 Command Line Tools，沒有完整 Xcode。

## Remaining blockers

### P0 — 送審前必須完成

1. 重新啟動並完成 Apple organization membership；確認 legal entity、Account Holder、agreements 與 membership Active。
2. 安裝完整 Xcode 26+ 與 iOS 26+ SDK，完成 unit/UI tests、Release archive、Validate App、TestFlight smoke。
3. 建立審核員可完整測試且不暴露第三方 API secret 的路徑。建議採可撤銷、有限額、短效的 review-only backend/token flow；不要把個人 provider key 放入 binary、repo 或 Review Notes。
4. 部署本機更新後的 `sgh-voice-web/privacy.html`。正式站目前仍是 2026-07-30 舊版。
5. 在 App Store Connect 完成 App Privacy answers；至少核對 Audio Data、Other User Content、Health、linked、App Functionality、no tracking。
6. 準備 iPhone screenshots；若維持 iPhone + iPad target，另需 13-inch iPad screenshots 與 iPad layout smoke。

### P1 — App Review 前完成

- 企業會員核准後重新確認 `DEVELOPMENT_TEAM`、App ID、distribution certificate/profile。
- 用 archive 實證 `PrivacyInfo.xcprivacy` 已被打包，並檢查 Xcode privacy report。
- 完成 Beta Description、What to Test、review contact、Review Notes、Support URL、age rating；若發行 EU，完成 DSA trader status。
- 以日文、英文、繁體中文各跑一次 simulator／實機 UI smoke；資源與 Swift 靜態檢查已通過，但尚未用完整 Xcode 驗證實際 bundle inclusion、截字與 VoiceOver。
- 建立 model lifecycle monitor，優先追蹤 `claude-haiku-4-5-20251001` 最早 2026-10-15 retirement boundary。
- 處理 nested `ios/SGHVoice/.git` 與 outer repo 的 source-of-truth 風險；發版只能以 outer repo 為準。
- 將目前必要 untracked iOS 檔案納入版本控制：`OutputContracts.swift`、`PrivacyInfo.xcprivacy`、App Icon、三語 `InfoPlist.strings`。

## 建議產品改善順序

1. **Reviewer / trial access**：建立受限 backend token flow，同時可成為新使用者不必先理解三種 API key 的 onboarding；正式商業模式、成本與 App Store payment policy 需另行決策。
2. **日文／英文 UI verification**：三語資源與動態錯誤 lookup 已補齊；下一步是在完整 Xcode 上驗證實際 bundle inclusion、Dynamic Type、截字與 VoiceOver 朗讀。
3. **錄音進度**：現在已有 10 分鐘上限，下一步應顯示錄音秒數與剩餘時間。
4. **iPad production polish**：若保留 iPad，需對四方向、sheet、長文結果與 Dynamic Type 做 simulator / 實機驗證。
5. **API lifecycle**：把 provider model availability / retirement 檢查加入 release checklist，不要等使用者回報 404 或 model-not-found。

## 官方查核

完整來源與逐項 checklist：

- [2026-08-09-ios-app-store-official-requirements.md](./2026-08-09-ios-app-store-official-requirements.md)
- [Apple Upcoming Requirements](https://developer.apple.com/news/upcoming-requirements/)
- [Apple App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- [Apple Program Enrollment](https://developer.apple.com/help/account/membership/program-enrollment)
