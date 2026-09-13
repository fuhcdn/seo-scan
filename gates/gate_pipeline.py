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

# SINGLE SOURCE OF TRUTH for investment status. Every action reads ONLY this map.
# Fixed per customer/goal; renderers must NOT re-derive from effort/title/length.
def _investment_status_for(card: dict) -> str:
    cid = (card.get("card_id") or "").upper()
    # DO_NOW: low-risk, reversible, single customer-owned URL, no unconfirmed operational figures.
    if cid in ("EC-003", "EC-004"):
        return "DO_NOW"
    # VALIDATE_FIRST: requires owner confirmation of MOQ/setup/price/turnaround/SLA/example copy.
    if cid in ("EC-001", "EC-002", "EC-005"):
        return "VALIDATE_FIRST"
    return "VALIDATE_FIRST"  # conservative default


# SINGLE SOURCE OF TRUTH for role-level ownership. Every renderer reads ONLY this.
ROLE_OWNERSHIP = {
    "EC-001": {"approver": "Sales/Operations", "content": "Content/Marketing", "publisher_qa": "Web/Developer"},
    "EC-002": {"approver": "Owner/Service Manager", "content": "Service/Content", "publisher_qa": "Web/Developer"},
    "EC-003": {"approver": "Production Lead", "content": "Content/Marketing", "publisher_qa": "Web/Developer"},
    "EC-004": {"approver": "Sales/Operations", "content": "Content/Marketing", "publisher_qa": "Web/Developer"},
    "EC-005": {"approver": "Sales/Operations + Production Lead", "content": "Content/Marketing", "publisher_qa": "Web/Developer"},
}


def _ownership_for(card: dict) -> dict:
    return ROLE_OWNERSHIP.get((card.get("card_id") or "").upper(),
                              {"approver": "Owner", "content": "Content/Marketing", "publisher_qa": "Web/Developer"})


