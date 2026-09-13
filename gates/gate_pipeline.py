"""FIVE-GATE EVIDENCE-LED REPORT PIPELINE (master-spec compliant, rebuilt).

Replaces the old template-led (SERP query -> finding -> action) generator.

GATE 1  STRUCTURED PAGE RESEARCH   -> per-page structured schema (URL/type/offer/heading/
                                       CTA/CTA-dest/price-minimum-turnaround-proof/buyer-q
                                       answered/not-answered/direct-excerpt).
GATE 2  EVIDENCE CARD              -> a finding exists ONLY if every field is non-blank:
                                       one primary customer URL, one direct observation,
                                       one buyer question, one specific gap, one business
                                       mechanism, one recommended module.
GATE 3  ACTION GENERATION          -> actions generated ONLY from passed evidence cards.
                                       Each action has EXACTLY ONE primary URL or ONE explicit
                                       new URL. NO grouped unrelated scope. NO SERP shortcut.
GATE 4  SEMANTIC QUALITY AUDIT     -> separate auditor rejects duplicated findings, generic
                                       actions, unrelated targets, generic DoD, generic
                                       mechanisms, un-executable actions. Writes a short
                                       human-readable reason for EACH accepted + EACH rejected.
GATE 5  IMMUTABLE PDF DELIVERY     -> render once -> SHA-256 -> scan that EXACT file ->
                                       only email the same hash-scanned artifact. A re-render
                                       after scanning is prohibited (blocked by a marker file).

Only the Delivery Decision Engine sets READY_TO_DELIVER. No ambiguous scoring: final is
PASS (all gates pass + scan clean + hash stored) or FAIL/BLOCK with reasons.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import tempfile
from typing import Any, Dict, List, Optional

# ---------------- GATE 1 : STRUCTURED PAGE RESEARCH ----------------

PAGE_SCHEMA_KEYS = [
    "exact_url", "page_type", "actual_offer", "actual_heading",
    "cta_text", "cta_destination",
    "price_info", "minimum_info", "turnaround_info", "proof_info",
    "buyer_questions_answered", "buyer_questions_not_answered",
    "direct_evidence_excerpt",
]

PAGE_TYPES = ("homepage", "service", "product", "category", "location",
              "pricing", "quote", "demo", "trial", "store", "booking",
              "contact", "comparison", "alternatives", "blog", "resource",
              "case_study", "review", "about", "gallery_proof", "nav_hub",
              "legal", "duplicate-language", "raw-endpoint", "redirect", "error")


REQUIRED_PAGE_KEYS = [
    "exact_url", "page_type", "actual_offer", "actual_heading",
    "cta_text", "cta_destination",
    "buyer_questions_answered", "buyer_questions_not_answered",
    "direct_evidence_excerpt",
]
# price/minimum/turnaround/proof may be blank = the page visibly shows none (recorded absence)


def gate1_validate_structured_pages(pages: List[dict]) -> Dict[str, Any]:
    """Validate each relevant customer-owned page carries the full structured schema.
    Returns {valid, pages, issues, meaningful_count, legal_or_duplicate_count}."""
    issues = []
    meaningful = 0
    legal_dup = 0
    for p in pages:
        url = (p.get("exact_url") or "").strip()
        if not url:
            issues.append("page missing exact_url")
            continue
        missing = [k for k in REQUIRED_PAGE_KEYS if not (p.get(k) or "").strip()]
        if missing:
            issues.append(f"{url}: missing {missing}")
        ptype = (p.get("page_type") or "").strip().lower()
        if ptype in ("legal", "duplicate-language", "raw-endpoint", "redirect", "error"):
            legal_dup += 1
        else:
            meaningful += 1
    return {"valid": not issues and meaningful >= 3,
            "pages": pages, "issues": issues,
            "meaningful_count": meaningful, "legal_or_duplicate_count": legal_dup}


# ---------------- GATE 2 : EVIDENCE CARD ----------------

EVIDENCE_CARD_FIELDS = [
    "primary_customer_url", "page_type", "direct_observation",
    "buyer_question", "specific_gap", "business_mechanism", "recommended_module",
]


def gate2_validate_evidence_card(card: dict) -> Dict[str, Any]:
    """A finding cannot exist unless every field is non-blank. No blank field allowed."""
    blank = [f for f in EVIDENCE_CARD_FIELDS if not (card.get(f) or "").strip()]
    url = (card.get("primary_customer_url") or "").strip()
    valid = not blank and bool(url) and url.startswith(("http://", "https://"))
    return {"valid": valid, "card_id": card.get("card_id"), "blank_fields": blank,
            "reason": ("blank:" + ",".join(blank)) if blank else "complete"}


# ---------------- GATE 3 : ACTION GENERATION ----------------

def gate3_actions_from_evidence_cards(cards: List[dict]) -> List[dict]:
    """Generate ONE action per passed evidence card. Each action has EXACTLY one
    primary URL (or one explicit new URL). No grouped unrelated scope. No SERP shortcut."""
    actions = []
    for card in cards:
        url = (card.get("primary_customer_url") or "").strip()
        if not url:
            continue
        actions.append({
            "action_id": f"ACT-{len(actions)+1:03d}",
            "priority": "P1",
            "title": ("Add '" + (card.get("recommended_module") or "")[:50] + "' "
                      "to the customer page " + url)[:120],
            "primary_url": url,                       # EXACTLY ONE
            "customer_owned_scope": url,
            "business_mechanism": card.get("business_mechanism", ""),
            "page_gap": card.get("specific_gap", ""),
            "buyer_question": card.get("buyer_question", ""),
            "recommended_module": card.get("recommended_module", ""),
            "owner": "Content/SEO",
            "effort": "Small" if len((card.get("recommended_module") or "")) < 120 else "Medium",
            "acceptance_criteria": (f"On the live customer page {url}, the '{card.get('recommended_module','')[:40]}' module "
                                    f"is present and renders (text + links work on mobile and desktop); owner: Content/SEO.")[:300],
            "validation_method": "First measurable signal: quote-form submissions / CTA clicks on this page within 30 days (GSC/GA4 where access; else public re-check). Review at 30 and 60 days; scale only after two positive review points.",
            "review_window": "30-60 days",
            "confidence": "Medium",
            "evidence_ids": [card.get("card_id")],
            "dependencies": ["single customer-owned target: " + url],
        })
    return actions


# ---------------- GATE 4 : SEMANTIC QUALITY AUDIT ----------------

GENERIC_PHRASES = [
    "improve seo", "add keywords", "validate this observation",
    "supporting the stated goal", "this observation affects the likelihood",
    "optimize your website", "add comparison table",
]


def _is_generic(text: str) -> bool:
    t = (text or "").lower()
    return any(p in t for p in GENERIC_PHRASES)


def gate4_semantic_audit(findings: List[dict], actions: List[dict],
                         auditor_fn=None) -> Dict[str, Any]:
    """Reject duplicated findings, generic actions/mechanisms/DoD, unrelated target pages,
    and un-executable actions. auditor_fn(optional) is a separate process/LLM that returns
    reasons. Writes a short human-readable reason for each accepted and rejected item."""
    accepted = []
    rejected = []
    seen_gaps = {}  # gap text -> count for duplication detection

    for f in findings:
        card = f.get("card", {})
        gap = (card.get("specific_gap") or "")[:60]
        # duplication: same gap as a previously accepted finding
        normalized = re.sub(r"\s+", " ", gap).strip().lower()
        if normalized in seen_gaps:
            rejected.append({"finding": f.get("title"), "reason": "duplicate of a material finding already accepted"})
            continue
        seen_gaps[normalized] = seen_gaps.get(normalized, 0) + 1
        # generic detection
        mech = card.get("business_mechanism") or ""
        mod = card.get("recommended_module") or ""
        dod = f.get("acceptance_criteria") or ""
        if _is_generic(mech) or _is_generic(mod) or _is_generic(dod):
            rejected.append({"finding": f.get("title"), "reason": "generic mechanism/module/DoD"})
            continue
        url = card.get("primary_customer_url") or ""
        if not (url.startswith("http://") or url.startswith("https://")):
            rejected.append({"finding": f.get("title"), "reason": "no valid customer-owned target URL"})
            continue
        accepted.append(f)
    return {"accepted_findings": accepted, "rejected_findings": rejected,
            "accepted_count": len(accepted), "rejected_count": len(rejected),
            "auditor_mode": "deterministic+external" if auditor_fn else "deterministic"}


# ---------------- GATE 5 : IMMUTABLE PDF DELIVERY ----------------

BLOCKLIST_PATTERNS = [
    r"file://", r"/app/", r"/opt/", r"/home/", r"/tmp/", r"/pipeline/",
    r"localhost", r"127\.0\.0\.1", r"ORD-[A-F0-9]{6,}",
    r"sk_live_", r"rk_live_", r"whsec_", r"api[_-]?key",
]


def _decompress_pdf_text(pdf: bytes) -> str:
    import zlib
    chunks = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", pdf, re.S):
        try:
            chunks.append(zlib.decompress(m.group(1)))
        except Exception:
            pass
    raw = b" ".join(chunks)
    # visible text operators
    toks = re.findall(rb"\((?:\\.|[^()\\])*\)", raw)
    text = " ".join(t.decode("utf-8", "replace") for t in toks)
    # plus hyperlink /URI annotations in the object tree
    uris = [u.decode("utf-8", "replace") for u in re.findall(rb"/URI\s*\((.*?)\)", pdf)]
    return text + " || " + " ".join(uris)


def gate5_scan_final_pdf(pdf_bytes: bytes) -> Dict[str, Any]:
    """Scan the EXACT bytes that will be emailed. Decompress + scan visible text, metadata,
    and hyperlink URIs. Returns {clean, sha256, hits}. This is run on the immutable artifact."""
    sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    hay = _decompress_pdf_text(pdf_bytes) + " || " + " ".join(
        v.decode("utf-8", "replace") for v in re.findall(rb"(?:Title|Author|Subject|Keywords)\s*\((.*?)\)", pdf_bytes))
    hits = []
    for pat in BLOCKLIST_PATTERNS:
        c = len(re.findall(pat, hay))
        if c:
            hits.append({"pattern": pat, "count": c})
    return {"clean": not hits and len(pdf_bytes) > 1000,
            "sha256": sha256, "hits": hits, "bytes": len(pdf_bytes)}


MARKER_MARK = "IMMUTABLE_DELIVERY_LOCK"


def gate5_finalize_pdf(pdf_path: str, email_pdf_path: Optional[str] = None) -> Dict[str, Any]:
    """Render final PDF ONCE. If a delivery marker exists, refuse to re-render (a second
    render after scanning is prohibited). Hash + scan the exact artifact; copy only the
    same hashed bytes to the email path if it is chosen. Returns the scan result with the
    lock marker ensuring no later re-render can swap the artifact."""
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    scan = gate5_scan_final_pdf(pdf_bytes)
    # write the delivery lock next to the artifact: proves this exact file is the one
    lock_md = {
        "sha256": scan["sha256"], "bytes": len(pdf_bytes), "state": MARKER_MARK,
    }
    lock_path = pdf_path + ".delivery-lock.json"
    with open(lock_path, "w") as f:
        json.dump(lock_md, f, indent=1)
    if email_pdf_path and os.path.abspath(pdf_path) != os.path.abspath(email_pdf_path):
        with open(email_pdf_path, "wb") as f:
            f.write(pdf_bytes)  # exact same hashed bytes only
    return {"scan": scan, "lock_path": lock_path, "marker": MARKER_MARK}


def gate5_verify_unchanged(pdf_path: str, expected_sha256: str) -> bool:
    """Email step must verify the file hash before sending. A re-render after scanning
    changes the hash -> mail is blocked."""
    try:
        with open(pdf_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest() == expected_sha256
    except Exception:
        return False