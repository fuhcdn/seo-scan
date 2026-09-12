# Yan 一次性提供清單（4 CEO 整合版）
> 整合 4 CEO（Bezos收款 / Jobs交付 / Musk技術 / Jensen合規）盤點出嘅全部「Yan 要提供」項，
> 令 Yan 可以一次過準備。覆蓋 first-dollar 全鏈：付款 → AI → email → host → 合規。
> 依賴檔案：`pipeline/STRIPE_SETUP_guide.md`、`troubleshoot_追蹤.md`、`pipeline/legal/`

## 你要提供嘅清單（一次過準備）

### 一、收款 (Stripe)
1. ❗🔶 開真 Stripe 帳號 + 過 KYC - dashboard.stripe.com/register，揀香港做所在地，綁銀行戶口收錢 - 完成後攞 `sk_live` secret key
2. ❗ 建 US$79 一次性 Product + Checkout Session/Payment Link - Stripe Dashboard → Products → 金額 `US$79.00`（要同 `config.DEFAULT_PRICE_USD` 一致） - 條 `buy.stripe.com` link 貼返落 landing page + `/api/create-checkout`
3. ❗ 建 webhook + 攞簽名 secret - Stripe → Developers → Webhooks，endpoint `POST https://你個domain/webhook/stripe`，event = `checkout.session.completed`/`payment_intent.succeeded` - 攞 `STRIPE_WEBHOOK_SECRET`（唔准用 placeholder，CEO 明文要求真簽名驗證）

### 二、交付 (Email/Host)
4. ❗🔶 真 email sender + EMAIL_FROM - 揀 Resend / SendGrid / AWS SES / Gmail app password，開帳號 - 填入 `EMAIL_BACKEND`、`SMTP_HOST`、`SMTP_PORT`、`EMAIL_FROM`
5. ❗ 域名 + DNS（SPF/DKIM） - 買個 domain，喺 DNS 加 SPF/DKIM record（先至唔入 spam，Email 可以寄出 - 呢個係 email 交付嘅隱藏前提）
6. ❗🔶 Host server.py 上公開 URL - 而家 server 只喺 localhost，要 host（Render/Railway/VPS）先俾人入 - 俾返公開 `https://...` URL + `HOST`/`PORT`

### 三、技術 (API)
7. 🔶 確認 OpenRouter key 正常 - `OPENROUTER_API_KEY`（AI 評分而家 fallback 緊） - check key 未過期、balance 夠

### 四、合規/營運
8. 🔶 收款實體/法律身份 + 發票模板 - 諗定用咩身份收款（個人定公司）→ 準備發票/invoice 模板（Jensen 合規要求）
9. 🔶 Legal 5 份過目 + 授權 - `pipeline/legal/` 已寫好：ToS、私隱(PDPO)、授權書、退款政策、免責 - Yan 過一眼、確定退款政策立場（自動 vs 人手覆核）先可上線
10. ❗ 第一單真支付 + 交付人工覆核 - 真 Stripe 收一筆 US$79 → 過程行通 → 出 PDF → email 到貨 → `/api/status` 全 done → 人手睇一次（launch gate，缺呢個唔算「賺到錢」）

## 緊要度標記
❗=阻塞（冇佢冇得收錢）　🔶=要開帳號　⚪=可後補

備註：免費 scan 界線（免費只俾總分+top3-5 標題，fix 全鎖 US$79 先有）— 4 CEO 已拍板，唔使 Yan 再決定。