# Android 日文十二鍵：依使用者三星截圖改善

日期：2026-10-09。沿用 `integration-20261009-7xje8Y` 工作區及上一輪未提交修改；只追加日文鍵盤重排，不改英文數字列、注音排列、語音動畫、詞庫、供應商或網站。

## 完成內容

截圖參考的「十二鍵」是中央 3 欄 × 4 列，左右另有功能鍵，不是整個鍵盤總共只有 12 個按鈕。本版依相同功能分區安排，保留 SGH 頂列、品牌色和既有整體高度。

| Before | After | Why |
| --- | --- | --- |
| 假名三欄＋右側功能列，底下另有第五列工具 | 中央十二鍵＋左右各四顆功能鍵，共四列 | 結構接近參考圖，假名鍵不再與底部工具排競爭高度 |
| 左右游標鍵都在右邊不同列 | 同一列左右兩側各一顆 | 手指與移動方向一致；仍移動輸入欄游標，不是選字游標 |
| 日文讀音大框占據候選橫向空間 | 小讀音列在固定候選區上方 | 候選字獲得完整寬度，輸入與清空不改按鍵座標 |
| 一般圓角、有框線按鍵 | 日文區使用 6dp 圓角、無描邊的白色假名鍵與淺灰功能鍵 | 降低視覺負擔，保留即時按壓回饋，不加位移動畫 |
| 多次連按超過想要的假名時需重選 | 左上 ↶ 回到同組上一個假名 | 是假名反向輪替，不會撤銷輸入欄其他文字 |
| 空白直接採用第一個漢字候選 | 十二鍵組字期間右側顯示「候補」，展開候選供本人選；左「変換」同樣開候選 | 不自行把假名換成第一個漢字；右下「確定」仍可直接輸入原假名 |

中央排列：

```text
あ    か    さ
た    な    は
ま    や    ら
小゛゜ わ    、。?!
```

- 左列：↶、←、変換、あA1。
- 右列：刪除、→、空白／候補、換行／確定。
- `あA1` 開 SGH 內部選單，保留片假名／平假名、ABC 羅馬字及 123 數字符號；不新增系統鍵盤切換按鈕。
- 假名維持 flick 與連按。標點輕按「、」，長按選「。」「！」「？」「…」；本輪未把標點改成 flick。
- 未強制改所有人的預設日文輸入樣式。若目前在日文羅馬字，按既有「12キー」進入此排列。
- 英文頂部 1–0、注音固定候選高度、先前語音／場景詞庫修改均保留。

## 修改檔案

相對 `android/SGHVoice/app/src/`：

- `main/java/com/shingihou/sghvoice/ime/manual/ManualKeyboardLayoutProvider.kt`：四列五欄（中央三欄＋雙側功能列）。
- `main/java/com/shingihou/sghvoice/ime/manual/ManualKeyboardModels.kt`：反向假名、候選、輸入選單 action。
- `main/java/com/shingihou/sghvoice/ime/japanese/JapaneseComposer.kt`：單一假名反向輪替。
- `main/java/com/shingihou/sghvoice/ime/KeyboardView.kt`：小讀音列、候選展開、選單、原地狀態標籤、日文鍵帽與文字適配。
- `main/java/com/shingihou/sghvoice/ime/VoiceInputIME.kt`：反向假名接線，其餘模式對日文專用 action 不做編輯。
- 新增 `main/res/values{,-ja,-en}/japanese_keypad_strings.xml`。
- `test/.../ime/manual/ManualKeyboardLayoutProviderTest.kt`、`test/.../ime/japanese/Kana12KeyFlickTest.kt`、新增 `test/.../ime/JapanesePhoneLayoutUiTest.kt`。
- `debug/README.md`：原生預覽與互動說明。

## 驗證

最終全量：**63 suites／518 tests，0 failures、0 errors、0 skipped**。`lintDebug`：0 errors／118 warnings（與上一輪同數量，不代表零警告）。`assembleDebug` 成功，Gradle `BUILD SUCCESSFUL in 1m 44s`，`git diff --check` 通過。

```sh
ANDROID_HOME=/Users/lin/Library/Android/sdk ./gradlew :app:testDebugUnitTest :app:lintDebug :app:assembleDebug --no-daemon --max-workers=2
```

最後 Debug APK SHA-256：`80f46206f83d55e01a5585bc03341542a5f3bb65ef26ae865a9d8f528e8c90aa`。版本仍為 2.8.9 / 39，未當作正式更新發布。

先執行新排列測試，確認原排列 `expected 4 / actual 5` 失敗，再實作。原有兩條要求第五列工具排的測試依新需求改為檢查雙側四鍵、中央三欄及所有功能入口；並未刪除功能驗證。

第一輪 targeted：7 suites／69 tests 全過，包括真實 Android View 的觸控手勢、游標 action、模式高度及新增選單操作。後續再補大字體鍵帽內緣與日文讀音獨立列檢查。

新增檢查包含 320／393dp 寬度、1／1.5 倍字體、90／100／125% 高度。逐一比對所有按鍵座標與尺寸、保留同一 View 物件不重建；檢查 44dp 觸控下限、功能文字不溢出、兩個假名候選也可手動展開、收合回到相同位置、單一輕按不意外呼叫系統 IME picker。

視覺驗收另發現 Android 指定背景會覆蓋文字 padding。加上「背景不得覆寫 6dp 內距」的真實 View 測試後先確認失敗，再把內距設定移至背景之後，最後全量重新通過。小螢幕大字體預覽已重新檢查。

## 預覽與產物

相對工作區：

- `android/SGHVoice/app/build/reports/keyboard-preview/japanese-rails-standard-idle.png`
- `android/SGHVoice/app/build/reports/keyboard-preview/japanese-rails-standard-typing.png`
- `android/SGHVoice/app/build/reports/keyboard-preview/japanese-rails-compact-large-font-typing.png`
- `android/SGHVoice/app/build/reports/keyboard-preview/japanese-before-rails.png`（上一輪保留圖）
- Debug APK：`android/SGHVoice/app/build/outputs/apk/debug/app-debug.apk`，非正式更新包。

均為 Robolectric 原生 View 本機渲染，不是生成式設計圖，也不是三星手機實測。使用合成假名，不使用截圖中的對話內容。

## 發布狀態與限制

尚未 commit、push、Firebase 部署或上傳 APK。依使用者要求先交預覽。沒有連接 Android 實機，最終手感仍需手機確認；這次沒有新增日文詞庫或聲稱達到三星的日文預測能力。候選維持固定單列、可橫捲並手動展開，不以自動增加候選列推動鍵盤。
