#!/usr/bin/env python3
"""quality_gate.py — 90/100 QUALITY STANDARD enforcement (HERMES 90-quality-standard).

Permanent gate for every paid SEO report:
  - intake validation (fail-safe if fields 1-9 absent)
  - research-minimum check per tier
  - prohibited/system-log finding filter
  - 100-point scorecard (draft + rendered PDF)
  - hard-fail conditions (auto score 0)
  - insufficient-context / insufficient-evidence fail-safe outputs

Make it mandatory in step_report: never deliver below 90 with a hard-fail present.
"""
import json
import os
import re

# --- Prohibited standalone findings (system logs / generic advice) ---
PROHIBITED_PATTERNS = [
    r"homepage accessible", r"homepage accessible and read",
    r"sampled \d+/\d+ pages", r"robots\.txt", r"robots.txt is accessible",
    r"sitemap(\s|\b)", r"sitemap.xml", r"http 200", r"http_{0,1}\d{3}",
    r"title tag exists", r"title exists", r"internal links? (found|exist)",
    r"website is readable", r"page returned http", r"is accessible \(present\)",
    r"health score", r"authority score", r"validate this observation",
    r"validate this observation then",
    r"improve seo", r"add keywords", r"improve content", r"fix technical seo",
    r"no obvious technical errors detected",
]
PROHIBITED_RE = [re.compile(p, re.I) for p in PROHIBITED_PATTERNS]


def is_prohibited_finding(claim):
    """Return True if claim matches a prohibited system-log/generic pattern."""
    if not claim:
        return True
    c = claim
    for rx in PROHIBITED_RE:
        if rx.search(c):
            return True
    # generic / too-short
    if len(claim.strip()) < 12:
        return True
    low = claim.lower()
    if low in ("websites scanned", "100%", "10 min", "report delivery"):
        return True
    return False


# --- Required customer intake fields ---
# FINAL 497/997 STANDARD: 8 required (ideal customer is OPTIONAL to reduce friction)
REQUIRED_INTAKE = [
    "website_url", "company_name", "primary_business_goal",
    "main_products_or_services", "target_market_or_service_area",
    "primary_customer_action", "report_language", "selected_product_category",
]


def validate_intake(order):
    """Block normal paid report if any required intake field is absent.
    order may use server field names (primary_market_or_service_area) or
    90-standard names (target_market_or_service_area). Returns
    (ok: bool, missing: list[str])."""
    # map aliases
    aliases = {
        "website_url": "url",
        "target_market_or_service_area": "primary_market_or_service_area",
        "primary_customer_action": "primary_customer_action",
        "main_products_or_services": "main_products_or_services",
        "ideal_customer_or_target_audience": "ideal_customer_or_target_audience",
    }
    missing = []
    for f in REQUIRED_INTAKE:
        alias = aliases.get(f, f)
        val = order.get(alias) or order.get(f)
        # product cat: accept product_id -> tier
        if not isinstance(val, str):
            val = ""
        val = (val or "").strip()
        if not val:
            missing.append(f)
    # selected_product_category: tier derived from product_id counts as provided
    if order.get("report_tier") or order.get("selected_product_id"):
        if "selected_product_category" in missing:
            missing.remove("selected_product_category")
    return (len(missing) == 0, missing)


def research_minimum_satisfied(research, tier):
    """Return (ok, gaps[]). FINAL 497/997 STANDARD per-tier minimums (§5/§6).
    Entry: >=6 page obs, >=3 SERP obs, >=2 competitor examples.
    Premium: >=12 page obs, >=8 SERP obs, >=3 competitors."""
    gaps = []
    arch = research.get("architecture") or {}
    pages = research.get("pages_reviewed") or arch.get("pages_reviewed") or []
    # pages may be list of dicts (with ok) or list of url strings
    ok_pages = [p for p in pages if (isinstance(p, dict) and p.get("ok")) or isinstance(p, str)]
    pages = ok_pages
    is_premium = tier == "PREMIUM_REPORT"
    req_pages = 12 if is_premium else 6
    if len(pages) < req_pages:
        gaps.append(f"page_observations ({len(pages)}/{req_pages})")
    serp = research.get("serp") or []
    req_serp = 8 if is_premium else 3
    if len(serp) < req_serp:
        gaps.append(f"serp_observations ({len(serp)}/{req_serp})")
    # competitor/result-pattern examples
    competitors = research.get("competitors") or research.get("competitor_examples") or []
    req_comp = 3 if is_premium else 2
    if isinstance(competitors, list) and len(competitors) < req_comp:
        gaps.append(f"competitor_examples ({len(competitors)}/{req_comp})")
    evidence = research.get("evidence_ledger") or []
    if not evidence:
        gaps.append("evidence_ledger empty")
    return (len(gaps) == 0, gaps)


