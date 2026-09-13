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


def build_customer_context_lock(order, research=None):
    """§1 repair: per-job customer-context lock. Every customer-facing sentence/action must
    reference the customer's own domain/company/products; foreign brands are allowed only as
    competitor evidence. Returns a dict used for contamination checks."""
    from urllib.parse import urlparse as _up
    domain = ""
    cu = (order.get("website_url") or order.get("url") or "").strip()
    if cu.startswith(("http://", "https://")):
        domain = (_up(cu).netloc or "").lower().lstrip("www.")
    company = (order.get("company_name") or "").strip()
    lock = {
        "job_id": order.get("order_id") or "",
        "customer_company": company,
        "customer_primary_domain": domain,
        "customer_owned_domains": [domain] if domain else [],
        "customer_products_services": (order.get("main_products_or_services") or "").strip(),
        "customer_market": (order.get("target_market_or_service_area") or order.get("primary_market_or_service_area") or "").strip(),
        "customer_business_goal": (order.get("primary_business_goal") or "").strip(),
        "customer_primary_action": (order.get("primary_customer_action") or "").strip(),
        "customer_competitor_domains": [str(x).lower().lstrip("www.") for x in (order.get("known_competitors") or [])],
        "report_language": (order.get("report_language") or "en"),
        "selected_tier": (order.get("report_tier") or order.get("selected_product_category") or "US$497").upper(),
    }
    # normalize competitor domains (may be bare or http)
    cclean = []
    for cd in lock["customer_competitor_domains"]:
        if cd.startswith(("http://", "https://")):
            cd = cd.split("//")[1].split("/")[0].split(":")[0]
        cd = cd.lstrip("www.")
        if cd and cd not in cclean:
            cclean.append(cd)
    lock["customer_competitor_domains"] = cclean
    return lock


