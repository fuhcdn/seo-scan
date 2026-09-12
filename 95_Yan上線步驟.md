# 🔧 Yan 專屬：上線前要你親手做嘅 4 樣（step-by-step）

> 目標：seoscanaudit.com 由「HTTP 530 未上線」→ 收第一筆真 US$497。
> 呢 4 樣只有你（帳號持有人）做得到，我無權限。做完返嚟話我知，我就落 goal 一直跑到完成。

---

## ✅ 你已經確認咗
- 定價：正價 US$497 / Growth US$997 / 首50早鳥 US$397（只宣傳、唔顯示已售數）
- 退款：交付前可全退 / 交付後免費重審
- 收款實體：個人
- Stripe：已有 live key + 過咗 KYC
- Hosting：你有 VPS（未 config）
- 5語言：英＋繁中＋簡中＋日＋西，一次過齊先上
- v1：即刻入個性化引擎 + 質量 Gate

---

## 🔴 做緊 ＃1 — Stripe：建 Product + Webhook（約 15 分鐘）

**登入 https://dashboard.stripe.com （已經有 live key 個帳號）**

### 1.1 建 3 個 Product（Products → 加 Product）
| Product 名 | Price（一筆過） | 用途 |
|---|---|---|
| `AI SEO Audit`（正價） | **US$497.00** | 主力 |
| `AI SEO Audit Growth` | **US$997.00** | 進階 |
| `AI SEO Audit 早鳥` | **US$397.00** | 首50早鳥 |

每個建完記低 price ID（形如 `price_1xxxx`），話我知。

**收款頁必須：** 強制收集客戶 **email**（付款設定入面開，呢個係交付目的）

### 1.2 建 Webhook（Developers → Webhooks → Add endpoint）
- Endpoint URL：`https://seoscanaudit.com/webhook/stripe`
- 揀事件：`checkout.session.completed`（勾埋 `payment_intent.succeeded` 更穩）
- 建完後會俾你一個 **Webhook Signing Secret**（形如 `whsec_xxx`）→ 抄低話我知

### 1.3 唔好做
- ❌ 唔好用 $79 / $99 / 舊 Payment Link
- ✅ 就係用上面 3 個新 price

---

## 🔴 做緊 ＃2 — VPS：開網站（約 20-30 分鐘）

### 2.1 確認 VPS 有：
- **SSH 權限**（登入到）
- **公網 IP**（形如 `123.45.67.89`）
- 可開 **port 80/443**

### 2.2 DNS 指向（喺你買 seoscanaudit.com 個 registrar / Cloudflare 控制台）
加一條 **A record**：
```
Name:  @     |  Type:  A     |  Value: <你VPS個IP>   |  TTL: 自動
Name:  www   |  Type:  A     |  Value: <你VPS個IP>   |  TTL: 自動
```
（如果你用緊 Cloudflare：**橙雲 proxy 暫時設灰雲/DNS only**，等上線成功先開橙雲，唔係又 mud 530）

### 2.3 開 SSH 話我知
- 我幫你喺 VPS 度裝 Python + 上埋 `server.py`（我 agent 可以做）
- 你需要俾我：**IP + SSH username + 點入**（port/key/password 點講）

> ⚠️ **只要你有 SSH 權限，部署由我做。** 你要做嘅只係 Drop 個 SSH 權限俾我 + set DNS。

---

## 🔴 做緊 ＃3 — Email 發送（約 10-15 分鐘）

報告要 email 送去客度。揀其中一個（最易 → 最難）：

| Provider | 幾易 | 價 | EMAIL_SENDER |
|---|---|---|---|
| **Resend**（recommended） | 最易 | 首 3,000 封免費 | 你網域 email |
| Gmail app password | 易 | $0 | 你 gmail |
| AWS SES | 中 | $0 起 | 你網域 email |

開完攞到：
- **SMTP_HOST / PORT / USER / PASSWORD**（或 Resend API key）
- **EMAIL_FROM**（建議 `report@seoscanaudit.com`）
- 如果 EMAIL_FROM 用你自訂網域 → 要喺 DNS 加 **SPF + DKIM** record（provider 會話你知加咩）

全部抄低話我知。

---

## 🔴 做緊 ＃4 — OpenRouter key 確認（5 分鐘）

你之前 /opt/data/.env 有 OpenRouter key，但我唔知佢:
- 仲有冇 credit（上次用剩 ~$21）
- 係咪有效

**你撳一次睇下:** 攞到個 `.env` 位置或者確認 key 有效即可。如果唔肯定，我幫你 check。

---

## 📝 搞掂之後——你話我知呢啲嘢

做完 1-4，將以下資料交返俾我（我用嚟接通+落 code）：
1. Stripe 3 個 price ID（497 / 997 / 397）
2. Stripe Webhook Signing Secret（whsec_xxx）
3. VPS 嘅 IP + SSH 登入方法
4. Email 有SMTP/Resend key + EMAIL_FROM
5. OpenRouter key 確認

**交齊我就落 goal，一路跑到「4 CEO 一致：可賣、80% 三日內第一單」為止。**
（如果你交唔齊某樣，話我知邊樣未有，我睇下可唔可以繞過或後補。）