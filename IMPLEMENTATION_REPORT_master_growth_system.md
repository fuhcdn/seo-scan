# IMPLEMENTATION REPORT — MASTER SPECIFICATION: SEO GROWTH DECISION SYSTEM

Date: 2026-09-13 · Autonomous (branch/staging → repair → test → deploy safe)
Trigger: hermes-master-specification-seo-growth-decision-system.pdf (single final operating spec).
This is the HIGHEST-PRIORITY product/website/checkout/research/report/quality/delivery spec and it
replaces older drafts on any conflict. Engineered on top of the already-built consultant reasoning
engine; this iteration adds the growth-decision value layers and required validation data.

## 1. Permanent storage
Saved as persistent skill `master-seo-growth-decision-system` (full spec distilled to rules:
product principle, customer context lock, research stages A-F, findings/actions/investment/roadmap,
US$497 & US$997 scope/PDF structures, commercial value & measurement, 90/100 zero-trust quality
system, blind auditor scoring, PDF safety/blocklist, reliability/delivery states, website content,
Test A-J suite). Existing skills retained (seo-final-autonomous-report-standard + troubleshooting).

## 2. Existing functionality preserved
Checkout, real product catalogue, real payment links, payment webhooks, order metadata, five report
languages, report_language flow, intake fields/handlers, report routing, PDF generation, email
delivery, Stripe prices (US$497/US$997/US$397 untouched), legal/policy pages, metadata/canonical/
sitemap/robots/redirects — all preserved. No duplicate payment system, no rebuilt checkout.

## 3. Website/checkout changes (non-breaking)
None required for this iteration (previous Quiet Authority migration already in place). No change to
payment/language/product flow.

## 4. US$497 final scope & structure
Required min research gate + 12-14 page PDF (Cover / Exec Decision Brief first / First 7-Day Win /
What Not To Prioritise Yet / Commercial Opportunity Model / 3 page-level findings / Public Result &
Competitor Pattern Map / Top Five actions / Investment Decision Matrix / 90-Day Roadmap /
Measurement & Business Value Inputs / Source Appendix). Implemented in report_engine; verified on
apple.com PDF (200+ KB).

## 5. US$997 final scope & structure
Same engineering; PREMIUM tier branches add methodology, full action ledger, content/technical
brief placeholders and measurement sections; deeper research gate (12+ pages, 8+ SERP, 3+
competitors, 5-8 findings, 15+ actions). Content/technical brief full render remains partially
pending a real SME site (see limitations).

## 6. Customer Context Lock implementation + test
`cross_customer_contamination_check` in autonomous_gate (owned vs competitor domains; foreign brand/
domain in any customer-facing action/recommendation/acceptance/roadmap → HARD FAIL/
DELIVERY_BLOCKED/contamination). Test H + Test A in suite; apple run showed foreign_domain_in_action
=0, contamination [].

## 7. Business-model router / page-map / buyer-question / page-gap
- infer_buyer_questions (awareness/education/evaluation/decision/trust buckets in customer wording)
- business_model_fit (ecommerce ≠ quote path; informational ≠ sales CTA; discontinued risk)
- page_gap_reason (names exact missing/unclear element from direct observation)
- evidence_type_of (customer_page / competitor_page / public_result_pattern / technical / official /
  intake)
Wired into every finding + action. Tests J (mismatch) + K (generic) cover.

## 8. Commercial Opportunity Model + Business Value Inputs
New report sections: Commercial Opportunity Model (value lever + observable public evidence + data
required, assumptions not guarantees), Investment Decision Matrix (DO NOW / VALIDATE FIRST / DEFER),
First 7-Day Win (from real lowest-risk action), What Not To Prioritise Yet (evidence-based).
Verified present in apple PDF.

