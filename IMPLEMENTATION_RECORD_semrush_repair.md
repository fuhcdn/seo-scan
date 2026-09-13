# Repair Implementation Record — Semrush test report (autonomous repair)

Date: 2026-09-13
Trigger: hermes-next-step-repair-semrush-test-report.pdf

## FINAL STATUS (repair complete)
Semrush test report true delivery status: **DELIVERY_BLOCKED** (not a passing report, not customer-deliverable).

The new (repaired) model, when run on the same Semrush target, now correctly resolves to:
- rejected_findings_count: 7 (competitor observations no longer become findings)
- action_count: 3 (only customer-owned actions)
- delivery_state: RESEARCH_INCOMPLETE (no valid SERP from datacenter IP; competitor reads don't count)
- No normal PDF produced / not emailed (no fake passage).

This is the CORRECT insufficient-public-evidence path per repair instruction §2: "If valid SERP result
evidence cannot be obtained from permitted sources, do not fake a passing test. Demonstrate the correct
insufficient-evidence path and report the capability limitation."

## Immediate correction
The Semrush test report PDF (SEO-Opportunity-Diagnostic-semrush-test-2026-09-13.pdf)
is NOT a passing report. Its true delivery status: **DELIVERY_BLOCKED**.
Do not send to customers. Do not treat 82 as evidence of quality.

Observed hard failures in that report:
- A) Competitor pages (Ahrefs/Moz/Backlinko) used as ACTION targets (customer cannot edit them)
- B) Direct competitor page reading labelled as SERP research
- C) Unsupported negative competitor claim ("titles unfocused" without evidence)
- D) Generic commercial reasoning ("Relates to the stated goal (X)")
- E) Actions built from competitor observations, not customer-owned changes
- F) 90-day roadmap repeating invalid action text
- G) possible internal path leakage: file:///app/pipeline/out/SEO-Opportunity-Diagnostic-semrush-test-2026-09-13.html
     (verify + fix in the renderer/filename path so no internal path lands in PDF)

## Score correction required (delivery): 
- competitor action targets -> hard fail / block
- no valid SERP research -> max 69/100
- generic commercial reasoning -> strategic value cannot pass
- invalid Action Ledger -> max 69/100
- invalid action-ID roadmap -> max 79/100
- internal file path visible -> hard fail / block

## Repairs to implement (not sentence rewrites — permanent model fixes)
1. Customer-ownership validator: block any action/finding/roadmap targeting external/competitor domain;
   require customer_owned_scope on every action; competitor URL only in evidence/source field.
2. Evidence-type validator: evidence item must be one of
   customer_page / competitor_page / serp_result_pattern / technical_public_check /
   official_documentation / customer_provided_input. competitor_page MUST NOT satisfy serp minimum.
3. SERP parser validator: reject observations containing none parsed / no result parsed /
   blank link / blank snippet / empty result / mixed w/o described pattern / bot challenge.
4. Action completeness validator: block if missing customer-owned scope, action verb,
   business reason, owner, effort, acceptance, validation, evidence.
5. Executive-summary validator: block if any exec decision lacks concrete customer-owned First Action.
6. Roadmap validator: block if roadmap Action IDs don't exist / fail validation / target external.
7. PDF privacy validator: block internal path/order/infra/raw-log leakage.
8. Correct research reasoning sequence: intake -> customer-owned asset map -> customer decision
   questions -> SERP (if valid) -> competitor (separate) -> compare on CUSTOMER pages -> finding
   -> customer-owned action -> roadmap from valid actions only.
9. Competitor reasoning: neutral observable wording; competitor research = expose customer
   opportunity, never invent competitor defects; observe pattern -> compare with customer page
   -> gap on customer-owned page -> action on SEMRUSH-owned URL.

## ROLLBACK
git commit baseline exists (674df9a / f608dfb). All changes on dedicated work; deploy to staging
first; production after tests pass.