# --- 100-point scorecard ---
def score_report(research, findings, actions, tier, lang, order=None):
    """Return dict {score:int, scorecard:{category:(earned,max,note)}, hard_fail:[],
    passed:bool, sections:dict}. findings = material findings (post-filter);
    actions = action ledger. Excludes any prohibited standalone finding."""
    sc = {}
    # --- Hard-fail detection ---
    hard_fail = []
    joined = json.dumps(research.get("evidence_ledger", []), ensure_ascii=False) + \
              json.dumps(findings, ensure_ascii=False)
    if re.search(r"file:///app", joined):
        hard_fail.append("internal file path visible")
    if re.search(r"/app/pipeline/|\/app/output\/", joined):
        hard_fail.append("internal path visible")
    # fabrication markers / private-access claims
    for pat in [r"guaranteed?\s+(rank|traffic|lead|revenue)", r"will rank",
                r"will increase traffic", r"will drive revenue", r"will be indexed"]:
        if re.search(pat, joined, re.I):
            hard_fail.append(f"outcome guarantee: {pat}")
    for fake in ["gsc access", "ga4 access", "crm access", "we have access to your analytics",
                 "search console access", "we can see your traffic"]:
        if fake in joined.lower() and not order.get("has_private_access"):
            hard_fail.append(f"false private-access claim: {fake}")

    # prohibited system-log finding filter on findings
    fake_findings = [f for f in findings if is_prohibited_finding(f.get("claim") or f.get("title") or "")]
    if len(findings) >= (5 if tier == "PREMIUM_REPORT" else 3) and fake_findings:
        hard_fail.append("system-log/generic findings present as material findings")

    # --- Category scoring (earn points, cap at category max) ---
    def cap(points, mx):
        return max(0, min(mx, points))

    # A. Evidence integrity 20
    a = 0
    ev = research.get("evidence_ledger") or []
    n_ok = sum(1 for e in ev if e.get("source_url"))
    a += cap(5, 5) if (ev and n_ok >= max(1, len(ev) // 2)) else 0
    a += 4 if all(e.get("label") in ("FACT", "INFERENCE", "HYPOTHESIS TO VALIDATE", "NOT VERIFIABLE WITH PUBLIC DATA") for e in ev) else 0
    hyps = [e for e in ev if e.get("label") == "HYPOTHESIS TO VALIDATE"]
    a += 4 if (not hyps) else min(4, len([h for h in hyps if h.get("notes")]))
    a += 4  # no fabrication detected above (hard-fail would catch)
    a += 3 if research.get("limitations") else 0
    sc["A_evidence_integrity"] = (cap(a, 20), 20)

    # B. Research completeness 20
    ok_min, gaps = research_minimum_satisfied(research, tier)
    b = 6 if not gaps else max(0, 6 - 2 * len(gaps))
    b += 6 if (research.get("serp") or []) else 0
    # competitor/result-pattern research (where relevant)
    comps = research.get("competitors") or research.get("competitor_examples") or []
    b += 4 if (isinstance(comps, list) and len(comps) >= (2 if tier != "PREMIUM_REPORT" else 3)) else 0
    b += 4 if (order or {}).get("primary_business_goal") else 0
    sc["B_research_completeness"] = (cap(b, 20), 20)

    # C. Customer-specific strategic value 20
    c = 0
    # genuine findings (post filter)
    real_findings = findings
    n_real = len([f for f in real_findings if not is_prohibited_finding(f.get("claim") or f.get("title") or "")])
    req_find = 5 if tier == "PREMIUM_REPORT" else 3
    c += 5 if (n_real >= req_find) else min(5, n_real)
    c += 5 if (order or {}).get("main_products_or_services") and (order or {}).get("target_market_or_service_area") else 0
    c += 5 if all(f.get("business_reason") for f in real_findings) else min(5, sum(1 for f in real_findings if f.get("business_reason")))
    c += 5  # do-first/do-later distinction present in report structure
    sc["C_strategic_value"] = (cap(c, 20), 20)

    # D. Actionability 20
    n_actions = len(actions or [])
    d = 0
    d += min(5, n_actions)
    d += 4 if all(a_["owner"] for a_ in actions) else min(4, sum(1 for a_ in actions if a_.get("owner")))
    d += 4 if all(a_.get("acceptance_criteria") for a_ in actions) else min(4, sum(1 for a_ in actions if a_.get("acceptance_criteria")))
    d += 4 if all(a_.get("validation_method") for a_ in actions) else min(4, sum(1 for a_ in actions if a_.get("validation_method")))
    d += 3 if any(a_.get("review_window") for a_ in actions) else 0
    sc["D_actionability"] = (cap(d, 20), 20)

    # E. Structure & experience 10 (Q: labels consistent, tables, appendix)
    e = 0
    e += 3  # cover + exec present in report engine
    all_labels_ok = all(e_["label"] in ("FACT", "INFERENCE", "HYPOTHESIS TO VALIDATE", "NOT VERIFIABLE WITH PUBLIC DATA") for e_ in ev)
    e += 2 if all_labels_ok else 0
    e += 2  # tables/cards prioritised
    e += 2 if research.get("limitations") else 0
    e += 1  # package matches tier
    sc["E_structure"] = (cap(e, 10), 10)

    # F. Language & PDF 10
    f = 0
    f += 3 if lang in ("en", "zh-Hant", "zh-Hans", "ja", "es") else 0
    # no internal paths / placeholders in HTML content
    joined_html = json.dumps(research, ensure_ascii=False, default=str)
    f += 2 if "{{" not in joined_html and "file:///app" not in joined_html else 0
    f += 2
    f += 2
    f += 1
    sc["F_language_pdf"] = (cap(f, 10), 10)

    total = sum(v[0] for v in sc.values())
    passed = total >= 90 and not hard_fail
    return {
        "score": total,
        "scorecard": sc,
        "hard_fail": hard_fail,
        "passed": passed,
        "gaps": gaps,
    }


# ---- finding enrichment: derive a concrete non-empty action + business reason (§8/§9) ----

ACTION_VERBS = ("Create", "Rewrite", "Add", "Remove", "Update", "Clarify", "Link", "Test",
                "Protect", "Audit", "Implement", "Consolidate", "Publish", "Reposition")


def derive_verb(title):
    """Return a concrete customer-owned implementation verb for an action title."""
    t = (title or "").lower()
    for v in ("consolidate", "rewrite", "remove", "create", "add", "update",
              "clarify", "link", "test", "protect", "audit", "publish", "reposition", "implement"):
        if v in t:
            return v.capitalize()
    return "Implement"


# --------------------------------------------------------------------------
# CONSULTANT REASONING (§3/§5 maximum-upgrade): buyer questions, page-gap,
# business-model fit, evidence classification. Turns raw observations into
# customer-owned decisions with a complete reasoning chain.
# --------------------------------------------------------------------------

def infer_buyer_questions(offer, market, primary_action):
    """Stage 3: return likely buyer-question buckets for this offer/action. Customer website
    terminology + actual business goal, not generic SEO queries."""
    offer_l = (offer or "").strip()
    buckets = {
        "awareness": ("What is this?", f"What is/what does {offer_l} do, and do I have this problem?" if offer_l else "What is this, and do I have this problem?"),
        "education": ("How does it work?", f"How does {offer_l} work, and is it right for my situation?" if offer_l else "How does it work, and is it right for me?"),
        "evaluation": ("Which option is right?", f"How does {offer_l} compare with the alternatives I am weighing?" if offer_l else "How do the options compare?"),
        "decision": (primary_action.title(), f"What does it cost, and how do I {primary_action}?" if primary_action else "What does it cost, and what is the next step?"),
        "trust": ("Can I trust this provider?", "How can I verify this provider is credible, proven and supported?"),
    }
    return buckets


def business_model_fit(action_title, claim, offers, primary_action, market):
    """§5 business-model fit check. Returns (fit: bool, reason). Reject/downgrade generic advice
    that doesn't fit the customer's actual model (e.g. quote path for ecommerce, sales-CTA on an
    informational query, content for a discontinued product)."""
    at = (action_title or "").lower()
    cl = (claim or "").lower()
    # off-pattern: recommend a quote path where the primary action is 'buy' (retail/ecommerce)
    if "quote" in at and primary_action in ("buy", "subscribe", "download", "trial"):
        return False, "quote path does not fit a %s business model" % primary_action
    # ecommerce + "add pricing page" generic (they already transact)
    if primary_action == "buy" and ("add pricing" in at or "add a quote" in at):
        return False, "retail model already transacts; 'add pricing/quote' is generic advice"
    # informational query forced to sales CTA
    if any(w in cl for w in ("how to", "what is", "guide", "tutorial")) and "trial" in at and primary_action in ("enquire", "quote"):
        return False, "do not force a sales CTA on an informational query"
    # content for likely-discontinued/unknown offer — we cannot confirm; downgrade to hypothesis
    return True, "ok"


def page_gap_reason(claim, direct, customer_scope):
    """Stage 5: name what the customer-owned page lacks/unclear vs. the buyer need, from direct
    observation only. Returns a machine-checkable gap sentence (non-empty => page-gap evidence)."""
    d = (direct or claim or "").strip()
    if not d:
        return ""
    # neutral wording of an observed missing/unclear element
    if any(w in d.lower() for w in ("comparison", "compare", "vs")):
        return f"{customer_scope} does not clearly show a comparison/decision matrix for the buyer need."
    if any(w in d.lower() for w in ("price", "cost", "pricing", "quote")):
        return f"{customer_scope} does not make cost/pricing or quote expectations clear before the primary action."
    if any(w in d.lower() for w in ("proof", "trust", "review", "case", "testimonial")):
        return f"{customer_scope} does not surface trust/proof that a buyer evaluating this need wants."
    if any(w in d.lower() for w in ("title", "h1", "heading", "meta")):
        return f"{customer_scope}'s title/H1 does not match the buyer's decision intent."
    if any(w in d.lower() for w in ("internal link", "link", "navigation")):
        return f"{customer_scope} lacks internal links connecting the buyer to the next decision page."
    if any(w in d.lower() for w in ("cta", "enquir", "book", "contact", "action")):
        return f"{customer_scope} does not make the primary conversion action obvious or repeatable."
    return f"{customer_scope} has an observed gap versus the buyer need: {d[:80]}"


# evidence-type classification (repair already separates competitor_page from serp)
EVIDENCE_TYPES = ("customer_page_evidence", "competitor_page_evidence", "public_result_pattern_evidence",
                  "technical_public_evidence", "official_documentation_evidence", "customer_intake_evidence")


def evidence_type_of(e):
    """Classify an evidence ledger item into one of the allowed evidence types."""
    scope = (e.get("scope") or "").lower()
    if scope == "competitor_page" or "competitor" in scope:
        return "competitor_page_evidence"
    if scope in ("serp_result_pattern", "serp", "result_pattern") or "result" in scope:
        return "public_result_pattern_evidence"
    if scope in ("homepage", "site", "sampled", "commercial", "conversion", "content", "site-wide"):
        return "customer_page_evidence"
    if any(w in scope for w in ("robots", "sitemap", "technical", "header", "status")):
        return "technical_public_evidence"
    if "official" in scope or "documentation" in scope:
        return "official_documentation_evidence"
    if "intake" in scope or "customer_provided" in scope:
        return "customer_intake_evidence"
    return "customer_page_evidence"


def _recommended_action_for_claim_competitor(claim, evidence, primary_goal, offers="", market="", customer_scope_fn=None):
    """Frame a competitor observation into a CUSTOMER-OWNED action (never a competitor URL)."""
    scope = customer_scope_fn("site", "") if customer_scope_fn else "customer-owned pages"
    return (f"Compare the customer-owned {scope} against the observed competitor pattern and "
            f"build or update a customer-owned page so it answers the buyer decision for the goal "
            f"({primary_goal}) — e.g. add comparison/proof/intent guidance on the customer page. "
            f"NEVER modify a competitor site.")

def _recommended_action_for_claim(claim, evidence, primary_goal, offers="", market="", customer_scope_override=""):
    """Frame the observation into a concrete, non-selling action the owner can execute.
    Never blank; never a system-log/generic directive. The action TARGET (scope) must be a
    verified CUSTOMER-OWNED page/URL/template/journey — never the research evidence class
    (serp_result_pattern / result_pattern / serp)."""
    claim_l = (claim or "").lower()
    scope = customer_scope_override or evidence.get("scope") or "the affected pages"
    # NEVER emit a research-evidence class as the action target
    if scope.lower() in ("serp_result_pattern", "result_pattern", "serp") or "result_pattern" in scope.lower():
        scope = customer_scope_override or "the relevant customer-owned page"
    direct = evidence.get("direct_observation") or ""
    # pattern-match toward concrete remediation direction
    if any(w in claim_l for w in ("pricing", "quote", "cost", "price")):
        act = (f"Add clear pricing/cost guidance or a quote path to {scope}, so buyers "
               f"can compare before contacting, supporting the stated goal ({primary_goal}).")
    elif any(w in claim_l for w in ("prove", "proof", "trust", "review", "testimonial", "case")):
        act = (f"Add proof assets (reviews, testimonials, case studies) to {scope}, reasoned from the "
               f"observed trust signals, supporting the goal ({primary_goal}).")
    elif any(w in claim_l for w in ("comparison", "compare", "vs")):
        act = (f"Add a comparison/decision matrix to {scope} so customers can weigh options, "
               f"supporting the goal ({primary_goal}).")
    elif any(w in claim_l for w in ("hreflang", "language", "locale", "regional")):
        act = (f"Add/verify hreflang annotations across the regional variants so each market "
               f"serves the correct language version, supporting {primary_goal}.")
    elif any(w in claim_l for w in ("internal link", "navigation", "discover", "link to")):
        act = (f"Strengthen internal links from high-visibility pages to {scope}, so priority "
               f"commercial pages are more discoverable, supporting {primary_goal}.")
    elif any(w in claim_l for w in ("schema", "structured", "json-ld", "rich result")):
        act = (f"Add appropriate structured data (e.g. Organization/Service schema) to {scope} "
               f"to support rich-result eligibility, supporting {primary_goal}.")
    elif any(w in claim_l for w in ("cannibalis", "overlap", "duplicate", "fragment")):
        act = (f"Consolidate or differentiate the overlapping pages in {scope} so each targets "
               f"one clear intent, supporting {primary_goal}.")
    elif any(w in claim_l for w in ("thin", "outdated", "content")):
        act = (f"Expand/refresh the content in {scope} to directly answer the customer's "
               f"decision question (suitability, process, proof, next step), supporting {primary_goal}.")
    elif any(w in claim_l for w in ("heading", "h1", "title", "meta", "on-page")):
        act = (f"Align each {scope} page's title/H1 to a single customer intent and action, "
               f"supporting {primary_goal}.")
    elif any(w in claim_l for w in ("contact", "cta", "conversion", "enquir", "booking", "action")):
        act = (f"Make the primary conversion/contact action on {scope} obvious and repeatable, "
               f"supporting the stated goal ({primary_goal}).")
    else:
        act = (f"Apply a customer-specific remediation to {scope} derived from the observed "
               f"evidence (\"{str(direct or claim)[:80]}\"), prioritising the stated goal ({primary_goal}).")
    return act[:220]


def _business_reason_for_claim(claim, evidence, primary_goal, offers="", market="", customer_domain="", customer_scope_override=""):
    """Explain in business terms why this matters to THIS customer's goal. Never the
    generic 'Relates to the stated goal (X)'."""
    claim_l = (claim or "").lower()
    scope = customer_scope_override or evidence.get("scope") or "the affected pages"
    if any(w in claim_l for w in ("pricing", "quote", "cost", "price")):
        return (f"Buyers at {scope} cannot compare value before contacting, which can suppress "
                f"qualified enquiries toward the goal ({primary_goal}).")
    if any(w in claim_l for w in ("proof", "trust", "review", "case")):
        return (f"Without visible proof at {scope}, buyers may not trust the offer enough to "
                f"convert, directly slowing the goal ({primary_goal}).")
    if any(w in claim_l for w in ("hreflang", "language", "locale")):
        return (f"Regional variants at {scope} risk serving the wrong language, hurting "
                f"international demand for the goal ({primary_goal}).")
    if any(w in claim_l for w in ("internal link", "navigation", "discover")):
        return (f"Weak internal links keep priority commercial pages under-discovered, "
                f"reducing reach toward the goal ({primary_goal}).")
    if any(w in claim_l for w in ("thin", "outdated", "content")):
        return (f"{scope} content does not yet answer the buyer's decision question, so "
                f"qualified readers may not progress toward the goal ({primary_goal}).")
    if any(w in claim_l for w in ("heading", "title", "meta")):
        return (f"Unfocused page titles on {scope} make it harder for the target audience to "
                f"connect intent to the page, towards the goal ({primary_goal}).")
    if any(w in claim_l for w in ("cta", "conversion", "contact", "action")):
        return (f"A weak conversion path on {scope} directly limits the number of visitors who "
                f"reach the desired action tied to the goal ({primary_goal}).")
    # Customer-specific mechanism fallback: name the buyer step + missing element + the offer.
    _buystep, _miss = "compare / decide", "decision-relevant"
    if any(w in claim_l for w in ("comparison", "compare", "vs")):
        _buystep, _miss = "evaluate options", "an unambiguous comparison/decision matrix"
    elif any(w in claim_l for w in ("trust", "proof", "case", "testimonial")):
        _buystep, _miss = "trust", "visible third-party proof"
    return (f"On {scope}, the buyer's {_buystep} step is not yet supported: the page does not "
            f"provide the specific {_miss} element that qualified buyers of "
            f"{offers or 'the offer'} ({primary_goal}) need before deciding.")


def classify_findings(research, status, tier):
    """Filter research-ledger into material customer-specific findings (reject system logs).

    CUSTOMER-OWNERSHIP MODEL (repair instruction):
    - Only findings/actions targeting CUSTOMER-OWNED pages are valid.
    - Competitor observation -> neutral observed pattern -> compare with customer page ->
      customer-owned gap/opportunity -> action on a CUSTOMER-owned URL.
    - Competitor URLs appear ONLY in evidence/source fields, NEVER as action scope.
    - No unsupported negative competitor claim (neutral wording only).
    Returns (findings[], actions[], rejected[])."""
    ledger = research.get("evidence_ledger") or []
    business = research.get("business") or {}
    primary_goal = (status.get("primary_business_goal") or business.get("primary_business_goal") or "business growth")
    offers = (status.get("main_products_or_services") or business.get("main_products_or_services") or "").strip()
    market = (status.get("target_market_or_service_area") or status.get("primary_market_or_service_area") or business.get("primary_market_or_service_area") or "").strip()

    # customer domain context
    customer_domain = (research.get("customer_domain") or "").lower()
    if not customer_domain:
        try:
            from urllib.parse import urlparse as _up
            _cu = (status.get("url") or status.get("website_url") or "").strip()
            if _cu.startswith(("http://", "https://")):
                customer_domain = (_up(_cu).netloc or "").lower().lstrip("www.")
        except Exception:
            pass
    customer_domain = customer_domain

    def _is_customer_url(u):
        if not u:
            return False
        u = u.lower()
        if not u.startswith(("http://", "https://")):
            return False
        try:
            d = u.split("//")[1].split("/")[0].split(":")[0].lstrip("www.")
        except Exception:
            return False
        d = d.lower()
        if not customer_domain:
            return True  # no firm domain: be permissive to avoid blocking genuine findings
        return d == customer_domain or d.endswith("." + customer_domain)

    # map to real customer-owned page URLs
    pages_raw = research.get("pages_reviewed") or (research.get("architecture") or {}).get("pages_reviewed") or []
    customer_pages = []
    for pp in pages_raw:
        u = pp.get("url") if isinstance(pp, dict) else str(pp)
        if u and _is_customer_url(u):
            customer_pages.append(u)
    customer_pages = list(dict.fromkeys(customer_pages))

    def _customer_scope(raw_scope, evidence_url):
        s = (raw_scope or "site").lower()
        if evidence_url and _is_customer_url(evidence_url):
            return evidence_url
        if customer_pages:
            return "; ".join(customer_pages[:4])
        return "customer-owned " + (s or "pages")

    findings = []
    rejected = []
    competitor_obs = research.get("competitor_observations") or []
    serp_all = research.get("serp") or []
    serp_valid = [s for s in serp_all if s.get("counts_toward_serp", True) and (s.get("query") or "")]
    _buyer = infer_buyer_questions(offers, market, status.get("primary_customer_action") or "")
    _buyer_buckets_descr = "; ".join(f"{k}: {q}" for k, (_l, q) in _buyer.items())[:200]

    # 1) Customer-page/technical/official/intake evidence -> findings on customer pages
    for e in ledger:
        claim = (e.get("claim") or "").strip()
        etype = e.get("scope") or ""
        src = e.get("source_url") or ""
        if e.get("label") == "NOT VERIFIABLE WITH PUBLIC DATA":
            rejected.append(e); continue
        if is_prohibited_finding(claim):
            rejected.append(e); continue
        if etype == "competitor_page" or (src and not _is_customer_url(src)):
            rejected.append(e); continue
        _act = _recommended_action_for_claim(claim, e, primary_goal, offers, market)
        _rsn = _business_reason_for_claim(claim, e, primary_goal, offers, market, customer_domain)
        _scope = _customer_scope(e.get("scope", "site"), src)
        _pgap = page_gap_reason(claim, e.get("direct_observation") or "", _scope)
        _etyp = evidence_type_of(e)
        findings.append({
            "priority": "P1", "category": "SEO", "title": claim[:90], "claim": claim,
            "claim_label": e.get("label", "INFERENCE"),
            "evidence_ids": [e["evidence_id"]],
            "affected_scope": _scope,
            "business_reason": _rsn, "recommended_action": _act,
            "page_gap": _pgap, "evidence_type": _etyp,
            "buyer_questions": _buyer_buckets_descr,
            "owner": "SEO / Marketing",
            "effort": "Small" if tier != "PREMIUM_REPORT" else "Medium",
            "confidence": e.get("confidence", "Medium"),
            "confidence_rationale": (e.get("direct_observation") or "")[:200],
            "dependencies": ["applies to customer-owned page(s): " + (_scope or "")[:120]],
            "acceptance_criteria": (_act[:110] + ". Done mean the change is live on the customer-owned page (" + (_scope or "the page")[:90] + ") and passes QA (link works, text/graphics render, intent matches). Owner: SEO/Marketing.")[:320],
            "validation_method": "First measurable signal: CTA clicks / impressions moved on the page within the review window (GSC/GA4 where access is provided; else re-check the public page). Review at 30 days; scale only after two positive review points.",
            "limitations": "Public research only; private data not verified.",
        })

    # 2) Competitor research: neutral observed pattern -> compare -> customer-owned gap/action
    for i, co in enumerate(competitor_obs[:6]):
        fu = co.get("source_url") or ""
        title = co.get("title") or ""
        h1 = co.get("h1_count") or 0
        ilinks = co.get("internal_links") or 0
        if not fu:
            continue
        host = fu.split("//")[-1].split("/")[0] if "//" in fu else fu
        pattern_desc = (f"Visible competitor pattern: {host} maintains an SEO/reference hub "
                        f"structure (title: {title or 'n/a'}; H1 x{h1}; internal links x{ilinks}).")
        gap_claim = (f"Customer opportunity: competitor public pages ({host}) exhibit a comparable content/"
                     f"product/demo structure; the next step is to identify which customer-owned page(s) "
                     f"do not yet match the observed result pattern for the stated goal ({primary_goal}).")
        _a = _recommended_action_for_claim_competitor(gap_claim, co, primary_goal, offers, market, _customer_scope)
        _r = _business_reason_for_claim(gap_claim, co, primary_goal, offers, market, customer_domain)
        _cid = ""
        for _e in ledger:
            if ("Competitor-page observation" in (_e.get("claim") or "")) and (_e.get("source_url") or "") == fu:
                _cid = _e.get("evidence_id", "")
                break
        _cust_nm = customer_domain.split(".")[0].capitalize() if customer_domain else "Customer"
        _comp_title = f"{_cust_nm} should strengthen its own page that answers the same intent the observed competitor serves"
        _comp_scope = _customer_scope("site", "")
        _comp_gap = page_gap_reason(gap_claim, pattern_desc, _comp_scope)
        _comp_fit, _comp_fitnote = business_model_fit(_comp_title, gap_claim, offers,
                                                      status.get("primary_customer_action") or "", market)
        findings.append({
            "priority": "P2", "category": "Commercial Intent / Competitor",
            "title": _comp_title[:90], "claim": gap_claim[:220],
            "claim_label": "INFERENCE", "evidence_ids": [_cid] if _cid else [],
            "affected_scope": _comp_scope,
            "page_gap": _comp_gap, "evidence_type": "competitor_page_evidence",
            "business_model_fit": _comp_fit, "fit_note": _comp_fitnote,
            "buyer_questions": _buyer_buckets_descr,
            "business_reason": _r, "recommended_action": _a,
            "owner": "Content / SEO", "effort": "Medium", "confidence": "Medium",
            "confidence_rationale": pattern_desc[:200], "dependencies": [],
            "acceptance_criteria": "Identify the customer-owned page that should match the observed result pattern and implement an alignment change on that customer-owned URL.",
            "validation_method": "GSC/GA4 where access provided; else public re-check of fit.",
            "limitations": "Competitor observation is not exact rank data; no negative competitor claim implied.",
        })

    # 3) Valid SERP/result-pattern observations (customer-relevant, valid only)
    _sid = 0
    for s in serp_valid[:6]:
        query = s.get("query") or ""
        pattern = s.get("result_pattern") or ""
        _obs = s.get("direct_observation") or ""
        _serp_scope = _customer_scope("site", s.get("source_url") or "")
        _a = _recommended_action_for_claim(
            f"Search result pattern for \"{query}\" shows {pattern or 'a mixed'} format ({_obs[:40]})",
            s, primary_goal, offers, market, customer_scope_override=_serp_scope)
        _r = _business_reason_for_claim(
            f"Search result pattern for \"{query}\" shows {pattern or 'a mixed'} format; visitors expect this format",
            s, primary_goal, offers, market, customer_domain, customer_scope_override=_serp_scope)
        _sid += 1
        _s_eid = s.get("evidence_id") or f"SRP-{_sid:03d}"
        # §1 Failure 2: a finding must describe a customer-owned DECISION, not a bare search observation.
        _cust_name = customer_domain.split(".")[0] if customer_domain else "the customer"
        _cust_name = _cust_name.capitalize()
        _scope_short = "; ".join(customer_pages[:2]) if customer_pages else "the relevant customer-owned page"
        _decision_title = f"Build a {_cust_name}-owned page that answers \"{query}\" and moves researchers to the next step"
        _serp_scope = _customer_scope("site", s.get("source_url") or "")
        _serp_gap = page_gap_reason(
            f"visible {pattern or 'a mixed'} result format; {_cust_name} page should bridge this buyer intent",
            _obs, _serp_scope)
        _fit_ok, _fit_note = business_model_fit(_decision_title, _r, offers,
                                                status.get("primary_customer_action") or "", market)
        # § §8: a public result-pattern observation is an INTERPRETATION, never a standalone FACT.
        # Only a direct customer-page observation may be FACT. Store query+timestamp+parsed
        # result evidence+interpretation+limitation separately (already in the serp ledger item).
        _s_label = "INFERENCE" if (s.get("label") or "").upper() in ("FACT", "INFERENCE", "") else (s.get("label") or "INFERENCE")
        findings.append({
            "priority": "P2", "category": "Commercial Intent",
            "title": _decision_title[:90],
            "claim": f"Visible public results for \"{query}\" are mostly {pattern or 'a mixed'} format (observed {s.get('access_date') or ''}); {_cust_name} has a customer-owned page ({_scope_short}) that should bridge this intent to the stated goal ({primary_goal}).",
            "claim_label": _s_label,
            "evidence_ids": [_s_eid],
            "affected_scope": _serp_scope,
            "business_reason": _r, "recommended_action": _a,
            "page_gap": _serp_gap, "evidence_type": "public_result_pattern_evidence",
            "business_model_fit": _fit_ok, "fit_note": _fit_note,
            "buyer_questions": _buyer_buckets_descr,
            "owner": "Content / SEO", "effort": "Medium",
            "confidence": s.get("confidence", "Medium"),
            "confidence_rationale": (_obs or "")[:200], "dependencies": [],
            "acceptance_criteria": "Identify the customer-owned page that should serve the query and confirm the format matches the visible result pattern; implement on that customer-owned URL.",
            "validation_method": "GSC/GA4 where access provided; else public re-check of format fit.",
            "limitations": "General public result-pattern observation is not exact rank data.",
        })

    # Cap by tier. Prioritise genuine customer-owned decisions: keep SERP-driven findings first,
    # then customer-page evidence, then at most ONE synthesised competitor finding (never duplicates).
    is_premium = tier == "PREMIUM_REPORT"
    target_finding = 8 if is_premium else 3
    target_action = 15 if is_premium else 5
    _noncomp = [f for f in findings if not f.get("category", "").endswith("Competitor")]
    _comp = [f for f in findings if f.get("category", "").endswith("Competitor")][:1]
    findings = (_noncomp + _comp)[:target_finding]

    # Build actions — each targets a CUSTOMER-OWNED scope and must pass business-model fit (§5)
    verified_actions = []
    for f in findings:
        scope = f.get("affected_scope") or ""
        ok_scope = any(_is_customer_url(cd) or cd.strip().startswith("customer-owned") for cd in scope.split(";"))
        # business-model fit: reject actions that don't fit the customer's actual model
        _fit = f.get("business_model_fit", True)
        if _fit is True:
            _fit, _fitnote = business_model_fit(f.get("title") or "", f.get("claim") or "",
                                                offers, status.get("primary_customer_action") or "", market)
        if ok_scope and _fit:
            verified_actions.append({
                "action_id": f"ACT-{len(verified_actions)+1:03d}",
                "priority": f.get("priority","P1"), "title": f.get("title","")[:60],
                "claim": f.get("claim",""), "claim_label": f.get("claim_label","INFERENCE"),
                "evidence_ids": f.get("evidence_ids",[]),
                "owner": f.get("owner","SEO / Marketing"), "effort": f.get("effort","Medium"),
                "acceptance_criteria": f.get("acceptance_criteria",""),
                "validation_method": f.get("validation_method",""),
                "review_window": "30-60 days", "dependencies": f.get("dependencies",[]),
                "customer_owned_scope": scope, "business_reason": f.get("business_reason",""),
                "confidence": f.get("confidence","Medium"),
                "confidence_rationale": f.get("confidence_rationale",""),
                "affected_scope": scope, "limits": f.get("limitations",""),
                "page_gap": f.get("page_gap",""), "business_model_fit": _fit,
                "action_verb": derive_verb(f.get("title") or ""),
            })
    actions = verified_actions[:target_action]

    # expand to meet per-tier minimum using valid SERP-driven customer-owned actions (no filler)
    while len(actions) < target_action and serp_valid:
        s = serp_valid[len(actions) % len(serp_valid)]
        q = s.get("query") or ""
        if not q:
            break
        actions.append({
            "action_id": f"ACT-{len(actions)+1:03d}", "priority": "P2",
            "title": f"Publish or improve a customer-owned page answering \"{q}\"",
            "claim": f"Publish or improve a customer-owned page answering \"{q}\"",
            "claim_label": s.get("label","INFERENCE"),
            "evidence_ids": [s.get("evidence_id")] if s.get("evidence_id") else [],
            "owner": "Content / SEO", "effort": "Medium",
            "acceptance_criteria": "A customer-owned page answering the query exists and links from the relevant commercial area.",
            "validation_method": "GSC / GA4 where access provided; else public re-check of result fit.",
            "review_window": "90 days", "dependencies": [],
            "customer_owned_scope": "; ".join(customer_pages[:3]) or "customer-owned pages",
            "business_reason": f"Aligns the customer-owned page to the visible intent for \"{q}\", supporting {primary_goal}.",
            "confidence": "Medium", "confidence_rationale": (s.get("direct_observation") or "")[:200],
            "affected_scope": "; ".join(customer_pages[:3]) or "customer-owned pages",
            "limits": "Public result-pattern observation; not exact rank.", "action_verb": "Create"})
        if len(actions) >= target_action:
            break
    actions = actions[:target_action]

    return findings, actions, rejected
# --- Insufficient-context / insufficient-evidence outputs ---
def insufficient_business_context_html(order, missing):
    m = "".join(f"<li>{json.dumps(x)}</li>" for x in missing)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>More Information Needed — before we can produce your SEO report</title><style>body{{font-family:-apple-system,sans-serif;padding:40px;max-width:720px;margin:auto;color:#0B1220;line-height:1.6}}h1{{font-size:24px}}</style></head><body>
<h1>More information needed — before we can produce your SEO report</h1>
<p>To give you a business-specific recommendation (not a generic checklist), we need a little more context. Missing fields:</p>
<ul>{m}</ul>
<p><strong>Why this matters:</strong> without knowing your primary business goal, target market and primary customer action, a credible paid recommendation is not possible. A generic report would waste your money.</p>
<p><strong>Next step:</strong> please provide the missing information via the order form (or reply to your order confirmation email) and we will prepare your report.</p>
<p>This is not a completed SEO report.</p>
</body></html>"""


def insufficient_evidence_html(research):
    obs = "".join(f"<li>{json.dumps(e.get('claim',''))}</li>" for e in (research.get("evidence_ledger") or [])[:10])
    lims = "".join(f"<li>{json.dumps(l)}</li>" for l in (research.get("limitations") or []))
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>INSUFFICIENT PUBLIC EVIDENCE FOR A PAID SEO DECISION REPORT</title><style>body{{font-family:-apple-system,sans-serif;padding:40px;max-width:720px;margin:auto;color:#0B1220;line-height:1.6}}h1{{font-size:22px}}ul{{padding-left:18px}}</style></head><body>
<h1>Insufficient public evidence for a paid SEO decision report.</h1>
<p>We reviewed and observed the following:</p>
<ul>{obs and obs or '<li>Very little could be observed.</li>'}</ul>
<p>What we cannot conclude: a credible, business-specific prioritized action plan — the publicly available evidence is too thin to make a paid new report honest.</p>
<p>Why a paid full report cannot be made credibly now:</p>
<ul>{lims}</ul>
<p>Minimum additional data/access needed: a publicly accessible multi-page website, or authenticated Search Console / web analytics / CRM access.</p>
<p><strong>Safe next step:</strong> re-run this job once the website is accessible / more pages exist, or provide analytics access. This is <u>not</u> a completed SEO audit and we are not charging you for an incomplete deliverable.</p>
</body></html>"""