# CEO4 營運設計 — 免費版內容界線 + 質量 Gate + 新 Target 營運 + 轉化漏斗

> CEO4 (營運/品質驗證) 設計文檔。依從 Yan 糾正：免費版唔可以收得太狠，要俾返 10-20% 完整內容令人睇到「真有嘢改」先肯買；質量要提升；target 由「agency/freelancer 白牌」轉向「已有網站想改善 SEO 嘅生意人」。
> 對齊決策 #001 定價：免費 scan 入門 / US$99 單次 / US$350 4 次包。回覆一律廣東話。

---

## 1. 免費版 vs 付費版 —— 內容界線（10-20%）

原則：免費版=「分診書」，令人信「我個網站真係有嘢好改」；付費版=「執行藍圖」，令人可以即刻改好。分界唔喺「量」，喺「價值類型」——診斷俾你，執行收住。

### 完整付費報告嘅內容清單（現有 10 節）
01 執行摘要（總分 gauge + KPI：緊急問題數 / 全部發現數 / 首10項可提升 / 預期修後分數）
02 五大支柱概覽（問題分佈條）
03-07 五大支柱發現與修復（每項：標題 + 優先度 + 支柱 + 影響力 + 可提升分 + 點解重要 + 點樣修 + code）
06 代碼範例 Code Snippets
07 競爭對比 Competitive Benchmark
08 頂 10 項優先行動 Top-10 Action Plan
10 方法與免責聲明

### 免費版俾（約 10-20%「洞見」，0%「執行」）
| 俾 | 唔俾 |
|---|---|
| 總分（/100 gauge） | ❌ |
| 問題總數 + 緊急問題數（「你網站有 47 個問題、3 個緊急」） | ❌ |
| 五大支柱問題分佈條（睇得到廣度，唔開細節） | 每支柱內逐項清單 |
| 預期修後分數（「修晒可 +18 分」） | ❌ |
| Top 3 問題完整講解：標題 + 點解重要 + 影響力 + 可提升分 | 第 4 條以後所有問題 |
| 對「最高影響嗰 1 項」俾一個 free quick-win 修復提示 | 其餘問題嘅「點樣修」 |
| （選）導去免費 PDF 摘要 download | 全部 code snippets |

### 付費版收住（80-90%）
- 每個問題嘅「點樣修」/ how_to_fix → 呢個先係執行價值，係解鎖位
- 第 4 條以後所有問題嘅完整講解
- 全部代碼範例
- Top-10 優先行動計劃（有順序嘅執行路徑）
- 競爭對手差距表

### 點解咁界（Yan 立場）
免費版最緊要有「真實體感」：Top 3 問題完整講解 + 一個真實 quick-win 令生意人自己跟住改到少少嘢 → 佢先信「呢間野真係識」。啱啱收起「剩低點改」——當佢見到「我明明改咗嗰 1 個都見到／預計有分」，自然想知埋其餘 44 個點改。免費 10-20% = 俾到「證明價值」嘅證據，但「完成價值」必須付費。

### 技術硬邊界（防 extract-by-grep）
免費版返回內容由 server 端 Unity 控制（現有 /api/scan 已分 free vs locked）。鎖定項目喺 HTML 用 locked class + 唔喺 API response 度傳完整 how_to_fix——即使有人撳「檢視原始碼」都攞唔到完整內容。免費 PDF 摘要另生成一份 free template，唔好由付費 PDF 直接裁剪（防 PDF 內嵌完整 fix list 被人剷走 lock）。

---

## 2. 質量 Gate —— 保證每份報告有深度、唔係模板

問題核心：AI 審計報告最易淪為「20 條 common 問題硬塞」嘅模板，冇網站獨特資訊。新增 QC gate，喺 pipeline_runner 於「AI fix 生成 → PDF render」之間執行 validate_quality()，唔過就自動重跑一次；再唔過就掉落 review queue，唔俾直接出。

