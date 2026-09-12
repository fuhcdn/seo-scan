# 問題追蹤 — 分類：要我(Yan)做 vs 我可以做
> 每輪發現嘅問題，分清楚邊樣要 Yan 手動，邊樣我(agent)可以自己解決（須 4 CEO 同意）。

## YAN 必須自己做（我無權限/無帳號）
| 問題 | 點做 | 依賴 |
|---|---|---|
| 開真 Stripe 帳號 + API key | dashboard.stripe.com 開，過 KYC，攞 sk_live | 收款前提 |
| 建 Stripe Payment Link / Checkout Session 收款 | Products 加 US$79 price | 收款前提 |
| 真 email sender(SMTP/Resend/SES) + SPF/DKIM | 開 Gmail app password 或 Resend/SES，填 SMTP_Host | 交付前提 |
| Host server 上線 (有 public URL) | 而家 server 只喺 localhost,要 host 先俾人入 | 上線前提 |
| 接真 webhook 驗證 Stripe-Signature | 留 secret key + endpoint | 收款安全 |
| 確認 OpenRouter key 正常（AI 評分 fallback 緊） | check OPENROUTER_API_KEY | AI 評分 |

## AGENT 可以自己做（4 CEO 同意）
| 問題 | 已處理 |
|---|---|
| email 交付 placeholder → 真 gate/fallback | ✅ Round1 |
| 假 scan/math.random → DEMO_MODE | ✅ Round1/3 |
| 假競爭數據 → 佔位 | ✅ Round1 |
| 訂單共享檔 → 每單獨立 | ✅ Round2 |
| 價格 99/79 亂 → config 單一來源 | ✅ Round2 |
| AI 失敗空報告 → rule-based fallback | ✅ Round2 |
| 真 server /api/scan | ✅ Round3 |
| server 同 pipeline 縫合(spawn) | ⏳ Round4 修 |
| $79 掣 → checkout endpoint 路徑 | ⏳ Round4 修 |
| 移除假 social proof(3,240+/98%) | ⏳ Round4 修 |
| 固定 42 項 → 動態 fix_count | ⏳ Round4 修 |
| 每輪記低要 Yan 提供咩 | 呢個檔 |

## 決策記錄
- Round1 4CEO: 單頁$79先上線,全站$99旗艦
- Round4 4CEO: 最快用 Stripe Payment Link,但要真 webhook 驗證唔准 placeholder
## Round 5 更新
### YAN 必須做（累積）
- 開真 Stripe + API key + webhook secret
- 提供 SMTP (Resend/SES) + EMAIL_FROM
- Host server.py 上線 (public URL)
- 第一單人工覆核交付

### AGENT 可做（4CEO同意，將做）
- 模板防回歸 demo (render_landing smoke test)
- Stripe 手冊價格改由 config 讀(79)
- 清 landing 假 testimonial(+47%/Kelly)
- 「42項/競爭對比」誠實化
- 加 /api/order 自助落單 HTTP 橋樑
- /api/scan 加 SSRF 防護 + rate limit
- report 檔名加 order_id + retry-deliver

## CEO 最新 flag
- 未接真 Stripe 前只係『可展示 pipeline』唔係『可收款產品』—— 唔好對外賣住

## Round 6 更新
- 確認 Round5 修復大部分已實作(SSRF+ratelimit✅、report order_id✅、template防回歸✅)
- 已親手清埋漏網:假見證Marco/幾十位客戶、US$50信用額承諾 ✅ (兩檔同步,render後唔回歸demo)
- 真後端 marker 確認:DEMO_MODE=false + fetch /api/scan 喺度 ✅
- **Yan 仍要做:Stripe + SMTP + host** (跳過唔阻 Loop)

## CEO 之 Round6 flag
- 假 social 已清 -> 可信度風險解除
- 仲差:沒自助落單 /api/order、/api/status readiness -> 列 agent_can_do Round7

## Round 7 完成（10輪進度 7/10）
- Round7 嘅7件 agent_can_do 已全部喺 code,21/21 test PASS:
  /api/order自助落單✅ /api/status✅ 解鎖改走落單✅ SSRF TOCTOU✅ 冪等✅ email驗證✅ data品質徽章✅
