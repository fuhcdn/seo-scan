# Implementation record — remove hardcoded 'Semrush' from report generator

- **Date/time:** 2026-09-13 (6-hourly 4-CEO full review)
- **Issue:** `classify_findings` competitor branch hardcoded the foreign brand "Semrush" into
  customer-facing report text, and embedded the observed competitor host in the finding title.
- **Risk class:** R2 (report-quality / contamination). Reversible, no payment/legal/data change.
- **Trigger:** 4-CEO review. CEO2 (Product Quality) reproduced it; CEO1 flagged the delivery
  blast-radius (competitor findings self-blocking as DELIVERY_BLOCKED).
- **Affected components:** `pipeline/quality_gate.py` → `_recommended_action_for_claim_competitor`
  + competitor finding block in `classify_findings`.
- **Evidence:** (1) grep `quality_gate.py` → "align a Semrush-owned page" and
  "Semrush-owned public pages" present at HEAD; generated backlinko/semrush test artifacts showed
  "Semrush-owned" in Decision cards. (2) Contamination gate (`autonomous_gate.py
  cross_customer_contamination_check`) scans findings title/recommended_action/affected_scope and
  actions for foreign brands (KNOWN_FOREIGN_BRANDS includes ahrefs/semrush/moz/backlinko/...).
- **Root cause:** generator injected "Semrush" (and the observed competitor host in the title) into
  scan-checked fields → either leaked a foreign brand into the customer's report, or caused
  DELIVERY_BLOCKED self-block on any report with a competitor observation.
- **Change (smallest safe):** reroute wording to customer-owned; competitor host retained only in
  the `claim`/`gap_claim` field, which the contamination checker does not scan (evidence field).
  - recommended_action: "align a Semrush-owned page …" → "build or update a customer-owned page …"
  - gap_claim: "Semrush-owned public pages …" → "competitor public pages ({host}) …"
  - finding title: "…competitors serve ({host})" → "…the observed competitor serves" (removed host).
- **Verification / tests:**
  - `python3 -m py_compile pipeline/quality_gate.py` → OK.
  - `python3 tests/test_autonomous_quality_gate.py` → 9/9 PASS (A–I incl. H cross-customer
    contamination blocked, I post-render leakage).
  - Real-generator simulation: `_recommended_action_for_claim_competitor` + competitor finding with
    host `ahrefs.com` → `cross_customer_contamination_check` returns 0 (no self-block); "ahrefs"
    absent from all scan-checked fields (only in claim/evidence). Before fix: contam_count=2.
- **Regression scope checked:** product mapping / $497·$997 tiers, 5 languages, report_language,
  PDF, email not touched (3-line text change inside one generator branch). No payment/legal code
  changed.
- **Commit:** `1ad7ce4` on `master` (working tree clean). Local == remote origin/master at 681bee9;
  new commit pushed to origin on next permitted git push. Production origin is git-driven.
- **Deploy state:** commit ready; production rebuild is performed by the owner-side VPS deploy
  session (`docker compose up -d --build`, requires `VPS_ROOT_PW` not present in this cron env).
  Live production currently already serves pre-fix HEAD (Semrush strings were live); this commit
  remains to be deployed.
- **Rollback:** `git revert 1ad7ce4` (or `git checkout 681bee9 -- pipeline/quality_gate.py`).
- **Remaining risk (owner/R3 open items, NOT changed here):**
  - Stripe presentment currency shows EUR (e.g. €893.85) on live checkout vs US$997 landing — R3
    (payment presentation) — owner decision.
  - Live refund policy is conditional; "refund@[your-domain].com" placeholder; no live refund badge —
    R3 (legal/refund) — owner decision.
  - Brand inconsistency ("SEO Scan.ai" titles vs domain seoscanaudit.com) — R3 (brand) — owner.
  - Blind auditor + report pipeline depend on OPENROUTER_API_KEY (present in secrets.env; confirm in
    production env) — verified present in local secrets.env.
  - local stale dev process pid 164857 (old server.py) — not the public origin; operational hygiene.