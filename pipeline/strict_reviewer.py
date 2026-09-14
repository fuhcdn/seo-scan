#!/usr/bin/env python3
"""strict_reviewer.py — INDEPENDENT STRICT QUALITY REVIEWER AGENT (owner directive 2026-09-14c).

ROLE B. Separately identifiable agent/process with its own prompt, rubric and
execution boundary. Reads the ACTUAL candidate PDF + job manifest + evidence
cards + action objects and issues an immutable, machine-verifiable scorecard.

May NOT: edit the report, edit cards/actions, generate PDFs, send email, or set
delivery state. Its only outputs are scorecard + hard fails + repair
instructions + delivery decision (PASS / DELIVERY_BLOCKED) bound to the exact
candidate artifact SHA.

The generator (ROLE A) can never produce or alter this record.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "gates"))

import gate_pipeline as gp  # noqa: E402

REVIEWER_AGENT_ID = "strict-quality-reviewer-v1"
REVIEWER_MODEL = "deepseek/deepseek-chat-v3-0324"

REQUIRED_CATEGORIES = [
    "evidence_accuracy", "finding_distinctness", "customer_specificity",
    "customer_context_integrity", "business_logic_integrity",
    "commercial_priority_discipline", "action_executability",
    "action_scope_discipline", "claims_safety", "roadmap_consistency",
    "journey_map_integrity", "pdf_customer_readiness", "delivery_artifact_integrity",
]

FOREIGN_TERMS = ("screen-printing", "embroidery", "/gallery/", "get-a-quote",
                 "quote-form", "apparel", "garment", "printing", "apple imprints")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def sign(record):
    """Machine-verifiable signature of the immutable scorecard."""
    core = json.dumps(record, sort_keys=True, ensure_ascii=False)
    return sha256((core + REVIEWER_AGENT_ID).encode())


def review(candidate_pdf, job, cards, acts, attempt):
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    data = open(candidate_pdf, "rb").read()
    csha = sha256(data)
    visible = gp.extract_visible_text_mature(data)
    vlow = visible.lower()
    scan = gp.gate5_scan_final_pdf(data)
    domain = ((job.get("url") or "").lower().replace("https://", "").replace("http://", "")
              .replace("www.", "").rstrip("/"))
    company = (job.get("company_name") or "").strip()
    hard_fails = []
    deductions = []   # [{location, section, action_id, issue, why, improvement, points}]
    repair_plan = []

    # ---------- A. deterministic: PDF safety ----------
    if not scan["clean"] or scan["hard_fails"]:
        hard_fails += ["PDF_SAFETY:" + f for f in scan["hard_fails"]]

    # ---------- B. foreign customer content ----------
    for t in FOREIGN_TERMS:
        if t in vlow:
            hard_fails.append("FOREIGN_JOURNEY_MAP_CONTENT:" + t)
            hard_fails.append("FOREIGN_CUSTOMER_CONTEXT:" + t)
            deductions.append({"location": "full document", "section": "any",
                               "issue": f"foreign customer term '{t}' present",
                               "why": "cross-customer contamination", "points": 20,
                               "improvement": f"remove all '{t}' content; rebuild from this job's evidence only"})

    # ---------- C. domain ownership ----------
    urls = sorted(set(re.findall(r"https?://([a-zA-Z0-9.\-]+)/", visible)))
    foreign_urls = [u for u in urls if domain not in u and u not in ("seoscanaudit.com", "www.w3.org")]
    if foreign_urls:
        hard_fails.append("NO_FOREIGN_CUSTOMER_URL:" + ",".join(foreign_urls))
        deductions.append({"location": "URLs in body", "section": "any", "issue": f"foreign domains {foreign_urls}",
                           "why": "customer-owned-URL rule violated", "points": 15,
                           "improvement": "keep only customer-owned URLs"})

    # ---------- D. journey map integrity ----------
    jacts = set(re.findall(r"ACT-\d{3}", visible))
    current_acts = {(a.get("action_id") or "") for a in acts}
    bad_acts = jacts - current_acts
    if bad_acts:
        hard_fails.append("JOURNEY_MAP_ACTION_ID_MISMATCH:" + ",".join(sorted(bad_acts)))
    jm = re.search(r"Customer Journey Map(.{0,2500})", visible, re.S)
    if jm and not re.search(r"persimmon|development|buyer", jm.group(1), re.I):
        hard_fails.append("JOURNEY_MAP_ACTION_TEXT_MISMATCH")

    # ---------- E. empty/placeholder fields ----------
    if re.search(r"Goal:\s*\.", visible) or re.search(r"Goal:\s*$", visible, re.M):
        hard_fails.append("EMPTY_GOAL_FIELD")
        deductions.append({"location": "page 1", "section": "header", "issue": "Goal field empty",
                           "why": "blank customer field", "points": 5,
                           "improvement": "populate goal from the job intake"})
    for ph in ("[Insert", "TBD", "placeholder", "Lorem ipsum", "XXX"):
        if ph.lower() in vlow:
            hard_fails.append("PLACEHOLDER_TEXT:" + ph)

    # ---------- F. internal evidence ID leak ----------
    cust_visible = visible.split("Source / Evidence Appendix")[0]
    leak = re.findall(r"\b(?:GB|EC)-\d{3}\b", cust_visible)
    if leak:
        hard_fails.append("CUSTOMER_FACING_EVIDENCE_ID_LEAK")
        deductions.append({"location": "customer-visible sections", "section": "any",
                           "issue": f"internal evidence IDs {sorted(set(leak))} in customer text",
                           "why": "internal identifiers must never reach the customer", "points": 6,
                           "improvement": "use customer-facing Finding N labels only"})

    # ---------- G. DO NOW with unresolved approvals ----------
    for a in acts:
        if (a.get("investment_status") or "") == "DO_NOW":
            hard_fails.append("DO_NOW_REQUIRES_NO_UNRESOLVED_APPROVAL:" + str(a.get("action_id")))
            deductions.append({"location": "roadmap", "section": "status",
                               "action_id": a.get("action_id"),
                               "issue": "DO NOW while approval dependency unresolved",
                               "why": "priority/approval consistency", "points": 10,
                               "improvement": "set VALIDATE FIRST until approvals confirmed"})

    # ---------- H. multi-URL scope ----------
    for a in acts:
        pu = (a.get("primary_url") or "")
        if ";" in pu:
            hard_fails.append("NO_MULTI_URL_ACTION_SCOPE:" + str(a.get("action_id")))

    # ---------- I. date consistency ----------
    obs_dates = re.findall(r"2026-09-\d{2}", visible)
    gen_date = time.strftime("%Y-%m-%d")
    if obs_dates and min(obs_dates) > gen_date:
        hard_fails.append("REPORT_DATE_BEFORE_EVIDENCE_DATE")
    stale = re.findall(r"Report date (\d{4}-\d{2}-\d{2})", visible)
    date_note = {"report_dates_visible": stale, "today": gen_date,
                 "research_dates_visible": sorted(set(obs_dates))}

    # ---------- J. generic role labels (attorney for non-law-firm) ----------
    if "attorney" in vlow and "law" not in (job.get("url") or "").lower():
        deductions.append({"location": "ownership rows", "section": "actions",
                           "issue": "generic 'attorney' role label for a non-law-firm customer",
                           "why": "unprofessional generic role label", "points": 3,
                           "improvement": "replace with the customer's real roles (e.g. Regional Sales Director)"})
        hard_fails.append("GENERIC_ROLE_LABEL:attorney")

    # ---------- K. unsupported claims (hypothesis discipline) ----------
    for claim in ("highest-value", "largest segment", "converts at higher rates",
                  "revenue uplift", "will increase conversions"):
        if claim in vlow and "hypothesis" not in vlow:
            deductions.append({"location": "mechanism/roadmap text", "section": "any",
                               "issue": f"unsupported claim '{claim}' without hypothesis wording",
                               "why": "claims discipline", "points": 4,
                               "improvement": "reword as hypothesis to validate with CRM/analytics data"})
            break

    # ---------- L. structural completeness (from shared evaluator, advisory input) ----------
    try:
        from evidence_report_runner import evaluate_scorecard
        sc = evaluate_scorecard(scan, visible, acts, cards, [{"mode": "reviewer"}], 0, domain)
        structural = sc["STRUCTURAL_COMPLETENESS_SCORE"]["value"]
    except Exception as e:
        structural = 0
        hard_fails.append("REVIEWER_STRUCTURAL_CHECK_ERROR:" + str(e)[:80])
    if structural != 100.0:
        hard_fails.append("STRUCTURAL_COMPLETENESS_BELOW_100")

    # ---------- M. LLM independent semantic audit (separate prompt/identity) ----------
    llm_scores = {}
    llm_repair = []
    try:
        from seo_crawler import resolve_openrouter_key, openrouter_chat, _coerce_msg_content
        key = resolve_openrouter_key()
        cats = ", ".join(REQUIRED_CATEGORIES)
        prompt = (
            "You are the INDEPENDENT STRICT QUALITY REVIEWER AGENT for a paid customer SEO report "
            f"(customer: {company}, domain: {domain}). You did NOT write this report. Grade ONLY what you "
            "can verify in the extracted PDF text below. For each category [" + cats + "] give 0-100 with "
            "at least one artifact-specific deduction (quote the exact text) whenever anything is less than "
            "perfect; 100 requires concrete evidence it is fully met. Also list ordered, concrete repair "
            "instructions (file/section-level). Be strict: if evidence is missing, generic, stale or "
            "unverifiable, deduct.\n\n"
            "Reply ONLY as JSON: {\"categories\":{\"<name>\":{\"score\":N,\"deduction\":\"...\"}},"
            "\"repair_instructions\":[\"...\"]}\n\nPDF TEXT (truncated):\n" + visible[:14000])
        payload = {"model": REVIEWER_MODEL, "messages": [
            {"role": "system", "content": "You are a strict independent quality reviewer. Never self-approve; grade only visible evidence."},
            {"role": "user", "content": prompt}], "temperature": 0, "max_tokens": 2500}
        env = openrouter_chat(key, payload)
        content = _coerce_msg_content(env.get("choices", [{}])[0].get("message", {}).get("content", ""))
        js = content[content.find("{"): content.rfind("}") + 1] if content and "{" in content else "{}"
        parsed = json.loads(js)
        llm_scores = parsed.get("categories", {})
        llm_repair = parsed.get("repair_instructions", []) or []
    except Exception as e:
        hard_fails.append("REVIEWER_LLM_AUDIT_UNAVAILABLE:" + str(e)[:80])

    # category scores: min(deterministic-driven floor, LLM score); unknown -> 0 until evidenced
    categories = {}
    for cname in REQUIRED_CATEGORIES:
        entry = llm_scores.get(cname) or {}
        try:
            s = int(entry.get("score", 0))
        except Exception:
            s = 0
        s = max(0, min(100, s))
        categories[cname] = {"score": s, "max": 100, "pct": s,
                             "deduction": entry.get("deduction") or "not evidenced by reviewer"}
    overall = round(sum(v["score"] for v in categories.values()) / len(categories), 1)

    decision = "PASS" if (overall >= 90 and all(v["pct"] >= 90 for v in categories.values())
                          and not hard_fails and structural == 100.0) else "DELIVERY_BLOCKED"
    if decision == "PASS":
        repair_plan = []
    else:
        for d in sorted(deductions, key=lambda x: -x.get("points", 0)):
            repair_plan.append(f"[{d.get('action_id') or d.get('section','general')}] {d['issue']} -> {d['improvement']}")
        repair_plan += llm_repair
        for hf in hard_fails:
            repair_plan.append(f"HARD FAIL {hf}: must be eliminated before delivery.")

    record = {
        "reviewer_agent_id": REVIEWER_AGENT_ID,
        "reviewer_run_id": f"REV-{int(time.time())}-{sha256((csha + ts).encode())[:8]}",
        "job_id": job.get("order_id"),
        "customer_name": company,
        "approved_customer_domain": domain,
        "candidate_version": f"R{attempt}",
        "candidate_sha256": csha,
        "pdf_filename": os.path.basename(candidate_pdf),
        "pdf_bytes": len(data),
        "generation_timestamp": ts,
        "research_observation_dates": sorted(set(obs_dates)),
        "overall_score": overall,
        "structural_completeness_score": structural,
        "categories": categories,
        "deductions": deductions,
        "hard_fails": hard_fails,
        "foreign_content_scan": {t: (t in vlow) for t in FOREIGN_TERMS},
        "domain_ownership_validation": {"domains_seen": urls, "foreign": foreign_urls},
        "journey_map_validation": {"action_ids_seen": sorted(jacts),
                                   "current_action_ids": sorted(current_acts),
                                   "mismatch": sorted(bad_acts)},
        "date_consistency": date_note,
        "action_scope_validation": {a.get("action_id"): (a.get("primary_url") or "") for a in acts},
        "claims_safety_notes": "unsupported superlatives must be hypothesis-worded",
        "delivery_decision": ("INDEPENDENT_REVIEW_PASS" if decision == "PASS" else "DELIVERY_BLOCKED"),
        "repair_instructions": repair_plan,
        "pdf_safety_scan": {"hard_fails": scan["hard_fails"], "sha256": scan["sha256"]},
    }
    record["reviewer_signature"] = sign({k: v for k, v in record.items() if k != "reviewer_signature"})
    return record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate-pdf", required=True)
    ap.add_argument("--job-id", required=True)
    ap.add_argument("--attempt", type=int, required=True)
    ap.add_argument("--cards", required=True)
    a = ap.parse_args()
    job = json.load(open(os.path.join(_HERE, "output", f"order_{a.job_id}.json"), encoding="utf-8"))
    cf = json.load(open(a.cards, encoding="utf-8"))
    cards = [c for c in cf.get("golden_evidence_cards", []) if gp.gate2_validate_evidence_card(c)["valid"]]
    acts = gp.gate3_actions_from_evidence_cards(cards, customer_context=cf.get("customer") or {})
    rec = review(a.candidate_pdf, job, cards, acts, a.attempt)
    os.makedirs(os.path.join(_HERE, "output", "reviews"), exist_ok=True)
    out = os.path.join(_HERE, "output", "reviews", f"{a.job_id}_R{a.attempt}_review.json")
    json.dump(rec, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps({"review_file": out, "decision": rec["delivery_decision"],
                      "overall": rec["overall_score"], "hard_fails": rec["hard_fails"],
                      "signature": rec["reviewer_signature"][:16]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
