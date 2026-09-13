# Repair record — Backlinko test + enforce real QA (autonomous)

Date: 2026-09-13
Trigger: hermes-repair-backlinko-test-and-enforce-real-qa.pdf
Treated: latest Backlinko PDF = DELIVERY_BLOCKED (failed staging artifact, not 80/82/90/100).

## Root causes to repair
1. Cross-customer contamination — Backlinko report contained Semrush statements/actions (Decision 2/3).
2. Raw SERP observation used as finding/action (a result list is evidence, not a decision).
3. Generic commercial consequence (missing the 5-element business mechanism).
4. Action Ledger had observations, not customer-owned work.
5. Invalid 90-day roadmap (repeated invalid actions).
6. Privacy/infra leakage — rendered PDF still contained file:///app/pipeline/out/...html.
7. False quality-audit pass — generator could still influence score; need true zero-trust final artifact audit.

## Repairs to implement
- CUSTOMER_CONTEXT_LOCK at job start (job_id, customer_company, customer_primary_domain,
  customer_owned_domains, products/services, market, goal, primary_action,
  competitor_domains, report_language, selected_tier). Clear prior-job context; namespace
  research by job ID; any unapproved foreign brand/domain in customer-facing action text =
  CROSS_CUSTOMER_CONTAMINATION hard fail.
- Evidence→decision transformation: evidence → customer page → gap → business consequence
  → customer-owned action. Finding titles describe a customer decision, never bare search/competitor observation.
- 5-element business mechanism (goal + named offer + named question/decision stage +
  named customer page/path + plausible mechanism).
- Action must start with concrete verb + target customer-owned asset; require action_verb,
  customer_owned_scope, business_reason, acceptance, validation, evidence, owner, effort.
- Roadmap references only pass-validator Action IDs (action-ID + customer scope + owner +
  acceptance + dependency + review point).
- Post-render PDF final-artifact linting (visible text/header/footer/links/name/metadata):
  block if file:// /app/ /pipeline/ /opt/ /home/ /tmp/ localhost 127.0.0.1 VPS/container
  internal order ref, payment ref, customer email, secret/token/key, OR foreign brand in action text.
- Zero-trust audit: generator cannot set final score; independent blind auditor + deterministic
  final-artifact validator + customer_context_lock_pass; only delivery decision engine sets READY_TO_DELIVER.

## ROLLBACK
Baseline prior commit (pre-backlinko-repair). Changes on dedicated work; deploy staging first,
production after tests A-E pass.