# Android Alpha 招募與邀請自動化：啟用前檢查

查證日期：2026-09-26。狀態：**付款資料與售價已設定；尚未實作／啟用自動邀請，仍需新版 Alpha、測試資格設定與 Resend 存取**。

## 已確認的方向

使用者選擇「封閉測試 Alpha：公開招募，供正式上架前測試」。

使用者後續確認收費方式：**保留付費 App，下載購買價格 US$10.00，一次性購買，不是月費或年費訂閱**。2026-09-26 使用者完成付款資料後，已在 Play 儲存售價。Google 的批次換算將美國設成 US$9.99，已透過該國價格儲存格精確覆寫為 **US$10.00**，並確認「変更を保存しました」。未改成免費或建立訂閱。

已確認 Console 儲存價格：日本 **JPY 1,580**、台灣 **TWD 330.00**。批次價格表設定不代表擴大 Alpha 發布地區。現有 BYOK 模式的外部 AI 使用費，不能宣稱包含在 App 一次性購買價格內。

目標流程是：網站申請 → 儲存申請 → Resend 寄參加說明 → 取得測試資格 → 本人在 Google Play 加入 → 經 Play 安裝／更新。不是填表後直接下載 APK，也不是寄出信件就算加入測試。

## 即時查證結果

| 範圍 | 2026-09-26 實際狀態 | 影響 |
| --- | --- | --- |
| Play Alpha | 非啟用；草稿 `2.7.5-alpha1`，App Bundle `25 (2.7.5)` | 不能把網站最新版本當作已在 Play 發布 |
| Alpha 地區 | 台灣、日本 | 不宣稱全球可參加 |
| Alpha 資格 | 選擇手動信箱名單，尚未使用 Google Groups | 寄信本身不會新增資格 |
| Alpha opt-in | Console 顯示網址但複製按鈕停用，要求先發布 App | 不把網址當作已啟用的邀請 |
| Alpha 人數 | 0 人 opt-in | 不把網站登記或內部測試人數計入 |
| 發布檢查 | 1 個錯誤：尚未完成 Dashboard 設定 | 不是按下送審即可完成 |
| Dashboard | 早先為 11/13；後續付款資料與價格已完成，總進度未重查 | 不將售價保存視為完成送審／發布 |
| App pricing | 有料；US$10.00、JPY 1,580、TWD 330.00 已保存 | 一次性下載購買，尚未發布新版 Alpha |
| Payments | 使用者已建立付款資料，價格功能解鎖 | Console 仍顯示需新增收款方式；未代填銀行資料或接受 15% 方案條款 |
| Google Groups | Play 管理帳號的群組清單為 0 | 需要另設測試群組，不能套用其他帳號的無關群組 |
| Firebase | `sgh-meishi`、Hosting site `sgh-voice`；Billing API 回傳 `billingEnabled=true` | 不需要另升級計費方案 |
| Functions | GET 列表回傳 403：Cloud Functions API 未使用或已停用 | 目前尚無可用的邀請後端證據，未啟用 API |
| Firestore | `(default)`，STANDARD，`asia-northeast2` | 既有網站資料庫；尚未新增集合或更改 Rules |
| Resend | 開啟 domains 後導向公開首頁；已停在登入頁 | 無法驗證寄件網域、權限、金鑰或執行 REST smoke |
| 既有網站 | 表單直接寫 `sgh-voice-downloads`，隨後下載 APK／DMG | 不是 Alpha 招募流程；本輪尚未更改線上網站 |

Play Console：

