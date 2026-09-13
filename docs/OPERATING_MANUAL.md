# OPERATING MANUAL — seoscanaudit.com

## 產品目的
自動化、evidence-led SEO Growth Decision reports 俾靠網站帶嚟 sales/quote/booking/enquiry/call/trial/subscription 嘅中小企。
- US$497 — SEO Opportunity Diagnostic（ENTRY）
- US$997 — SEO Growth Blueprint（PREMIUM,未有 production implementation,唔好開始）
- 首 50 早鳥 US$397
- 5 語言:en / es / ja / zh-Hans / zh-Hant
- 交付目標:24 小時內 email PDF;production-ready 後毋需 routine human review

## 不可變規則（違反 = 立即停止）
1. **付款保護**:付款斷鏈已修。未經 Yan 批准,禁止改 payment/Stripe/price/checkout/webhook/refund/legal/domain/DNS/brand。
2. **品質底線**:每 semantic category ≥90% + overall ≥90/100 + 零 hard fail 先 READY_TO_DELIVER;<90 只可以 STAGING_TEST_PASS,永不可交付。
3. **誠實**:零 fabricated facts/rank/traffic/revenue;證據唔夠就出 insufficient-evidence 誠實文件;唔識寫就係「做不到」,唔准講「做不到」係一個 answer。任何 hard fail = DELIVERY_BLOCKED。
4. **canonical flow**:任何 PDF 只可以經 `pipeline/verified_pdf_delivery.py` verify + send。禁止 render A→scan B→email C。禁止第三套 sender/renderer。
5. **Apple Imprints = Golden Reference A,FROZEN**;只作 shared-change regression fixture。
6. **高風險先批準**:真客戶 email、outbound marketing、paid ads、真退款、法律條款、品牌、定價、public promises —— 全部要先 approval request。
7. **Secrets**:永不出現喺 chat/Git/PDF/docs/memory。發現即停,只回覆「發現敏感資料,已停止處理」。

## 日常運作
- Staging:VPS `/deploy/seo-staging/`(container `seo-staging-seo-staging-1`,port 8080)
- Production:VPS `/deploy/seo/app/`(container `app-seo-scan-1`,port 8000)
- Deploy 方式:SFTP bundle → `docker compose up -d --build`(留意 container rebuild 會重置手動 pip install;依賴以 requirements.txt 為準,pypdf>=6.0.0)
- Feature flag:`REPORT_PIPELINE_VERSION=legacy | evidence_v1`(delivery record 會記錄;production 預設 legacy,直至 E2E 過)
- 測試:`.venv/bin/python tests/test_autonomous_quality_gate.py`(30 tests)

## 人工 escalation boundary(必須搵 Yan)
付款差額、退款請求、legal page 錯誤、domain/DNS 異常、真客戶投訴、任何 DELIVERY_BLOCKED 於真實訂單、Stripe webhook 連續失敗。

## 詳細參照
- SYSTEM_MAP.md — 資料流
- QUALITY_STANDARD.md — 品質/hard fail
- PRODUCTION_RUNBOOK.md — deploy/rollback/incident
- RISK_REGISTER.md — 現存風險
- BACKLOG.md — 未完成工作
