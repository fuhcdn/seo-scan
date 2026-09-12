# CEO3 技術方案：即時體驗／速度推轉化（v1）

賣點聚焦（Musk 一句）：免費 scan 唔係 30 秒 promise，係 3 秒 real。價值唔係靠 copy 講，係靠客喺付款前「親手睇到自己網站出事」而 get 到 —— 而呢一刻必須夠快、夠真、夠即時。

---

## 核心診斷：而家免費 scan 慢嘅根因，唔係網速，係架構

/opt/data/seo-audit-business/pipeline/server.py 嘅 `POST /api/scan` 係「成條付費 pipeline 同步跑晒」。seo_crawler.run() 內四個收費級動作全部 serial 排隊：

- 抓主頁：FETCH_TIMEOUT = 15s
- HEAD 速度探針：8s
- 抓 robots.txt：10s
- OpenRouter LLM 評分＋生成 fix_list：timeout = 120s（呢個先係主兇）

最壞 case 加埋 ≈ 153 秒；典型都要 20-40 秒。免費 scan 根本唔需要 fix_list / AI 評分 —— 個免費 tier 界線（06_CEO4 已立）淨係要：score + fix_count + top_issues + signals。呢啲全部係規則可即時算出嘅嘢（rule_based_fixes() 已經係 deterministic）。

即係話：**免費路徑喐緊 LLM，係為咗攞自己唔需要嘅數據**。斬咗佢，免費 scan 由 30s+ 直落到 ~2s。

---

## 1. 免費 scan 即時化（最高槓桿，改呢個先）

方向：免費＝規則快算；付費＝用家唔食 latency 的 async 深度 LLM。

- 喺 server 開兩條路徑：
  - FREE path（/api/scan 直接）：抓主頁（hard cap 4-5s）→ extract_signals → rule_based_fixes → 即時 score + top_issues + fix_count。唔 call LLM。deterministic，ms 級。
  - PAID path（已存在嘅 pipeline_runner，webhook spawn async）：深度 100-500 頁 + LLM 完整 fix_list + 競爭對比 + PDF。客人唔會喺免費 scan 度食呢段 latency。
- 網絡動作改並行：head_speed 探針同 robots.txt 用 ThreadPoolExecutor 同主頁抓取並行，唔好 serial。
- Hard timeout 收窄：free path 全盤 deadline ≤6s，任何單一步唔等到齊先回。

回覆格式唔變（shape_scan_response 個窄 payload 已經啱用），但注意 free score 會跴住 fallback 估算 —— 加 data_quality 標籤（已有）照出，誠實標「快掃估算」，付費版先係精確。

前端對應：
- runScan() 個 fetch 加 AbortController timeout（例如 12s），到點就返 error，唔好令個 spinner 無限等 —— 永遠唔可以讓客「load 住唔郁」。
- 回覆到即 render，唔好再有任何等待。
- 加一個「你網站出事」即時 proof moment：結果牌直接顯示最大條 urgent 問題嘅點解 + 一睇就明嘅一句修法（免費可露 1 個 quick-win，06 界線已准）。

順帶架構收益：免費 scan 唔郁 LLM → 免費 tier 成本 ≈ 0（冇 API 支出），可以安心做「無限免費掃描」做口碑，唔怕俾人打爆。

---

## 2. 樣本報告 —— $497 值嘅實物證明

$497 嘅值唔係 tagline 證明到，係「客睇到買到個乜」先證明到。而家完全冇樣本，客要靠估。

做法（低成本，用現成 seo_report_template.py 出 PDF）：
- 實爬一個真實（或半真實）細站（例如 landing 已用嘅 restaurant-hk.com / 自己 house demo site），用真 pipeline 出一份完整報告。
- Mask 步驟：所有 pag URL → 改 generic（/contact 隱去），隱 domain、隱 title/meta、品牌用 dummy，剝走任何客戶可識別位。變成「真實但匿名」樣本。
- 起一個 /sample-report 路由 serve 樣本 PDF + HTML preview，並喺 3 個位放入口：
  1. 定價卡「Full AI Audit Report」下（「睇實物樣本 →」）
  2. 免費 scan 完嘅 CTA 旁（即刻 connect：你頭先睇到嘅係免費版，入面先生係完整版）
  3. 頁底
