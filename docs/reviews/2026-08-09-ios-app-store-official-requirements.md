# SGH Voice iOS：App Store 官方要求查核（2026-08-09）

> 查核日：2026-08-09（Asia/Tokyo）
> 範圍：Apple Developer Program、build/upload、privacy manifest、App Privacy、第三方 AI、截圖、TestFlight/App Review、export compliance、目前 iOS model lifecycle。
> 證據基準：Apple、OpenAI、Anthropic、Groq 第一方文件，以及本 repository 目前 iOS 原始碼。外部政策會變動，正式 upload 前應再重跑一次檢查。

## 1. Executive verdict

目前不是「可立即送 TestFlight / App Review」狀態。程式已有不錯的隱私基礎（明示第三方 AI 同意、Keychain、麥克風說明、privacy manifest、TLS export key），但仍有四個 production/submission blocker：

1. **Apple organization membership 必須先核准並啟用**：組織 enrollment 要完成法律實體、D-U-N-S、簽約權限、公司網域信箱及公開公司網站驗證；repository 不能證明會員已啟用。[Apple：Program enrollment](https://developer.apple.com/help/account/membership/program-enrollment)
2. **目前機器沒有可用的完整 Xcode**：`xcode-select -p` 指向 `/Library/Developer/CommandLineTools`，`xcodebuild` 明確回覆必須使用完整 Xcode；而 2026-04-28 起 iOS/iPadOS upload 必須用 Xcode 26 或更新版與 iOS/iPadOS 26 SDK 或更新版。[Apple：Upcoming Requirements](https://developer.apple.com/news/upcoming-requirements/)
3. **送審素材未完成**：target 是 universal app（`TARGETED_DEVICE_FAMILY = "1,2"`），因此 iPhone 與 iPad 截圖都要準備；repo 目前只有 1024 App Icon，沒有 App Store screenshots。[Apple：Screenshot specifications](https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications/)
4. **Reviewer 無法自然取得完整功能**：App 的 STT 與 LLM 都依賴使用者自備 OpenAI / Anthropic / Groq API key，repo 沒有 reviewer demo mode。Apple 要求提供完整 access、必要設定與可測資源；第一個 external TestFlight build 也會送 Beta App Review。[Apple：Guideline 2.1](https://developer.apple.com/app-store/review/guidelines/#performance)、[Apple：TestFlight Overview](https://developer.apple.com/help/app-store-connect/test-a-beta-version/testflight-overview)

模型方面，**iOS 目前實際列出的 model ID 在 2026-08-09 都尚未 deprecated/retired**。但 Anthropic 預設 `claude-haiku-4-5-20251001` 的官方保證只到「不早於 2026-10-15」，需建立 lifecycle 監控；`claude-fable-5` 強制 30 天資料保留，必須在隱私揭露中維持清楚區分。[Anthropic：Model deprecations](https://platform.claude.com/docs/en/about-claude/model-deprecations)、[Anthropic：API and data retention](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention)

## 2. Apple Developer Program / organization enrollment

### 官方要求

組織 enrollment 至少需要：

- Apple Account 開啟 two-factor authentication，且申請人達所在地法定成年年齡。
- 法律實體；DBA、商號、虛構名稱或分公司不接受，法律實體名稱會成為 App Store seller name。
- 該法律實體的九位 D-U-N-S Number。
- 申請人有權代表組織簽訂 Apple 法律協議（owner/founder、executive、senior project lead，或獲授權員工）。
- 與公司 domain 關聯的工作信箱。
- 公開可用、內容完整且 domain 與公司關聯的網站；單純社群頁面或網域停放頁不接受。

來源：[Apple：Program enrollment](https://developer.apple.com/help/account/membership/program-enrollment)、[Apple：D-U-N-S Number](https://developer.apple.com/help/account/membership/D-U-N-S/)

### 對目前進度的判定

- 這份 repository 無法讀取 Apple 帳號的 enrollment status，因此不能只靠程式碼宣稱 membership 已核准。
- 在 Apple 完成簽約權限驗證、Account Holder 接受協議並完成年費／會員啟用前，不能進入正常 App Store Connect 建 App、簽署 distribution、TestFlight upload 的完整流程。
- Apple 官方沒有在 enrollment 說明頁保證固定核准天數；不要對內或對外承諾「幾天一定完成」。如果 D&B 資料剛更新，Apple 說明頁寫的是最多約 2 個工作天同步到 Apple；這不是 Apple 人工 enrollment 審查 SLA。[Apple：D-U-N-S Number](https://developer.apple.com/help/account/membership/D-U-N-S/)

### 啟用後立即執行

1. 確認 Membership 顯示 Active、正確 legal entity 與 Account Holder。
2. 接受最新 agreements；若要 EU 上架，同步完成 DSA trader status。Apple 自 2024-10-16 起要求在 EU 發布更新時提供 trader status。[Apple：Upcoming Requirements](https://developer.apple.com/news/upcoming-requirements/)
3. 建立 `com.shingihou.SGHVoice` App ID、distribution certificate/profile 與 App Store Connect app record。
4. 確認 2026 新 age-rating 問題已完整回答；Apple 自 2026-01-31 套用新版 age-rating system。[Apple：Upcoming Requirements](https://developer.apple.com/news/upcoming-requirements/)

## 3. Xcode / SDK / archive and upload

### 官方要求

- 自 2026-04-28 起，送到 App Store Connect 的 iOS / iPadOS app 必須使用 **Xcode 26 或更新版**，並以 **iOS 26 / iPadOS 26 SDK 或更新版**建置。[Apple：Upcoming Requirements](https://developer.apple.com/news/upcoming-requirements/)
- 這是「建置 SDK」要求，並不表示 deployment target 必須改成 iOS 26；目前 `IPHONEOS_DEPLOYMENT_TARGET = 17.0` 可以保留，只要 archive 使用符合要求的 SDK。

### Repo / machine evidence

- `ios/SGHVoice/SGHVoice.xcodeproj/project.pbxproj`
  - `CreatedOnToolsVersion = 26.3`
  - `SUPPORTED_PLATFORMS = "iphoneos iphonesimulator"`
  - `IPHONEOS_DEPLOYMENT_TARGET = 17.0`
  - `MARKETING_VERSION = 2.7.0`
  - `CURRENT_PROJECT_VERSION = 8`
  - `PRODUCT_BUNDLE_IDENTIFIER = com.shingihou.SGHVoice`
- 本機 `xcodebuild -version` 失敗：active developer directory 是 Command Line Tools，而非 Xcode；`/Applications` 也找不到 `Xcode*.app`。

### Blocker / completion gate

- 安裝完整 Xcode 26+（建議與 project 建立版本相容的 26.3 或更新正式版），切換 `xcode-select`，再跑：
  - `xcodebuild -version`
  - `xcodebuild -showsdks`
  - simulator unit/UI tests
  - generic iOS device Release archive
  - Organizer Validate App
- 最終 archive 要確認實際 SDK，而不是只看 project 的 `SDKROOT = auto`。

## 4. Privacy manifest / required reason APIs

### 官方要求

- `PrivacyInfo.xcprivacy` 用來聲明 app/SDK 蒐集的資料種類，以及使用 required reason API 的合法理由；無效 manifest 會遭 App Store Connect 拒絕。[Apple：Privacy manifest files](https://developer.apple.com/documentation/bundleresources/privacy-manifest-files)、[Apple：Adding a privacy manifest](https://developer.apple.com/documentation/bundleresources/adding-a-privacy-manifest-to-your-app-or-third-party-sdk)
- 自 2024-05-01 起，使用 required reason API 卻未在 manifest 提供 approved reason 的新 app/update 不被 App Store Connect 接受。[Apple：Describing use of required reason API](https://developer.apple.com/documentation/bundleresources/describing-use-of-required-reason-api)

### 目前實作判定

`ios/SGHVoice/SGHVoice/PrivacyInfo.xcprivacy` 已存在，並包含：

- `NSPrivacyAccessedAPICategoryUserDefaults` / reason `CA92.1`。
- Audio Data、Other User Content、Health，皆標成 linked、App Functionality、not tracking。
- `NSPrivacyTracking = false`，無 tracking domain。

這與目前程式大致相符：

- `ApiConfig.swift`、`DictionaryManager.swift` 使用 `UserDefaults.standard`，且只讀寫 app 自己的 preferences；Apple 對 `CA92.1` 的定義正是「只供 app 本身存取的 user defaults」。[Apple：NSPrivacyAccessedAPITypeReasons](https://developer.apple.com/documentation/bundleresources/app-privacy-configuration/nsprivacyaccessedapitypes/nsprivacyaccessedapitypereasons)
- App 直接以 Foundation / AVFoundation / Security 實作，project 沒有 Swift Package 或第三方 SDK dependency；目前未看到需額外 SDK privacy signature 的套件。
- `FileManager.temporaryDirectory`、刪除暫存錄音本身未顯示 app 主動讀取 file timestamp、disk space、system boot time 或 active keyboard；目前不需為這些額外加 reason。正式 archive 後仍應用 Xcode privacy report 再驗一次。
- Project 使用 file-system-synchronized group，manifest 理應納入 target resources；但因本機無 Xcode，目前未能以 archive bundle 實證 `PrivacyInfo.xcprivacy` 已被打包，這是 release gate。

### Health 資料聲明

一般 free-form text/voice 不需要把使用者「可能」說出的每種內容逐一聲明；Apple 明確舉例，通用文字欄與錄音可用 Other User Content + Audio Data 表示。但 SGH Voice iOS 另有明確的「醫療・藥品・生技」scene，會引導醫療詞彙處理，因此保守保留 Health 類別是合理的，而不是純粹過度聲明。[Apple：App privacy details](https://developer.apple.com/app-store/app-privacy-details/)

## 5. App Privacy、audio / health / third-party AI disclosure

### App Store Connect 必填，不會由 manifest 自動完成

- iOS 必須提供可公開存取的 Privacy Policy URL，並在 App Store Connect 回答 app 及第三方 partner 的資料處理行為；回答要涵蓋所有平台版本中最完整的情況，且實務變更時需更新。[Apple：Manage app privacy](https://developer.apple.com/help/app-store-connect/manage-app-information/manage-app-privacy)
- Apple 對「collect」的定義是：資料傳出裝置並以可讀形式保存超過完成該次 request 所需時間。如果只為即時服務且立即丟棄，App Store Connect 可不視為 collection。[Apple：App privacy details](https://developer.apple.com/app-store/app-privacy-details/)
- Apple Guideline 5.1.2(i) 要求在把 personal data 分享給第三方（明確包含 third-party AI）前，清楚揭露分享對象並取得 explicit permission。[Apple：App Review Guidelines 5.1](https://developer.apple.com/app-store/review/guidelines/#privacy)
- Privacy policy 還必須說明 data collection/use、所有第三方、retention/deletion、撤回同意／要求刪除，並確認第三方提供相同或相等保護。[Apple：App Review Guidelines 5.1.1](https://developer.apple.com/app-store/review/guidelines/#privacy)

### 目前做對的部分

- `MainView.swift` 在首次開始錄音前顯示「外部 AI 處理同意」，列出：
  - 錄音音訊送 OpenAI 或 Groq；
  - 逐字稿送 Anthropic、OpenAI 或 Groq；
  - 使用 BYOK，可能與服務商帳號關聯；
  - 可取消，並可從 Settings 撤回同意。
- `NSMicrophoneUsageDescription` 已說明會錄音並送往所選 STT provider，且有中、日、英 localization。
- App 內已有 [SGH Voice Privacy Policy](https://voice.shingihou.com/privacy.html) 連結；2026-08-09 live check 為 HTTP 200，但正式站仍是 2026-07-30 舊版，尚未包含本機工作樹新增的 iOS 暫存刪除、Keychain、詞庫 prompt、外部 provider retention 與 iOS 清除資料方式。部署更新是送審前 blocker。
- `PrivacyInfo.xcprivacy` 的 Audio Data / Other User Content / Health + App Functionality + not tracking 與 app capability 一致。因 request 使用使用者 provider account 的 API key，保守標成 linked 是可辯護的。

### 仍需在送審前確認／改善

1. **App Store Connect 的 App Privacy answers 必須手動建立並與 manifest／privacy page 一致**：至少檢查 Audio Data、Other User Content、Health；purpose = App Functionality；no tracking；linked 狀態依 provider 帳號關聯採保守 `Yes`。不能因 repo 有 manifest 就假設 Nutrition Label 已完成。
2. **把第三方 retention 寫得更具體**：目前 privacy page 主要說「新義豊伺服器不保存」，但 Apple 會看第三方實際 retention：
   - OpenAI API 的 abuse-monitoring logs 預設可能含 customer content，最多保留 30 天，除非客戶獲准 Zero Data Retention / Modified Abuse Monitoring；API data 預設不用於訓練，除非 opt-in。[OpenAI：Data controls](https://platform.openai.com/docs/models/default-usage-policies-by-endpoint)
   - Groq inference 預設不保留 customer inputs/outputs，但為 system reliability / suspected abuse 可能暫存最多 30 天；可啟用 ZDR。[Groq：Your Data in GroqCloud](https://console.groq.com/docs/your-data)
   - Anthropic Messages API 的 conversation content 現在預設不保留；但 `claude-fable-5` 是 Covered Model，強制 30 天 retention，不能套 ZDR。[Anthropic：API and data retention](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention)
3. Privacy page 應明確陳述如何確認第三方提供 Apple 要求的 same/equal protection，或在無法做出真實確認時移除該 provider；只叫使用者自行閱讀供應商政策，可能不足以滿足 Guideline 5.1.1(i)。
4. 由於 medical scene 是明確功能，App Store metadata 不應宣稱診斷、治療、療效或合規保證；若 marketing 把它定位成 medical app，Apple 會提高 scrutiny。App 並未使用 HealthKit，勿在 metadata 暗示 HealthKit integration。[Apple：Guidelines 1.4 / 5.1.3](https://developer.apple.com/app-store/review/guidelines/#physical-harm)

## 6. Provider API key architecture risk

目前 iOS 是 BYOK，key 存 Keychain，沒有把開發者 secret hard-code 進 app，這比內嵌共用 key 安全。但 OpenAI 官方仍明確要求「不要把 API key 部署在 browser 或 mobile app client」，而應經過可信 backend；client-side key 遺失會造成盜用與費用風險。[OpenAI：API key safety](https://help.openai.com/en/articles/5112595-best-practices-for-api-key)

這不等於 Apple 一定拒絕 BYOK，但屬 production security / support 風險：

- 短期：維持 Keychain、遮蔽輸入、提供撤銷/輪替說明；不要把任何 reviewer/shared provider key 寫入 binary、repo 或 App Review notes。
- 中期：評估 scoped user token、provider-supported OAuth（若有）或最小權限 backend token broker。若改成公司代付 backend，需重新評估成本、rate limiting、abuse、privacy labels、retention、帳戶刪除及 App Store payment policy。

## 7. Screenshots / iPhone / iPad

### 官方要求

- 每個 required device set 可上傳 1–10 張 JPEG/JPG/PNG；不能含 alpha。App preview 是 optional。[Apple：Upload screenshots](https://developer.apple.com/help/app-store-connect/manage-app-information/upload-app-previews-and-screenshots)
- iPhone 建議提供最高解析度 6.9-inch screenshot set；Apple 會依規則縮放到較小裝置。[Apple：Screenshot specifications](https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications/)
- 如果 app 可在 iPad 執行，13-inch iPad screenshot set 是 required。[Apple：Screenshot specifications](https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications/)

### 目前缺口

- Project `TARGETED_DEVICE_FAMILY = "1,2"`，代表 iPhone + iPad。
- Repo 沒有 App Store screenshots / app preview 素材。
- App 對 iPad 宣告四方向，iPhone 宣告 portrait + landscape；必須實機／simulator 確認旋轉後沒有重疊、過寬、sheet 爆版。

### 決策

- 若 Phase 1 要支援 iPad：至少產出 iPhone 6.9-inch 與 iPad 13-inch 的正式截圖，並跑 iPad layout smoke test。
- 若 Phase 1 不打算支援 iPad：送審前把 target family 明確限為 iPhone，並重新驗證 archive metadata；不要只是不提供 iPad 截圖。

## 8. TestFlight / App Review completeness

### 官方流程

- TestFlight 要填 beta app description、What to Test、feedback email 等 test information；build 最長可測 90 天。[Apple：TestFlight Overview](https://developer.apple.com/help/app-store-connect/test-a-beta-version/testflight-overview)
- Internal testers 最多 100 位；external testers 最多 10,000 位。第一個加入 external group 的 build 會送 TestFlight App Review；後續 build 可能不需完整 review。[Apple：TestFlight Overview](https://developer.apple.com/help/app-store-connect/test-a-beta-version/testflight-overview)、[Apple：Invite external testers](https://developer.apple.com/help/app-store-connect/test-a-beta-version/invite-external-testers)
- App Review 要求完成 metadata、可用 URL、on-device stability、完整 access、必要 demo account/resources、live backend、非顯而易見功能與設定的 review notes。[Apple：Guideline 2.1](https://developer.apple.com/app-store/review/guidelines/#performance)
- App Review information 中要有 contact name/email/phone、notes；若需登入則 demo account 不能過期。[Apple：Platform version information](https://developer.apple.com/help/app-store-connect/reference/app-information/platform-version-information)

### SGH Voice 特有 blocker

Reviewers 沒有 OpenAI / Anthropic / Groq key 就無法完成核心語音辨識。不能把共用 personal API key 塞進 binary 或公開 notes；OpenAI 也明確說 key 不應分享、每位成員應使用自己的 key。[OpenAI：API key safety](https://help.openai.com/en/articles/5112595-best-practices-for-api-key)

送 external TestFlight 前要選一條可被 Apple 實測、又不洩漏 provider secret 的路徑：

- 與 App Review 事先確認 fully featured demo mode；或
- 建立受限、可撤銷、有限額的 review-only backend/token flow，並在 review notes 提供使用方式；不得把真實 secret 放進文件或原始碼。

Review notes 至少要說明：BYOK、外部 AI consent、資料流、醫療 scene 的限制、錄音手勢、翻譯長按動作、privacy policy URL、如何進入 reviewer test path。所有 endpoint 在 review 期間必須可用。

## 9. Export compliance

### 官方要求

Apple 建議在 Info.plist 加 `ITSAppUsesNonExemptEncryption`。若 app（含 linked libraries）不使用 encryption，或只使用免文件的 encryption，就設 `NO`；使用 `NSURLSession` 進行 HTTPS 這類 OS 內建 encryption 通常免上傳 export documentation。[Apple：Complying with Encryption Export Regulations](https://developer.apple.com/documentation/security/complying-with-encryption-export-regulations)

### 目前判定

- Project Debug / Release 都已有 `INFOPLIST_KEY_ITSAppUsesNonExemptEncryption = NO`。
- iOS code 使用 `URLSession` HTTPS 與 Apple Security/Keychain，未看到自訂 crypto 或第三方 crypto library。
- 依目前 code，`NO` 合理，通常不需另上傳 encryption document；仍須在每次引入新 SDK/crypto 後重評估。美國年終 self-classification 是否適用，Apple 文件提醒可能仍需由公司依出口法務情境判斷。

## 10. Model lifecycle check（截至 2026-08-09）

| Provider / code path | Repo model ID | 官方狀態 | 判定 / 行動 |
|---|---|---|---|
| OpenAI STT | `whisper-1` | 官方 model page 仍列為可用，支援 `v1/audio/transcriptions`；未列為 deprecated | 可用；不是 blocker。可另測 `gpt-4o-mini-transcribe` / `gpt-4o-transcribe`，但不得未測即換。[OpenAI Whisper model](https://developers.openai.com/api/docs/models/whisper-1) |
| OpenAI LLM | `gpt-4o` | 官方 detail page 顯示 alias `gpt-4o` 指向 `gpt-4o-2024-08-06`；被標成 Deprecated 且排定 2026-10-23 shutdown 的是舊 snapshot `gpt-4o-2024-05-13`，不是 repo 使用的 alias | 目前可用但屬較舊 generation；應規劃 regression-tested migration，不是現時 shutdown blocker。另勿把 2026-02 的 ChatGPT retirement 誤當 API retirement。[OpenAI GPT-4o model](https://developers.openai.com/api/docs/models/gpt-4o)、[OpenAI API deprecations](https://developers.openai.com/api/docs/deprecations)、[ChatGPT retirement notice](https://openai.com/index/retiring-gpt-4o-and-older-models/) |
| Groq STT | `whisper-large-v3-turbo` | Groq production model，未列入 deprecation；也是舊 Distil Whisper 的官方 replacement | 可用。[Groq Supported Models](https://console.groq.com/docs/models)、[Groq Deprecations](https://console.groq.com/docs/deprecations) |
| Groq LLM | `openai/gpt-oss-120b` | Groq production model，未列入 deprecation，且是多個 2026 deprecation 的 replacement | 可用。[Groq GPT-OSS 120B](https://console.groq.com/docs/model/openai/gpt-oss-120b)、[Groq Deprecations](https://console.groq.com/docs/deprecations) |
| Anthropic default | `claude-haiku-4-5-20251001` | Active；tentative retirement 不早於 2026-10-15 | 現在可用，但只剩約兩個月到最早 retirement boundary；立即建立 migration watch。[Anthropic Model deprecations](https://platform.claude.com/docs/en/about-claude/model-deprecations) |
| Anthropic options | `claude-sonnet-5`, `claude-opus-5`, `claude-opus-4-8`, `claude-fable-5` | 2026-08-09 均為 Active | model ID 本身無 blocker；Fable 5 強制 30 天 retention，且不是 ZDR eligible。[Anthropic Models overview](https://platform.claude.com/docs/en/about-claude/models/overview)、[Anthropic Data retention](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention) |

補充：Anthropic 4.6 generation 之後的 dateless model ID 是 pinned release ID，不是會偷偷換權重的 evergreen alias；目前 `claude-sonnet-5` 等格式本身合法。[Anthropic：Model IDs and versioning](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions)

### Lifecycle follow-up

- 每週／每月至少監控：OpenAI models/deprecations、Groq deprecations、Anthropic model deprecations。
- 對任何 model swap 跑同一份中／日／英 dictation + translation regression corpus，再更新 Settings 顯示、privacy/retention、pricing reference 與 review notes。
- 不要把「ChatGPT UI 退休」誤當成「OpenAI API 已停用」，也不要只因 model 尚 active 就忽略 Anthropic tentative retirement date。

## 11. Submission checklist（可執行）

### P0 — 無法送審前必做

- [ ] Apple organization membership = Active；agreements/annual membership 已完成。
- [ ] 安裝並選用完整 Xcode 26+；確認 iOS 26+ SDK。
- [ ] Release archive、unit/UI tests、Organizer validation 通過。
- [ ] Archive bundle 內實際包含 `PrivacyInfo.xcprivacy`，Xcode privacy report 無未聲明 required reason API。
- [ ] App Store Connect App Privacy answers 與 Audio / Other User Content / Health、linked/no-tracking、第三方 retention 一致。
- [ ] 建立可讓 Apple 完整測試、且不暴露第三方 API secret 的 reviewer path。
- [ ] iPhone screenshots；若維持 iPad target，另有 13-inch iPad screenshots 與 layout smoke。

### P1 — 正式 App Review 前

- [ ] Privacy policy 明確補齊 OpenAI/Groq/Anthropic/Fable retention 與 same/equal-protection 說明。
- [ ] Beta description、What to Test、feedback/contact、review notes 完成。
- [ ] Support URL 有實際聯絡方式；privacy URL live；metadata 不過度承諾醫療能力。
- [ ] Age rating 新問題完成；若發 EU，完成 DSA trader status。
- [ ] Export compliance 保持 `ITSAppUsesNonExemptEncryption = NO` 並於 archive 驗證。
- [ ] 建立 model deprecation monitor，優先追蹤 Haiku 4.5 的 2026-10-15 earliest retirement boundary。

## 12. Primary official sources

### Apple

- [Program enrollment](https://developer.apple.com/help/account/membership/program-enrollment)
- [D-U-N-S Number](https://developer.apple.com/help/account/membership/D-U-N-S/)
- [Upcoming Requirements](https://developer.apple.com/news/upcoming-requirements/)
- [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- [Privacy manifest files](https://developer.apple.com/documentation/bundleresources/privacy-manifest-files)
- [Describing use of required reason API](https://developer.apple.com/documentation/bundleresources/describing-use-of-required-reason-api)
- [App privacy details](https://developer.apple.com/app-store/app-privacy-details/)
- [Manage app privacy](https://developer.apple.com/help/app-store-connect/manage-app-information/manage-app-privacy)
- [Screenshot specifications](https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications/)
- [TestFlight Overview](https://developer.apple.com/help/app-store-connect/test-a-beta-version/testflight-overview)
- [Platform version / App Review information](https://developer.apple.com/help/app-store-connect/reference/app-information/platform-version-information)
- [Encryption export regulations](https://developer.apple.com/documentation/security/complying-with-encryption-export-regulations)

### OpenAI

- [Whisper API model](https://developers.openai.com/api/docs/models/whisper-1)
- [GPT-4o API model](https://developers.openai.com/api/docs/models/gpt-4o)
- [API deprecations](https://developers.openai.com/api/docs/deprecations)
- [ChatGPT GPT-4o retirement notice（明確說當時 API 無變更）](https://openai.com/index/retiring-gpt-4o-and-older-models/)
- [API data controls and retention](https://platform.openai.com/docs/models/default-usage-policies-by-endpoint)
- [API key safety](https://help.openai.com/en/articles/5112595-best-practices-for-api-key)

### Anthropic

- [Models overview](https://platform.claude.com/docs/en/about-claude/models/overview)
- [Model deprecations](https://platform.claude.com/docs/en/about-claude/model-deprecations)
- [Model IDs and versioning](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions)
- [API and data retention](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention)
- [Authentication / key lifecycle](https://platform.claude.com/docs/en/manage-claude/authentication)

### Groq

- [Supported Models](https://console.groq.com/docs/models)
- [Model Deprecation](https://console.groq.com/docs/deprecations)
- [GPT-OSS 120B](https://console.groq.com/docs/model/openai/gpt-oss-120b)
- [Speech to Text](https://console.groq.com/docs/speech-to-text)
- [Your Data in GroqCloud](https://console.groq.com/docs/your-data)