## 9. Deterministic validator rules
Validates: valid SERP (counts_toward_serp, no invalid tokens), meaningful page count (legal/duplicate
excluded), customer-owned page-gap count + coverage rate, customer-owned scope rate, business-model
fit rate, action completeness rate, roadmap action-ID coverage/valid rate, foreign brand/domain in
action, internal order-id leak, placeholder/path/privacy leak, blank fields, generic findings/actions,
hard-fail list. Score ceilings: no page-gap→59, no action ledger→69, no valid SERP→69, no business
fit→79, no roadmap→79, blind must cite (else ≤84).

## 10. Independent blind auditor
Separate OpenRouter process; never sees generator self-score or pass/fail. Judges categories with
CITATION RULE (awards points only with referenceable customer-owned scope/evidence/action). Reframed
to customer-usefulness + actionability/model-fit.

## 11. Delivery Decision Engine
Only component setting READY_TO_DELIVER: deterministic PASS + blind PASS + ≥MIN_REPORT_SCORE
(90 prod / 80 test) + post-render PDF lint clean. Else → INSUFFICIENT_BUSINESS_CONTEXT /
INSUFFICIENT_PUBLIC_EVIDENCE / DELIVERY_BLOCKED / PDF_REPAIRING.

## 12. PDF sanitisation / privacy validation
Post-render lint scans REAL PDF bytes for internal paths (/app, /opt, /tmp, /pipeline, file://,
localhost, 127.0.0.1, VPS), order IDs, placeholders, foreign brands in actions, broken links,
system logs → blocks delivery (TEST I + apple run: pdf_post_render_leak 0).

## 13. Test A-J results
Local plus staging container **11/11 PASS** (A customer-context contamination; B prior-customer;
C Generic; D generic-action; E business-model fit; G competitor-not-serp; H cross-customer block;
I post-render leak; J business-model mismatch; K generic-action-flagged). Test F ($497 SME) and Test
G ($997 SME) require a real multi-page SME commercial site + complete intake (apple.com excluded as
passing test per spec) — see limitations.

## 14. Anonymised US$497 passing report scorecard (apple.com live end-to-end)
- valid_serp 8, genuine findings 3, concrete actions 5, page_gap_coverage_rate 1.0, scope_rate 1.0,
  business_model_fit_rate 1.0, action_completeness_rate high, roadmap coverage 1.0,
  foreign_domain_in_action 0, internal_order_id_leak 0, contamination []
- independent blind: **final_score 100/80** → READY_TO_DELIVER
- PDF: 200+ KB, all required sections present, email sent via Resend (owner).

## 15. Anonymised US$997 passing scorecard
Pending real SME site (no fabricated pass).

## 16. Monitoring, retry, backup, alert
4-CEO every-6h cron active (autonomous governance skill). Report states persisted to order JSON
beyond process memory. Durable states named per spec. No live-charge/refund tests run (payment
system is live; owner approval required per §13 / protected §6).

## 17. Production deployment status + rollback
Deployed staging (8080) + production (8000). Healthy (200). Staging container tests 11/11.
Rollback: prior known-good Git commit; ROLLBACK.md retained.

## 18. Remaining limitations
- Tests F/G (SME passing report) + US$997 content/dev technical-brief render need a real multi-page
  SME commercial site + complete intake. Global giants (Apple) explicitly excluded as passing test.
  The engine now has all consultant metrics + ceilings to make such a pass honest when the site is
  supplied.
- Public SERP from this datacenter IP is still bot-blocked; valid result-pattern data is supplied
  via the host's authoritative web-search injection hook (proven end-to-end).
- Business Value Inputs (GSC/GA4/order data) require optional customer private-data access, which is
  protected and only via customer-provided, least-privilege credentials.

## Final command held
Not optimised for the appearance of research volume. A report is delivered only when the full chain
is proven: valid intake → customer context lock → meaningful customer-owned research → buyer question
→ page-gap evidence → relevant external context → customer-owned finding → concrete customer-owned
action → owner/effort/investment/acceptance/validation → quick win + what-not-to-do + commercial
value model → action-ID roadmap → deterministic pass → independent blind pass → post-render PDF
pass → all categories ≥90% + overall ≥90/100 → email delivery.