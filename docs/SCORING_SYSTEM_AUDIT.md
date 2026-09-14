# SCORING SYSTEM AUDIT + 改進方案（owner 指令：次次同分、計分真實、參考同行）

## 1. 現狀真相（code 實證）

免費 scan 有**兩套計分路徑**，呢個係「次次唔同分」嘅根源：

| 路徑 | 觸發 | 邏輯 | 一致性 |
|---|---|---|---|
| **A. Rule-based fallback**（`_estimate_score`） | Free tier（`skip_ai=True`）或 AI 失敗 | 100 分起，每個 finding 按優先級扣分（urgent −15/high −8/medium −4/low −2） | ✅ 完全 deterministic（同一網站 = 同一分，實測 94/94/94） |
| **B. OpenRouter AI scorer**（`ai_score`） | Paid report pipeline / 某些條件 | LLM 按 signals 評 0-100,**temperature 0.2**——唔係 0,有輕微隨機 | ⚠️ 同一網站每次可能 ±3-8 分 |

**問題點**:
1. 兩套路徑標準唔同——客掃同一網站,一次行 A 一次行 B,分數自然唔同
2. AI path `temperature: 0.2` 有隨機性（應為 0 或用 seed）
3. AI prompt 每次可能包含唔同 crawl 抽樣(邊幾頁被抓)→ 輸入都唔同
4. Rule fallback 嘅扣分權重（15/8/4/2）冇對外解釋，亦冇同 AI 標準校準
5. TTFB 等伺服器訊號每次測量自然波動（82ms/290ms/77ms）→ 分數若含 TTFB 項就會浮動

## 2. 同行計分方法參考（web research）

| 工具 | 方法 | 一致性處理 |
|---|---|---|
| **Google Lighthouse** | 6 大類指標各自加權（Performance 權重 25% 類）+ 分數由**測量值映射到固定曲線**（如 FCP/LCP 有官方 score curve）| 同一資料 = 同一分；多次跑用**中位數**而非單次 |
| **Semrush Site Audit** | 主題式 issue 計分（errors/warnings/notices 比例公式） | deterministic;分數=健康公式 |
| **Ahrefs Site Audit** | Health score = (通過頁內部連結權重)/(總頁) | deterministic |
| **Screaming Frog** | 唔俾總分——只出 issue 清單（避免分數波動問題） | n/a |

**同行共識**:(a) 分數必須由**測量值經固定公式**計出，唔可以由 LLM 自由評分;(b) 效能類訊號要**多次取樣取中位數**;(c) 分類權重公開。

## 3. 改進方案（建議，自主實作部分 + 提案部分）

### ✅ 自主修（deterministic、免費、無風險）
1. **AI scorer temperature 0.2 → 0**——消除 LLM 隨機（一致性第一）
2. **單一真相分數**：免費 scan 同 paid report 都行同一條 deterministic 公式；AI 只用嚟寫「解釋/建議文字」，唔再用嚟「俾分」。分 = 固定公式，文字 = LLM。噉分數永遠一致，AI 仍然提供深度。
3. **公式公開結構**（對齊同行）:
   - Technical（crawled errors/canonical/robots/gzip/cache）25%
   - On-page（title/meta/H1/alt/schema）25%
   - Performance（TTFB 三次取樣中位數、LCP proxy）20%
   - Content/conversion（每條客戶目標路徑有無 CTA/信任/pricing 線索）20%
   - Mobile/social/meta-prefetch 10%
4. **TTFB/效能取樣中位數**：crawl 時同一 URL 測 3 次，取中位（消除網絡波動）
5. **分數旁邊標示「同一網站再掃分數一致」**——管理期望

### ⏸ 要 owner 批（影響 paid report 報價值）
6. 免費/paid 分數差異聲明：free scan 規則快算 vs paid 報告深度（頁數/證據/決策）——市場溝通
7. AI 仍寫 finding 文字（paid path）——成本 vs 一致性取捨

## 4. 實作狀態
- [x] temperature 0（自主，已做）
- [x] 中位數 TTFB 取樣（自主，已做）
- [x] deterministic 加權公式入 code（自主，已做）
- [x] 分數一致性測試（同一 fixture 固定分）(已做)
- [ ] 客戶溝通文案（等 owner 揀措辭）
