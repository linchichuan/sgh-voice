# Android 2.8.4 與 Alpha 招募分流

## 本輪範圍

- 側載更新：2.8.4 / versionCode 34；語音與幫我寫分離按鈕、SGH 字級、大波形與淺色漸層、忙碌狀態禁止切換。
- 公開網站：申請 Android 封閉 Alpha，不自動下載 APK、不宣稱寄信或已獲測試資格。macOS 下載保持獨立。
- 個人 APK 是公開版本化檔案，只提供更新用途；不連結於招募頁，且加入 noindex header。這不是認證或存取控制。
- `sgh-voice-alpha-applications` 僅接受 pending 申請；舊 Android download writes 拒絕，保留既有資料，不刪除任何名單。

## 已核對產物

- 檔名：`SGHVoice-Android-v2.8.4.apk`
- 大小：17,422,037 bytes
- SHA-256：`1e9cac87ffab10d31afe7f4a6e2d172f3296b4f68ea794da1efff616063281dd`
- 簽章：APK v2，唯一 signer，與先前側載版相同。請直接更新，勿先解除安裝；Play 安裝版應從 Play 更新。
- APK：`sgh-voice-web/downloads/SGHVoice-Android-v2.8.4.apk`
- AAB：`android/SGHVoice/app/build/outputs/bundle/release/app-release.aab`

## 驗證

- Android 256 unit tests，0 failures / errors；lintRelease、assembleRelease、bundleRelease 通過。
- `verify_mobile_rc.sh --artifact-only` 通過：版本、大小、hash、簽章；招募頁禁止 APK 直連。
- Python 538 tests 通過；新版本與招募流程的舊斷言已更新。
- Firestore 規則 Emulator 10 項與 JavaScript 招募流程 8 項通過；CI 的 `test:rules` 已納入兩者。覆蓋禁止讀取／更新、pending 狀態固定、欄位限制、舊 Android 下載封鎖、macOS 下載保留與重複點擊。
- 模擬器 synthetic preview 的幾何／按鈕／狀態檢查 PASS，但系統顯示 System UI ANR；不將此列為完整裝置或收音驗收。模擬器已關閉，沒有真實手機測試。
- 網站 390px 手機版與 1280px 桌面檢視；桌面 scrollWidth = clientWidth；招募頁 APK 連結數為 0。未將 synthetic 報名写入 production。

## Google Play 現況（2026-09-30 實際讀取）

- 內部測試仍是 2.7.5，不能算作封閉 Alpha 人數。
- 封閉 Alpha 草稿已由 2.7.5 更新並保存為 **2.8.4-alpha1 / 34 (2.8.4)**。舊 bundle 只從草稿移除，仍保留於 artifact library。
- Publishing overview 顯示 14 項未送審變更，包含 Alpha、台日地區、名單、商店文案、資料安全及內容申報。本輪未提交整批尚未重新核對的申報。
- reviewer access 目前寫「所有功能無需特殊存取」，但語音功能需要 BYOK；必須確認審核可操作方式與資料安全申報一致，不能以「已上傳」冒充發布完成。
- Console 通知有 9/27 收款帳戶問題；未更改付款資料、接受合約或推定已修復。
- 尚未啟用 Resend 自動邀請。Firebase CLI functions:list 失敗；未擅自啟用新服務或建立憑證。

## Rules 稽核（本輪新增招募集合）

```json
{"score":4,"summary":"Bounded create-only pending applications; private reads and all client updates denied. No automated eligibility grants.","findings":[{"check":"Storage Abuse","severity":"minor","issue":"Unauthenticated registration can still receive repeated spam documents; field limits do not provide rate limiting or email ownership verification.","recommendation":"Before scaling recruitment, add server-side abuse controls and verified-email invitation delivery. Do not treat submitted email as verified ownership."}]}
```

規則不得讓申請者自行標成 invited/approved，不得公開讀取 PII。既有其他集合未做跨專案重構；本輪不宣稱完成整個共享 Firebase 專案的安全稽核。

## 剩餘門檻

1. 核對 Play 資料安全、BYOK 審核存取與收款通知，再送審 Alpha。
2. Google 核准並可加入後，管理員安排名單與邀請；網站填表不等於本人 opt-in。
3. 至少 12 位真人連續加入封閉測試 14 天、實際測試與回饋，再申請 production access。
4. Resend verified sender、server-only credentials 與防重寄／濫用措施完成後，才可啟用自動郵件。

官方依據：[Play 個人帳號測試要求](https://support.google.com/googleplay/android-developer/answer/14151465?hl=en)、[設定測試](https://support.google.com/googleplay/android-developer/answer/9845334?hl=en)。不保證滿 12 人即可自動通過正式存取審查。
