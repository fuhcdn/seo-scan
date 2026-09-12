# CEO3 技術方案：由「模板化」變「每網站獨特深度審計」

目標：攞任何網站都唔再出一式一樣嘅分數同建議。每個網站按自身特性（技術棧 / 結構 / 內容類型 / 競爭玩法）出唔同深度嘅分析、唔同權重嘅分數、引用佢實際內容嘅可執行修復。同時每單成本低過 US$3，維持 ~90% 毛利，英文 master + 5 語言 i18n。

---

## 核心診斷（點解而家「攞乜都一樣」）

模板化咁係源自一個致命設計決定：**評分器對所有網站用同一組固定權重，同一份檢查清單，同一套建議文字。** 好似對一間餐廳同一部手機用同一張健康檢查表——表面 check 得完，深度完全唔兔。要拆，就必須喺三個位置落手：入門分類（site fingerprint）、權重計算（adaptive weights）、建議生成（evidence-based fixes）。

---

## 第一層：Site Fingerprint（網站指紋）—— 一切個性化嘅根

爬取之前，先用一個 5 秒嘅「探測 phase」建立網站數碼指紋，之後所有行為都根據呢份指紋改動。

採集（全部 cheap、程式化，唔使 LLM）：
- 攞 robots.txt、sitemap.xml、homepage header、X-Robots-Tag、canonical、generator meta、html lang
- 由 generator/CMS 特徵偵測技術棧（WordPress/Shopify/Wix/headless/static/custom）
- 由 sitemap/page 數估算規模；由 URL pattern 偵測結構（/product/、/blog/、/category/、/services/）

輸出一個 JSON fingerprint，沿 4 條軸分類：
1. 內容類型：transactional（電商）/ content-marketing / lead-gen（服務/本地）/ SaaS定价頁 / directory-marketplace / news-blog / portfolio
2. 技術棧：7 類主流 CMS + custom/headless
3. 規模：小型（<50 頁）/ 中型（50–5000）/ 大型（>5000）
4. 競爭玩法：品牌 vs 非品牌、電商高競爭類目、本地意圖（location keywords）

呢個 fingerprint 就係「個性化」嘅開掣：**唔同 fingerprint 行唔同檢查、唔同權重、唔同深度、唔同建議優先序。** 驗收標準：同一條測試樣本（SaaS vs 電商 vs blog）一定要產生唔同嘅 fingerprint，先算拆到模板化。

---

## 第二層：兩段式評分器（唔再係一條死權重公式）

分數分兩個 stage，第二 stage 先係個性化嘅真正來源。

Stage 1 —— 通用底層分（所有網站同一把尺，對齊 Google/Ahrefs 權威做法）：
- tech fundamentals：crawlability、indexability、meta（title/description）、schema、performance（Core Web Vitals 訊號）、mobile、HTTPS、redirects、Sitemap/robots、canonical、結構化資料
- 呢 part 係「權威標準盤點」，確保唔會因為個性化而走樣。

Stage 2 —— 個性化深度層（核心改動）：
- 唔再係「一個固定平均分」。總分 = 權重向量 × 維度分數，而**權重向量係逐站由 fingerprint 計出嚟**。
- 例：電商 → category 頁深度 / product schema / faceted-URL param bloat / pagination 權重拉高；本地服務 → NAP 一致、geo schema、maps、reviews 權重拉高；內容型 → 內容深度、E-E-A-T、internal link 到 money pages、topical coverage 權重拉高。
- 結果：兩個網站同拎 92 分，**含義唔同、報告解釋唔同**——都會明講「邊一項維度係你呢類網站嘅擔當」，唔再係打個總分俾人睇。

呢個「同分唔同意義」先係破除模板化嘅關鍵：評分器唔止俾分，仲要識得講「你點解拎呢個分」。

---

## 第三層：深度指標 —— 唔淨係表面數

評分員唔淨係砌 header，要真係爬入去汁內容做分析：

內容深度（每頁程式化汁料，零 LLM 成本）：
- 字數、h1–h6 章節樹結構、列表/表格/定義性內容是否存在、主關鍵字有冇喺 title/H1/頭 100 字、主題詞 TF-IDF 密度

頁面質素（逐頁 flag，全部程式化）：
- title 長度 / title 重複、H1 缺失或重複、薄內容偵測（<300 字頁面）、重複/千篇一律 boilerplate 比例、image alt 覆蓋率、schema 有效性和 or 錯誤、internal link 數目、孤兒頁（無 internal link 入嚟）

爬法本身要 adaptive：
- BFS 深度受限、honor robots、同 content 去重、param-aware（唔好爬死 faceted URL）
- 免費版：5–10 頁（= 10–20% 內容，Yan 要求）；付費版：100–500 頁，規模越大越深

競爭對比（加「vs 競爭對手」深度，唔靠貴 SERP API）：
- 揀網站 top 5–15 個 money keywords 成一 cluster；對 cluster 嘅 aggregate 競爭內容檔案做對比：標題 CTR pattern、內容厚度中位數、誰排住、serve-intent 吻合度
- 用免費/平價 SERP 或 clusterML 手法推斷，唔需要逐 keyword 買 API

