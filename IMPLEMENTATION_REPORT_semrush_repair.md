# IMPLEMENTATION REPORT — Semrush Test Report Repair (Final Autonomous Repair)

Date: 2026-09-13 · Autonomous (governance: verify → rollback → staging → repair → test → deploy safe)

## 1. Root causes of the 82/100 false-positive (now fixed)
The earlier Semrush PDF scored 82 because the underlying model had hard failures; the score was not
evidence of passing quality. Repaired at the MODEL level (not sentence rewrites):
- **Competitor pages treated as customer pages** (actions targeted Ahrefs/Moz/Backlinko).
- **Direct competitor reading labelled as SERP research**.
- **Unsupported negative competitor criticism** (title "unfocused" without evidence).
- **Generic commercial reasoning** ("Relates to the stated goal (X)").
- **Actions that were not customer-owned implementation steps**.
- **Roadmap repeating invalid actions.**
- **Possible internal path leakage** in the rendered PDF path.

## 2. Files/workflows/validators changed
- `pipeline/research.py` — Stage C split permanently: `serp` holds ONLY valid SERP/result-pattern
  observations (`counts_toward_serp=True`); competitor reads go to `competitor_observations`
  (`counts_toward_serp=False`, `source=competitor_page`), never counted toward SERP minimum, never a
  finding/action target. Adds `customer_domain` + `customer_owned_domains`.
- `pipeline/quality_gate.py` — rewrote `classify_findings`: evidence with competitor/external source URL
  is rejected as a finding basis; competitor observations become NEUTRAL observed pattern → compare with
  customer page → gap on customer-owned URL → action. Every finding has customer-owned `affected_scope`.
  Actions require `customer_owned_scope` + `action_verb`(derive_verb) + specific `business_reason`.
- `pipeline/autonomous_gate.py` — added permanent validators:
  - **Customer-ownership validator**: blocks any action/finding/roadmap target on a non-customer domain.
  - **Evidence-type validator**: `serp` counts only `counts_toward_serp` items; competitor_page never does.
  - **SERP parser validator**: rejects none parsed / no result parsed / blank snippet / blob / mixed w/o
    pattern / bot challenge.
  - **Action completeness validator**: block if missing customer-owned scope / action / reason / owner / effort / acceptance / validation / evidence.
  - **Executive-summary validator**: block if any exec decision lacks a concrete customer-owned first action.
  - **Roadmap validator**: block if roadmap Action IDs don't exist in the ledger.
  - **PDF privacy validator** (existing + post-render leak scan already enforced).
  - **Score ceilings** (§2): competitor-action target → hard-fail(block); no valid SERP → max 69;
    invalid roadmap → max 79; invalid action ledger → max 69; internal path → hard-fail.
- `tests/test_autonomous_quality_gate.py` — added Test F (competitor target blocked) + Test G
  (competitor page not counted as SERP). **7/7 pass** locally AND inside staging container.

## 3. SERP vs direct competitor reading — clearly separated
Valid SERP requires query, time, source, readable parsed visible result + customer relevance. If the
provider is bot-blocked (the datacenter-IP situation), the system does NOT call competitor reads "SERP".
It uses them only as competitor research, and if valid SERP remains insufficient it follows the
Insufficient-Public-Evidence flow (never invents, never calls "mixed"/"none parsed" a finding).

## 4. Customer-ownership logic
`customer_domain` derived from intake URL. Every action's `affected_scope`/`customer_owned_scope` must
target that domain (or a stated new customer asset); competitor URLs appear only in an evidence field.
Action test F proves a competitor-domain action is hard-failed (blocked).

## 5. Test results
- Local deterministic suite: **7/7 PASS** (A failure-regression, B 497, C 997, D insufficient-evidence,
  E privacy, F competitor-target-blocked, G competitor-not-serp).
- Staging container: **7/7 PASS**.
- Production deploy: full regression green (5 langs + checkout → Stripe live + gate baked).
- **Repaired model on the SAME Semrush target** → `rejected_findings_count:7`, `action_count:3`,
  `delivery_state: RESEARCH_INCOMPLETE`, **no PDF emailed** (the correct insufficient-evidence path;
  not a fake pass).

## 6. PDF privacy-sanitisation
Clean customer-safe filename convention only (`SEO-Opportunity-Diagnostic-[Company]-[YYYY-MM-DD].pdf`),
post-render leak scan of PDF bytes rejects `/app`, `file://`, `localhost`, `127.0.0.1`, `ORD-` → blocks
delivery; no internal order IDs in report body.

## 7. Deployment/monitoring + rollback point
Deployed to BOTH staging (8080) and production (8000) via docker compose; both healthy. Rollback point:
prior known-good Git commit (pre-repair). No price/payment/product/payment-link/five-language/
report_language/legal change.

## 8. Remaining capability limitation (stated honestly)
With the current datacenter IP, public SERP providers (DDG lite/html, Bing, Searx) return a bot challenge
or geo-garbage, so NO valid SERP/result-pattern observations can be obtained from permitted free sources on
this host. Consequently any report requiring SERP minimums honestly resolves to Insufficient-Public-Evidence.
This is by design (never fabricate). Changing the outbound IP / adding a permitted search API would lift
valid-SERP capture; until then the honest fail-safe is exercised, per the repair instruction.