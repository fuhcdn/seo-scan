# CEO3 技術方案 v2：技術棧 / i18n / 前端流程 / 部署上線（530→live）

範圍：seoscanaudit.com 賣 AI SEO 審計，5 語言，免費 scan 已通，定價 $497。
原則（Musk）：唔重寫、唔過度工程、用最少步驟推到第一單。現有 stdlib Python server 係資產，唔係負債。

---

## 一、技術棧：決定 = 繼續 server-render（唔轉 static generator / 唔上 SPA）

現況核實：server.py（純 stdlib `http.server`，零第三方依賴）已經 serve 單頁 landing，且已有
SSRF 防護、per-IP 限流、/api/scan 真後端。改寫去 Node/Next/SPA = 淨係拖慢三日目標、風險放大。

決定：
- Origin = 維持呢個 Python server（屬 server-render）。佢有能力出動態內容（scan 結果、訂單狀態、checkout、法律頁），static generator 根本滿足唔到。
- Marketing 層（landing）用「build 時 prerender」：config.py 嘅 `render_landing()` 模式擴展成人 per-locale prereader。即 config 為單一真源 → 填價格 + 填 locale 字串 → 出多個分語言靜態 HTML。呢啲 HTML 由 server 直接 serve。
- 互動淨係 vanilla JS 三條 call（scan / order / checkout），唔引入 React/Vue 依賴。冇 build toolchain，冇 node_modules。
- 唔開 background queue（Celery 等）；交付靠 server 收到 stripe webhook 後 `Popen` detached `pipeline_runner.py`，現有做法已夠。

純 server-render 唔滿足嘅位 = 冇。所以：**唔好 static generator，keep server-render。** 冇架構改動成本。

## 二、5 語言 i18n 架構

語言選擇（建議，需 Yan 拍板）：EN(master)、zh-Hant(繁中)、zh-Hans(簡中)、ja(日)、es(西)。
繁/簡分開當兩種，因為 SEO 同用戶群唔同；日/西覆蓋主要外銷客。韓文(ko)做後補。

通則（CEO4 方案照搬）：規則邏輯統一一份英文 master，淨係「表達」分層。唔可以 5 份邏輯各自為政。

檔案結構：
  /i18n/en/ui.json        <- master，穩定 key（home.title, cta.unlock, price.std 等）
  /i18n/zh-Hant/ui.json
  /i18n/zh-Hans/ui.json
  /i18n/ja/ui.json
  /i18n/es/ui.json
  /templates/landing.{locale}.html   <- 由 master 模板 + config 價格 + ui.json 生成
  /templates/report_fix.{locale}.md  <- 報告 fix 模板（英文 master，其餘翻譯層）
  /templates/email.{locale}.txt

兩類翻譯，分開處理：
1. 靜態 UI 字串 → stable ID key，每 locale 一份 json。一次 machine translate + 一人 review pass，版本化落 repo。
   SEO 術語用 glossary 鎖死，唔自由翻（例如「canonical」「hreflang」「Core Web Vitals」唔翻譯）。
2. 動態生成內容（審計 findings）→ 爬取+審計保留原語言，最後一步先 batch translate 去目標 locale（一次翻譯 pass，慳 token）。
   報告 model 永遠英文 master，翻譯喺「輸出前一層」做。

語言路由：
- 全站用 path-based：`/`（粵語/預設，redirect 去 accept-language 或落 default）、`/en/`、`/zh-Hant/`、`/zh-Hans/`、`/ja/`、`/es/`。
  優點：每語言係獨立可爬 URL，無 cookie 依賴，hreflang 乾淨，避免 duplicate content。子域名（en.xxx）唔用——切散 authority，細域名蝕底。
- 每個渲染 <html lang="{locale}">、<link rel="canonical" href="{locale}-absolute-url">、
  <link rel="alternate" hreflang> 5 個 + x-default（指 /en/ 或 /）。
- 語言切換器：每個頁 render 出 5 條 alternat 連結做 UI toggle（順帶自然生成 hreflang 地圖）。

