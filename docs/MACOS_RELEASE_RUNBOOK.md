# SGH Voice macOS release runbook

正式 macOS 產物分為「建置／公證」與「遠端發布」兩個獨立步驟。任何步驟失敗都不得把本機測試 DMG 標示為正式版。

## 1. 一次性設定

- 安裝與 Apple Developer Team 相符的 `Developer ID Application` 憑證。
- 使用 `xcrun notarytool store-credentials <profile>` 將 App Store Connect 公證憑證寫入 Keychain。
- 依 `requirements-dev.lock` 建立專案虛擬環境；建置腳本不會臨時安裝或升級工具。

憑證、密碼、App Store Connect key 與 Keychain profile 不得寫入 Git、CI log 或 release manifest。

## 2. 正式建置

正式建置前必須先完成審查、提交、建立 `vX.Y.Z` tag，並維持乾淨 worktree：

```bash
NOTARY_KEYCHAIN_PROFILE=SGH_NOTARY ./build.sh --version X.Y.Z --release --preflight
NOTARY_KEYCHAIN_PROFILE=SGH_NOTARY ./build.sh --version X.Y.Z --release
```

成功條件：Developer ID 簽章、hardened runtime、secure timestamp、Apple notarization、staple、Gatekeeper assessment 皆通過，且 `dist/` 內同時產生 DMG 與 `.sha256`。

## 3. GitHub draft release

先由人員在 GitHub 建立對應 tag 的 **draft release** 並審核版本說明。接著執行只讀 preflight：

```bash
scripts/publish_macos_release.sh --tag vX.Y.Z --artifact dist/SGH.Voice-X.Y.Z-apple-silicon.dmg
```

確認輸出後，才加上 `--execute` 上傳。腳本不會建立或發布 release，也不會覆蓋同名資產；如同名資產已存在，必須停止並調查，而不是使用 `--clobber`。

## 4. 發布後驗證

- 從 release 頁重新下載 DMG，核對公開 SHA-256。
- 在未安裝開發憑證的乾淨 macOS 使用者環境完成下載、掛載、拖入 Applications、首次啟動與麥克風／輔助使用權限 smoke test。
- GitHub Release 仍須由具權限的人員明確按下 Publish；該外部動作不由建置腳本代替。