---

## 第四層：個性化改進方法（fix list 引用實際內容，唔係萬金油）

改進引擎接收三份 input，缺一就唔完整：
1. per-page findings，**每條附實際 URL + 問題證據**（邊幾頁 title 重複、邊頁得 120 字、邊個 schema 錯）
2. site fingerprint
3. competitor benchmark

輸出規則：**建議要引用該網站真實內容先算係「個人化」**。唔可以再出「建議增加內容豐富度」呢種廢話，要出：
- 「你呢 3 頁 H1 重複，建議改成以下三個唔同角度」
- 「你嘅 category page 平均 120 字，top 5 競爭對手平均 800 字，呢份係建議加入嘅內容區塊清單」
- 每條 fix 標籤：受影響 URL、預期影響（高/中/低）、實作成本、**驗證準則**（改完幾耐可以再測返邊個指標）

呢個輸出直接可落手，唔使收窄位。證實「個人化」有用，就靠呢層：兩條唔同 type 網站出嚟嘅 fix list 一定要字面唔同，且每條都 trace 到返去一個實際爬取發現。

---

## 第五層：成本控制（維持高毛利 ~90%）

成本包袱 = token（爬取+LLM 呼叫）+ 時間。四條殺手：

1. **兩級模型架構**：bulk 分類/抽取用平快模型（deepseek 類、極平）；**只有最後一層深 fix 求解先派強模型**，而且限制喺「最高價值 findings + crown-jewel 頁」，唔係全爬取。語言理解先動用強模型，指標汁料全部程式化。
2. **程式化為先**：字數/H1/重複/orphan/schema/alt 全部係 regex+parser，零 LLM 成本。LLM 淨喺真係要理解語意先出場（內容質素判斷、intent、fix 文字）。
3. **爬取 budget 按規模伸縮**：付費封頂於 N 頁；固定樣板（CMS boilerplate）跳過；sitemap/robots 做 cache。
4. **成本目標硬指標**：每單 LLM 總花費 < US$3（目標 $1–2）。US$99 定價下，即使加少少 infra 都維持到 ~90% 毛利。驗收時用實際 token 記錄驗證呢條線。

---

## 第六層：i18n 5 語言架構（英文 master → 翻譯）

原則：**所有規則是統一一份，得個「表達」先做語言分層。** 唔可以 5 份邏輯各自為政。

1. **English master 為單一真源**：評分規則、findings 模板、fix 模板全部用英文寫 dead。係好多位嘅「主檔」，其他語言淨係翻譯層。
2. **兩種翻譯類別，分開處理**：
   - 靜態模板/UI 字串 → 用 stable ID 做 key，5 個 locale 各一份 .json。一次過 machine translate + 一人 review pass，版本化。terms（SEO 術語）用 glossary 鎖實，唔砌自由翻。
   - 動態生成內容 → 爬取+審計保持原語言，最後一步先將 findings 批次 translate 去目標 locale（一次翻譯 pass，batch 做，慳成本）。
3. **語言路由**：html lang + content 偵測輸入網站語言；報告用該語言出嚟；UI 提供 5 語言 toggle。master 資料模型永遠係英文，長文按 key 落檔：/i18n/{locale}/。
4. **QA 守門**：CI check 強制「master 每個 key 喺 5 個 locale 都存在」+ plural 一致。漏 key 即刻 fail，唔俾漏網翻譯上線。

---

## 推行順序（每步驗證先落下一步）

Phase 1 – site fingerprint + adaptive weights + 爬取深度伸縮（破除「似似樣」最大一步）
Phase 2 – 程式化內容深度指標（字數/重複/orphan/schema）
Phase 3 – 引用 URL 嘅 per-site fix 生成（強模型、限 budget）
Phase 4 – competitor cluster 對比
Phase 5 – i18n 5 locale 推出
Phase 6 – 成本調校 + 平模型 fallback

---

## 驗證方法（點證明拆咗模板化）

建一個「唔同型網站測試集」（SaaS / 電商 / 本地服務 / 內容 blog），每次跑審計後自動斷言：
- fingerprint 彼此唔同
- 權重向量彼此唔同
- fix list 字面唔同
- 每條 fix trace 到返去一個實際發現
呢個當做「sameness 回歸檢測」落 CI——任何改動令兩條唔同網站撞返同一套輸出，即刻 fail。呢先係「個性化」改到嘅**可驗證證據**，唔係靠感覺。

---

## 邊啲位係「唔改」嘅（避免過度工程）
- Stage 1 權威標準盤點必須全站一致（唔可以因為個性化搞到基本盤走樣）——呢就係 Ahrefs/頂級 agency 做法：先通用盤點，再按垂直深度。
- 唔做 full-page LLM 全文咀嚼（成本爆）；程式化汁料先行，LLM 只做語意收窄。
- 唔做即時 real-time SERP 買 API；用 cluster 推斷，慳成本。