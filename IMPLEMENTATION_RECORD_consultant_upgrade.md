# Upgrade record — MAXIMUM UPGRADE: SEO CONSULTANT reasoning engine (autonomous)

Date: 2026-09-13
Trigger: hermes-maximum-upgrade-seo-consultant-reasoning-engine.pdf (highest-priority upgrade)
Two identical copies received (doc_e3798e5bbd74, doc_a406a9175eec).

## Core mission
Turn the system from a report generator into a genuinely useful evidence-led SEO strategist for SMBs.
Current failure = weak consultant reasoning (not lack of data). Evidence is not the conclusion.

## Already implemented (verify + keep)
- CUSTOMER_CONTEXT_LOCK (build_customer_context_lock) + cross_customer_contamination_check
- customer-owned action/finding model (classify_findings rewrites)
- Zero-trust gate (deterministic + independent blind auditor + delivery engine)
- Post-render PDF final-artifact lint (infra + contamination)
- Claim labels FACT/INFERENCE/HYPOTHESIS/NOT-VERIFIABLE
- Step research SERP-injection hook (valid public result-pattern source)

## New to implement in this upgrade
1. Research reasoning stages enforced in classify: customer context framing, customer-owned page map,
   buyer-question stages, result-pattern/competitor classification (separate), page-gap analysis.
2. Business-model fit check (§5): reject/downgrade actions that don't fit the customer's actual model
   (e.g. quote path for ecommerce, content for discontinued product, forcing sales CTA on informational).
3. Deterministic metrics to add/strengthen: business_mechanism_completeness_rate, customer_owned_scope_rate,
   unverified_current_offer_count, generic_finding_count, generic_action_count.
4. Score ceilings (§8): any hard fail→blocked; no customer-owned page-gap evidence→max59; no valid
   customer-owned action ledger→max69; no business-model fit evidence→max79; no blind-auditor
   citations→max84.
5. Blind auditor must answer 7 customer-usefulness questions with citations; award zero if no citation.
6. Tests A–G incl. SME-site passing test (explicitly NOT Apple/Semrush/Backlinko/Ahrefs/Moz/Google/MS).

## Rollback
Prior known-good commit. Work on branch/staging; deploy after tests pass.

## Final directive
Optimise for a customer-owned, commercially sensible decision — not the appearance of research volume.
A report is excellent only when an owner can hand it to the right person and say:
"Change this page, in this way, for this customer reason, by this owner, and check it like this."