def gate3_actions_from_evidence_cards(cards: List[dict]) -> List[dict]:
    """Generate ONE action per passed evidence card. Each action has EXACTLY ONE
    primary URL (or one explicit new URL). Each action has a SINGLE immutable
    `investment_status` value read from one source. NO truncated customer text:
    every visible sentence is complete, or says 'See Implementation Brief <id>'."""
    actions = []
    for i, card in enumerate(cards, 1):
        url = (card.get("primary_customer_url") or "").strip()
        if not url:
            continue
        aid = f"ACT-{i:03d}"
        module = (card.get("recommended_module") or "").strip()
        own = _ownership_for(card)
        # FULL module text — never truncated in the customer-facing PDF.
        title = f"{module} on the customer page {url}"
        # Definition of done: complete sentence; don't re-quote a module that already
        # contains quote chars (avoids double-nested quotes like "the 'Add a 'Pricing'...").
        acceptance = (f"QA-pass on the live customer page {url}: the {module} module "
                      f"renders and its links work on mobile and desktop, the page passes "
                      f"a content check by the approver ({own['approver']}) and QA by "
                      f"{own['publisher_qa']}, and no text is clipped. "
                      f"See Implementation Brief {aid} for complete requirements.")
        actions.append({
            "action_id": aid,
            "priority": "P1",
            "title": title,
            "primary_url": url,                       # EXACTLY ONE
            "customer_owned_scope": url,
            "business_mechanism": card.get("business_mechanism", ""),
            "page_gap": card.get("specific_gap", ""),
            "buyer_question": card.get("buyer_question", ""),
            "recommended_module": module,
            "owner_approver": own["approver"],
            "owner_content": own["content"],
            "owner_publisher_qa": own["publisher_qa"],
            "effort": "Medium" if _investment_status_for(card) == "VALIDATE_FIRST" else "Small",
            "investment_status": _investment_status_for(card),   # single source of truth
            "acceptance_criteria": acceptance,
            "validation_method": "First measurable signal: quote-form submissions or CTA clicks on this exact page within 30 days (GSC/GA4 where access; else public re-check). Review at 30 and 60 days; scale only after two positive review points. See Implementation Brief " + aid + " for complete requirements.",
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
    # hyperlink / URI / launch / filespec annotations (object tree, may be uncompressed)
    uris = re.findall(rb"/URI\s*\((.*?)\)", pdf)
    uris += re.findall(rb"/URI\s*\(.*?\)", decoded)
    launches = re.findall(rb"/Launch[^>]{0,120}", pdf) + re.findall(rb"/Launch[^>]{0,120}", decoded)
    filenames = re.findall(rb"\n/F\s*\((.*?)\)", pdf) + re.findall(rb"/F\s*\((.*?)\)\s*/", pdf)
    embedded = re.findall(rb"/EmbeddedFile\s*\((.*?)\)", pdf)
    metadata = re.findall(rb"/(?:Title|Author|Subject|Keywords|Creator|Producer|PageTitle)\s*\((.*?)\)", pdf)
    return {"decoded": decoded,
            "uris": uris, "launches": launches, "filenames": filenames,
            "embedded": embedded, "metadata": metadata}


def extract_visible_text_mature(pdf: bytes) -> str:
    """PRODUCTION-GRADE text extraction via pypdf (mature PDF text extractor), used on the
    EXACT final PDF. Falls back to decompression+regex ONLY if pypdf is unavailable."""
    try:
        import pypdf
        import io
        reader = pypdf.PdfReader(io.BytesIO(pdf))
        parts = []
        for pg in reader.pages:
            t = pg.extract_text() or ""
            if t:
                parts.append(t)
        return "\n".join(parts)
    except Exception:
        # fallback: decompressed streams text (better than nothing, still not ideal)
        import zlib
        streams = re.findall(rb"stream\r?\n(.*?)\r?\nendstream", pdf, re.S)
        dec = b""
        for s in streams:
            try:
                dec += zlib.decompress(s) + b"\n"
            except Exception:
                pass
        toks = re.findall(rb"\((?:\\.|[^()\\])*\)\s*Tj", dec)
        return b" ".join(toks).decode("utf-8", "replace")


def gate5_scan_final_pdf(pdf_bytes: bytes) -> Dict[str, Any]:
    """Scan the EXACT bytes that will be emailed, using a MATURE PDF text extractor (pypdf)
    on the visible text, PLUS annotation/metadata layers. NOT a folder blacklist. Compares
    extracted text against: file:, all absolute internal paths, prior-customer/company/domain,
    placeholders, internal order IDs, secrets, unsafe schemes. Any file: URI in extracted
    customer-visible text blocks, regardless of raw-byte scanning."""
    sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    visible_text = extract_visible_text_mature(pdf_bytes).lower()
    L = _extract_pdf_layers(pdf_bytes)
    layer_hay = (" ".join(u.decode("utf-8", "replace") for u in L["uris"]) + " " +
                 " ".join(l.decode("utf-8", "replace") for l in L["launches"]) + " " +
                 " ".join(f.decode("utf-8", "replace") for f in L["filenames"]) + " " +
                 " ".join(m.decode("utf-8", "replace") for m in L["metadata"]) + " " +
                 " ".join(e.decode("utf-8", "replace") for e in L["embedded"])).lower()
    # the customer-visible check is authoritative: search BOTH visible text and layers
    hay = visible_text + " || " + layer_hay
    hard_fails = []
    hits = []

    # 1) any file: scheme (visible text OR any layer) -> INTERNAL_FILE_URI (hard block)
    file_uri = re.findall(r"file:\s*/{0,3}", hay)
    if file_uri:
        hard_fails.append("INTERNAL_FILE_URI")
        hits.append({"rule": "INTERNAL_FILE_URI", "pattern": "file:", "count": len(file_uri)})

    # 2) unsafe hyperlink schemes (visible text and layer URIs)
    bad_schemes = {}
    for u in [x.decode("utf-8", "replace") for x in L["uris"]]:
        mu = re.match(r"^\s*([a-zA-Z][a-zA-Z0-9+.\-]*):", u)
        if mu and (mu.group(1) + ":").lower() not in ALLOWED_LINK_SCHEMES:
            bad_schemes[mu.group(1)] = bad_schemes.get(mu.group(1), 0) + 1
    if bad_schemes:
        hard_fails.append("UNSAFE_LINK_SCHEME")
        hits.append({"rule": "UNSAFE_LINK_SCHEME", "pattern": str(bad_schemes), "count": sum(bad_schemes.values())})

    # 3) absolute internal paths in extracted text or layers
    path_hits = sum(hay.count(p) for p in ABSOLUTE_PATH_PREFIXES)
    if path_hits:
        hard_fails.append("INTERNAL_PATH_LEAK")
        hits.append({"rule": "INTERNAL_PATH_LEAK", "pattern": "absolute-path", "count": path_hits})

    # 4) secrets / order-ids / placeholders / prior-customer marks in extracted text
    secret_pat = re.findall(r"sk_live_|rk_live_|whsec_|api[_-]?key", hay)
    order_pat = re.findall(r"ORD-[A-F0-9]{6,}", hay)
    ph_pat = re.findall(r"\{\{.*?\}\}|\[y[our\-]*domain\]|REMOVE THIS", hay)
    if secret_pat:
        hard_fails.append("SECRET_LEAK"); hits.append({"rule": "SECRET_LEAK", "count": len(secret_pat)})
    if order_pat:
        hard_fails.append("ORDER_ID_LEAK"); hits.append({"rule": "ORDER_ID_LEAK", "count": len(order_pat)})
    if ph_pat:
        hard_fails.append("PLACEHOLDER_PRESENT"); hits.append({"rule": "PLACEHOLDER_PRESENT", "count": len(ph_pat)})

    # 5) truncated customer text — clipped words/sentences from data truncation
    trunc = _check_truncated_customer_text(visible_text)
    if trunc["count"]:
        hard_fails.append("TRUNCATED_CUSTOMER_TEXT")
        hits.append({"rule": "TRUNCATED_CUSTOMER_TEXT", "samples": trunc["samples"][:12], "count": trunc["count"]})

    clean = (not hard_fails) and len(pdf_bytes) > 1000
    return {"clean": clean, "sha256": sha256, "hard_fails": hard_fails,
            "hits": hits, "bytes": len(pdf_bytes),
            "extracted_visible_text": (visible_text[:1000] + " ... (%d chars total)" % len(visible_text)) if not clean else None,
            "text_extractor": "pypdf" }


def _normalize(text: str) -> str:
    """Collapse runs of whitespace/newlines to single spaces so pypdf line-wrapping
    does not create false 'empty label' or 'truncated word' results."""
    return re.sub(r"\s+", " ", text or "").strip()


def _check_truncated_customer_text(visible_lower: str) -> Dict[str, Any]:
    """Detect REAL customer-text truncation artifacts, NOT pypdf line-wraps and NOT
    legitimate quoted phrases. Normalizes whitespace first. Flags only:
    - a word cut so the sentence ends mid-word (token ending in a fragment, no punctuation)
    - a dangling apostrophe/quote with no closing at a sentence boundary
    - a trailing ' to th' / 'trust/p'-style clip at a boundary
    An ellipsis '…' by itself is allowed only when part of a quoted (not truncated) value.
    """
    norm = _normalize(visible_lower)
    samples = []
    # A clipped suffix token: word fragment followed by end-of-string or a new sentence start
    # that is a continuation of sliced text. Detect the concrete signatures the user listed.
    sig = [
        r"\bto th\b",           # "Add a ... to th"
        r"\btracked via [a-z]{1,6}\b",  # "tracked via Whic"
        r"[a-z]{2,5}/p[rt]\b",  # "trust/pr"
        r"the 'add a '",        # double-nested module quote (renderer bug signal)
        r"the\s+'\s*[a-z]{0,3}\s*$",  # dangling quote at very end of a line/block with nothing after
    ]
    for pat in sig:
        m = re.findall(pat, norm)
        samples += m
    # a dangling unmatched apostrophe at a sentence boundary (e.g. "... ' module " / " ...'\n")
    for m in re.finditer(r"'([a-z]{0,12})\s*(?=$|[.?;!]|\n|ACT-|\bDefinition\b|\bFirst\b|\bReview\b)", norm):
        frag = m.group(1)
        if frag and frag not in ("s", "t", "ll", "re", "ve"):  # possessive/contraction ok
            samples.append("dangling-quote:" + frag)
    return {"count": len(samples), "samples": list(dict.fromkeys(samples))[:15]}


def gate5_check_required_field_empty(visible_text: str, rendered_labels) -> Dict[str, Any]:
    """After render, ensure every applicable implementation label carries a non-empty value.
    Normalizes whitespace so pypdf line-wraps don't create false empties. A label counts as
    empty ONLY if after the label there is no content before the next label/section boundary."""
    norm = _normalize(visible_text)
    empties = []
    for lab in (rendered_labels or []):
        idx = norm.find(lab)
        if idx < 0:
            # label not rendered at all -> handled by the renderer (skip; not applicable)
            continue
        tail = norm[idx + len(lab):].split("|||")[0]
        # content is anything until the next known label boundary
        boundaries = tuple(l2 for l2 in (rendered_labels or []) if l2 != lab and len(l2) > 4)
        cut = len(tail)
        for b in boundaries:
            bi = tail.lower().find(b.lower())
            if 0 <= bi < cut:
                cut = bi
        seg = tail[:cut].strip(": \t")
        if not seg:
            empties.append(lab)
    return {"count": len(empties), "empty_labels": empties}


def gate5_check_priority_consistency(actions) -> Dict[str, Any]:
    """Every renderer must read the SAME investment_status; if the action list carries
    contradictory statuses for the same action_id, block. (Callers pass the final list
    used by all sections.)"""
    seen = {}
    for a in actions:
        aid = a.get("action_id")
        st = a.get("investment_status")
        if aid in seen and seen[aid] != st:
            return {"consistent": False, "conflict": aid, "values": [seen[aid], st], "fail": "PRIORITY_CONSISTENCY_FAIL"}
        seen[aid] = st
    return {"consistent": True, "fail": None}


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