# Android 英文與日文離線字典擴充

本文件記錄 2026-10-09 的靜態字典擴充。所有字典查詢都在裝置內完成，執行時不下載資料，也不傳送輸入內容。這些是明確選取的候選詞，不會自動改寫使用者的輸入。

## 收錄規模

| 資料 | 擴充前 | 目前資產 | 未壓縮大小 |
|---|---:|---:|---:|
| 英文 AOSP 詞頻詞庫 | 僅 558 個本地精選詞 | 45,371 個語料詞，另保留原精選詞 | 566,462 bytes |
| 日文 JMdict | 19,631 讀音／22,819 候選 | 26,818 讀音／32,005 候選 | 891,233 bytes |

兩份資料共 1,457,695 bytes；相較原日文資料加本地英文 seed，新增 TSV 約 820 KB。實際 APK 增幅會受 ZIP 壓縮與程式碼影響，以建置產物量測為準。

## 英文來源與篩選

- 官方來源：[AOSP LatinIME](https://android.googlesource.com/platform/packages/inputmethods/LatinIME/)。
- 固定 commit：`127336e9f29d69607eab55982324b210279ae8c5`。
- 原始資料：該 commit 的 `dictionaries/en_wordlist.combined.gz`；gzip SHA-256：`07682388185c285d307e341d1733331af8699f735b4137e9f22571017fab69d2`。
- 上游資料本身 header 為 `version=54,date=1414726273`（2014 年），不是 2026 年的新詞語料；固定 repo commit 不代表詞頻資料更新日期。
- 上游 `Android.bp` 指定 Apache-2.0，完整 `NOTICE`（包括 Lexiteria 聲明）隨 APK 保存於 `assets/english/AOSP_NOTICE.txt`。
- 只收未標 flags、長度 2–32 的小寫英文字母單詞及內部 apostrophe 縮寫，保留頻率至少 60 的詞；上限 50,000。本次符合條件 45,371 詞，未為了填滿上限加入更多罕見詞。
- 原有 `LocalEnglishCandidateProvider` 精選詞維持順序並優先於語料詞；資產無法解析時仍回退到精選詞。
- 這是通用前綴補全資料，不是完整拼字更正、專名或最新技術術語資料庫。

## 日文來源與篩選

- 官方來源：[JMdict_b](https://www.edrdg.org/pub/Nihongo/JMdict_b.gz)，資料日期 `2026-10-09`。
- 原始 gzip SHA-256：`04cc54f92f7d82078c788e8957d44783bd565df377e7de3571bdac6fad7d2140`。
- 授權：[EDRDG CC BY-SA 4.0](https://www.edrdg.org/edrdg/licence.html)。資料衍生物保持同授權，程式碼授權獨立；完整授權與 attribution 已封裝，App 設定保有 JMdict 來源說明。
- 使用 `JMdict_b`，不加入獨立 JMnedict 人名庫。
- 收錄第一級與第二級 `ichi/news/spec/gai` 常用標記，以及 `nf01`–`nf48` 新聞詞頻分組。
- 排除 search-only、rare、obsolete 的字形／讀音，以及只有古語、廢語或量詞用途的 entry。正常用途的漢字新字體保留，例如 `会議／画像／来週／電車`，不經中文繁簡轉換。
- 完整詞典形式不等同日文句子轉換引擎；這次沒有導入形態分析、動詞活用或句子模型。

## 載入與查詢

`AndroidEnglishCandidateProvider(context)` 提供 `EnglishCandidateProvider` 與 `warmUp()`；IME 應在背景 warm-up，並維持密碼／禁止建議欄位的候選抑制。

日文維持既有 lazy Map 載入，英文用依字母排序的精簡候選表。前綴查詢先二分定位，再遍歷該前綴的完整匹配範圍，以固定大小的 top-K heap 保留候選；只排序最後 K 個結果。移除了日文「只看字母序最前 64 讀音／256 候選」的截斷，以免後段高頻詞永遠查不到。

## 重建與驗證

先取得一次官方原始檔並記錄 hash，生成時使用 `--input` 重用本機檔。原始大型資料不提交到 repo；APK 僅帶生成資產。來源 URL、commit／資料日期、SHA-256、篩選參數、輸出大小／hash 保存在各資料夾的 `snapshot.json`。

```sh
python3 android/SGHVoice/tools/generate_english_lexicon.py \
  --input /path/to/aosp-en-wordlist.gz \
  --notice-file /path/to/AOSP_NOTICE.txt

python3 android/SGHVoice/tools/generate_japanese_lexicon.py \
  --input /path/to/JMdict_b.gz \
  --license-file android/SGHVoice/app/src/main/assets/japanese/CC-BY-SA-4.0.txt

python3 -m unittest discover -s android/SGHVoice/tools/tests
```

英文產生器也接受 Gitiles `?format=TEXT` 的 base64 下載格式。更新日文時應在 APK 發布流程更新官方 snapshot 並重跑測試，保持 EDRDG 要求的更新程序。

Kotlin 驗證包含 `CompactEnglishLexiconTest`、`CompactJapaneseLexiconTest` 與 `OfflineLexiconPerformanceTest`。最後一項記錄載入時間、GC 後保留 heap 增量，以及 `a/s/th/あ/か/し` 各 100 次查詢的 p50／p95／max；數值只代表桌面 JVM，不是 Android 實機驗收。

### 2026-10-09 桌面 JVM 實測

主 agent 統一執行的 `testDebugUnitTest` 已通過上述 Kotlin 字典測試；最終效能測試 XML 記錄 `tests=1, failures=0, errors=0`，時間為 `2026-10-09T03:48:51.012Z`。全量 Android 475 項、Python generator 7 項測試通過。

| 資料 | 載入時間 | GC 後保留 heap 增量 |
|---|---:|---:|
| 英文 45,371 詞 | 90.75 ms | 3,766,752 bytes |
| 日文 32,005 候選 | 155.99 ms | 5,881,392 bytes |

每個前綴先 warm-up 20 次，再量測 100 次，要求最多 24 個候選：

| 前綴 | p50 | p95 | 最大值 |
|---|---:|---:|---:|
| `a` | 0.092 ms | 0.631 ms | 1.179 ms |
| `s` | 0.147 ms | 0.474 ms | 0.803 ms |
| `th` | 0.034 ms | 0.136 ms | 0.644 ms |
| `あ` | 0.290 ms | 0.736 ms | 1.522 ms |
| `か` | 0.470 ms | 0.948 ms | 1.298 ms |
| `し` | 0.442 ms | 0.936 ms | 1.524 ms |

來源：`app/build/test-results/testDebugUnitTest/TEST-com.shingihou.sghvoice.ime.manual.OfflineLexiconPerformanceTest.xml` 的 `system-out`。這是桌面測試 JVM 的單次觀察，包含測試執行器／JIT／GC 波動；heap 為 GC 前後估計差值，並非 Android 裝置的 PSS。尚需以實體 Android 裝置檢查首次切換鍵盤、連續輸入延遲及記憶體壓力，不將此數字作為手機效能承諾。
