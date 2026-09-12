# ROLLBACK — seoscanaudit.com Baseline & Recovery

本文件係 seoscanaudit.com 喺開始任何 redesign 之前嘅 **Rollback / Restore 操作手冊**。
所有 client-facing 功能（付款、checkout、五語言、report automation、PDF、email、database/orders/reports）完成 baseline backup 並驗證後先可以開始 redesign。

## 1. Baseline identifiers（已驗證）

| 項 | 值 |
|---|---|
| Baseline Git commit SHA | `9f483c335ab79552c308a9960a15e5e16d51168b` |
| Baseline Git tag / release | `baseline-good-before-quiet-authority-redesign-20260912-1900` |
| Baseline 建立時間 | `2026-09-12 19:00–19:05 UTC` |
| Production branch | `master` |
| Redesign branch | `redesign/quiet-authority` |
| Remote repository | `https://github.com/fuhcdn/seo-scan.git`（已確認 push 成功；token 不記錄於此）|
| Staging environment | 未建立（尚未 deploy staging——design 開始前需建立）|

## 2. Backup identifiers

| Backup | Identifier / 位置 |
|---|---|
| Database backup | **無獨立 database** —— 訂單/狀態儲存喺 JSON files（`output/order_*.json`），已含喺 `runtime-data.tar.gz` |
| Uploaded-files backup | `reports.tar.gz`（deployed `/deploy/seo/app/pipeline/out/` 內 PDF/HTML reports + legal）|
| Reports / report-job data | `runtime-data.tar.gz`（`output/` orders + deliveries）+ `reports.tar.gz` |
| Configuration backup | `config.tar.gz`（docker-compose.yml、Dockerfile、config.py、product_catalog.py、generate_languages.py）|
| Full deployed-code backup | `deployed-code.tar.gz`（`/deploy/seo/app/` pipeline + 部署設定）|
| 全部 backup 儲存位置 | **本地** `/opt/data/backups/seo-scan/20260912-1900/` ＋ **VPS** `/backups/seo-scan/20260912-1900/` （獨立於 production `/deploy`）|

## 3. Environment / secrets 儲存位置

**Secrets 永不入 Git。** 記錄名稱同儲存位置（唔印值）：

| Secret | 位置 |
|---|---|
| STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET / PRICE_* / SMTP* / RESEND_API_KEY / EMAIL_* / PUBLIC_URL 等 | `VPS /deploy/seo/app/secrets.env`（production 運行用）|
| 加密備份 | `VPS /backups/secrets/secrets.env`（chmod 600）|
| OPENROUTER_API_KEY | `local /opt/data/.env` |
| GitHub token | `local .git-token`（gitignored）|
| Cloudflare token | `local .cloudflare_token`（gitignored）|

完整 secret-name 清單：`/opt/data/backups/seo-scan/20260912-1900/secret-names.txt`（只有名稱，無值）。

## 4. 現有 deployment 方法

- **宿主**：VPS `187.53.137.215`（srv1970379.hstgr.cloud），Ubuntu + Docker 29.7.2 + Traefik(docker provider)
- **部署目錄**：`/deploy/seo/app/`
- **Container**：`app-seo-scan-1`（port 8000），docker-compose（Traefik labels: Host `seoscanaudit.com`, entrypoints websecure, certresolver letsencrypt）
- **網域**：`seoscanaudit.com` → DNS 指 VPS (Cloudflare proxy 已停，origin 直達)
- **SSH 部署**：paramiko（venv `/tmp/deployenv`），root password auth
- **秘密載入**：`secrets.env`（docker-compose `env_file`）+ local `/opt/data/.env`
- **重建流程**：上傳 files → `docker compose up -d --build` → health `/health` OK

## 5. Rollback steps（還原）

### A. Website code rollback（design 出錯時）
1. 切返 baseline tag：`git checkout baseline-good-before-quiet-authority-redesign-20260912-1900`
2. 由該 tag 打包 code：`git archive baseline-good-before-quiet-authority-redesign-20260912-1900 | tar -x -C /tmp/rollback/`
3. 上傳 `/tmp/rollback/pipeline/` → `/deploy/seo/app/pipeline/`（只覆蓋 code，唔郁 secrets.env）
4. `cd /deploy/seo/app && docker compose up -d --build`
5. 等待健康：`curl https://seoscanaudit.com/health` → `{"ok":true}`
6. **唔好** destructive reset production branch / 重寫 shared history —— 用 revert 或新 commit。

