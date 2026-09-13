# SYSTEM MAP — 真實資料流（已驗證）

## Production flow（客戶真實經歷）
```
客戶 → https://seoscanaudit.com (Cloudflare+Traefik+VPS 187.53.137.215)
  → landing_*.html (5語言,免費 scan 入口)
  → POST /api/scan → seo_crawler.run() (免費診斷:總分+Top5)
  → POST /api/order (intake 8欄,建 order_<id>.json)
  → POST /api/create-checkout → stripe_lib.create_checkout_session
      → Stripe Checkout (price id 由 product_catalog→secrets.env env pointer)
  → Stripe webhook POST /webhook/stripe → verify_webhook_signature
      → get_session_paid (re-retrieve確認 paid)
  → spawn_delivery_pipeline() → pipeline_runner.py (detached subprocess)
      ├─ step_research: research.py (SERP injection hook: _serp_inject_<order>.json)
      ├─ crawl: seo_crawler.py (SSRF 擋、rate-limit)
      ├─ quality_gate.py + autonomous_gate.py (90 硬閘,角色分離 blind audit)
      ├─ report: report_engine.py → seo_report_template.py → html_to_pdf
      │    (Chromium --no-pdf-header-footer)
      ├─ post-render: pdf_scanner.py (zlib) ← 舊,將被 canonical 取代
      └─ step_deliver:
           ├─ verified_pdf_delivery.prepare_verified_artifact()
           │    (pypdf exact-artifact scan + .for-email.pdf + 3-way SHA)
           │    失敗 → DELIVERY_BLOCKED,唔寄
           └─ backend: resend API 或 _smtp_send() — attach 嘅係 verified artifact
  → 客戶收到 PDF email
  → GET /api/status?order_id= (order_<id>.json 狀態)
```

## Golden/staging flow（品質引擎,evidence_v1）
```
gates/evidence_report_runner.py --customer <name>
  ├─ GATE1 structured pages (tests/fixtures/gate1_<customer>_pages.py)
  ├─ GATE2 evidence cards (tests/fixtures/golden_evidence_cards_<customer>.json)
  ├─ GATE3 actions from cards (investment_status single source)
  ├─ GATE4 deterministic + external OpenRouter semantic audit
  │    (auditor outage → fail-closed,唔會 PASS)
  ├─ build_report (journey/roadmap/matrix/prep-plan 全部 data-driven)
  ├─ validators: business-logic contamination / roadmap action-data /
  │    priority consistency / field-empty / truncated
  └─ GATE5 canonical delivery: verified_pdf_delivery
       (pypdf scan + .for-email.pdf + 3-way SHA + pre-send recheck)
```

## Feature flag
`REPORT_PIPELINE_VERSION=legacy | evidence_v1`
- 記錄喺 delivery record;不影響 routing(現時兩邊都行 canonical delivery service)
- production 預設 legacy 交付路徑;evidence_v1 全接入屬 E2E 後嘅 owner 決定

## Key shared modules
| Module | 作用 |
|---|---|
| pipeline/verified_pdf_delivery.py | 唯一 canonical verify+send service |
| pipeline/pipeline_runner.py | production 交付 orchestrator |
| pipeline/server.py | HTTP 入口 (scan/order/checkout/webhook/status) |
| pipeline/stripe_lib.py | Stripe API wrapper |
| pipeline/product_catalog.py | 產品→tier→price env pointer |
| pipeline/quality_gate.py / autonomous_gate.py | 90閘 + blind audit + decide_delivery |
| pipeline/report_engine.py / seo_report_template.py | report 生成+render |
| gates/gate_pipeline.py / evidence_report_runner.py | 5-gate evidence-led engine |
| tests/fixtures/ | Golden A/B 卡+頁+scorecard |

## Storage
- 訂單:output/order_<id>.json(無 database)
- 交付 marker:output/deliveries/<order>_delivery.txt
- delivery record:*.delivery-record.json(gitignored)
- 報告 PDF:pipeline/out/ 或 /app/gates/out/

## Monitoring(現狀:薄弱)
- 淨得 /health endpoint
- 無 uptime probe / 告警 / log aggregation / watchdog(見 RISK_REGISTER)
