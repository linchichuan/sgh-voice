# voice.shingihou.com — Review & Rebuild Plan

**Reviewer:** Claude (Opus 4.7)
**Date:** 2026-05-25
**Scope:** index.html / i18n.js / style.css / main.js / privacy.html / firestore.rules

---

## TL;DR

頁面**結構完整、視覺基礎扎實**，藍紫橘的品牌色 + DM Sans + Noto CJK 字體層級合理。但**有 1 個會直接讓功能失敗的 bug（NPP 表單寫不進 Firestore）**、**SEO 基礎建設大量缺漏**（favicon/sitemap/robots/schema.org/terms.html）、**Pro 方案的商業可行性需要重新審視**，以及一個語言策略不一致（CLAUDE.md 說 5 語但 i18n 只有 3 語）。

新生的 6 張圖剛好填補了視覺空白，rebuild 時把它們放進對應位置即可。

---

## 🔴 P0 — Critical（會壞 / 直接影響轉換）

### 1. NPP 表單寫進 Firestore 會被 deny（Beta 申請功能形同虛設）

`index.html:490` 寫進 collection `npp_testers`，但 `firestore.rules` 沒有對應規則 → 落到最後一條 `match /{document=**} { allow read, write: if false; }` → **所有 NPP 申請都會 silently 失敗**。

頁面雖然會跳成功訊息（catch block 沒分辨 error type），但 Firestore console 看不到任何資料。

**修法**：在 `firestore.rules` 加：

```javascript
match /npp_testers/{docId} {
  allow create: if request.resource.data.keys().hasAll(['name', 'email', 'device', 'timestamp'])
                && request.resource.data.email is string
                && request.resource.data.email.size() < 256
                && request.resource.data.email.matches('.+@.+\\..+');
  allow read, update, delete: if false;
}
```
重新 deploy：`firebase deploy --only firestore:rules --project sgh-meishi`

順便 `sgh-voice-beta-requests` 規則裡寫了要 `message` 欄位但沒人在用這條 collection — 看要不要刪。

### 2. `terms.html` 不存在但 footer / nav 有連結 → 點下去 404

`index.html:534`：`<a href="terms.html">利用規約</a>`，檔案不存在。privacy.html 也沒寫好對應的「利用規約」連結。

**修法**：把 privacy.html 複製一份改寫成 terms.html，或暫時把這個 link 移除 / 改成 `href="#"` 並加 `aria-disabled="true"`。

### 3. 語言策略內部不一致

| 來源 | 支援語言 |
|---|---|
| CLAUDE.md 描述 | 5 語：日 / 繁中 / 英 / 越 / 泰 |
| 實際 `i18n.js` | 3 語：ja / zh / en |
| 語言切換 dropdown | 3 語：ja / zh / en |
| `hreflang` meta tag | 3 語：ja / zh-Hant / en |
| OG `locale:alternate` | 2 語：zh_TW + en_US（少日文 alternate） |

**決定要哪一個再 align 全部**。如果決定就走 3 語：把 CLAUDE.md 改掉、加上 OG ja_JP alternate。如果要補上越南/泰文 → 把 i18n.js、dropdown、hreflang 一次補齊（量大）。

---

## 🟠 P1 — High（SEO / 商業面強衝擊）

### 4. SEO 基礎建設大缺
缺：
- `favicon.ico` / `apple-touch-icon.png`（**沒任何 icon**）
- `robots.txt`
- `sitemap.xml`
- `schema.org` 結構化資料（SoftwareApplication / Organization / FAQ）
- Twitter Card meta（`twitter:card`、`twitter:image`）
- `og:image`（OG image 也沒設定，剛剛生成的 og-share.png 還沒接上）
- `llms.txt`（給 LLM crawler 用，2025+ 後新興最佳實務）

→ 直接影響 Google / Bing / Perplexity / ChatGPT 抓取品質。

### 5. Pro 方案的「API 料金込み・使い放題」 ¥980/月 商業風險

`index.html:327-328`：宣告 Pro 用戶不用 API key、由 server 提供，價格 ¥980。

如果 user 跑滿一個月（Whisper + Claude），單一重度用戶的 API cost 可能就遠超 ¥980。**這條商業模型在規模化時會虧錢**。

選項：
- **方案 A**：改為「相當的 token 額度（例：100 萬 tokens / 月）」明確 cap
- **方案 B**：去掉「使い放題」字樣，改為「合理使用上限」
- **方案 C**：先別上 Pro，等實際使用數據再開

### 6. 主要轉換動作（下載）的摩擦點