QA 守門（CI，唔俾漏網翻譯上線）：
- 強制 master 每個 key 喺 5 個 locale 都存在，漏 key 即 fail。
- plural / 數字格式一致（$497 唔好喺日文變 ¥，令單價渲染一律用 config 數值 + 統一 formatting helper）。

上線次序（配合「三日第一單」）：Phase 1 只上 EN + zh-Hant，其餘 3 個後補——私隱文件齊成套先解鎖多語言，唔好為 5 語言拖慢首單。

## 三、免費 scan → $497 → 交付：前端流程同 endpoints 對照

頁面流程（單頁，唔整 multi-step 埋太多 conversion 摩擦）：

STEP 1 免費診斷
  用戶喺 /{locale}/ 入 URL → 前端 JS `POST /api/scan {url}`
  伺服器：SSRF 驗證 + 限流(10/min)，真爬，回覆 shape_scan_response（免費窄 payload）：
    {url, score, fix_count, top_issues[5], signals{title,meta,h1,h2}, server_signals}
  前端 render：「你嘅 SEO 總分 + 問題數量 + Top5 標題 + 1 個 quick-win」。唔洩漏完整 fix_list（免費界線已立）。

STEP 2 email capture（轉化關鍵）
  CTA「解鎖完整審計 US$497」。點擊 → 出現 email 輸入框（+ 同意 consent checkbox，合規硬需求）。

STEP 3 落單
  `POST /api/order {url, customer_email}`
  伺服器：驗 email 格式(400)、再驗 SSRF、生成 order_id、寫 order_<id>.json status=running。
  回覆 {order_id, status_url}。
  前端收到 order_id 後即：`POST /api/create-checkout {url, order_id, customer_email}`
  伺服器：經 stripe_lib 建真 Stripe Checkout Session（價格 = config.DEFAULT_PRICE_USD = 497，唔理 client 傳咩）。
  回覆 {redirect_url, checkout_session_id, price_usd}。
  前端 `window.location = redirect_url`（Stripe 托管收款頁）。

STEP 4 付款完成返嚟
  Stripe redirect 去 `{PUBLIC_URL}/success?order={order_id}` → 呢頁要 serve success + status 輪詢。
  注意：**server 而家冇 /success 路由（會 404）→ 必須新增 GET /success**，用嚟服務 /api/status 輪詢同顯示下載連結。係上線前 gap。

STEP 5 Stripe webhook（自動交付開關）
  Stripe 發 `checkout.session.completed` → `POST /webhook/stripe`（Stripe-Signature 驗證）
  伺服器確認 paid → `spawn_delivery_pipeline(order)`：Popen detached 跑 `pipeline_runner.py`，
  帶 payment_ref / order_id / url / customer_email。HTTP request 即返，唔等 crawler。

STEP 6 交付
  pipeline_runner：付費深度爬(100-500頁) → seo_report_template 出 PDF + HTML → 寄 email →
  更新 order_<id>.json → status=done, report_pdf/report_html(basename), delivery_marker。

STEP 7 前端出結果
  成功頁每 5 秒 `GET /api/status?order_id={id}`，直到 status=done → 顯示下載連結（report_pdf / report_html）。
  失敗就顯示 ai_error / 客服 email。

失敗路徑（而家已 cover）：bad email→400、SSRF→400、限流→429、重複 payment_ref 冪等。

免費 vs 付費界線（保 $497 價值）已落 code，唔郁：免費=診斷(分/數/Top5/1 quick-win)，點修/code/競爭對比/PDF 全鎖付費。

## 四、部署 530 → live：最短可行路 + 成本

530 根因（已核實）：seoscanaudit.com DNS 指向 Cloudflare(104.21/172.67)，但 origin 冇嘢 serve → Cloudflare 回 530 = origin unreachable。唔係 code 錯，係冇機喺 public URL 度跑。

最短可行路（建議，成本 $0 起步）：