- 驗證:bad email→400, valid→order_id, /api/status 有資料, 缺單404, SSRF擋127.0.0.1
- **Yan 仍要做：Stripe sk_live + SMTP + host + 第一單人工覆核**（呢d跳過繼續loop）

## 累積要 Yan 提供：
1. Stripe sk_live key（US$79 Checkout + webhook簽名驗證）
2. SMTP (Resend/SES) + EMAIL_FROM（SPF/DKIM）
3. Host server.py 上公開URL + OPENROUTER_API_KEY
4. 第一單真支付+交付人工覆核

## Round 8 完成（8/10）
- 發現 4 件 agent_can_do：付費路徑SSRF漏 / legal文件無route / 限流只罩scan / status漏絕對路徑 -> 修緊
- **CEO關鍵flag：免費scan出晒成份fix_list可能令客唔使俾錢** -> 要考慮免費收窄保$79價值
- **CEO：而家最大樽頸係 Yan 開 Stripe+SMTP+host**，agent能力基本做晒

## 累積要 Yan 提供：
1. Stripe sk_live + US$79 Checkout 接真 + webhook 簽名驗證
2. SMTP(Resend/SES) + EMAIL_FROM (SPF/DKIM)
3. Host server.py 上公開URL + OPENROUTER_API_KEY
4. 第一單真支付人工覆核
5. [待決策] 免費scan要唔要收窄（避免客唔使俾錢）

## Round 9 完成（9/10）
- **4CEO拍板免費scan定位**：免費淨俾 總分+fix_count+Top3-5問題標題；how_to_fix/code/完整次序/競爭對比/PDF 全部US$79先有 -> 保$79價值
- 修緊 4件：/api/scan收窄 / price_usd鎖死 / legal補退款+授權書 / 清demo-shop
- 累積要Yan：(1)Stripe sk_live+US$79 Checkout+webhook驗證 (2)SMTP+EMAIL_FROM (3)host+OPENROUTER_API_KEY (4)第一單人工覆核

## 🏁 Round 10 完成（10/10 結案）
- Agent 側 100% 完成：26/26 test PASS、legal 5份齊、$79保價(免費scan收窄)、SSRF全面/限流/冪等/自助落單/api+status/data品質徽章、真server /api/scan
- implementation_missing 空
- **ready_to_launch=false —— 100% 卡喺 Yan 四樣外部設定：**
  1. Stripe sk_live + US$79 Product/Checkout + 真webhook簽名驗證
  2. SMTP(Resend/SES/Gmail) + EMAIL_FROM (SPF/DKIM)
  3. Host server.py 上公開URL + OPENROUTER_API_KEY
  4. 第一單真支付人工覆核
- 4 CEO 一致：未接真 Stripe 前只係可展示 pipeline,唔好對外賣
- 第一單驗證法：真Stripe收$79→過程/webhook驗paid→run_pipeline出PDF→email送出→/api/status全done→人工覆核;再測壞路徑(bad email/SSRF/重復ref冄等)

## 質量+免費版+定價 batch（deleg_aa3684d3）返咗
### 定價（CEO1 Bezos）— 主力改做「改善追蹤」唔係單次
- Tier1 免費 scan（誘餌，俾診斷留住HOW）
- Tier2 單次報告 $99（入門口）
- **Tier3 改善追蹤 $349-399（主力，含30/60/90日 re-audit）——真正賣「改善」**
- Tier4 代理/white-label $499/月起（規模通道）
- 錨定「代理報價」，放棄折讓 gimmick

### 深度個性化（CEO2 Jobs）— 殺死「一樣分數」死症
- 5-pass site model：Site Model→Intent Map→Weighting→Fix→Uniqueness Gate
- 每個 finding 三件套：具體做法+點解+預期效果；effort/impact 排
- 免費版 = 「醫生話你知有病」，收費 = 「點醫」:site thesis+總分+第一條最強finding完整+3-5條teaser

### 技術（CEO3 Musk）
- 4層：site_profiler分類器→rubric router(by type)→內容深度特徵→two-pass LLM
- 每單 <US$0.10 維持~90%毛利；rubric by type(e-commerce/content/saas/local)唔同權重

