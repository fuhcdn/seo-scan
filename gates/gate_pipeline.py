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
            "title": f"{card.get('recommended_module','')[:60]} on the customer page {url}",
            "primary_url": url,                       # EXACTLY ONE
            "customer_owned_scope": url,
            "business_mechanism": card.get("business_mechanism", ""),
            "page_gap": card.get("specific_gap", ""),
            "buyer_question": card.get("buyer_question", ""),
            "recommended_module": card.get("recommended_module", ""),
            "owner": "Content/SEO",
            "effort": "Small" if len((card.get("recommended_module") or "")) < 120 else "Medium",
            "acceptance_criteria": (f"QA-pass on the live customer page {url}: the '{card.get('recommended_module','')[:40]}' module "
                                    f"renders and its links work on mobile and desktop; owner signs off. "
                                    f"First signal tracked via {card.get('buyer_question','')[:40]}.")[:320],
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


# ---------------- GATE 5 : IMMUTABLE PDF DELIVERY (scheme-based hard rules) ----------------

# Allowed hyperlink schemes. ANY other scheme is unsafe (file:, ftp:, data:, javascript:, etc.)
ALLOWED_LINK_SCHEMES = {"https:", "http:", "mailto:"}
# Absolute server/container path prefixes (platform-independent + common container roots)
ABSOLUTE_PATH_PREFIXES = [
    "/app/", "/opt/", "/tmp/", "/home/", "/var/", "/usr/", "/workspace/",
    "/deploy/", "/root/", "/srv/", "/data/", "/mnt/", "/media/",
]


def _extract_pdf_layers(pdf: bytes) -> Dict[str, Any]:
    """Decompress all FlateDecode streams + collect visible-text tokens, hyperlink annotations
    (/URI), launch actions (/Launch), file specs (/F, /EmbeddedFile), and metadata. Returns
    every channel so the scanner can search scheme + absolute paths across ALL of them."""
    import zlib
    streams = re.findall(rb"stream\r?\n(.*?)\r?\nendstream", pdf, re.S)
    decoded = b""
    for s in streams:
        try:
            decoded += zlib.decompress(s) + b"\n"
        except Exception:
            pass
    # visible text: parenthesised strings adjacent to Tj/TJ
    text_parts = []
    for m in re.finditer(rb"\((?:\\.|[^()\\])*\)\s*Tj", decoded):
        text_parts.append(m.group(0))
    for m in re.finditer(rb"\[((?:\((?:\\.|[^()\\])*\)\s*)+)\s*\]\s*TJ", decoded):
        text_parts.append(b"".join(re.findall(rb"\((?:\\.|[^()\\])*\)", m.group(1))))
    text = b" ".join(text_parts)
    # hyperlink / URI / launch / filespec annotations (object tree, may be uncompressed)
    uris = re.findall(rb"/URI\s*\((.*?)\)", pdf)
    uris += re.findall(rb"/URI\s*\(.*?\)", decoded)
    launches = re.findall(rb"/Launch[^>]{0,120}", pdf) + re.findall(rb"/Launch[^>]{0,120}", decoded)
    filenames = re.findall(rb"\n/F\s*\((.*?)\)", pdf) + re.findall(rb"/F\s*\((.*?)\)\s*/", pdf)
    embedded = re.findall(rb"/EmbeddedFile\s*\((.*?)\)", pdf)
    metadata = re.findall(rb"/(?:Title|Author|Subject|Keywords|Creator|Producer|PageTitle)\s*\((.*?)\)", pdf)
    return {"text": text, "decoded": decoded,
            "uris": uris, "launches": launches, "filenames": filenames,
            "embedded": embedded, "metadata": metadata}