### Gate A — 獨特資訊含量（Site-Specificity，核心新增檢查）
Rule：**每一項 finding 必須帶 ≥1 個 site-specific 實測證據**（實 crawl 到嘅訊號 / 真實 URL / 實測數值），否則該 finding 自動降級或剔除。
- 泛泛例子（唔合格）：「你嘅網頁內容太薄」（冇證據）
- 合格例子：「你『Plumbing Services』主頁正文得 87 字、4 句，含 Ctrl 冇圖片 alt 標籤 —— 而 DOM 實測 12 張 <img> 得 3 個有 alt」（有 page URL + 實測數字）
實作：crawler 輸出 raw measurement 字典；AI fix 生成 prompt 強制「每項 finding 必須引用 measurement JSON 嘅真實鍵/值，揾唔到證據就唔好寫嗰項（skip 好過塞假）」；render 前 validate：每條 fix 必須含 evidence 欄。

### Gate B — 深度（Page-Level）檢查
Rule：報告必須包含 ≥ N 條 page-level finding（指向真實深度 URL，例如 site.com/plumbing），唔可以淨係 site-level 泛泛结论。冇 page-level 材料 → 判「crawl 深度不足」→ 回返 crawler 加深度頁。

### Gate C — 非模板檢查（Boilerplate blocklist）
Rule：對「點解重要 / 點樣修」文字做 blocklist 比對（20 條高頻 generic 修辭）。若超過某比例（例如 30%）嘅 finding 與 generic 模板 verbatim 重複 → 判「AI 跌返模板」→ 失敗重跑。

### Gate D — 回歸一致性（再現性）
Rule：同一 URL 重跑，分數 + 獨特資訊內容穩定一致；大偏差就係冇綁定證據嘅隨機生成 → 改進生成 prompt。

### Gate E — 營運抽樣 QC
Rule：每 10 份報告自動抽 1 份，排入獨立 review queue（A11 驗證腦 / 人工 spot-check），照 05_評分卡 rubric 打返實際分。抽樣結果回饋 prompt 改進，形成量度閉環。

### 加入 05_評分卡嘅新 QC 行（已附加，見文後）
獨特資訊 / 頁面深度 / 非模板 / 再現性 —— 四條都係 gate columns：全勾先計「做得好」。

---

## 3. 新 Target「已有網站想改善 SEO 嘅生意人」—— 營運含意

由「agency/freelancer 白牌客」轉向「生意人自己嚟」，六樣要調：

1. 語氣：生意人唔係 SEO 專家 → 初學者層級。每個問題用「問題 → 對你生意嘅影響 → 點改」結構，Jargon 後補一句廣東話/中文解釋（唔好淨寫「canonical tag」要寫「重複內容嘅網址標記」）。收窄「方法論/免責」篇幅，放報告最尾，焦點放「你有咩問題、執邊三樣、預料提升幾多」。

2. 交貨節奏：生意人重視「即刻有嘢睇」但反感被急逼。付款 → 10 分鐘內（最好即時）交付 PDF / 網上版。交付後只做 1 次 recap email（帶下一步 + 退款/再問入口），唔搞訂閱式後續推銷。US$350「4 次包」對生意人重新定位為「4 個頁面 / 分階段執」嘅任務導向，唔係預付套餐。

3. 退款政策：生意人買「唔肯定嘅技術服務」需要零風險入場 → 加「7 日、不問理由、全額退款」保證。原因：退款保證係轉化催化劑而唔係成本——報告即時交付、退款率可控（目標 <3%）；但係要防 abuse（一 URL 一次計，重複申請先檢查）。退款入口清晰 + 自動化（Stripe refund API），減少人手。呢條要同 CEO4 合規腦對齊：寫入 ToS / 免責聲明（04_決策紀錄 #002 已有 5 份合規文件），PDPO 私隱條款唔受影響。

4. 交付格式：生意人想要「一頁睇得明」，唔係 40 頁 tech PDF → 報告首兩頁做「老闆摘要」（score、Top 3、預期分），技術細節放後面附錄。預設 PDF 或網上 interactive 版都行呢個 head-first 結構。