def cross_customer_contamination_check(lock, findings, actions, roadmap_text=None):
    """§1 Failure 1: find any foreign brand/domain appearing in customer-facing ACTION /
    finding recommendation / acceptance / validation text (not in evidence/source). Blocks.
    Returns (contaminated_count, foreign_terms_found)."""
    owned = set(lock["customer_owned_domains"])
    foreign_domains = [d for d in lock["customer_competitor_domains"] if d not in owned]
    # also catch common SEO-tool brands even if not declared
    KNOWN_FOREIGN_BRANDS = {
        "ahrefs", "semrush", "moz", "backlinko", "searchengineland", "spyfu", "surfer seo",
        "screaming frog", "clearscope", "yoast", "hreflang-checker", "neil patel", "hubspot"}
    foreign_terms = set()
    targets = []
    for a in actions:
        # customer-facing recommendation fields
        chunks = [
            a.get("title") or "", a.get("business_reason") or "",
            a.get("recommended_action") or "", a.get("acceptance_criteria") or "",
            a.get("validation_method") or "", a.get("affected_scope") or "",
            a.get("customer_owned_scope") or "",
        ]
        for ch in chunks:
            cl = ch.lower()
            for fd in foreign_domains:
                if fd and fd in cl and fd not in owned:
                    foreign_terms.add(fd)
            for brand in KNOWN_FOREIGN_BRANDS:
                if brand in cl and brand not in owned and brand not in (company := lock["customer_company"].lower()):
                    foreign_terms.add(brand)
    # Also flag foreign brand in DECISION-FACING finding fields (title is a decision, and its
    # recommended_action/scope are actions). BUT the finding's claim/evidence may name a
    # competitor as a source (§1 permits competitor in evidence/reference fields).
    for f in findings:
        for ch in [(f.get("title") or ""), (f.get("recommended_action") or ""),
                   (f.get("affected_scope") or "")]:
            cl = ch.lower()
            for fd in foreign_domains:
                if fd and fd in cl and fd not in owned:
                    foreign_terms.add(fd)
            for brand in KNOWN_FOREIGN_BRANDS:
                if brand in cl and brand not in owned and brand not in (lock["customer_company"] or "").lower():
                    foreign_terms.add(brand)
    return len(foreign_terms), sorted(foreign_terms)


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
        # selected_product_category: 由 internal product-map 推衍（consistent with quality_gate.validate_intake）
        if f == "selected_product_category" and not val:
            if (order or {}).get("report_tier") or (order or {}).get("selected_product_id"):
                val = True
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

    # SERP: valid vs invalid/unparsed (§5) — only counts_toward_serp observations count; competitor reads never count
    serp = research.get("serp") or []
    invalid_tokens = ["none parsed", "no result parsed", "blank snippet", "results are mostly mixed",
                      "unavailable", "Search could not be executed", "bot challenge",
                      "empty result", "blank link", "blank snippet"]
    valid_serp = 0; invalid_serp = 0
    valid_serp_queries = []
    for s in serp:
        if s.get("counts_toward_serp") is False:
            continue  # explicitly not SERP (e.g. competitor direct read)
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

    # ---- CUSTOMER-OWNERSHIP VALIDATOR (§4 repair) ----
    # Every action/finding/roadmap target must be on a customer-owned domain; a competitor/
    # external URL is allowed ONLY in an evidence/source field. Block as hard fail otherwise.
    customer_domain = (research.get("customer_domain") or "").lower()
    owned_domains = [d.lower().lstrip("www.") for d in (research.get("customer_owned_domains") or [])]
    if not owned_domains and customer_domain:
        owned_domains = [customer_domain]
    forbidden_targets = 0
    forbidden_target_urls = []
    competitor_terms = ("ahrefs.com", "moz.com", "backlinko.com", "semrush.com")
    for a in actions:
        scope = (a.get("affected_scope") or a.get("customer_owned_scope") or a.get("title") or "")
        # any URL inside scope on a competitor/external domain = forbidden action target
        for mm in re.finditer(r"https?://([^/\s]+)", scope):
            d = mm.group(1).lower().lstrip("www.").split(":")[0]
            if d and d not in owned_domains:
                forbidden_targets += 1
                forbidden_target_urls.append(mm.group(0))
                break
    v["forbidden_action_targets"] = forbidden_targets
    v["forbidden_action_target_urls"] = forbidden_target_urls

    # ---- ACTION COMPLETENESS VALIDATOR (§9/repair) ----
    incomplete_actions = 0
    for a in actions:
        need = [a.get("affected_scope"), a.get("business_reason"), (a.get("action_verb") or a.get("title"))]
        if any(not (x or "").strip() for x in need):
            incomplete_actions += 1
    v["incomplete_action_count"] = incomplete_actions

    # ---- EXEC SUMMARY VALIDATOR (each exec decision must have a customer-owned first action) ----
    decision_wo_action = 0
    for f in findings:
        if not (f.get("recommended_action") or "").strip() or not (f.get("affected_scope") or "").strip():
            decision_wo_action += 1
    v["exec_decision_wo_action"] = decision_wo_action

    # content/developer briefs (premium)
    v["content_brief_count"] = len(research.get("content_briefs") or [])
    v["technical_brief_count"] = len(research.get("technical_briefs") or [])

    # roadmap action-ID coverage (§10) — the renderer now builds a 90-day roadmap that
    # references every action ID from the ledger, so coverage = fraction of actions that
    # carry an action_id / are rendered into the roadmap.
    roadmap = research.get("roadmap") or []
    if roadmap:
        ids = set()
        for item in roadmap:
            t = str(item.get("title") or item.get("action_id") or "")
            found = re.findall(r"ACT-\d+|Action\s*\d+|\b\d{2,3}\b", t)
            ids.update(found)
        v["roadmap_action_id_coverage"] = min(1.0, len(ids) / max(1, len(roadmap)))
    elif actions:
        # actions are rendered into the 90-day roadmap by report_engine; coverage is high
        # only if they carry action_id + title + validation
        well_formed = sum(1 for a in actions
                          if (a.get("action_id") or a.get("title")) and
                          (a.get("validation_method") or a.get("acceptance_criteria")))
        v["roadmap_action_id_coverage"] = round(well_formed / max(1, len(actions)), 2)
    else:
        v["roadmap_action_id_coverage"] = 0.0

    # master-spec §9.2: completelness + foreign-brand/domain-in-action + order-id leak + roadmap valid rate
    v["action_completeness_rate"] = round(
        sum(1 for a in actions if (a.get("customer_owned_scope") or a.get("affected_scope"))
            and a.get("owner") and a.get("acceptance_criteria") and a.get("validation_method"))
        / max(1, len(actions)), 2) if actions else 0.0
    v["roadmap_valid_action_id_rate"] = 1.0 if v.get("roadmap_action_id_coverage", 0) >= 0.5 else 0.0
    _foreign = ("SEMRUSH", "AHREFS", "BACKLINKO", "MOZ")
    v["foreign_brand_in_action_count"] = sum(
        1 for a in actions if any(k in (a.get("title") or a.get("claim") or "").upper() for k in _foreign))
    v["foreign_domain_in_action_count"] = sum(
        1 for a in actions for cd in str(a.get("customer_owned_scope") or "").split(";")
        if cd.strip() and not cd.strip().startswith("customer-owned") and not any(d in cd.lower() for d in owned_domains))
    v["internal_order_id_leak_count"] = len(re.findall(r"ORD-[A-F0-9]{6,}", str(doc_text)))
    v["wrong_customer_company_language_count"] = 0

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

    # ---- CONSULTANT-REASONING metrics (maximum-upgrade) ----
    # customer-owned page-gap evidence rate: findings that name a concrete customer-owned gap
    page_gap_count = sum(1 for f in findings if (f.get("page_gap") or "").strip())
    v["customer_owned_page_gap_count"] = page_gap_count
    v["page_gap_coverage_rate"] = round(page_gap_count / max(1, len(findings)), 2)
    # customer-owned scope rate over actions
    _owned_rate = 0.0
    if actions:
        _owned_rate = sum(1 for a in actions
                          if (a.get("customer_owned_scope") or a.get("affected_scope") or "").strip()) / len(actions)
    v["customer_owned_scope_rate"] = round(_owned_rate, 2)
    # business-model fit rate
    _fit_n = len(actions)
    _fit_ok = sum(1 for a in actions if a.get("business_model_fit", True) is not False)
    v["business_model_fit_rate"] = round(_fit_ok / max(1, _fit_n), 2)
    v["unverified_current_offer_count"] = 0  # filled by research if it cannot confirm an offer is current
    # business-mechanism completeness: business_reason has a named page + mechanism (non-generic)
    _mech = 0
    for a in actions:
        br = (a.get("business_reason") or "").lower()
        if a.get("affected_scope") and br and len(br) > 25 and not br.startswith(("relates to", "this observation")):
            _mech += 1
    v["business_mechanism_completeness_rate"] = round(_mech / max(1, len(actions)), 2)
    v["wrong_company_or_language_count"] = 0

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
    # ---- repair-instruction hard fails (§4 validators) ----
    if v.get("forbidden_action_targets", 0) > 0:
        hard_fail.append(f"forbidden_action_target({v['forbidden_action_targets']})")
    # ---- MASTER SPEC FAILURE validators (user-rejected apple PDF) ----
    # (2) invalid action scope: actions must target a verified customer-owned URL/page/template/
    #     journey, never research-evidence classes like serp_result_pattern / result_pattern / serp
    _BANNED_SCOPES = ("serp_result_pattern", "result_pattern", " serp", "competitor_obs", "evidence_ledger")
    for _a in actions:
        _sc = " " + ((_a.get("customer_owned_scope") or "") + " " + (_a.get("affected_scope") or "") + " "
                     + (_a.get("title") or "")).lower()
        if any(_b in _sc for _b in _BANNED_SCOPES[0:3]):
            hard_fail.append("invalid_action_scope")
            break
    # (4) generic / canned business mechanism: exact user-flagged phrases must block
    v["generic_mechanism_count"] = 0
    _mech_scan = [(f.get("business_reason") or "") + " " + (f.get("claim") or "") for f in findings]
    _mech_scan += [(_a.get("business_reason") or "") + " " + (_a.get("claim") or "") for _a in actions]
    for _br in _mech_scan:
        if ("affects the likelihood that visitors progress toward" in _br or
                "this observation at" in _br and "does not" not in _br or
                "supporting the goal" in _br or
                "supporting the stated goal" in _br):
            v["generic_mechanism_count"] += 1
    if v["generic_mechanism_count"] > 0:
        hard_fail.append(f"generic_mechanism({v['generic_mechanism_count']})")
    # (7) definition-of-done: generic "implement and confirm via public source" is NOT acceptance
    v["generic_dod_count"] = 0
    for _a in actions:
        _ac = (_a.get("acceptance_criteria") or "").lower()
        if "confirm via public source" in _ac or "implement the action" == _ac.strip():
            v["generic_dod_count"] += 1
    if v["generic_dod_count"] > 0:
        hard_fail.append(f"generic_definition_of_done({v['generic_dod_count']})")
    if v["action_completeness_rate"] < 1.0:
        hard_fail.append("action_completeness_missing")
    # evidence-type / competitor-as-SERP guard: if any serp observation counts a competitor read
    # as serp, flag (research already separates; defensive)
    for _s in serp:
        if isinstance(_s, dict) and _s.get("counts_toward_serp") is False:
            pass  # already excluded above
    cd_low = (research.get("customer_domain") or "").lower()
    # invalid action-ID roadmap: if roadmap items reference an action that does not exist as customer-owned
    valid_ids = {a.get("action_id") for a in actions}
    roadmap = research.get("roadmap") or []
    invalid_roadmap_refs = 0
    for ri in roadmap:
        body = str(ri.get("title") or ri.get("action_id") or "")
        for aid in re.findall(r"ACT-\d+", body):
            if aid not in valid_ids:
                invalid_roadmap_refs += 1
    v["invalid_roadmap_refs"] = invalid_roadmap_refs
    if v.get("exec_decision_wo_action", 0) > 0:
        hard_fail.append("exec_decision_wo_action")

    v["hard_fail_list"] = hard_fail
    # score ceilings (§8 maximum-upgrade + repair): a report cannot score high if:
    # - any hard fail -> blocked
    # - no customer-owned page-gap evidence -> max 59
    # - no valid customer-owned action ledger -> max 69
    # - no business-model fit evidence -> max 79
    # - no independent blind-auditor citations -> max 84
    if v.get("forbidden_action_targets", 0) > 0:
        v["_ceiling"] = 0
    elif v.get("internal_path_leak_count", 0) > 0:
        v["_ceiling"] = 0
    elif v.get("cross_customer_contam", 0) > 0 if "cross_customer_contam" in v else False:
        v["_ceiling"] = 0
    elif hard_fail:
        v["_ceiling"] = 0 if any(h in ("internal_path_leak", "forbidden_action_target", "placeholder_present") for h in hard_fail) else 69
    elif v.get("customer_owned_page_gap_count", 0) < 3 and v.get("customer_owned_page_gap_count", 0) < min_findings:
        v["_ceiling"] = 59  # no customer-owned page-gap evidence -> max 59
    elif v.get("valid_serp_observation_count", 0) < min_serp:
        v["_ceiling"] = 69  # no valid SERP -> max 69
    elif v.get("concrete_action_count", 0) < min_actions:
        v["_ceiling"] = 69  # no valid customer-owned action ledger -> max 69
    elif v.get("business_model_fit_rate", 0) < 1.0 and v.get("business_model_fit_rate", 1.0) < 0.5:
        v["_ceiling"] = 79  # no business-model fit evidence -> max 79
    elif v.get("invalid_roadmap_refs", 0) > 0:
        v["_ceiling"] = 79  # invalid action-ID roadmap -> max 79
    else:
        v["_ceiling"] = None  # allow independent blind auditor to decide 90+
    return v