- 樣本至少 cover 三樣先夠證明值：overview 分數 breakdown、priority fix list（點解 + how_to_fix + code snippet）、競爭對比。
- 頁面 frame：明寫「以下係真實審計結果，已隱去客戶資料」—— 誠實落，唔造假。

樣本報告係除咗快 scan 之外第二高槓桿嘅信任資產。

---

## 3. Landing 速度 ＝ 信任

Landing 而家已經好：全 inline CSS/JS、冇外部 font/CDN、單一 21KB HTML，理論上 <1s interactive 做得到。但 server 有兩個拖慢位：

- 對 landing 都 send `Cache-Control: no-store` → 每次 reload 全量重拉。修：landing 係 build-time 靜態，應 cache 好耐（immutable / long max-age）。要用 config re-render 時先換 ETag。
- 冇 gzip。stdlib http.server 加 gzip 包 HTML（~21KB → ~5KB），TTFB 即刻靚咗，尤其海外客。要 env 開關，方便 agent/調試。

目標數字（要夠 concrete 先話到俾客知「快」）：
- Landing TTFB（首網）< 600ms，interactive < 1.5s，LCP < 1.5s（一串 inline heavy，冇 lazy 位，好易達）。
- 免費 scan 結果 p50 ≤ 2s、p99 ≤ 6s —— 唔好再寫「30 秒」，直接落個「平均 X 秒」或唔落時間數字，落咗就要做到。

---

## 4. 免費 → 付費無縫（零摩擦購買）

- 我脈絡唔斷：scan 完立刻結果卡下就係「解鎖完整審計」+ email 框。URL 一句話都唔使再貼，email 一填就落單——而家 flow 已 build，keep。
- 一致報價：server 自己由 config 夾死價格（DEFAULT_PRICE_USD=497），唔信 client 傳嘅 —— 正確，keep。但係 landing 而家 render 咗舊價（見下面 bug），要 re-render 令頁面／JS 同 server 報同一價。UI 報嘅同扣嘅一致係信任底線。
- 付款即交付承諾要靠 scan 快打底：客頭先 2 秒就攞到真結果，自然信「付款後 10 分鐘交報告」都得 —— 快掃係成個「信守」品牌嘅第一印象。
- 唔好喺 scan 結果同付款之間再加 gate／多一步 confirm，多一頁 ＝ 多一層 drop。
- 免費 scan cache 落 server（URL→signals+free result），付費落單直接 reuse 同一批 signals 做深挖，慳時間亦慳一致嘅感覺（客見番同一個分數，唔會覺得兩套數據）。

---

## 上線前必修（信任變現殺手，優先級最高）

1. **價錢 sync 爆鑊**（致命）：config.py 已改 497/997/首50-397，但 /opt/data/seo-audit-business/pipeline/landing_page.html（render 出嚟嗰個）仲係寫死 US$79/US$99「首20位」。「UI 報 $79、結帳扣 $497」＝即時不信任 + chargeback/投訴風險。唔可以上線。解法：確保 template 用佔位符（已齊），跑 `python config.py` re-render，之後任何改價必須 re-render，並加 CI 檢查 render 後 HTML 同 config 同步。
2. **社交證明 placeholder**：「好評率 待接入真數據」「— Beta 示範 (Illustrative)」放頁面睇起嚟似假嘢，削弱成個 proof section。scanCount 而家係 JS session 內計（reload 歸零）── 要伺服器端累計真數字，或者連個空 cell 都唔好擺。
3. **免費 /sample-report 落地**：未造好樣本前，$497 冇實物可嗌。
4. /success 路由係已知 gap（CEO3 v2 已記），未起之前付款行唔通，list 都出唔到。

---

## 落地優先次序（Musk：先做影響最大嗰件）

1. Free path 馘 LLM → scan 回落 2s。同時收緊 timeout + 並行抓取。（改 ~1 個 function，風險低，改完即轉化）
2. Landing gzip + cache + re-render sync 價錢。（信任止血，必做）
3. /sample-report 樣本報告 + 3 入口。（$497 實物化）
4. 前端 AbortController + 伺服器端 scanCount。（體驗收尾）

一件過做完第 1 步，免費 scan 由「30s promise」變成「2s real」—— 呢個先係成個即時體驗推轉化嘅樞紐。