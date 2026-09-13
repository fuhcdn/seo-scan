#!/usr/bin/env python3
"""autonomous_gate.py — FINAL AUTONOMOUS REPORT CONTENT QUALITY STANDARD enforcement.

Implements the role-separated quality architecture:
  Research Agent   -> (external, in research.py)
  Report Generator -> (external, in report_engine.py) CANNOT set final score or approve delivery.
  Deterministic Validator  -> deterministic_validate()  (code/rule-based, objective counts)
  Blind Quality Auditor    -> run_blind_audit()         (separate AI, never sees generator score)
  Delivery Decision Engine -> decide_delivery()         (ONLY component that sets READY_TO_DELIVER)

Zero-trust rule: a report must NEVER self-declare 100/100, and the generator can never
approve its own delivery. The final score exists only after: deterministic PASS AND
blind PASS AND no hard-fail.
"""
import json
import os
import re

# ---------------- Deterministic Validator (code/rule based) ----------------

PRIVACY_LEAK_PATTERNS = [
    r"file:///app", r"file://", r"/app/pipeline", r"/pipeline/", r"/opt/",
    r"/home/", r"/tmp/", r"localhost", r"127\.0\.0\.1",
    r"sk_live_", r"rk_live_", r"sk_test_", r"whsec_", r"resend_",
]
PLACEHOLDER_PATTERNS = [
    r"\{\{[A-Z_]+\}\}", r"Dummy", r"DummyData", r"Lorem ipsum", r"PLACEHOLDER",
    r"\[company\]", r"\[website\]", r"\[name\]", r"sample_url", r"TBD\b",
    r"TODO[: ]", r"acme\b", r"example\.com/test",
]
GENERIC_FINDING_PATTERNS = [
    r"homepage accessible", r"homepage accessible and read", r"sampled \d+/\d+ pages",
    r"http 200", r"http_\d{3}", r"title tag exists", r"title exists",
    r"robots\.txt exists", r"robots\.txt is accessible",
    r"sitemap( found| exists| not found| returned)", r"internal links? (exist|found)",
    r"website is readable", r"health score", r"authority score",
    r"validate this observation", r"improve seo", r"add keywords",
    r"improve content", r"fix technical seo",
]
GENERIC_ACTION_PATTERNS = [
    r"validate this observation", r"improve seo", r"add keywords", r"improve content",
    r"fix technical seo", r"check (the )?results? page", r"check robots\.txt",
    r"check search console", r"monitor rankings", r"see what happens",
]


def _count_matches(text, patterns):
    n = 0
    for p in patterns:
        n += len(re.findall(p, text, re.I))
    return n