1. Commit + push 去 fuhcdn/seo-scan.git（GitHub 已設 remote，render.yaml 已在 repo root blueprint auto-detect）。
2. Render → New → Blueprint（連間 GitHub repo）→ 用 deploy/Dockerfile build → 起 service 喺 free plan，health check /health → 攞到 https://seo-scan.onrender.com。
3. RD DNS（最簡 / 最快）：Render 加 custom domain seoscanaudit.com，喺 Cloudflare 將 apex A 或 CNAME 指去 Render service（用灰雲 grey-cloud 即 Router only，由 Render auto-issue TLS，零摩擦）。
   或者 keep Cloudflare 橙雲當 CDN + CNAME 去 onrender hostname。二揀一，灰雲最快清 530。
   （提醒：Cloudflare 前 + Render 後兩層 TLS 易拗，第一單行灰雲最穩。）
4. Render Dashboard 填 env（對應 secrets.env）：STRIPE_SECRET_KEY(live)、STRIPE_PRICE_ID(=497 product)、
   STRIPE_WEBHOOK_SECRET、SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD/EMAIL_FROM、OPENROUTER_API_KEY、
   PUBLIC_URL=https://seoscanaudit.com、DEFAULT_PRICE_USD=497。
5. Stripe Dashboard：Product price 由 US$79 改 US$497（+首50-US$397）→ 記低新 price ID 入 env；
   註冊 webhook endpoint https://seoscanaudit.com/webhook/stripe 揀 checkout.session.completed。
6. Run `python config.py` 重新 render landing（config 係單一真源，改完價必 re-render，防 template 回歸）。清「首20客」殘留改首50。
7. Smoke test（26/26 現有 tests 重跑 + 加 /success 測試）：/、/api/scan 返 free 窄 payload、/api/order+bad email→400、
   /api/status、SSRF 擋 127.0.0.1、rate limit、webhook 冪等。先用 Stripe **test mode** 跑一條完整單。
8. Launch gate（缺呢個唔算收到錢）：真 Stripe 收 US$497 → webhook 驗 paid → PDF → email 送達 → /api/status=done → 人手覆核壞路徑。

成本（每月，第一單導向）：
- Render free web：$0（但 15 分鐘冇流量會 sleep，第一下 slow；free 夠驗 1 單）。
- 想無 sleep：Render Starter ≈ $7/mo，或 $5 VPS（fly/Railway 都得）。
- Cloudflare DNS：$0。
- Stripe：2.9% + $0.30 / 單。
- LLM(OpenRouter)：target <$3/單（CEO3 v1 方案硬指標），$497 售價下毛利 ~90% 可維持。
- Email：Resend free(3k/mo) 或 Gmail SMTP $0 起步。
- 建議：free Render 上 MVP 接第一單，確認有真客畀錢先升 $7 plan。V1 唔洗買貴 infra。

## 上線前必補 gap（agent 可做，Yan 只擋四樣外部）
- 新增 GET /success 路由（成功 + status 輪詢 + 下載連結）——而家 404。
- Landing i18n 重構（而家硬編 zh-HK 單語言）—— Phase 1 至少拆 EN + zh-Hant 兩份。
- config 價格 79/99 → 497/997/首50-397 + 清「首20」+ Stripe price ID 同步 + re-render。
- 透明度行：「限首 50 位 US$397，名額用完回正價 US$497」頁尾一行細字。

Yan 親手四樣（agent 無權限，係唯一 blocking）：
1. 真 Stripe live key（過 KYC，要幾日）＋ price 建 US$497/首50-$397。
2. 域名發信 SPF/DKIM（EMAIL_FROM 唔好再係個人 gmail）。
3. Host 上公開 URL（上面第 2-4 步，或授權 agent 起 Render）。
4. OpenRouter key 驗證正常（而家 AI 評分 fallback 緊）。

無 530 解決 + 真 live key + 建 497 product 之前，做任何嘢都賣唔到——呢三件係 100% 阻塞，第一優先；今日起碼開 Stripe KYC。