### B. Database / uploaded-files rollback
- 狀態數據（orders/reports）喺 JSON，restore：
  1. 先備份「壞咗嘅 production state」：`cp -r /docker/hermes-agent-e41b/data/seo-audit-business/output /backups/production-broken-$(date +%s)/`
  2. 由 baseline 還原：解 `runtime-data.tar.gz` + `reports.tar.gz` 覆蓋返 `output/` 同 `pipeline/out/`
  3. 確認 customer/order/report data 完整（檢查 order_*.json 可讀、報告 PDF 存在）
- **不可無 backup 就 overwrite production database。**（本系統無獨立 DB，全部 JSON，風險低。）

### C. Payment / checkout rollback
還原後驗證：
- Payment links 可建（POST `/api/create-checkout` 返回 `checkout_session_id`）
- Product IDs 無變（`prod_seo_opportunity` / `prod_seo_growth`）
- 價格無變（ENTRY US$497 / PREMIUM US$997，由 `config.py` + secrets PRICE_*）
- Webhook `/webhook/stripe` reachable（POST 200）
- Payment-success flow：`/success?order=...` → 200
- Checkout → order metadata 完整

### D. Language system rollback
還原後驗證五語言齊全 + language selector + internal values 無變 + report_language 由 checkout → order → report job → PDF → delivery 全程貫穿：
- `/` `/en` `/zh-Hant` `/zh-Hans` `/ja` `/es` 全部 200
- internal language values 保持 `en, zh-Hant, zh-Hans, ja, es`

### E. Report workflow rollback
還原後驗證：ENTRY routing / PREMIUM routing / AI research / PDF gen / email confirmation / report delivery 全部 done（跑一次 dummy order 全鏈 status=done）。

## 6. Restore 後 verification checklist
- [ ] `https://seoscanaudit.com` 200 + `/health` ok
- [ ] 5 語言頁 200
- [ ] `/api/scan` POST 200（真分）
- [ ] `/api/create-checkout` 建到 session（$497/$997）
- [ ] `/legal/{privacy,terms,disclaimer,refund,en/*}` 200
- [ ] `/success?order=x` 200
- [ ] orders/reports JSON 可讀、PDF 存在
- [ ] 無 console errors / 無 502 on core routes

## 7. 重要 integration
- **Stripe**（live）：checkout、webhook `/webhook/stripe`、prices $397/$497/$997
- **Resend**（email delivery，EMAIL_BACKEND=resend）
- **OpenRouter**（AI 評分，fallback rule-based）
- **Traefik + Let's Encrypt**（HTTPS）
- **Cloudflare**（DNS；注意：SSL 需 host 精確，pinned fetch 已處理）

## 8. Emergency dependency / 存取
- VPS root SSH：password（用戶提供，值不記錄於此）
- Docker compose rebuild 係唯一 deploy 方法
- 無 cron job 依賴於 redeploy（除咗 OpenRouter balance 通知 cron，與網站無關）

## 9. Consistent principle（設計紅線）
Redesign 只改**視覺層**：warm-white 背景、深海軍藍字、靛藍 CTA、白色 cards、Quiet Authority typography。
**絕不更改**：product IDs、價格、pricing logic、checkout URL、payment links、payment provider、webhooks、payment-success flow、order metadata、五語言、language selector、internal language values、report_language field、URL intake、customer/company intake、form validation、report routing、lower/higher-tier logic、AI research、PDF gen、email、delivery、database、APIs、env vars、integrations、analytics、SEO metadata、canonical、sitemap、robots、redirects、privacy/terms/contact。
唔准 hard-code 價、呃客 fake data、claim 未存在 access。

## 10. 未完成 / 風險
- **Staging environment 未建立** —— design 開始前必須建（見 REDESIGN checklist）
- **Known baseline limitation**：`/robots.txt` 同 `/sitemap.xml` **未 serve**（server.py 無對應 route，回 404 JSON）。呢個係 baseline 已有狀態（非 regression）。屬「redesign 可改嘅 SEO metadata 改善項」，但要喺 staging 做，唔好喺 baseline 直接加。
- 現有 session 冇 database，restore 單純 JSON 覆蓋，風險低但須先備份「壞 state」
- 有 `CHECKOUT_TEST_PRICE`（$0.5 測試 mode）喺 secrets，屬正考慮中；正式價應轉返（見 baseline 決定）