5. 語言：對齊 00_多語言需求.md —— target 生意人可能粵語 / 中文 / 英文，落地時自動偵測或按表單揀語言。「點解重要」同「點樣修」靚個 local 翻譯先交。

6. 自動、但有「體溫」：全自動交付唔等於冷冰冰。付款後自動 email 帶客名 + FAQ 頁 + 一句「唔明邊度，直接覆呢封 email」。但 keep 全自動——唔開真人 support，用 auto-responder + FAQ 頂住，維持毛利 ~90%。

---

## 4. 免費 → 付費轉化漏斗（自然提升）

漏斗各步 + 每格有 metric，KPI = 免費 scan → 付費轉換率（README 已定為 input metric，最先郁）。基準：≥2-3%。

Step 0 — 免費 scan 低摩擦：一個 URL 輸入框，無需註冊（現有）→ 目標係最多人入，唔設門檻。

Step 1 — 即時出「診斷結果」（免費 10-20%，見第 1 節）：總分 + 問題總數 + 5 支柱 + Top 3 完整講解 + 1 個 quick-win + 預期修後分數。網頁上每個鎖定項目就企喺佢「已經見到」嘅問題旁邊 →「你明知有嘢，差一步就知點改」嘅自然好痕。CTA 同時做「解鎖完整修復藍圖 US${{PRICE_USD}}」+「7 日退款保證」badge（降 Risk）＋「首 20 客 US$79」緊迫（現有）。

Step 2 — 唔想即刻俾錢嘅人 → Email capture：免費版 offer「免費 PDF 摘要 download」→ 攞返 email 做 remarketing（呢個先係免費 scan 嘅真正回報：lead generation）。2-3 日後送一封「你嘅 Top 1 問題完整修復」再提示（甜頭，再俾多一項 now-to-fix），提醒完整版價值 + 「報告會因應 SEO 變化更新」嘅時效逼切感。

Step 3 — 解鎖旅程：pay-first、即時交付（快速收費先行原則，唔做 freemium 拖長）。付款 → 即刻 10 分鐘內出完整 PDF + recap email。

### 自然提升嘅三個引擎
- 遞增價值足跡：每條 locked finding 都企喺「免費版已展示」嘅問題旁邊，逐條提醒「上一步你見到有嘢，依家差一步就知點改」。
- 封住「即刻需求」：「你 47 個問題、3 個 urgent、修晒 +18 分」——心癢想知點改，而「點改」就係 paywall。免費必須俾到呢個「真實體感」（單一 score card 唔夠，要有人睇到「呢啲我真係改到少少」先信）。
- 退款保證降風險：生意人唔信技術嘢，退款 badge + 初學者語氣一齊推高轉化。

### 實驗（A/B 一項就夠，唔好多花）
免費內容份量 A/B：Top 3 vs Top 5 問題講解，睇轉化率同 email capture 率。另外可測 price anchor（US$99 對照 US$79）。其餘交 goto Kansei，唔 over-test。

### 反方向陷阱（Yan 立場，直接做）
免費版唔可以收得太狠——淨係一張分數卡就收，會令人「又係吸左 email 得個分數」就走。Top 3 完整 + 1 個真實 quick-win 先令佢「見到真有嘢改」，呢個先係免費版嘅目的。

---

## 附：05_評分卡新增 QC Gate 行（提案）
- [Jensen 獨特資訊] 每項 finding 帶 ≥1 個 site-specific 實測證據（URL/數值/實抓訊號），而非泛泛
- [Jensen 深度] 報告含 ≥N 條 page-level finding（指向真實深度 URL），唔淨係 site-level
- [Jensen 非模板] 泛泛模板語句（fix text 喺 blocklist）佔比 ≤ 30%；「點解重要」冇 verbatim 重複
- [Jensen 再現性] 同 URL 重跑，分數 + 獨特資訊內容穩定一致