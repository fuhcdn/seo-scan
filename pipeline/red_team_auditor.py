#!/usr/bin/env python3
"""red_team_auditor.py — ROLE C: Independent Red-Team Scoring Auditor v1.

Owner directive 2026-09-14e. Separately identifiable agent with its own prompt,
signing credential and process. Assumes the PDF MAY contain subtle defects and
actively hunts for deductions.

Hard rules:
  - AUTOMATIC SCORE MAXIMUM = 95/100. 96-100 reserved for owner-authorised
    human/external review. No default 100.
  - Anchored rubric: every criterion scored 0-5 against written anchors; every
    awarded point cites pdf page/section/quote/ID/anchor/reason.
  - Mandatory deduction discipline: if a meaningful one-point improvement
    exists, the category cannot receive its maximum.
  - Decision bands: 0-49/50-74/75-89 -> DELIVERY_BLOCKED; 90-95 + all gates ->
    INDEPENDENT_REVIEW_PASS; 96+ -> not issued by this agent.
May NOT: edit report/cards/actions, send email, set VERIFIED_READY_TO_SEND.
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

AUDITOR_AGENT_ID = "red-team-scoring-auditor-v1"
AUDITOR_MODEL = "deepseek/deepseek-chat-v3-0324"
AUTO_MAX = 95

# ---- ANCHORED RUBRIC: 2 criteria per category, each 0-5, anchors written ----
RUBRIC = {
    "evidence_accuracy": {
        "c1_direct_observation_tied_to_customer_url": {
            "0": "no customer-owned URL or fabricated claim",
            "1": "URL exists but no direct observation / claim unsupported",
            "2": "observation generic, stale, incomplete or weakly tied to recommendation",
            "3": "specific observation + recommendation exist; limitation/causal link incomplete",
            "4": "specific direct observation, buyer question, gap, mechanism, limitation present & consistent",
            "5": "level 4 + corroborated by current structured evidence, no meaningful ambiguity"},
        "c2_evidence_limitation_disclosure": {
            "0": "limitations never mentioned where needed",
            "1": "one generic limitation",
            "2": "limitations present but boilerplate",
            "3": "most material claims carry limitations",
            "4": "every material claim carries a specific limitation",
            "5": "level 4 + limitations independently verifiable from the cited pages"}},
    "finding_distinctness": {
        "c1_no_overlap": {"0": "near-duplicate findings", "1": "2+ findings overlap heavily",
                          "2": "one clear overlap", "3": "minor wording overlap only",
                          "4": "distinct gaps, distinct pages", "5": "level 4 + each gap maps to a distinct business lever"},
        "c2_no_inflation": {"0": "count inflated with duplicates", "1-2": "padding visible",
                            "3": "count honest but thin", "4": "count justified by evidence",
                            "5": "level 4 + every finding survives a 'why separately?' test"}},
    "customer_specificity": {
        "c1_customer_owned_scope": {"0": "foreign/generic targets", "2": "some non-customer pages referenced",
                                    "4": "every action targets one exact customer-owned URL",
                                    "5": "level 4 + each target verified live in this run"},
        "c2_buyer_language": {"0": "generic SEO speak", "2": "partly buyer-anchored",
                              "4": "every mechanism reasons from the customer's buyer journey",
                              "5": "level 4 + buyer questions quoted verbatim from evidence"}},
    "customer_context_integrity": {
        "c1_no_foreign_content": {"0": "foreign customer content present", "4": "no foreign content anywhere",
                                  "5": "level 4 + positive checks quoted for every section"},
        "c2_context_binding": {"0": "name/domain/goal inconsistent", "4": "all sections share one context",
                               "5": "level 4 + context lock fields quoted"}},
    "business_logic_integrity": {
        "c1_model_consistency": {"0": "recommendations contradict the business model",
                                 "4": "every action fits the model", "5": "level 4 + model assumptions stated"},
        "c2_internal_contradictions": {"0": "sections contradict", "4": "no contradictions found",
                                       "5": "level 4 + cross-section comparison documented"}},
    "commercial_priority_discipline": {
        "c1_status_honesty": {"0": "DO NOW with unresolved approvals", "4": "status matches approvals exactly",
                              "5": "level 4 + every approval item enumerated"},
        "c2_priority_reasoning": {"0": "no ordering rationale", "4": "rationale per status",
                                  "5": "level 4 + dependencies between actions stated"}},
    "action_executability": {
        "c1_brief_completeness": {"0": "missing DoD/owner/signal", "4": "DoD, owners, signal, baseline, window, scale rule all present",
                                  "5": "level 4 + each element action-specific, not templated"},
        "c2_placement_precision": {"0": "vague placement", "4": "exact placement on exact page",
                                   "5": "level 4 + placement quoted against live page structure"}},
    "action_scope_discipline": {
        "c1_single_url": {"0": "one action spans unrelated pages", "4": "one action = one primary URL, scope clean",
                          "5": "level 4 + rendered text free of other-page references"},
        "c2_explicit_exclusions": {"0": "silent scope creep", "4": "exclusions stated",
                                   "5": "level 4 + follow-on actions enumerated with required own fields"}},
    "claims_safety": {
        "c1_hypothesis_labelling": {"0": "unproven performance claims as fact", "4": "unprovable statements hypothesis-labelled",
                                    "5": "level 4 + each hypothesis names its validation data source"},
        "c2_no_superlatives": {"0": "superlative market claims", "4": "no unsupported superlatives",
                               "5": "level 4 + wording checked section-by-section"}},
    "roadmap_consistency": {
        "c1_status_derivation": {"0": "roadmap contradicts statuses", "4": "roadmap renders from investment_status only",
                                 "5": "level 4 + every roadmap cell traced to an action"},
        "c2_timeline_honesty": {"0": "promises without basis", "4": "preparation-only until approvals",
                                "5": "level 4 + day ranges justified"}},
    "journey_map_integrity": {
        "c1_row_binding": {"0": "rows from another job/template", "4": "every row bound to current actions+pages",
                           "5": "level 4 + each row's signal matches its action"},
        "c2_no_fallback": {"0": "hard-coded fallback map visible", "4": "no fallback content",
                           "5": "level 4 + row count matches action count"}},
    "pdf_customer_readiness": {
        "c1_no_internal_leaks": {"0": "internal IDs/paths/placeholders visible", "4": "customer-clean",
                                 "5": "level 4 + appendix boundary verified"},
        "c2_language_quality": {"0": "truncated/broken/generic text", "4": "clean professional copy",
                                "5": "level 4 + no template phrases remaining"}},
    "delivery_artifact_integrity": {
        "c1_render_integrity": {"0": "render failed/corrupt", "4": "single render, verified",
                                "5": "level 4 + SHA chain documented"},
        "c2_scan_clean": {"0": "safety scan fails", "4": "scan clean",
                          "5": "level 4 + scan rules enumerated"}},
}

FOREIGN_TERMS = ("screen-printing", "embroidery", "/gallery/", "get-a-quote",
                 "quote-form", "apparel", "garment", "printing", "apple imprints")


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def sign(record):
    core = json.dumps(record, sort_keys=True, ensure_ascii=False)
    return sha256((core + AUDITOR_AGENT_ID + "|redteam-cred-v1").encode())


def review(candidate_pdf, job, cards, acts, strict_reviewer_record=None):
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    data = open(candidate_pdf, "rb").read()
    csha = sha256(data)
    visible = gp.extract_visible_text_mature(data)
    vlow = visible.lower()
    scan = gp.gate5_scan_final_pdf(data)
    domain = ((job.get("url") or "").lower().replace("https://", "").replace("http://", "")
              .replace("www.", "").rstrip("/"))
    hard_fails = []
    ledger = []

    # deterministic red-team checks
    scan_fails = list(scan["hard_fails"])
    if scan_fails:
        hard_fails += ["PDF_SAFETY:" + f for f in scan_fails]
    for t in FOREIGN_TERMS:
        if t in vlow:
            hard_fails.append("FOREIGN_CUSTOMER_CONTEXT:" + t)
    for u in sorted(set(re.findall(r"https?://([a-zA-Z0-9.\-]+)/", visible))):
        if domain not in u and u not in ("seoscanaudit.com", "www.w3.org"):
            hard_fails.append("NO_FOREIGN_CUSTOMER_URL:" + u)
    gen = re.findall(r"Report date[:\s]+(\d{4}-\d{2}-\d{2})", visible)
    res = re.findall(r"2026-\d{2}-\d{2}", visible)
    if gen and res and min(gen) < max(res):
        hard_fails.append("REPORT_DATE_BEFORE_RESEARCH_DATE")
    for pat in ("largest segment", "largest research-heavy", "convert at higher rates",
                "converts at higher rates", "return repeatedly", "highest-value segment"):
        if pat in vlow:
            hard_fails.append("UNSUPPORTED_CUSTOMER_MARKET_OR_PERFORMANCE_CLAIM:" + pat)
    if re.search(r"Goal:\s*\.", visible):
        hard_fails.append("EMPTY_GOAL_FIELD")
    for ph in ("[insert", "placeholder", "lorem ipsum", "tbd"):
        if ph in vlow:
            hard_fails.append("PLACEHOLDER_TEXT:" + ph)
    cust_vis = visible.split("Source / Evidence Appendix")[0]
    if re.findall(r"\b(?:GB|EC)-\d{3}\b", cust_vis):
        hard_fails.append("CUSTOMER_FACING_EVIDENCE_ID_LEAK")
    jacts = set(re.findall(r"ACT-\d{3}", visible))
    cur = {(a.get("action_id") or "") for a in acts}
    if jacts - cur:
        hard_fails.append("JOURNEY_MAP_ACTION_ID_MISMATCH:" + ",".join(sorted(jacts - cur)))
    if "do now scope" in vlow:
        hard_fails.append("STATUS_TEXT_CONTRADICTION")
    if "attorney" in vlow:
        hard_fails.append("GENERIC_ROLE_LABEL:attorney")
    for a in acts:
        if ";" in (a.get("primary_url") or ""):
            hard_fails.append("NO_MULTI_URL_ACTION_SCOPE:" + str(a.get("action_id")))
        if ";" in (a.get("primary_url") or ""):
            pass
    # rendered multi-url: dev-page rollout language under contact-us-only action
    if any(a.get("primary_url", "").lower().rstrip("/").endswith("/contact-us") for a in acts) and \
            re.search(r"development pages ['\u2019']?enquire", vlow):
        hard_fails.append("NO_MULTI_URL_ACTION_SCOPE:ACT-001(rendered)")

    # MANDATORY DEDUCTION DISCIPLINE + anchored scoring (LLM red-team, own prompt)
    llm = {}
    llm_repair = []
    try:
        from seo_crawler import resolve_openrouter_key, openrouter_chat, _coerce_msg_content
        key = resolve_openrouter_key()
        rubric_txt = json.dumps(RUBRIC, indent=0)[:9000]
        prompt = (
            "You are the RED-TEAM SCORING AUDITOR (independent of the report writer and of the first "
            f"reviewer). Customer: {job.get('company_name')} ({domain}). Assume the PDF contains subtle "
            "unsupported claims, contradictions, generic template language, weak evidence, scope creep, "
            "stale content or context errors — find them if they exist.\n\n"
            "Score each category using the ANCHORED rubric below: for each criterion award 0-5 points "
            "against the written anchors, citing PDF page, section, exact quote, and reason. If a "
            "meaningful one-point improvement exists, the criterion CANNOT receive 5. Be adversarial.\n\n"
            "RUBRIC:\n" + rubric_txt + "\n\nReply ONLY as JSON: {\"categories\":{\"<name>\":"
            "{\"criteria\":{\"<criterion>\":{\"points\":N,\"page\":N,\"section\":\"...\","
            "\"quote\":\"...\",\"anchor\":\"...\",\"reason\":\"...\"}}},"
            "\"repair_instructions\":[\"...\"]}}\n\nPDF TEXT (truncated):\n" + visible[:12000])
        payload = {"model": AUDITOR_MODEL, "messages": [
            {"role": "system", "content": "You are the adversarial red-team scoring auditor. Never default to maximum. Every point must cite evidence."},
            {"role": "user", "content": prompt}], "temperature": 0, "max_tokens": 6000}
        from seo_crawler import openrouter_chat, _coerce_msg_content
        env = openrouter_chat(key, payload)
        content = _coerce_msg_content(env.get("choices", [{}])[0].get("message", {}).get("content", ""))
        js = content[content.find("{"): content.rfind("}") + 1] if content and "{" in content else "{}"
        try:
            llm = json.loads(js)
        except json.JSONDecodeError:
            # salvage: walk back to the last balanced closing brace of the categories object
            depth, end = 0, -1
            for i, ch in enumerate(js):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            llm = json.loads(js[:end]) if end > 0 else {}
            hard_fails.append("RED_TEAM_JSON_TRUNCATED:scored from partial audit output")
        llm_repair = llm.get("repair_instructions", []) or []
    except Exception as e:
        hard_fails.append("RED_TEAM_AUDIT_UNAVAILABLE:" + str(e)[:100])
        llm = {"categories": {}}

    # anchored category scoring: criteria average mapped to 0-100, CAPPED at 95
    categories = {}
    all_citations = []
    for cname, criteria in RUBRIC.items():
        cat_llm = (llm.get("categories") or {}).get(cname) or {}
        crit_out = {}
        pts = []
        for cr, anchors in criteria.items():
            cl = (cat_llm.get("criteria") or {}).get(cr) or {}
            try:
                p = int(cl.get("points", 0))
            except Exception:
                p = 0
            p = max(0, min(5, p))
            pts.append(p)
            crit_out[cr] = {"points": p, "page": cl.get("page"), "section": cl.get("section"),
                            "quote": (cl.get("quote") or "")[:160], "anchor": anchors.get(str(p), ""),
                            "reason": (cl.get("reason") or "")[:200]}
            if cl.get("quote"):
                all_citations.append({"category": cname, "criterion": cr,
                                      "page": cl.get("page"), "section": cl.get("section"),
                                      "quote": (cl.get("quote") or "")[:160],
                                      "points": p})
        if not pts:
            # audit output truncated/incomplete for this category: award the honest
            # level-3 anchor ("specific but incomplete evidence") NOT 0 and NOT default-max.
            hard_fails.append("RED_TEAM_SCORE_INCOMPLETE:" + cname)
            categories[cname] = {"score": 60, "pct": 60, "criteria": {},
                                 "note": "audit output truncated for this category; scored at level-3 anchor pending re-audit"}
            continue
        raw = round(sum(pts) / (len(pts) * 5) * 100)
        categories[cname] = {"score": raw, "pct": raw, "criteria": crit_out}
    overall = min(AUTO_MAX, round(sum(v["score"] for v in categories.values()) / len(categories)))
    # if any meaningful improvement was identified (LLM repair instructions exist), cap below max
    if overall >= AUTO_MAX and llm_repair:
        overall = AUTO_MAX - 1
        categories = {k: {**v, "score": min(v["score"], overall)} for k, v in categories.items()}

    bands = "0-49/50-74/75-89 BLOCKED; 90-95 eligible; 96-100 not automatable"
    decision = "INDEPENDENT_REVIEW_PASS" if (90 <= overall <= AUTO_MAX
                                             and all(v["pct"] >= 90 for v in categories.values())
                                             and not hard_fails) else "DELIVERY_BLOCKED"

    record = {
        "auditor_agent_id": AUDITOR_AGENT_ID,
        "auditor_run_id": f"RTA-{int(time.time())}-{sha256((csha + ts).encode())[:8]}",
        "job_id": job.get("order_id"),
        "customer_name": job.get("company_name"),
        "approved_customer_domain": domain,
        "candidate_sha256": csha,
        "pdf_filename": os.path.basename(candidate_pdf),
        "generation_timestamp": ts,
        "overall_score": overall,
        "score_cap": AUTO_MAX,
        "bands": bands,
        "categories": categories,
        "evidence_citations": all_citations[:40],
        "hard_fails": hard_fails,
        "repair_instructions": llm_repair,
        "delivery_decision": ("INDEPENDENT_REVIEW_PASS" if decision == "PASS"
                              else "DELIVERY_BLOCKED"),
        "strict_reviewer_decision_on_file": (strict_reviewer_record or {}).get("delivery_decision"),
    }
    record["auditor_signature"] = sign({k: v for k, v in record.items() if k != "auditor_signature"})
    return record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate-pdf", required=True)
    ap.add_argument("--job-id", required=True)
    ap.add_argument("--cards", required=True)
    ap.add_argument("--review-file", default="")
    a = ap.parse_args()
    job = json.load(open(os.path.join(_HERE, "output", f"order_{a.job_id}.json"), encoding="utf-8"))
    cf = json.load(open(a.cards, encoding="utf-8"))
    cards = [c for c in cf.get("golden_evidence_cards", []) if gp.gate2_validate_evidence_card(c)["valid"]]
    acts = gp.gate3_actions_from_evidence_cards(cards, customer_context=cf.get("customer") or {})
    srec = json.load(open(a.review_file, encoding="utf-8")) if a.review_file and os.path.exists(a.review_file) else None
    rec = review(a.candidate_pdf, job, cards, acts, srec)
    os.makedirs(os.path.join(_HERE, "output", "redteam"), exist_ok=True)
    out = os.path.join(_HERE, "output", "redteam", f"{a.job_id}_redteam.json")
    json.dump(rec, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps({"file": out, "decision": rec["delivery_decision"],
                      "overall": rec["overall_score"], "hard_fails": rec["hard_fails"],
                      "signature": rec["auditor_signature"][:16]}, indent=1))


if __name__ == "__main__":
    main()
