# REPAIR REPORT — Apple PDF rejected (8 observable failures), all fixed + enforced

Date: 2026-09-13 · Scope: Master Specification compliance. Apple PDF treated as a FAILED
staging test (not ready, not emailed, not a 90+ reference). Below: validator rules added,
proof the old-style PDF is blocked, clean regenerated staging report, scorecard, final
PDF scanner output. No self-declared 90/100 score — all scores are from the independent
blind auditor (OpenRouter, separate process) on its own.

## 1. Exact validator rules added (autonomous_gate.py deterministic_validate)
Each maps to one of your 8 reasons. All are HARD FAIL -> DELIVERY_BLOCKED.

- R1 INTERNAL_PATH_LEAK: post-render PDF scanner now DECOMPRESSES FlateDecode streams and
  scans visible text + metadata + headers/footers + hyperlink annotations (/URI, /Launch,
  /FileSpec, /F). The exact string `file:///app/pipeline/out/SEO-Opportunity-Diagnostic-
  apple-2026-09-13.html` matches `file://` + `/app/pipeline` + `/pipeline/` -> HARD_FAIL
  INTERNAL_PATH_LEAK -> DELIVERY_BLOCKED. (Old scanner read raw PDF bytes, which are
  compressed, so it missed the string -> the false-negative you caught.)
- R2 invalid_action_scope: any action whose customer_owned_scope / affected_scope / title
  contains `serp_result_pattern` / `result_pattern` / ` serp` -> invalid_action_scope
  HARD_FAIL. + generator fix: SERP findings now build their action against the actual
  customer-owned URL (from Customer Context Lock / page map), never the evidence class.
- R3 missing page-gap proof: every finding must carry a page_gap (exact customer URL ->
  direct observation -> buyer question -> specific missing element). page_gap_coverage_rate
  <1 -> action_completeness / page-gap HARD_FAIL. Generator builds page_gap from direct
  observation + customer-owned scope.
- R4 generic_mechanism: exact strings "affects the likelihood that visitors progress toward
  the stated business goal", "this observation at", "supporting the [stated] goal" in any
  finding/action business_reason|claim -> generic_mechanism HARD_FAIL. Generator fallback
  rewritten to name the buyer step + missing element + offer.
- R5 business_model_mismatch: quote path for a buy-model customer, forcing sales-CTA on an
  informational query, etc. -> action REJECTED at generator (business_model_fit()) and, at
  validator, business_model_fit_rate < 0.5 -> ceiling 79 (test J/O prove reject).
- R6 current_offer_verification: no material action for a named product without
  customer-owned/current availability; discontinued/unverified -> downgraded hypothesis or
  rejected (test E). tracked as unverified_current_offer_count.
- R7 generic_definition_of_done: "Implement the action and confirm via public source" is
  NOT acceptance. Generator now writes: done = change live on customer page + QA pass +
  owner; validation = first measurable signal (CTA clicks/impressions) + review window
  (30 days) + scale-only-after-two-positive-reviews. Validator: action_completeness_rate<1
  (needs customer-owned scope + owner + acceptance + validation on EVERY action) or
  "confirm via public source" -> HARD_FAIL.
- R8 evidence_classification: SERP/result-pattern observations are INTERPRETATIONS, not
  standalone FACT. Findings + appendix now relabel serp evidence to INFERENCE. Direct
  customer-page/competitor observations keep FACT. Store query+timestamp+parsed-result+
  interpretation+limitation separately (already separate fields in the SERP ledger item).

## 2. Test output proving the old Apple PDF is blocked
Two levels — (a) the exact user string injected into a real Chromium-rendered PDF, scanned
by the production pipeline scanner; (b) unit tests L/M/N/P in the suite + full A-P.

