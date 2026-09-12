# Stripe Payment Link 收款設定指南（US$79 / 份 — 由 config.DEFAULT_PRICE_USD 讀取）

用嚟將「AI SEO 審計報告」做到 **pay-first**：客戶撳 Payment Link 付款，
先開始 crawl → 生成 PDF → email 交付。以下步驟係俾 **Yan（帳號持有人）** 手動執行，
因為要真實 Stripe 帳號先連到 —— 而家只係 setup 指引，`pipeline_runner.py` 已用 `--payment-ref` 接好。

> **價錢單一來源（Round5）：** 收款金額一律由 `pipeline/config.py` 嘅 `DEFAULT_PRICE_USD` 讀取
> （現時 **US$79**）。本手冊任何地方**唔再 hardcode US$99** —— 改價就去改 `config.py`，
> runner、landing page、以及你喺 Stripe 開嘅 Product 都要對返呢個數。正價（strikethrough）係
> `config.REGULAR_PRICE_USD`（現時 US$99）。

> 現狀：`seo-audit-business` 未有真實 Stripe 帳號/API key，呢份文件係完整開通手冊。
> 開通後，將收款 webhook/付款 ref 餵俾 `pipeline_runner.py --payment-ref <pi_xxx>` 即可自動起單。

---

## 1. 開 Stripe 帳號（一次性）
1. 去 https://dashboard.stripe.com/register 用 Yan 嘅 email 註冊。
2. 揀「香港 / Hong Kong」做公司所在地（如賣俾香港客），或選你實際營運地。
3. 完成身份驗證 + 加上銀行戶口（收款用）。
4. 每個交易收 % 手續費 + 固定費用（香港常見約 2.9% + HK$2.20 / 筆，細節睇計畫頁）。
   → **訂價記得計埋**：US$79 一般都直接內化，唔使加。

## 2. 建立「Payment Link」（US$79 一次性，金額要對返 config）
1. 登入 Dashboard → **Products**（產品）→ 加一筆 **One-time** 產品／定價：
   - 名稱：`AI SEO 網站審計報告`（英文 `AI SEO Audit Report`）
   - Price：**一筆過**，金額 `US$79.00`，貨幣 USD（**確保同 `config.DEFAULT_PRICE_USD` 一致**）
2. → **Payment Links** → 揀呢個 Price → 產生一個連結（形如
   `https://buy.stripe.com/xxx`）。
3. 付款頁面設定：
   - 收集 **Email**（收款頁強制要求客戶留電郵 → 呢個就係交付目的地）
   - 收款後的重定向頁（Optional）：可以留空，或指去你 landing page。

## 3. 將 Payment Link 放喺邊
- 放落 `pipeline/landing_page.html` 主要 CTA 掣；
- 請客付款 → Stripe 收款頁會截到佢嘅 email。

## 4. 連返去 `pipeline_runner.py`（收款 → 自動交付）

`pipeline_runner.py` 係個**狀態機**：收到付款確認先起行（pay-first 強制）。

**最低門檻做法（手動，今個版本已支援）：**
1. 客戶付款後，喺 Stripe Dashboard → **Payments** 攞個付款 ID（`pi_3xxx...`）。
2. 跑一次自動交付：
   ```bash
   cd /opt/data/seo-audit-business
   python3 pipeline/pipeline_runner.py "https://客戶網站.com" \
       --payment-ref "pi_3xxx" --customer-email "客戶@email.com"
   ```
3. 完成後輸出：
   - `output/order_status.json`（步驟狀態紀錄）
   - `pipeline/out/<domain>_<order_id>_seo_audit_report.pdf`（交付用 PDF；Round5 檔名含 order_id，避免同域覆蓋）
   - `output/deliveries/<order_id>_delivery.txt`（交付標記，寫低 pdf 路徑 + 收件人）

**自動化門檻（遲啲先做，需要 server + domain）：**
- Stripe Dashboard → **Developers → Webhooks**，加 endpoint 指向你 server：
  `POST https://你個domain/webhook/stripe`
- 用 `checkout.session.completed` / `payment_intent.succeeded` event →
  攞返 `client_reference_id`（= 你 order_id）＋ customer email →
  再 call `pipeline_runner.py --payment-ref <pi> --customer-email <email>`。
- （呢步連埋 email 實際發送一齊做，見下節。）

## 5. 接返 email 實際交付（而家係 placeholder）
`step_deliver()` 而家淨係寫 `deliveries/<order_id>_delivery.txt` 標記檔，
**未真係 send email**（要揀 provider：Mailgun / SendGrid / AWS SES / 你自己 SMTP）。
接法：喺 `pipeline_runner.py` 嘅 `step_deliver()` 加一個 `send_email(to, subject, pdf_path)`
函式就得 —— 佢會攞 `--customer-email` 同 pdf 路徑，附上 PDF 送出。

---

## 檢查清單（開單前）
- [ ] Stripe 帳號已開 + 銀行已連結
- [ ] Payment Link 已建（一次性）並放上 landing page —— **金額要同 `config.py` 嘅 `DEFAULT_PRICE_USD` 一致**（現時 US$79；改價改 config，landing 會自動跟）

### 🔴 @Yan 要接（正式收錢前）
- [ ] 接真 Stripe 付款驗證：`pipeline_runner.py` 嘅 `_verify_stripe_payment()` 用 Payment Ref 對 Stripe
      Retrieve（Checkout Session `payment_status=='paid'` 或 PaymentIntent `status=='succeeded'`）
      確認已收款先放行。**未接之前係 placeholder，預設當已收款 —— 收真錢前一定要改返真驗證。**
- [ ] 確認收款單價同 `config.DEFAULT_PRICE_USD` 一致，再開 Payment Link。
- [ ] 已用 `--payment-ref` 跑通一次（或用 `--dev` 試跑）
- [ ] email 發送已接上（住先可用手動送 PDF）
- [ ] 睇 `output/order_status.json` 確認全部 step = `done`

## 命令速記
```bash
# 正式單（pay-first，強制付款確認）
python3 pipeline/pipeline_runner.py <URL> --payment-ref <pi_xxx> --customer-email <email>

# 開發測試（跳過付款檢查，唔使 Stripe）
python3 pipeline/pipeline_runner.py <URL> --dev

# 冇俾 payment-ref 會即時 reject，唔會開始 crawl（狀態寫喺 order_status.json）
```