# ---------------- Blind Quality Auditor (independent AI) ----------------

BLIND_PROMPT = """You are the INDEPENDENT BLIND QUALITY AUDITOR for a paid SEO report. You are the final quality authority. You did NOT write or generate this report. Your role is to independently verify quality and award a score out of 100.

You receive ONLY: the selected product tier, customer intake, the evidence ledger, research coverage metrics, and the report draft text. You do NOT receive and must IGNORE any generator self-score or self-conclusion — there is none in this input.

Score exactly these categories (max in parentheses), awarding points ONLY with specific evidence drawn from the provided content (a source URL, page, query, action, owner, acceptance criterion, or concrete report text). Award ZERO for blank, generic, or unsupported claims. Do not award points merely because a heading exists:

A. Customer usefulness (20): Does every priority concern the customer's OWN website/business? Is there a real customer-owned page-gap for every finding? Are competitor/result-pattern sources used as EVIDENCE, never action targets?
B. Research completeness (20): 6 meaningful customer-owned page coverage; 6 valid customer-specific result-pattern coverage; 4 competitor/result-pattern coverage (as evidence, not targets); 4 complete intake used.
C. Customer-specific strategic value (20): 5 real business decisions (not logs); 5 findings address offer/market/goal/action; 5 customer-specific business consequence (plausible mechanism connecting page gap to action); 5 genuine prioritisation.
D. Actionability & model-fit (20): 5 actions name customer-owned scope; 4 owner+realistic effort; 4 dependencies+acceptance; 4 validation+review; 3 roadmap action-ID-linked. Would the action be feasible and sensible FOR THIS EXACT business model (ecommerce ≠ quote path, etc.)?
E. Structure/customer experience (10): 3 useful executive brief; 2 consistent labels/confidence/sources; 2 readable tables/cards; 2 scope/limits clear; 1 tier scope correct.
F. PDF/language/privacy (10): 2 clean readable; 2 safe filename/metadata; 3 correct language/grammar; 2 no logs/paths/placeholders/broken links; 1 professional hierarchy no fake data.

CITATION RULE: For EVERY point you award, you must quote or reference actual customer-owned scope, evidence, action, acceptance criterion or report text. If you cannot point to specific evidence, award ZERO for that criterion. A report earns a score ONLY when it proves this complete chain:
valid evidence -> customer context -> customer-owned page-gap insight -> concrete customer-owned action (with owner/acceptance/validation) -> action-ID roadmap -> clean final PDF.

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


def decide_delivery(deterministic, blind, is_pdf_clean=True, min_score=None):
    """ONLY function permitted to set READY_TO_DELIVER. Returns (state, reason_list).
    READY_TO_DELIVER only when: deterministic PASS (no hard_fail_list) AND blind total>=90
    (or >=min_score when explicitly overridden, e.g. owner test) AND blind no hard_fail
    AND no deterministic hard-fail AND pdf clean."""
    # threshold: default 90 (permanent standard); owner may raise/lower for a test only via env
    if min_score is None:
        try:
            min_score = int(os.environ.get("MIN_REPORT_SCORE", "90"))
        except Exception:
            min_score = 90
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
    if 70 <= b_total <= min_score - 6:
        return "RESEARCH_INCOMPLETE", [f"blind score {b_total} in RESEARCH INCOMPLETE band; gather evidence"]
    if min_score - 5 <= b_total <= min_score - 1:
        return "QUALITY_REPAIRING", [f"blind score {b_total} in REVISE band (below {min_score}); repair specific gaps"]
    if b_total >= min_score:
        if not is_pdf_clean:
            return "PDF_REPAIRING", ["PDF privacy/layout validation failed"]
        return "READY_TO_DELIVER", [f"deterministic PASS + blind {b_total}/{min_score} PASS"]
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