目前 macOS 下載按鈕直接打 GitHub Releases `.dmg`，但：
- 沒有寫安裝後要做什麼（**第一次開要在系統設定授權麥克風 + 輔助使用 + 輸入監控 3 個**，CLAUDE.md 有寫但首頁沒寫）
- iOS / Android 都只連到 GitHub release page，**沒有 App Store / Google Play badge**（如果還沒上架，至少寫「審查中」+ 預計時間 + 改 Beta 申請按鈕）
- 無 SHA-256 checksum / GPG signature 連結（macOS 用戶可能會問「這安全嗎？」）

### 7. 性能（Core Web Vitals）

- **目前頁面 LCP 元素是 hero `<h1>` 文字** — 剛剛要加的 hero-main.png 變成 LCP 後**沒有 preload + 1.5MB 未壓縮**會直接拖垮 LCP
- 字體載入沒 `font-display: swap`（Google Fonts 預設有，但需要驗證）
- `i18n.js`（25KB）在 `<body>` 末尾載 — 沒事，但**翻譯生效會閃一下原文**
- 6 張新圖總共 8.5MB，**沒 WebP / AVIF 壓縮版本** — 對手機用戶過重
- 沒 `<link rel="preload" as="image" href="assets/generated/hero-main.webp">`

### 8. Hero subtitle 一整大坨

```
SGH Voice は、あなたの意図を汲み取る専属速記者のような存在です。単なる文字起こしではなく、無駄な言葉を削ぎ落とし、誤字を直し、完璧に整えます。中・日・英対応、データは 100% あなたの手元に。
```

97 字無斷句，視覺密度太高、可讀性低。建議拆成 2 行 + 用 `<br>`：

```
あなたの意図を汲み取る、AI 専属速記者。
中・日・英対応 · データは 100% あなたの手元に。
```

或拆成「主訴 + 3 個 benefit chip」（無駄削除 / 誤字修正 / 完璧整形）。

---

## 🟡 P2 — Medium（體驗 / 維護性）

### 9. 無障礙（A11y）

- `<button class="mobile-toggle" aria-label="Toggle menu">` 有 aria-label ✅ 但**沒有 `aria-expanded`** 反映展開狀態
- 語言 dropdown 沒 `role="menu"` / 鍵盤導覽（Esc 關閉、上下鍵切換）
- Hero `<h1>` 用了 `<br>` 強制斷行 — 螢幕閱讀器會讀成兩段，OK
- 所有 SVG 都沒 `<title>` 標籤（feature icon、step icon）
- 對比度：`--color-text-muted: #94a3b8` 在 `#f8faff` 背景上 contrast ratio ≈ **3.0 (WCAG AA fail for body text)**

### 10. main.js 的 IntersectionObserver 把所有 card opacity 設 0

```js
document.querySelectorAll(".feature-card, .step-card, .pricing-card, .download-card, .contact-card").forEach(el => {
    el.style.opacity = "0";  // ← 如果 JS 失敗，內容永遠看不到
```

**若 JS 失效或被 blocker 擋掉，整頁看起來是空的**。改成 CSS class + `prefers-reduced-motion` 媒體查詢 + JS 漸進增強會更穩。

### 11. Subscribe / NPP 表單沒做 rate limiting

純前端表單 → Firestore，沒 reCAPTCHA / honeypot field / cooldown，bot 可以無限灌資料。已知 Firestore rules 有檔 email 字串長度，但沒擋灌頻率。

修法（最簡單）：加 honeypot field（hidden `<input name="website">` 有值就 silently reject）。

### 12. CLAUDE.md 提到的功能在頁面上沒呈現

- iOS 細節（v1.0 已上線 per CLAUDE.md，但頁面說「リリースページ」很弱）
- Hybrid 模式有提，但**沒講 cost saving 的量化好處**
- Smart Replace、Quick-Rewrite hotkey、Continuous mode — 這些 v2.1 新功能 i18n 完全沒提

### 13. Firebase API key 直接寫在 HTML

`index.html:555` 寫死 Firebase config — 這對 Firebase web SDK 是「設計上的公開值」（靠 Firestore rules 鎖權限），技術上 OK。但**沒 domain restriction**：建議到 GCP Console > APIs & Services > Credentials > 限制這把 key 只能從 `voice.shingihou.com` 用。

---

## 🟢 P3 — Low（nit / 風格）

- 沒 `<meta name="author">` / `<meta name="generator">`
- Footer copyright 寫死 `© 2026`，跨年要手動改
- 沒 `noscript` fallback
- Logo SVG 是通用麥克風 icon，無品牌獨特性
- `nav.beta` 用 `Beta申請` 中間沒空格（日文 typography 慣例會 narrow space）
- 沒 dark mode 切換（很多開發者用戶會期待）

