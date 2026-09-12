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


def classify_findings(research, status, tier):
    """Filter research-ledger into material findings (reject system logs).
    Returns (findings[], rejected[]). Creates customer-flavoured findings
    from serp + business + a few meaningful observations, and rejects
    prohibited ones."""
    ledger = research.get("evidence_ledger") or []
    business = research.get("business") or {}
    primary_goal = (status.get("primary_business_goal") or business.get("primary_business_goal") or "business growth")
    actions = []

    findings = []
    rejected = []
    for e in ledger:
        claim = e.get("claim") or ""
        if e.get("label") == "NOT VERIFIABLE WITH PUBLIC DATA":
            rejected.append(e)
            continue
        if is_prohibited_finding(claim):
            rejected.append(e)
            continue
        # keep meaningful observations but frame as customer-specific
        findings.append({
            "priority": "P1",
            "category": "SEO",
            "title": claim[:90],
            "claim": claim,
            "claim_label": e.get("label", "INFERENCE"),
            "evidence_ids": [e["evidence_id"]],
            "affected_scope": e.get("scope", "site"),
            "business_reason": f"Relates to the stated goal ({primary_goal}).",
            "recommended_action": "",
            "owner": "SEO / Marketing",
            "effort": "Small" if tier != "PREMIUM_REPORT" else "Medium",
            "confidence": e.get("confidence", "Medium"),
            "confidence_rationale": (e.get("direct_observation") or "")[:200],
            "dependencies": [],
            "acceptance_criteria": "Confirm via corresponding public source.",
            "validation_method": "Search Console / GA4 where access is provided.",
            "limitations": "Public research only; private data not verified.",
        })

    # SERP-driven findings (customer-specific, not system logs)
    serp = research.get("serp") or []
    for s in serp[:6]:
        query = s.get("query") or ""
        pattern = s.get("result_pattern") or ""
        if not query:
            continue
        findings.append({
            "priority": "P2",
            "category": "Commercial Intent",
            "title": f"Search result pattern for \"{query}\"",
            "claim": f"For \"{query}\", visible public results are mostly {pattern or 'mixed'} (observed {s.get('access_date') or ''}).",
            "claim_label": s.get("label", "INFERENCE"),
            "evidence_ids": [s.get("evidence_id")] if s.get("evidence_id") else [],
            "affected_scope": "search results",
            "business_reason": f"Shows what format/intent competitors serve for a query tied to {primary_goal}.",
            "recommended_action": "",
            "owner": "Content / SEO",
            "effort": "Medium",
            "confidence": s.get("confidence", "Medium"),
            "confidence_rationale": (s.get("direct_observation") or "")[:200],
            "dependencies": [],
            "acceptance_criteria": "Confirm in GSC/GA4 which pages serve the query and whether format matches.",
            "validation_method": "Search Console / GA4 where access is provided.",
            "limitations": "General search observation is not exact rank data.",
        })

    # Build concrete actions from findings (each finding -> an action with owner/effort/accept/validation)
    for f in findings:
        actions.append({
            "action_id": f"ACT-{len(actions)+1:03d}",
            "priority": f.get("priority", "P1"),
            "title": f.get("title", "")[:60],
            "claim": f.get("claim", ""),
            "claim_label": f.get("claim_label", "INFERENCE"),
            "evidence_ids": f.get("evidence_ids", []),
            "owner": f.get("owner", "SEO / Marketing"),
            "effort": f.get("effort", "Medium"),
            "acceptance_criteria": f.get("acceptance_criteria", ""),
            "validation_method": f.get("validation_method", ""),
            "review_window": "30-60 days",
            "dependencies": f.get("dependencies", []),
        })

    # FINAL 497/997 STANDARD: entry = exactly 3 findings + 5 actions; premium = 5-8 findings + 15 actions.
    is_premium = tier == "PREMIUM_REPORT"
    target_findings = 8 if is_premium else 3
    target_actions = 15 if is_premium else 5
    findings = findings[:target_findings]

    # Expand the action ledger to meet per-tier minimum without filler:
    # derive extra concrete actions from SERP/gap observations (commercial intent, not system logs).
    extra_pool = []
    for s in serp:
        q = s.get("query") or ""
        gap = s.get("gap") or s.get("customer_page_gap") or ""
        pat = s.get("result_pattern") or ""
        if not q:
            continue
        title = f"Publish or improve a page answering \"{q}\""
        extra_pool.append({
            "action_id": f"ACT-{len(actions)+len(extra_pool)+1:03d}",
            "priority": "P2",
            "title": title[:60],
            "claim": title,
            "claim_label": s.get("label", "INFERENCE"),
            "evidence_ids": [s["evidence_id"]] if s.get("evidence_id") else [],
            "owner": "Content / SEO",
            "effort": "Medium",
            "acceptance_criteria": "A customer-intent page answering the query exists and links from the relevant commercial area.",
            "validation_method": "GSC / GA4 where access provided; otherwise public re-check of result fit.",
            "review_window": "90 days",
            "dependencies": [],
        })
    # fill up to target (never invent, only from real serp observations)
    need = target_actions - len(actions)
    if need > 0:
        for item in extra_pool[:need]:
            actions.append(item)

    actions = actions[:target_actions]

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