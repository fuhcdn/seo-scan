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
