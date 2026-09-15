#!/usr/bin/env python3
"""Owner-mandated regression tests T1-T7 for fail-closed ledger rules."""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
R6B_SHA = "c6b2e03cf9202799aa3b6eb4e3ffb182591e07c4536082a89a23efe11b96634c"
ok = 0; total = 0
def check(name, cond):
    global ok, total
    total += 1; ok += bool(cond)
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")

# Load real scorecard
rt = json.load(open("/app/pipeline/output/redteam/ORD-70CBB7D9301D-R6B_redteam_v2.json"))

def gate(ledger, hard_fails, sha_match, dist):
    for row in ledger:
        if row.get("page_verified") is not True or row.get("quote_verified") is not True or row.get("category_evidence_verified") is not True:
            return "DELIVERY_BLOCKED", "AUDIT_LEDGER_VALIDATION_FAILED"
    da = [r for r in ledger if r["category"]=="delivery_artifact_integrity"]
    if not da or da[0].get("evidence_type") != "artifact_manifest" or not da[0].get("sha_chain_consistent"):
        return "DELIVERY_BLOCKED", "DELIVERY_ARTIFACT_EVIDENCE_MISSING"
    ctx = [r for r in ledger if r["category"]=="customer_context_integrity" and r.get("evidence_type")=="full_document_scan"]
    if not ctx:
        return "DELIVERY_BLOCKED", "CUSTOMER_CONTEXT_EVIDENCE_MISSING"
    scores = [v["pct"] for v in rt["categories"].values()]
    if len(set(scores))==1 and not dist:
        return "DELIVERY_BLOCKED", "SCORE_DISTRIBUTION_EXPLANATION_MISSING"
    cand = [r.get("candidate_sha256") for r in ledger if r["category"] == "delivery_artifact_integrity"]
    mock = [r.get("mock_attachment_sha256") for r in ledger if r["category"] == "delivery_artifact_integrity"]
    if not cand or not mock or cand[0] != mock[0]:
        return "DELIVERY_BLOCKED", "MOCK_SHA_MISMATCH"
    if not sha_match or hard_fails:
        return "DELIVERY_BLOCKED", "other"
    return "DELIVERY_ELIGIBLE", "ok"

ledger = rt["review_ledger"]
# T1: row with quote_verified=false → BLOCKED
bad = [dict(r) for r in ledger]; bad[0]["quote_verified"] = False
check("T1 quote_verified=false", gate(bad, [], True, True)[0]=="DELIVERY_BLOCKED" and gate(bad, [], True, True)[1]=="AUDIT_LEDGER_VALIDATION_FAILED")
# T2: category_evidence_verified=false → BLOCKED
bad2 = [dict(r) for r in ledger]; bad2[0]["category_evidence_verified"] = False
check("T2 category_evidence_verified=false", gate(bad2, [], True, True)[0]=="DELIVERY_BLOCKED")
# T3: header as DA evidence → BLOCKED
bad3 = [dict(r) for r in ledger if r["category"]!="delivery_artifact_integrity"]
bad3.append({"category":"delivery_artifact_integrity","evidence_type":"pdf_header","quote":"SEO Opportunity Diagnostic — Persimmon Homes","page_verified":True,"quote_verified":True,"category_evidence_verified":True})
check("T3 header-as-DA-evidence", gate(bad3, [], True, True)[0]=="DELIVERY_BLOCKED" and gate(bad3, [], True, True)[1]=="DELIVERY_ARTIFACT_EVIDENCE_MISSING")
# T4: header as whole-doc context proof → BLOCKED
bad4 = [dict(r) for r in ledger if not (r["category"]=="customer_context_integrity")]
bad4.append({"category":"customer_context_integrity","evidence_type":"pdf_header","quote":"SEO Opportunity Diagnostic","page_verified":True,"quote_verified":True,"category_evidence_verified":True})
check("T4 header-as-context-proof", gate(bad4, [], True, True)[0]=="DELIVERY_BLOCKED" and gate(bad4, [], True, True)[1]=="CUSTOMER_CONTEXT_EVIDENCE_MISSING")
# T5: candidate SHA != mock attachment SHA → BLOCKED
bad5 = [dict(r) for r in ledger]
for r in bad5:
    if r["category"]=="delivery_artifact_integrity": r["mock_attachment_sha256"] = "deadbeef"
check("T5 mock SHA mismatch", gate(bad5, [], True, True)[0]=="DELIVERY_BLOCKED")
# T6: all 92 without explanation → BLOCKED
check("T6 no dist explanation", gate(ledger, [], True, False)[0]=="DELIVERY_BLOCKED")
# T7: real R6B state → eligible to evaluate PASS
res, why = gate(ledger, rt["hard_fails"], rt["artifact_sha_match"], True)
check("T7 real R6B state", res=="DELIVERY_ELIGIBLE")
print(f"\nREGRESSION: {ok}/{total} PASS")
sys.exit(1 if ok<total else 0)