(a) Real rendered PDF containing `file:///app/pipeline/out/SEO-Opportunity-Diagnostic-apple-2026-09-13.html`:
    render True
    blocked: True
    hard_fail: INTERNAL_PATH_LEAK
    hits: [file:///app x2, file:// x2, /app/pipeline x2, /pipeline/ x2]
    -> DELIVERY_BLOCKED.

(b) Test suite (local + staging container), 16/16 PASS, incl. new regressions:
    L-invalid-action-scope-blocked -> hard_fail ['invalid_action_scope']   (R2)
    M-generic-mechanism-blocked   -> hard_fail ['generic_mechanism(1)']    (R4)
    N-generic-done-blocked        -> hard_fail ['generic_definition_of_done(1)'] (R7)
    O-business-model-mismatch     -> quote path rejected                   (R5)
    P-pdf-scanner-file-url-blocked-> blocked + INTERNAL_PATH_LEAK         (R1)
    (A-I existing checks still pass)

## 3. Clean regenerated staging report (only if independently passes)
Staging, apple.com, ENTRY, current intake + injected valid SERP. Independent blind auditor
scored it itself; no generator self-score:
    delivery_state  READY_TO_DELIVER
    final_score     90/80  (independent blind auditor; >=80 test gate, >=90 would pass prod gate)
    hard_fail_list  []
    concrete_action_count  5
    valid_serp_observation_count  8
    genuine_finding_count  3
    generic_mechanism_count  0
    generic_dod_count  0
    invalid_action_scope  none
    customer_owned_page_gap_count  3 (page_gap_coverage_rate 1.0)
    customer_owned_scope_rate  1.0
    business_model_fit_rate  1.0
    action_completeness_rate  1.0
    pdf_post_render_leak  0, pdf_post_render_leak_hits []
    pdf_final_artifact_contamination []
    -> was NOT emailed (staging used a test recipient; Resend correctly rejected the
       example.com test address, proving nothing was delivered during the test).

## 4. Scorecard with evidence (independent blind auditor per category, this run)
    final_score 90/80, delivery_reasons ["deterministic PASS + blind 90/80 PASS"]
    Category evidence (from rendered report + validator counts):
      A evidence integrity: 20 (all material facts have direct source; SERP = INFERENCE)
      B research completeness: valid_serp 8, meaningful pages 12, competitor 3
      C strategic value: 3 genuine customer-owned decisions with mechanisms
      D actionability: 5 actions, all customer-owned scope + owner + acceptance + validation
      E structure: quick-win + investment matrix + commercial model + what-not present
      F pdf/language/privacy: pdf_post_render_leak 0, contamination [], filename clean

## 5. Final PDF scanner output (on the regenerated clean report)
    pdf_post_render_leak 0        (decompressed text + metadata + hyperlinks scanned)
    pdf_post_render_leak_hits []
    pdf_final_artifact_contamination []
    Scanner self-check on crafted leak PDF: blocked True, INTERNAL_PATH_LEAK.
    (On the OLD leaked PDF style: blocked True — see §2.)

## 6. No self-declared 90/100
The generator does not set a pass/fail or final score. All scores above are the independent
blind auditor's (OpenRouter, separate process, never shown the generator's self-assessment).
Delivery Decision Engine is the only component that can set READY_TO_DELIVER.

## Deployment / rollback
Deployed to staging (8080) + production (8000). Staging container tests 16/16. Production
healthy (200). Rollback: prior known-good Git commit (fb837f5). Pushed origin 09dddde.
Payment/checkout/five-language/report_language/legal untouched.

## Files changed
pipeline/pdf_scanner.py (new — real content extractor + scanner)
pipeline/autonomous_gate.py (R1-R8 validators + metrics)
pipeline/quality_gate.py (generator: customer-owned SERP scope, specific mechanism, precise
  DoD, INFERENCE label, page-gap/evidence-type on every finding)
pipeline/report_engine.py (_safe_href http-only; _evidence_label; appendix relabel)
tests/test_autonomous_quality_gate.py (added L-P -> 16/16)