- [Alpha](https://play.google.com/console/u/1/developers/8840072763780160930/app/4973929964610113084/tracks/4700540007704993475)
- [草稿檢查](https://play.google.com/console/u/1/developers/8840072763780160930/app/4973929964610113084/tracks/4700540007704993475/releases/1/review)
- [App pricing](https://play.google.com/console/u/1/developers/8840072763780160930/app/4973929964610113084/paid-app)

## 必須先完成的決策／存取

1. **付費設定**：US$10.00 一次性購買已保存；不再詢問免費／付費選擇。收款銀行資料與任何新增合約仍由使用者完成。Google 說明付費 App 的封閉測試者一般仍需購買；若另允許免費測試，需明確決定合法的 promo code 等方式，不以把整個 App 改免費處理，也不宣稱邀請信包含免費授權。
2. **Resend 登入與安全設定**：由使用者登入，確認現有 verified sender。金鑰僅放 server secret，不貼對話、前端、Git 或一般 log。沒有合法可用的 key 前，不能宣稱寄信已驗證。
3. **資格群組**：建議獨立 Alpha Google Group，由參加者自行加入，再 opt-in；成員資料不公開、一般成員不能群發。群組連結可轉寄，因此只能保證「先加入計畫」，不能保證每個成員都先填網站表單。若要求後者，需另定人工審核或具管理授權的 Workspace 自動加成員流程。
4. **Play 版本**：在送審前重新驗證並上傳預定公開招募的版本；不要直接送出舊 `2.7.5-alpha1` 草稿當成新版。付費、條款、資料安全與審查聲明需保持真實。

## Gate 0：最小實作契約（設計，非已部署）

| 項目 | 契約 |
| --- | --- |
| Provider role | Resend 作交易式邀請郵件 primary 候選；目前 not approved for production，缺帳號與 synthetic REST 驗證 |
| 語言與內容 | 繁中、日文、英文固定範本；無 AI 生成，不處理語音或逐字稿 |
| 前端資料 | 暱稱、手機 Play Store 使用的 Google 帳號信箱、語言、Android 參加意願、邀請用途同意 |
| 個資範圍 | 非 Gmail 可接受，但必須對應 Google 帳號；舊下載名單不自動移作招募寄信 |
| Runtime | 候選：獨立 Functions codebase + Hosting 同源路由；保留 macOS 既有路徑 |
| 資料狀態 | `registered → queued → provider_accepted`；若實作驗簽 webhook，才增加 `delivered / bounced / complained`；不自動寫 `play_enrolled` |
| 申請保存 | server-only、嚴格欄位、不可由公眾讀取；原始信箱不作公開文件 ID |
| 寄信限制 | 固定寄件者、固定群組及 Play 網址；不可由客戶端指定 sender、recipient list、HTML 或 URL |
| 逾時與重試 | 自訂每次 10 秒逾時、最多 2 次嘗試；使用同一 persisted idempotency key 與相同 payload；不在不確定時換 key 重寄 |
| 去重 | 自有持久化申請／outbox 去重；不可只依靠 Resend 24 小時 idempotency 視窗 |
| 成本與濫用 | 啟用前測試每信箱／來源／全站上限、重複與併發、供應商額度限制；數字待實際帳號 quota 確認，預設不開寄信 |
| Fallback / kill switch | 停止新邀請、保留已接受的申請與人工處理狀態；不能 fallback 寄 APK 或繞過 Play 資格 |
| 可攜性 | provider-neutral mail adapter；UI 和 domain service 不依賴 Resend SDK 型別 |
| Log | 只記 request ID、錯誤分類、HTTP 狀態、耗時；不記 key、姓名、email 或完整 request/response |
| 治理未完成 | 確認寄件 domain/region、retention/deletion、DPA/subprocessors、隱私告知、申請資料保留期及責任人後，才能處理真實招募名單 |

## 驗證及部署順序

1. 登入後以 Resend 官方 `delivered+<label>@resend.dev` 做 synthetic REST smoke；測 auth、成功、非法輸入、mock timeout／429，保存去識別結果。
2. 做 server-only adapter、fake adapter、申請服務及持久化去重測試；功能預設關閉。
3. 完成群組資格、Play 前置設定、新版審查／發布及真實 opt-in 頁驗證。
4. 改網站三語導線與同意文案；不得顯示「填表＝已加入」或「免費下載」。Android 的免費 Offer metadata 與公開 APK 旁路需在正式切換招募流程時一併處理；macOS 下載分開處理，不把 Android 售價套到 macOS。
5. 檢查舊 APK CTA、JSON-LD、release manifest、Hosting URL 等旁路；保留本機產物，不把隱藏 URL 宣稱為存取控制。此項需與個人側載更新路徑協調，不破壞已安裝版本資料。
6. 審核 CI / Functions / Hosting 各自發布權限；不可對共享 `sgh-meishi` 做未限定範圍的 deploy。
7. targeted tests、Rules emulator、桌機／手機及三語 smoke、synthetic E2E 完成後，再 commit / push / scoped deploy。
8. 收件服務接受、信箱實際收到、群組加入、Play opt-in、安裝成功分開紀錄。沒有證據的步驟不得寫完成。

## 官方文件快照

以下於 2026-09-26 查證；不是對帳號 entitlement 或審查結果的保證。

- [Play 測試設定](https://support.google.com/googleplay/android-developer/answer/9845334?hl=en)：資格、Groups、本人 opt-in、發布前連結限制、internal 與 closed 的互斥。
- [Play 收費設定](https://support.google.com/googleplay/android-developer/answer/6334373?hl=en)：免費提供後不能改回付費下載。
- [Play 新個人帳號測試要求](https://support.google.com/googleplay/android-developer/answer/14151465?hl=en)：12 人、連續 14 天與正式存取申請；此帳號 Dashboard 也顯示相同條件。
- [Android Publisher testers](https://developers.google.com/android-publisher/api-ref/rest/v3/edits.testers)：API 提供 `googleGroups[]`，不是 Console 個人信箱名單的任意新增 API。
- [Resend Send Email](https://resend.com/docs/api-reference/emails/send-email)、[synthetic addresses](https://resend.com/docs/dashboard/emails/send-test-emails)、[idempotency](https://resend.com/docs/dashboard/emails/idempotency-keys)、[webhook verification](https://resend.com/docs/webhooks/verify-webhooks-requests)。
- [Firebase Hosting + Functions](https://firebase.google.com/docs/hosting/functions)、[server secret configuration](https://firebase.google.com/docs/functions/config-env?gen=2nd)。

## 本輪操作界線

早先僅做唯讀查證；使用者自行完成付款資料後，依明確授權保存上述一次性 App 售價。未代建付款帳戶、未填銀行資料、未接受新合約、未建立群組、未送審、未寄信、未啟用 Functions API。邀請流程仍未改網站或資料庫。保留原有 `build.sh` 和舊 APK 的未提交變更。
