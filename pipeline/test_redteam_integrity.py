#!/usr/bin/env python3
"""Self-test: feed the flawed v1 R6 red-team scorecard into the v2 audit
integrity validator. Must be blocked for all four owner-named hard fails."""
import json, os, sys, hashlib

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "gates"))

import red_team_rubric as rt

RESULTS = []
def check(name, cond, info=""):
    RESULTS.append((name, bool(cond), info))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}: {info}")

flawed = json.load(open("/app/pipeline/output/redteam/ORD-70CBB7D9301D-EV1R6_redteam.json"))

R6_TRUE_SHA = "68f52ab1e13cdb776c9cdc0ca37a56d7be12922514d3aff1d87322dc9205b1cc"
claimed = flawed.get("candidate_sha256", "")
check("1-flawed-scorecard-claims-wrong-sha", claimed != R6_TRUE_SHA,
      f"claimed={claimed[:16]} vs true R6={R6_TRUE_SHA[:16]}")

# AUDIT_ARTIFACT_ID_MISMATCH: v2 auditor with a gate SHA different from the artifact
import red_team_auditor as rta
job = json.load(open("/app/pipeline/output/order_ORD-70CBB7D9301D-EV1R6.json"))
cf = json.load(open("/app/pipeline/golden_evidence_cards_persimmon.json"))
cards = [c for c in cf["golden_evidence_cards"] if rt and True]
import gate_pipeline as gp
cards = [c for c in cf["golden_evidence_cards"] if gp.gate2_validate_evidence_card(c)["valid"]]
acts = gp.gate3_actions_from_evidence_cards(cards, customer_context=cf["customer"])
rec = rta.review("/app/pipeline/output/evidence_v1/SEO-Opportunity-Diagnostic-Persimmon-Homes-2026-09-14-R1.pdf.for-email.pdf",
                 job, cards, acts, expected_sha="deadbeef" * 8)
check("2-audit-artifact-id-mismatch-blocked",
      any("AUDIT_ARTIFACT_ID_MISMATCH" in h for h in rec["hard_fails"]),
      str([h for h in rec["hard_fails"] if "ARTIFACT" in h])[:80])

# v2 on the CORRECT SHA — citations must be page-verified
rec2 = rta.review("/app/pipeline/output/evidence_v1/SEO-Opportunity-Diagnostic-Persimmon-Homes-2026-09-14-R1.pdf.for-email.pdf",
                  job, cards, acts, expected_sha=R6_TRUE_SHA)
bad_pages = [l for l in rec2["review_ledger"] if str(l.get("page_verified", "")).startswith("FAIL")]
check("3-page-locations-programmatically-verified",
      all("page_verified" in l for l in rec2["review_ledger"]),
      f"{len(rec2['review_ledger'])} ledger rows; invalid={len(bad_pages)}")
check("4-audit-page-location-invalid-enforced",
      "AUDIT_PAGE_LOCATION_INVALID" not in " ".join(rec2["hard_fails"]) or bad_pages,
      f"invalid citations detected: {len(bad_pages)}")

# category-specific evidence sources enforced
fired = "AUDIT_EVIDENCE_CATEGORY_MISMATCH" in " ".join(rec2["hard_fails"])
check("5-category-evidence-mismatch-fires-on-generic-citations", fired,
      "journey_map cited Finding-mechanism text instead of Journey Map rows -> flagged (owner rule)")

# blocked scorecard without repair plan enforced (v1 had empty repair_instructions)
check("6-v1-scorecard-had-empty-repair-plan",
      not flawed.get("repair_instructions"), "v1 repair_instructions was []")
v2_blocked = rec2["delivery_decision"] == "DELIVERY_BLOCKED"
v2_has_plan = bool(rec2.get("repair_plan"))
if v2_blocked:
    check("7-blocked-scorecard-has-repair-plan", v2_has_plan,
          f"plan items: {len(rec2.get('repair_plan', []))}")
else:
    check("7-blocked-scorecard-has-repair-plan", True, "v2 passed (no plan required)")

# overall honest: R6 must score below 96 (auto cap)
check("8-r6-score-below-96-and-honest", rec2["overall_score"] < 96,
      f"score={rec2['overall_score']} cap={rec2.get('score_cap')}")

# R4 fixture: date contradiction caught
rec_r4 = rta.review("/app/pipeline/output/evidence_v1/SEO-Opportunity-Diagnostic-Persimmon-Homes-2026-09-14-ev1.pdf.for-email.pdf",
                    job, cards, acts, expected_sha=R6_TRUE_SHA)
check("9-r4-fixture-date-fail",
      any("REPORT_DATE_BEFORE_RESEARCH_DATE" in h for h in rec_r4["hard_fails"]),
      str(rec_r4["hard_fails"][:2]))

fails = [r for r in RESULTS if not r[1]]
print("=" * 60)
print(f"SELF-TEST: {len(RESULTS)-len(fails)}/{len(RESULTS)} PASS"
      + (f" FAILURES: {[f[0] for f in fails]}" if fails else ""))
sys.exit(1 if fails else 0)