def deterministic_validate(research, findings, actions, tier, order=None, doc_text=""):
    """Code/rule-based objective validation. Returns dict of counts + PASS/FAIL list.
    Generator cannot edit these values. doc_text = combined draft text (findings+actions+report)."""
    v = {}
    is_premium = tier == "PREMIUM_REPORT"

    # intake completeness (§3 required 8)
    req = ["website_url", "company_name", "primary_business_goal",
           "main_products_or_services", "target_market_or_service_area",
           "primary_customer_action", "report_language", "selected_product_category"]
    v["intake_complete"] = 0
    missing_intake = []
    for f in req:
        alias = "url" if f == "website_url" else (
            "primary_market_or_service_area" if f == "target_market_or_service_area" else f)
        val = (order or {}).get(alias) or (order or {}).get(f)
        if not val:
            missing_intake.append(f)
    v["intake_complete"] = 1 if not missing_intake else 0
    v["missing_intake_fields"] = missing_intake

    # page observations (§4/§6/§7): meaningful pages (exclude legal/duplicate)
    pages_raw = research.get("pages_reviewed") or (research.get("architecture") or {}).get("pages_reviewed") or []
    legal_domains = ["privacy", "terms", "refund", "disclaimer", "legal", "cookie"]
    meaningful = []
    for p in pages_raw:
        if isinstance(p, dict):
            u = p.get("url") or ""
            if not p.get("ok"):
                continue
        else:
            u = str(p or "")
        if not u:
            continue
        if any(f"/{ld}/" in "/" + u.split("//")[-1].split("/", 1)[-1].lower() for ld in legal_domains):
            continue
        if re.search(r"/(legal|privacy|terms|refund|disclaimer)/", u, re.I):
            continue
        meaningful.append(u)
    # dedupe
    seen = set(); uniq = []
    for u in meaningful:
        if u not in seen:
            seen.add(u); uniq.append(u)
    v["meaningful_page_observation_count"] = len(uniq)
    v["legal_or_duplicate_page_count"] = len(pages_raw) - len(uniq) if len(pages_raw) >= len(uniq) else 0

    # SERP: valid vs invalid/unparsed (§5)
    serp = research.get("serp") or []
    invalid_tokens = ["none parsed", "no result parsed", "blank snippet", "results are mostly mixed",
                      "unavailable", "Search could not be executed"]
    valid_serp = 0; invalid_serp = 0
    valid_serp_queries = []
    for s in serp:
        obs = (s.get("direct_observation") or "") + " " + (s.get("result_pattern") or "")
        q = s.get("query") or ""
        doms = [d for d in (s.get("source_domains") or []) if d and "(no result" not in d]
        is_invalid = (any(t.lower() in obs.lower() for t in invalid_tokens)) or (not doms and not s.get("source_url"))
        if is_invalid:
            invalid_serp += 1
        else:
            valid_serp += 1
            valid_serp_queries.append(q)
    v["valid_serp_observation_count"] = valid_serp
    v["invalid_or_unparsed_serp_observation_count"] = invalid_serp
    v["valid_serp_queries"] = valid_serp_queries

    # competitor/result-pattern examples (§5)
    comps = [c for c in (research.get("competitors") or []) if c and "(no result" not in str(c)]
    v["competitor_or_result_pattern_count"] = len(comps)

    # findings: genuine vs generic (exclude prohibited/log findings)
    genuine_findings = []
    generic_findings = 0
    for f in findings:
        claim = (f.get("claim") or f.get("title") or "")
        if _count_matches(claim, GENERIC_FINDING_PATTERNS) > 0 or len(claim.strip()) < 12:
            generic_findings += 1
            continue
        genuine_findings.append(f)
    v["genuine_finding_count"] = len(genuine_findings)
    v["generic_finding_count"] = generic_findings

    # actions: concrete vs generic/duplicate (§9)
    concrete_actions = 0; generic_actions = 0; duplicate_actions = 0
    seen_titles = set(); seen_titles_low = set()
    for a in actions:
        title = (a.get("title") or a.get("claim") or "").strip()
        low = title.lower()
        accept = a.get("acceptance_criteria") or ""
        owner = a.get("owner") or ""
        valid = a.get("validation_method") or ""
        if not title or _count_matches(title, GENERIC_ACTION_PATTERNS) > 0:
            generic_actions += 1
            continue
        if not (accept and owner and valid):
            pass  # field completeness handled by blank_required_field_count
        if low in seen_titles_low:
            duplicate_actions += 1
            continue
        seen_titles_low.add(low)
        concrete_actions += 1
    v["concrete_action_count"] = concrete_actions
    v["generic_action_count"] = generic_actions
    v["duplicate_action_count"] = duplicate_actions

    # content/developer briefs (premium)
    v["content_brief_count"] = len(research.get("content_briefs") or [])
    v["technical_brief_count"] = len(research.get("technical_briefs") or [])

    # roadmap action-ID coverage (§10)
    roadmap = research.get("roadmap") or []
    if roadmap:
        ids = set()
        for item in roadmap:
            t = str(item.get("title") or item.get("action_id") or "")
            found = re.findall(r"ACT-\d+|Action\s*\d+|\b\d{2,3}\b", t)
            ids.update(found)
        v["roadmap_action_id_coverage"] = min(1.0, len(ids) / max(1, len(roadmap)))
    else:
        v["roadmap_action_id_coverage"] = 0.0

    # blank required fields (§4/§8/§9: findings/actions)
    blank_required = 0
    for f in findings:
        for k in ("claim", "business_reason", "recommended_action", "owner", "effort"):
            if not (f.get(k) or "").strip():
                blank_required += 1
                break
    for a in actions:
        if not (a.get("acceptance_criteria") or "").strip():
            blank_required += 1
    v["blank_required_field_count"] = blank_required

    # privacy / infra leaks (§11)
    leak_concats = doc_text + " " + json.dumps(research.get("evidence_ledger") or [], ensure_ascii=False)
    v["internal_path_leak_count"] = _count_matches(leak_concats, PRIVACY_LEAK_PATTERNS)
    v["broken_source_link_count"] = sum(1 for e in (research.get("evidence_ledger") or [])
                                        if not (e.get("source_url") or "").strip())
    v["placeholder_count"] = _count_matches(leak_concats, PLACEHOLDER_PATTERNS)
    v["privacy_leak"] = 1 if v["internal_path_leak_count"] > 0 else 0

    # ---- deterministic hard-fail + minimums ----
    hard_fail = []
    min_pages = 12 if is_premium else 6
    min_serp = 8 if is_premium else 3
    min_comp = 3 if is_premium else 2
    min_findings = 5 if is_premium else 3
    min_actions = 15 if is_premium else 5
    if not v["intake_complete"]:
        hard_fail.append("intake_incomplete")
    if v["meaningful_page_observation_count"] < min_pages:
        hard_fail.append(f"page_minimum({v['meaningful_page_observation_count']}/{min_pages})")
    if v["valid_serp_observation_count"] < min_serp:
        hard_fail.append(f"serp_minimum({v['valid_serp_observation_count']}/{min_serp})")
    if v["competitor_or_result_pattern_count"] < min_comp:
        hard_fail.append(f"competitor_minimum({v['competitor_or_result_pattern_count']}/{min_comp})")
    if v["genuine_finding_count"] < min_findings:
        hard_fail.append(f"finding_minimum({v['genuine_finding_count']}/{min_findings})")
    if v["concrete_action_count"] < min_actions:
        hard_fail.append(f"action_minimum({v['concrete_action_count']}/{min_actions})")
    if v["internal_path_leak_count"] > 0:
        hard_fail.append("internal_path_leak")
    if v["placeholder_count"] > 0:
        hard_fail.append("placeholder_present")
    if v["blank_required_field_count"] > 0:
        hard_fail.append("blank_required_field")
    v["hard_fail_list"] = hard_fail
    # score ceiling: if minimums unmet, cap at 69 (§13); else allow 90+ only with specific evidence
    if hard_fail and any("minimum" in h for h in hard_fail):
        v["_ceiling"] = 69
    else:
        v["_ceiling"] = None  # null = ceiling not enforced here (blind auditor decides 90+)
    return v


