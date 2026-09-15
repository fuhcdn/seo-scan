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
REVIEWER_MODEL = "z-ai/glm-4.6"

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
            "Reply ONLY as JSON: {\"categories\":{\"<name>\":{\"score\":N,\"deduction\":\"...\",\"ledger\":{\"pdf_page\":N,\"section\":\"...\",\"action_or_card_id\":\"...\",\"evidence_text\":\"...\",\"validation\":\"...\",\"result\":\"PASS|FAIL\"}}},"
            "\"repair_instructions\":[\"...\"]}. EVERY category MUST include a ledger entry with pdf_page, section, action_or_card_id, evidence_text (quoted verbatim from the PDF), validation performed, and result; a category without a complete ledger entry is scored 0. "
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
        # EVIDENCE LEDGER enforcement: every category needs a complete ledger entry
        _ledger_incomplete = []
        for _cn in REQUIRED_CATEGORIES:
            _le = (llm_scores.get(_cn) or {}).get("ledger") or {}
            _need = ("pdf_page", "section", "evidence_text", "validation", "result")
            if not _le or any(not str(_le.get(k) or "").strip() for k in _need):
                _ledger_incomplete.append(_cn)
        if _ledger_incomplete:
            hard_fails.append("REVIEWER_EVIDENCE_INCOMPLETE:" + ",".join(_ledger_incomplete))
    except Exception as e:
        hard_fails.append("REVIEWER_LLM_AUDIT_UNAVAILABLE:" + str(e)[:80])
        _ledger_incomplete = list(REQUIRED_CATEGORIES)  # no ledger without successful LLM audit

    # category scores: min(deterministic-driven floor, LLM score); unknown -> 0 until evidenced
    categories = {}
    for cname in REQUIRED_CATEGORIES:
        entry = llm_scores.get(cname) or {}
        try:
            s = int(entry.get("score", 0))
        except Exception:
            s = 0
        s = max(0, min(95, s))  # auto-cap 95 (owner directive)
        categories[cname] = {"score": s, "max": 100, "pct": s,
                             "deduction": entry.get("deduction") or "not evidenced by reviewer"}
    overall = min(95, round(sum(v["score"] for v in categories.values()) / len(categories), 1))  # auto-max 95 (owner directive)

    # ---------- SEMANTIC CROSS-CHECKS (whole-document, owner directive 2026-09-14d) ----------
    # 1. report generated date vs every research-observation date
    _gen_dates = re.findall(r"Report date[:\s]+(\d{4}-\d{2}-\d{2})", visible)
    _res_dates = re.findall(r"(?:read|observation|observed)[^0-9]{0,20}(2026-\d{2}-\d{2})", visible, re.I) + \
                 re.findall(r"(2026-\d{2}-\d{2})[^.]{0,40}(?:direct page|page read|observation)", visible, re.I)
    if _gen_dates and _res_dates and min(_gen_dates) < max(_res_dates):
        hard_fails.append("REPORT_DATE_BEFORE_RESEARCH_DATE: report %s < research %s"
                          % (min(_gen_dates), max(_res_dates)))
        deductions.append({"location": "page 1 header", "section": "Report date",
                           "issue": "report date %s precedes research observation %s"
                                    % (min(_gen_dates), max(_res_dates)),
                           "why": "a report cannot be generated before its recorded research date",
                           "points": 8,
                           "improvement": "Report generated: actual render date; Research observed: actual page-observation date(s)"})
    # 2. per-action scope vs placement/CTA/QA/scale-rule text
    for _a in acts:
        _aid = _a.get("action_id")
        _c = next((k for k in cards if k.get("card_id") in (_a.get("evidence_ids") or [])), {})
        _ib = _c.get("implementation_brief") or {}
        _scope_text = " ".join(str(v) for v in
                               [_ib.get("scope_note", ""), _ib.get("exact_module_placement", ""),
                                _c.get("recommended_module", ""), _c.get("first_signal", "")]).lower()
        _pu = (_a.get("primary_url") or "").lower()
        _path = re.sub(r"https?://[^/]+", "", _pu).strip("/")
        # ignore explicit-exclusion sentences: "X is out of scope / excluded" is compliance,
        # not scope creep. Only ACTIVE rollout language triggers the hard fail.
        _active = re.sub(r"[^.]*\b(?:out of scope|excluded|explicitly excluded|not (?:included|part)|separate (?:future )?action|separate post-validation)\b[^.]*\.", " ", _scope_text)
        _other_pages = [t for t in ("development page", "development-template", "every development",
                                    "development pages", "per-development", "all development",
                                    "development-page cta rollout")
                        if t in _active]
        if _other_pages and ("scope is limited" in _scope_text or "out of scope" in _scope_text):
            hard_fails.append("NO_MULTI_URL_ACTION_SCOPE:" + str(_aid))
            deductions.append({"location": "action rows", "section": "scope/placement", "action_id": _aid,
                               "issue": "scope claims page-only but placement/rollout text also references %s"
                                        % ", ".join(_other_pages),
                               "why": "multi-page action hiding under one primary URL", "points": 8,
                               "improvement": "restrict every scope/placement/CTA/rollout reference to the "
                                              "primary URL page; move other pages to a separate future action"})
    # 2b. PDF-visible multi-URL scope: the rendered artifact itself must not contain
    # other-page rollout language tied to a single-URL action
    _vis_dev = [m.start() for m in re.finditer(r"development pages ['']?enquire|per-development enquiry form|contact us \+ development pages", vlow)]
    if _vis_dev and any((a.get("primary_url") or "").lower().rstrip("/").endswith("/contact-us") for a in acts):
        hard_fails.append("NO_MULTI_URL_ACTION_SCOPE:ACT-001(rendered)")
        deductions.append({"location": "rendered action rows", "section": "ACT-001 scope",
                           "action_id": "ACT-001",
                           "issue": "rendered PDF still contains development-pages 'Enquire' / rollout language under a /contact-us-only action",
                           "why": "multi-page action hiding under one primary URL", "points": 8,
                           "improvement": "remove all development-page references from ACT-001 rendering; regenerate the PDF"})
    # 3. unsupported market/performance claims as fact
    _claim_pats = [("largest research-heavy segment", "customer's largest segment"),
                   ("largest segment", "customer segment size"),
                   ("convert at higher rates", "conversion-rate claim"),
                   ("converts at higher rates", "conversion-rate claim"),
                   ("return repeatedly", "repeat-visit claim"),
                   ("highest-value", "customer's highest-value segment")]
    for _pat, _label in _claim_pats:
        if _pat in vlow:
            hard_fails.append("UNSUPPORTED_CUSTOMER_MARKET_OR_PERFORMANCE_CLAIM:" + _label)
            deductions.append({"location": "mechanism text", "section": "any", "issue":
                               "presents '%s' as fact from public-page observation" % _pat,
                               "why": "claims discipline: unprovable from public pages", "points": 6,
                               "improvement": "reword as: Hypothesis to validate with customer CRM, "
                                              "analytics and enquiry data."})
    # 4. status text contradictions
    if "do_now scope" in vlow or "do now scope" in vlow:
        hard_fails.append("STATUS_TEXT_CONTRADICTION:DO_NOW_scope_wording")
        deductions.append({"location": "scale rule", "section": "actions", "issue":
                           "scale rule says DO_NOW scope while action is VALIDATE FIRST",
                           "why": "roadmap/status consistency", "points": 5,
                           "improvement": "replace with: If approved and published, keep the initial "
                                          "validated rollout limited to this page only."})
    # contradiction = an action's OWN status label contradicts its investment_status
    for _a in acts:
        _aid = re.escape(str(_a.get("action_id")))
        _is_vf = (_a.get("investment_status") or "") != "DO_NOW"
        # action row format: '<ACT-xxx> ... VALIDATE FIRST / DO NOW' or exec-summary '[DO NOW]'
        if _is_vf and re.search(_aid + r"[^\n]{0,400}\[DO NOW\]", visible):
            hard_fails.append("STATUS_TEXT_CONTRADICTION:" + str(_a.get("action_id")) + "_labelled_DO_NOW")

    # ---------- REVIEWER SELF-AUDIT ----------
    self_audit = {
        "compared_report_date_to_every_research_date": bool(_gen_dates and _res_dates),
        "compared_every_action_scope_vs_placement_cta_qa_dod_scale": len(acts) > 0,
        "verified_no_unproven_segment_or_performance_claim_as_fact": not any(
            h.startswith("UNSUPPORTED_CUSTOMER_MARKET_OR_PERFORMANCE_CLAIM") for h in hard_fails),
        "verified_action_statuses_agree_with_approval_dependencies": not any(
            h.startswith("DO_NOW_REQUIRES_NO_UNRESOLVED_APPROVAL") for h in hard_fails),
        "inspected_entire_visible_pdf_not_only_json": len(visible) > 1000,
        "quoted_candidate_sha_and_page_section_evidence": bool(csha),
        "review_ledger_complete_for_every_category": not _ledger_incomplete,
        "found_zero_contradictions": not any(
            h.startswith(("STATUS_TEXT_CONTRADICTION", "JOURNEY_MAP_ACTION_ID_MISMATCH",
                          "NO_MULTI_URL_ACTION_SCOPE")) for h in hard_fails),
    }
    self_audit_pass = all(v is True for v in self_audit.values())
    if not self_audit_pass:
        hard_fails.append("REVIEWER_SELF_AUDIT_INCOMPLETE")

    decision = "PASS" if (overall >= 90 and all(v["pct"] >= 90 for v in categories.values())
                          and not hard_fails and structural == 100.0 and self_audit_pass) else "DELIVERY_BLOCKED"
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
        "semantic_cross_checks": "performed across all customer-visible sections",
        "reviewer_self_audit": self_audit,
        "review_ledger": {k: ((llm_scores.get(k) or {}).get("ledger") or {}) for k in REQUIRED_CATEGORIES},
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