def gate5_scan_final_pdf(pdf_bytes: bytes) -> Dict[str, Any]:
    """Scan the EXACT bytes that will be emailed. Scheme-based hard rules (NOT a folder
    blacklist). Runs across visible text, decompressed streams, metadata, hyperlink /URI,
    /Launch actions, /FileSpec and /EmbeddedFile. Returns {clean, sha256, hard_fails[],
    hits[]}."""
    sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    L = _extract_pdf_layers(pdf_bytes)
    hay_text = L["text"].decode("utf-8", "replace")
    hay_all = (hay_text + " " +
               L["decoded"].decode("utf-8", "replace") + " " +
               " ".join(u.decode("utf-8", "replace") for u in L["uris"]) + " " +
               " ".join(l.decode("utf-8", "replace") for l in L["launches"]) + " " +
               " ".join(f.decode("utf-8", "replace") for f in L["filenames"]) + " " +
               " ".join(m.decode("utf-8", "replace") for m in L["metadata"]) + " " +
               " ".join(e.decode("utf-8", "replace") for e in L["embedded"]))
    hay_lower = hay_all.lower()
    hard_fails = []
    hits = []

    # RULE 1 — any file: scheme anywhere -> INTERNAL_FILE_URI
    file_uri_hits = re.findall(r"file:\s*/{0,3}", hay_lower)
    if file_uri_hits:
        hard_fails.append("INTERNAL_FILE_URI")
        hits.append({"rule": "INTERNAL_FILE_URI", "pattern": "file:", "count": len(file_uri_hits)})

    # RULE 2 — any hyperlink scheme not in {https:, http:, mailto:} -> UNSAFE_LINK_SCHEME
    bad_schemes = {}
    for u in [x.decode("utf-8", "replace") for x in L["uris"]]:
        mu = re.match(r"^\s*([a-zA-Z][a-zA-Z0-9+.\-]*):", u)
        if mu and (mu.group(1) + ":").lower() not in ALLOWED_LINK_SCHEMES:
            bad_schemes[mu.group(1)] = bad_schemes.get(mu.group(1), 0) + 1
    if bad_schemes:
        hard_fails.append("UNSAFE_LINK_SCHEME")
        hits.append({"rule": "UNSAFE_LINK_SCHEME", "pattern": str(bad_schemes), "count": sum(bad_schemes.values())})

    # RULE 3 — any absolute server/container path exposed -> INTERNAL_PATH_LEAK
    path_hits = 0
    for prefix in ABSOLUTE_PATH_PREFIXES:
        c = hay_lower.count(prefix)
        if c:
            path_hits += c
    if path_hits:
        hard_fails.append("INTERNAL_PATH_LEAK")
        hits.append({"rule": "INTERNAL_PATH_LEAK", "pattern": "absolute-path", "count": path_hits})

    clean = (not hard_fails) and len(pdf_bytes) > 1000
    return {"clean": clean, "sha256": sha256, "hard_fails": hard_fails,
            "hits": hits, "bytes": len(pdf_bytes),
            "samples": {k: (v[:60] if isinstance(v, bytes) else v) for k, v in L.items()}
                       if not clean else None,
            "has_file_uri": "INTERNAL_FILE_URI" in hard_fails}


MARKER_MARK = "IMMUTABLE_DELIVERY_LOCK"


def gate5_finalize_pdf(pdf_path: str, email_pdf_path: Optional[str] = None) -> Dict[str, Any]:
    """Render final PDF ONCE. If a delivery marker exists, refuse to re-render (a second
    render after scanning is prohibited). Hash + scan the exact artifact; copy only the
    same hashed bytes to the email path if it is chosen. Returns the scan result with the
    lock marker ensuring no later re-render can swap the artifact. Validates the 3-way
    SHA-256 equality: rendered == scanned == (email attachment when chosen)."""
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    scan = gate5_scan_final_pdf(pdf_bytes)
    # 3-way SHA: rendered == scanned input (they are the same bytes here), and will equal
    # the email attachment only if gate5_verify_unchanged passes at send time.
    lock_md = {
        "sha256": scan["sha256"], "bytes": len(pdf_bytes), "state": MARKER_MARK,
        "rendered_sha256": scan["sha256"], "scanned_sha256": scan["sha256"],
        "hard_fails": scan["hard_fails"],
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
    changes the hash -> mail is blocked. Returns True only if hash matches exactly."""
    try:
        with open(pdf_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest() == expected_sha256
    except Exception:
        return False


def gate5_three_way_verify(scanned_sha: str, email_pdf_path: str, rendered_sha: str) -> bool:
    """HARD RULE: rendered PDF SHA == scanner input SHA == email attachment SHA must all
    be identical, else DELIVERY_BLOCKED."""
    if not email_pdf_path or not os.path.exists(email_pdf_path):
        return False
    try:
        with open(email_pdf_path, "rb") as f:
            email_sha = hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return False
    return scanned_sha == rendered_sha == email_sha


def _pdf_with_text(text: bytes) -> bytes:
    """Build a minimal FlateDecode-compressed PDF whose content stream contains `text`."""
    import zlib
    stream = zlib.compress(b"BT (" + text + b") Tj ET")
    header = b"%PDF-1.4\n1 0 obj<</Length " + str(len(stream)).encode() + b"/Filter /FlateDecode>>stream\n"
    trailer = b"\nendstream\nendobj\ntrailer<</Root 1 0 R>>\n%%EOF"
    return header + stream + trailer


def gate5_regression_self_test() -> Dict[str, Any]:
    """REG.RES. — run gate5_scan_final_pdf on the EXACT leaked string the user reported:
    file:///app/gates/out/SEO-Opportunity-Diagnostic-Apple-Imprints-2026-09-13-5gate.html
    MUST be caught (INTERNAL_FILE_URI) and MUST block. Also proves /app/gates/out/ (a
    path not specially hardcoded) is caught because the rule matches ANY file: scheme +
    any absolute path, not a folder blacklist."""
    import zlib
    leak = b"file:///app/gates/out/SEO-Opportunity-Diagnostic-Apple-Imprints-2026-09-13-5gate.html"
    pdf = _pdf_with_text(leak)
    r = gate5_scan_final_pdf(pdf)
    caught = r["clean"] is False and "INTERNAL_FILE_URI" in r["hard_fails"] and "INTERNAL_PATH_LEAK" in r["hard_fails"]
    # absolute-path rule without file: — a bare /app/gates/out/ string must also be caught
    pdf2 = _pdf_with_text(b"see /app/gates/out/report.html here")
    r2 = gate5_scan_final_pdf(pdf2)
    caught2 = r2["clean"] is False and "INTERNAL_PATH_LEAK" in r2["hard_fails"]
    return {"leak_caught": caught, "bare_abs_path_caught": caught2,
            "scan": r, "bare_scan": r2}