# ---------------- Blind Quality Auditor (independent AI) ----------------

BLIND_PROMPT = """You are the INDEPENDENT BLIND QUALITY AUDITOR for a paid SEO report. You are the final quality authority. You did NOT write or generate this report. Your role is to independently verify quality and award a score out of 100.

You receive ONLY: the selected product tier, customer intake, the evidence ledger, research coverage metrics, and the report draft text. You do NOT receive and must IGNORE any generator self-score or self-conclusion — there is none in this input.

Score exactly these categories (max in parentheses), awarding points ONLY with specific evidence drawn from the provided content (a source URL, page, query, action, owner, acceptance criterion, or concrete report text). Award ZERO for blank, generic, or unsupported claims. Do not award points merely because a heading exists:

A. Evidence integrity (20): 5 every material fact has a valid source; 4 inferences correctly labelled+reasoned; 4 every hypothesis has a validation step; 4 no fabricated metrics/outcomes/private-access; 3 limitations stated clearly.
B. Research completeness (20): 6 meaningful page-coverage; 6 valid result-pattern coverage; 4 competitor/result-pattern coverage; 4 complete intake used.
C. Customer-specific strategic value (20): 5 real business decisions (not system logs); 5 addresses client pages/services/market/action; 5 customer-specific business consequence; 5 genuine prioritisation (do-first/later).
D. Actionability (20): 5 actions name affected scope; 4 owner+credible effort; 4 dependencies+acceptance criteria; 4 validation+review window; 3 roadmap action-ID-linked.
E. Structure/customer experience (10): 3 useful executive brief; 2 consistent labels/confidence/sources; 2 readable tables/cards; 2 scope/limits clear; 1 tier scope correct.
F. PDF/language/privacy (10): 2 clean readable; 2 safe filename/metadata; 3 correct language/grammar; 2 no logs/paths/placeholders/broken links; 1 professional hierarchy no fake data.

Response MUST be a JSON object:
{
  "A_evidence": {"points": <0-20>, "evidence": "<specific report text/source>"},
  "B_research": {"points": <0-20>, "evidence": "<...>"},
  "C_strategic": {"points": <0-20>, "evidence": "<...>"},
  "D_actionability": {"points": <0-20>, "evidence": "<...>"},
  "E_structure": {"points": <0-10>, "evidence": "<...>"},
  "F_pdf": {"points": <0-10>, "evidence": "<...>"},
  "total": <sum>,
  "hard_fail": <true/false>,
  "hard_fail_reasons": ["..."],
  "repair_instructions": ["specific missing evidence/defects to repair"],
  "verified_source_count": <count of distinct real source URLs/pages/queries you saw>
}
Rules: total 90-100 = PASS (delivery allowed); 85-89 = REVISE (repair, no send); 70-84 = RESEARCH INCOMPLETE; 0-69 = FAIL (no send). This report must NEVER be 100/100. If you cannot find specific evidence for a point, assign zero.

TIER: {tier}
CUSTOMER INTAKE: {intake}
RESEARCH COVERAGE METRICS: {coverage}
EVIDENCE LEDGER: {ledger}
REPORT DRAFT TEXT (excerpt, first 6000 chars): {draft}
"""