---

## 📋 Rebuild Plan（執行順序）

### Phase A — Bug Fix（必做、~1 小時）
1. **改 `firestore.rules` 加 `npp_testers` 規則 + deploy** ← 不做這條 Beta 申請功能全壞
2. **建 `terms.html`**（內容暫時 copy privacy.html 改寫）或拿掉 footer 連結
3. 確定語言策略（3 語 vs 5 語）並 align 所有來源

### Phase B — 接圖 + SEO 基礎（~2 小時）

4. **加 6 張新圖到對應位置**：
   - `hero-main.png` → `#hero` 用做 `<picture>` background（或 hero 右側 visual）
   - `feature-trilingual.png` → `features.f1` 卡片 background 或 thumbnail
   - `feature-medical.png` → `features.f7` 醫療特化模式卡片
   - `feature-privacy.png` → 新加一張卡片「データは 100% あなたの手元に」（從 hero subtitle 提取）
   - `og-share.png` → `<meta property="og:image">`
   - `download-devices.png` → `#download` section 上方主視覺
5. **壓縮所有圖**到 WebP：`cwebp -q 80 hero-main.png -o hero-main.webp`（裝 `brew install webp`），目標 < 200KB each
6. **加 `<link rel="preload" as="image">`** for hero LCP
7. **建 favicon** 三件套（favicon.ico / apple-touch-icon.png / favicon-192.png）
8. **建 `robots.txt`** + **`sitemap.xml`**
9. **加 schema.org `SoftwareApplication`** JSON-LD + `Organization` JSON-LD
10. **加 Twitter Card meta**：`twitter:card=summary_large_image` + `twitter:image=https://voice.shingihou.com/assets/generated/og-share.webp`

### Phase C — 文案 + UX 調整（~2 小時）

11. **重寫 hero subtitle**（拆短 + 加 benefit chips）
12. **重寫 Pro 方案文案**（決定 cap 還是去掉「使い放題」）
13. **download section** 加安裝步驟（macOS 3 個權限 + 截圖）
14. **補 iOS / Android 真實狀態**（如果還在審查就明確寫「審査中・〇月リリース予定」）
15. **加 「データは 100% 手元に」單獨 card**（搭配 feature-privacy.png）

### Phase D — A11y + 性能（~1 小時）

16. main.js IntersectionObserver 改成 CSS class + `prefers-reduced-motion` 防禦
17. 修對比度（`--color-text-muted` 改 `#64748b`）
18. 加 `<title>` 給所有 SVG / `aria-expanded` 給 mobile toggle
19. 加 honeypot field 給兩個表單
20. Firebase API key 加 domain restriction（GCP Console 手動）

### Phase E — 部署 + 驗證

21. `firebase deploy --only hosting:sgh-voice --project sgh-meishi`
22. 跑 Lighthouse Mobile（目標 Performance ≥ 90 / A11y ≥ 95 / SEO ≥ 100）
23. PageSpeed Insights 手動 check
24. Twitter card validator + Facebook OG debugger 各 ping 一次
25. Google Search Console 重新 submit sitemap

---

## 📦 圖片映射表（rebuild 時用）

| 檔案 | 用途 | 放在哪個 section / line |
|---|---|---|
| `hero-main.png` | Hero 主視覺 | `#hero` 取代 `.hero-bg` 的三個 orb / 或放右側 |
| `feature-trilingual.png` | 3言語混合認識 feature card | `features.f1`（line 142） |
| `feature-medical.png` | 医療特化モード feature card | `features.f7`（line 155） |
| `feature-privacy.png` | 隱私 / 本地處理 feature card | 新建一張 feature card（或加在 hero 右側） |
| `og-share.png` | 社群分享縮圖 | `<meta property="og:image">` |
| `download-devices.png` | Download section 主視覺 | `#download` section header 上方 |

---

## ⚠️ Out of Scope（這次不處理）

- **i18n 補越南文 / 泰文**（量大，先決定要不要再說）
- **terms.html 完整法務內容**（法律應該找律師審 / 拿 shingihou.com 主站既有的）
- **Logo 重新設計**（要動就要動到品牌 system，不是只有 voice.shingihou.com 的事）
- **Dark mode**（先 ship 再說）
- **A/B test 框架**（沒 traffic 不用測）

---

**下一步**：要我**直接開始 Phase A**（bug fix）嗎？還是你想先看完報告自己決定 phase 順序？
