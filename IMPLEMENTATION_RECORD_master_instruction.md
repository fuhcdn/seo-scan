# Implementation Record — HERMES MASTER INSTRUCTION (SEO reports)

Date: 2026-09-12 · Project: /opt/data/seo-audit-business/pipeline/

Source standard registered at:
- /opt/data/seo-audit-business/skills/hermes-single-master-instruction-seo-reports.pdf (源檔)
- Skill `seo-report-master-standard` (SKILL.md + references/master-instruction-fulltext.md)

## Files changed / added
- `product_catalog.py` (NEW) — 內部產品目錄 + ENTRY/PREMIUM 層級路由（single source of truth）。
  Two tiers: `prod_seo_opportunity` → ENTRY_REPORT, `prod_seo_growth` → PREMIUM_REPORT.
  Five configured languages: en, zh-Hant, zh-Hans, ja, es. Never hard-codes price value
  (reads config + PRICE_* env).
- `research.py` (NEW) — 公開網絡研究 + 證據帳本 (Evidence Ledger) + public-data limits (B3).
- `report_engine.py` (NEW) — 兩級報告生成器（ENTRY 10 sections / PREMIUM 15 sections,
  含 premium-only Method/Confidence table + Prioritized Action Ledger + Content Intelligence
  + Measurement Plan）+ QA gate (run_qa, Part I) + INSUFFICIENT_PUBLIC_EVIDENCE fail-safe。
- `server.py` (MOD) — /api/order 硬 gate：selected_product_id 存在（PRODUCT_MAPPING_ERROR）、
  report_language ∈ 5 語言（INVALID_LANGUAGE）、company_name、primary_business_goal；
  訂單存 report_language/selected_product_id/report_tier/company_name/business 欄位；
  /api/create-checkout 由 order file 讀 product → 路由對應 price；
  /webhook/stripe spawn 攜帶 product/language/tier/business 落 pipeline。
- `stripe_lib.py` (MOD) — get_price_id(selected_product_id)/create_checkout_session 支援
  product 路由 + metadata[selected_product_id]。
- `pipeline_runner.py` (MOD) — 新增 research step (證據帳本)、evidence-led tier report
  （step_report 用 report_engine + QA）、report_language 貫穿；email subject/body 按語言。

## Fields added (order checkouts / report job)
- report_language (req, 5 languages) · selected_product_id (req) · company_name (req)
- primary_business_goal (req: leads/sales-revenue/qualified-traffic/local-enquiries/subscriptions/other)
- primary_market_or_service_area (req) · main_products_or_services (req)
- known_competitors (opt, ≤5) · notes_or_constraints (opt)
- 內部導出：report_tier (ENTRY/PREMIUM), report_skill, evidence_count, research_path

## Route mapping
- GET /success?order=... (付款成功頁) · GET /health
- POST /api/order (validate + store + tier resolve) · POST /api/create-checkout (product→price)
- POST /webhook/stripe (真 verify + spawn w/ full order metadata)
- GET /api/status?order_id=... · GET /legal/* (多語言)

## Trigger
Stripe checkout.session.completed webhook → 真 verify payment_status==paid →
spawn `pipeline_runner.py <url> --order-id --product-id --report-language …`
→ research → findings → tier report → QA → PDF → email(Resend, 按報告語言).

## PDF delivery
Chromium HTML→PDF (report_engine.html_to_pdf → seo_report_template.html_to_pdf)。
PDF title=company+product; HTML lang=report_language; email subject/body 按語言。

## Test outcomes (dummy lower-tier + dummy higher-tier)
1. **ENTRY dummy** (ORD-ENTRY-TEST, prod_seo_opportunity, en):
   research 3 evidence items; report 10 sections, 0 CJK, QA passed, PDF 138KB. ✓
2. **PREMIUM dummy** (ORD-PREM-TEST, prod_seo_growth, en):
   report 15 sections (includes Methodology/Confidence, Prioritized Action Ledger,
   Content Intelligence, Measurement Plan), 0 CJK, QA passed, PDF 164KB. ✓
3. **Language dummy** (ORD-ZH-TEST, zh-Hant): framework labels all Traditional Chinese
   (執行摘要/範圍、方法/來源附錄/90 天行動計劃), lang=zh-Hant, proper CJK. ✓
4. **Checkout validation** (unit): missing product→MISSING_PRODUCT; invalid lang→INVALID_LANGUAGE;
   invalid goal→INVALID_BUSINESS_GOAL; unknown product→PRODUCT_MAPPING_ERROR; valid→200 + tier. ✓

## Blocked / further work
- 未 live 部署（container rebuild 未跑）——本記錄尚未 deploy 去 VPS。
- Search Console / GA4 / CRM 存取未有 → 報告以 public-web 為基礎，validation items 明確列出。
- Stage C SERP research 現時 research.py 有介面 (merge_serp) 但未接真實 web_search；現報告
  「No SERP observations」誠實標示。要接 web_search 先做到完整 SERP/competitive section。
- entry/premium 行動深度現由 evidence count 決定（deterministic）；AI 補強（LLM 評分）仍
  屬 fallback（KeyError 未修）。建議下一步接 web_search + 修 AI scoring。
- 付款鏈仍受 Yan 指示唔郁：CHECKOUT_TEST_PRICE 喺 production secrets 存在（測試中）。