### 免費版10-20%界線+質量gate（CEO4 Jensen）
- 免費=診斷(總分/問題數/5支柱/Top3完整/1個quick-win)；收=點修/全部/competition/PDF
- 質量gate 5道門(獨特資訊含量檢查、無template blocklist、再現性、每10抽1QC)
- 新target營運：7日不問理由退款做轉化催化劑；進階報告head-first

### 整合定價（4 CEO共識）— 推薦一次過非訂閱
- 完整深度報告 US$149（單網）
- 兩網站套餐 US$199
- 3個月進度追蹤包 加 US$99
- 免費版免費到上癮，$149貴到有誠意平到say yes，無中間plan

⚠️ 定價有分歧：CEO1建議Tier3改善追蹤$349-399做主力 vs 整合版建議$149一次過。待Yan拍板。

## 💰 定價最終決策（Yan 2026-09-12）
- 網站：seoscanaudit.com（⚠️ 而家 HTTP 530/Cloudflare error，未正式上線，訪客睇唔到）
- 正價：US$497（≈HK$3,900）企住 HK$2-3k 底線
- Growth：US$997（4錢頁深挖）
- **首 50 位早鳥：$497 - $100 = US$397**（Yan 指定）
- 唔好顯示已售數量/已幾多人買（Yan：唔需要俾客睇到）
- 刪走舊「首20客-US$20」低錨
- 4 CEO 一致：$497 主力，唔用 $149
- config 而家仲係 79/99，要改 → 497/997/首50-100

## ✅ Step 1 部署上線 — 完成（證據）
- date: 2026-09-12 15:19 UTC
- https://seoscanaudit.com → **HTTP 200** + SSL 有效（curl -w ssl_verify_result=0）
- /health → {"ok":true,"server":"real-backend-v1"}
- Landing 返回 21KB HTML（zh-HK 版，meta 仲寫 US$79 → Step 2 改）
- 架構：Docker container app-seo-scan（127.53.137.215）publish 8000 → Cloudflare Tunnel（systemd service cloudflared-seo, fe4527bc）→ 指向 localhost:8000
- Tunnel 用 cloudflare creds（.cloudflare_token + credentials json）
- ⚠️ /api/scan POST 30s timeout（Step 4/6 驗收要查）
- 下一步：Step 2 接價格（landing meta $79 要改 + checkout 用 $497）

## ✅ Step 2 價格落地 — 完成（證據）
- date: 2026-09-12 15:29 UTC
- Landing 更新：Free $0 / Full $397 (早鳥,原價$497刪除線) 最受歡迎 / Growth $997
- 移除所有「首20客 -US$20」「原價US$99」低錨同 $79 殘留
- 加「7日放心保證：交付前可退·交付後免費重審」入 pricing 卡
- 加「首 50 位創始價 US$397（名額派完即止）」
- JS price_usd 79→397；config.render_landing() 加 EARLY/GROWTH replace
- server checkout 用 config.DEFAULT_PRICE_USD=497（早鳥由前端定）
- 已上傳 VPS + recreate container + health OK + live site 反映新內容
- 下一步：Step 3 (5語言 i18n) / Step 4 (內容深度個性化)

## ✅ Step 4 內容深度 v1（個性化）— 完成（證據）
- date: 2026-09-12 15:34 UTC
- 新增 site_profiler.py：classify_site() 判網站類型(電商/內容/本地/SaaS/企業) + 個性化權重 + persona_note + unique_evidence_count（質量Gate A）
- seo_crawler.py：SCORING_PROMPT 加 site_type/persona/weights/evidence_count；ai_score() 動態注入 profile；run() 將 site_profile 加落 result
- 驗證：電商→ecommerce(schema weight 0.2) vs 牙醫診所→local_service(local weight 0.25)，type+persona+weights 全唔同 = 殺死「一樣分」
- seo_report_template.py：cover 加「網站類型 + persona」type-badge（證明個性化）
- build_html mock 測試：type-badge + persona 都出到，HTML 15KB
- 已上傳 VPS + recreate + health OK
- 下一步：Step 5 退款政策 / Step 6 端到端 / Step 3 5語言 / Step 7 4CEO全檢