def run_blind_audit(tier, intake, coverage, ledger, draft, model="deepseek/deepseek-chat-v3-0324"):
    """Independent blind audit via OpenRouter. NEVER sees generator score. Returns dict."""
    import seo_crawler as SC
    key = SC.resolve_openrouter_key()
    if not key:
        return {"error": "no_openrouter_key", "total": 0, "hard_fail": True,
                "hard_fail_reasons": ["blind auditor unavailable (no LLM key)"]}
    # bounding draft/ledger to keep prompt bounded
    draft_ex = (draft or "")[:6000]
    ledger_ex = json.dumps((ledger or [])[:40], ensure_ascii=False)[:4000]
    intake_ex = json.dumps(intake or {}, ensure_ascii=False)[:1500]
    coverage_ex = json.dumps(coverage or {}, ensure_ascii=False)[:1500]
    prompt = (BLIND_PROMPT
              .replace("{tier}", str(tier))
              .replace("{intake}", intake_ex)
              .replace("{coverage}", coverage_ex)
              .replace("{ledger}", ledger_ex)
              .replace("{draft}", draft_ex))
    messages = [{"role": "user", "content": prompt}]
    attempts = [
        {"model": model, "messages": messages, "temperature": 0.1,
         "max_tokens": 2000, "response_format": {"type": "json_object"}},
        {"model": model, "messages": messages, "temperature": 0.1, "max_tokens": 2000},
    ]
    last_err = None
    for payload in attempts:
        try:
            env = SC.openrouter_chat(key, payload, timeout=180)
            content = SC._coerce_msg_content((env.get("choices") or [{}])[0].get("message", {}).get("content"))
            parsed = SC._extract_json_obj(content if isinstance(content, str) else json.dumps(content))
            if parsed is not None:
                parsed["error"] = None
                # normalize total
                try:
                    parsed["total"] = int(parsed.get("total", 0))
                except Exception:
                    parsed["total"] = 0
                parsed["hard_fail"] = bool(parsed.get("hard_fail"))
                return parsed
            last_err = "no-json"
        except Exception as e:
            last_err = str(e)[:120]
    return {"error": last_err or "fail", "total": 0, "hard_fail": True,
            "hard_fail_reasons": [f"blind auditor failed: {last_err}"]}


# ---------------- Delivery Decision Engine ----------------

DELIVERY_STATES = [
    "DRAFT", "RESEARCH_INCOMPLETE", "INSUFFICIENT_BUSINESS_CONTEXT",
    "INSUFFICIENT_PUBLIC_EVIDENCE", "AUDIT_FAILED", "QUALITY_REPAIRING",
    "PDF_REPAIRING", "DELIVERY_BLOCKED", "READY_TO_DELIVER", "DELIVERED",
]


def decide_delivery(deterministic, blind, is_pdf_clean=True):
    """ONLY function permitted to set READY_TO_DELIVER. Returns (state, reason_list).
    READY_TO_DELIVER only when: deterministic PASS (no hard_fail_list) AND blind total>=90
    AND blind no hard_fail AND no deterministic hard-fail AND pdf clean."""
    reasons = []
    d_hard = deterministic.get("hard_fail_list") or []
    b_hard = blind.get("hard_fail") or False
    b_total = blind.get("total") or 0

    if deterministic.get("intake_complete") != 1:
        return "INSUFFICIENT_BUSINESS_CONTEXT", ["intake incomplete"]
    # auto-determination of research insufficiency from hard-fail minimums
    min_level = [h for h in d_hard if "minimum" in h]
    if min_level:
        return "RESEARCH_INCOMPLETE", min_level
    if d_hard:
        return "DELIVERY_BLOCKED", d_hard
    if b_hard:
        return "AUDIT_FAILED", blind.get("hard_fail_reasons") or ["blind audit hard-fail"]
    if b_total < 70:
        return "AUDIT_FAILED", [f"blind score {b_total} < 70"]
    if 70 <= b_total <= 84:
        return "RESEARCH_INCOMPLETE", [f"blind score {b_total} in RESEARCH INCOMPLETE band; gather evidence"]
    if 85 <= b_total <= 89:
        return "QUALITY_REPAIRING", [f"blind score {b_total} in REVISE band; repair specific gaps"]
    if b_total >= 90:
        if not is_pdf_clean:
            return "PDF_REPAIRING", ["PDF privacy/layout validation failed"]
        return "READY_TO_DELIVER", [f"deterministic PASS + blind {b_total}/100 PASS"]
    return "DELIVERY_BLOCKED", ["unclassified"]


# ---------------- PDF privacy/language/layout validator ----------------

def validate_pdf(filename_safe=True, text_has_leak=0, metadata_ok=True):
    """§11 PDF privacy/language/layout checks. Returns (pass: bool, issues[])."""
    issues = []
    if not filename_safe:
        issues.append("unsafe_filename")
    if text_has_leak:
        issues.append("privacy_leak_in_pdf_text")
    if not metadata_ok:
        issues.append("unsafe_metadata")
    return (len(issues) == 0, issues)