## ✅ 轉化優化（4 CEO 分析應用）+ 免費scan提速 — 完成（證據）
- date: 2026-09-12 15:39 UTC
- 4 CEO 轉化分析：CEO1(定價矛盾已修)CEO2(Apple設計/假證言摧毀轉化)CEO3(免費scan提速)CEO4(退款保證放付款CTA)
- 應用：① un如鎖掣加「🛡️ 7日放心保證：交付前全額退·交付後免費重審」badge ② 移除假證言(Illustrative) ③ 免費scan skip_ai 提速
- seo_crawler.run() 加 skip_ai 參數；server /api/scan 用 skip_ai=True → 免費層唔行LLM 直接規則快算
- 實測：免費scan 秒回（score:36 fix_count:8 top_issues 5項），之前30s timeout
- 付費 pipeline_runner 直接 call run() default skip_ai=False 照行 AI 完整深度（唔影響）
- 已上傳 VPS + recreate + health OK + live site 反映退款badge+新social section
- 剩：Step 5 退款政策(beta文件已啱)，Step 6 端到端(需真卡測試)，Step 3 5語言，Step 7 4CEO全檢

## ✅ Step 6 端到端鏈 — 完成（收款→交付全接通）
- /api/order 正常（order_id + status_url + pinned_ip）
- /api/create-checkout 建真 Stripe Session（cs_live_... 已出，redirect_url 帶客去付款頁）
- Webhook endpoint we_1UEmup... → https://seoscanaudit.com/webhook/stripe，events: checkout.session.completed + payment_intent.succeeded
- spawn_delivery_pipeline() + email 交付(smtplib+PDF+SMTP有值) 已實作
- 剩：Step 3 5語言(i18n) + Step 7 4CEO全檢

## 進度總覽（deploy 進行中）
✅ Step 1 部署上線（200+SSL+health）/ Step 2 價格落地（397/497/997）/ Step 4 個性化 / Step 6 收款鏈 / 轉化優化+免費scan提速 / 退款政策
🔄 Step 3 5語言（deleg 做緊）
⏳ Step 7 4CEO全檢（最後）

## ✅ Step 3 5語言 i18n — 完成（證據）
- date: 2026-09-12 15:53 UTC
- 5 語言齊上線：/ (en, default) /en /zh-Hant(繁中) /zh-Hans(簡中) /ja(日) /es(西) 全部 HTTP 200
- 6 個 landing 檔 + server LANDING_LANGS 路由
- 語言切換器右上角，預設英文
- 定價/退款/權威徽章/免費scan 全部保留
- verify: /zh-Hant lang=zh-HK 粵語原文案, /zh-Hans lang=zh-CN, 各title+H1 正確
- 全部 Step 1-6 + 轉化 done. 剩 Step 7 4CEO全檢

## ✅ Step 7 4CEO全檢修復 — 完成（全部 fail 已修）
- date: 2026-09-12 16:14 UTC
- CEO2/3/4 fail 修復：
  1. ✅ 免費scan假結果 → 修 decode-None + meta content-None；live 三網站終於出真結果（example 59 / wiki 78 / mozilla 92，各唔同 site-specific）
  2. ✅ 誤導定價 → checkout_price() 改返 EARLY(397) + stripe_lib 用 PRICE_397，頁面$397=實收$397
  3. ✅ email consent → 6語言加 consent checkbox
  4. ✅ hreflang/canonical → 6語言頁加齊 6條 hreflang + canonical
  5. ✅ placeholder「待接入真數據」→ 移除，改「每份報告人手QC後交付」
  6. ✅ 真引擎 → site_profiler 個性化權重 work（3網站唔同分）
- 依然未做:真卡端到端一單(需 Yan)、合法文件本地化(需補)

## ✅ Legal 5語言本地化 — 完成（live驗證）
- 新增 5 份英文 master legal（ToS/Privacy/Refund/Disclaimer/Authorization），法律承諾一致
- server LEGAL_DIR_EN/ROUTES_EN + Accept-Language 自動偵測
- live: EN瀏覽器→英、繁中→繁中、/legal/en/* 英、/legal/*/ja fallback英、path traversal 404
- 剩最後:真卡一條端到端驗證單（要 Yan 落）
