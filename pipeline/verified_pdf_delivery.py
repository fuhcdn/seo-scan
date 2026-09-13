#!/usr/bin/env python3
"""
Canonical verified-PDF artifact / delivery service — the ONLY component allowed
to prepare, verify and send a customer-facing report PDF.

Used by BOTH production (pipeline_runner.py) and golden/staging
(gates/evidence_report_runner.py). No other code path may attach a mutable
pdf_path to an email; senders receive ONLY the verified .for-email.pdf.

Flow (hard rules, per handover spec §3/§10):
  1. read exact final PDF artifact (rendered once, after all headers/footers/
     metadata/links)
  2. calculate rendered SHA-256
  3. pypdf visible-text extraction on that exact artifact
  4. metadata / annotation / link-scheme inspection
  5. all final-PDF hard-fail rules
  6. create immutable .for-email.pdf copy
  7. calculate scanned SHA and email-artifact SHA
  8. verify rendered == scanned == email SHA
  9. immediately before sending, re-check .for-email.pdf SHA
 10. send only the verified .for-email.pdf
 11. persist a delivery record (job id, pipeline version, language, scanner
     result, state, SHAs, timestamp)

Env inputs read at send time (values never logged):
  SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD / SMTP_SSL (or legacy
  SMTP_* names used by pipeline_runner) and EMAIL_FROM / EMAIL_SENDER.
A caller may instead pass send_fn=callable(pdf_path, to, subject, from_) for
mock/safe-test senders.
"""
import hashlib
import io
import json
import os
import re
import shutil
import time

DEFAULT_PDF_RULES = "pypdf_exact_artifact_v1"

# ---------------------------------------------------------------- hard rules
ABS_PATH_PREFIXES = ("/app/", "/opt/", "/tmp/", "/home/", "/var/", "/usr/",
                     "/workspace/", "/deploy/")
ALLOWED_LINK_SCHEMES = {"https:", "http:", "mailto:"}
SECRET_PATTERNS = [
    r"sk_live_[A-Za-z0-9]{8,}", r"rk_live_[A-Za-z0-9]{8,}",
    r"whsec_[A-Za-z0-9]{8,}", r"ghp_[A-Za-z0-9]{20,}",
    r"AKIA[0-9A-Z]{16}", r"re_[A-Za-z0-9]{20,}",
    r"-----BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY",
    r"eyJ[A-Za-z0-9_-]{30,}",  # raw JWT
]
PLACEHOLDER_PATTERNS = [
    r"\$\{[A-Za-z_][A-Za-z0-9_.]*\}",       # ${VAR}
    r"\[[A-Za-z0-9_. @]*domain[A-Za-z0-9_. @]*\]",  # [your-domain].com
    r"\[你的域名\]", r"YOUR_API_KEY", r"<API_KEY>", r"xxx_PASSWORD_xxx",
]
ORDER_ID_PATTERN = r"\b(?:ORD|ORDER|PAY|CS_|pi_|sub_)[-_]?[0-9A-Fa-f]{8,}\b"


def sha256_of(path_or_bytes):
    if isinstance(path_or_bytes, bytes):
        return hashlib.sha256(path_or_bytes).hexdigest()
    h = hashlib.sha256()
    with open(path_or_bytes, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_visible_text_pypdf(pdf_bytes: bytes) -> str:
    """PRODUCTION-GRADE extraction via pypdf on the exact artifact.
    No regex-over-raw-bytes-only fallback: if pypdf is unavailable this raises,
    and the caller MUST block delivery (fail-closed)."""
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    parts = []
    for page in reader.pages:
        t = page.extract_text() or ""
        if t:
            parts.append(t)
    return "\n".join(parts)


def extract_pdf_layers(pdf_bytes: bytes) -> dict:
    """Metadata / annotations / link URIs / launch actions / filespecs via pypdf
    (plus raw-bytes URI sweep as an ADDITIONAL layer, never as the only check)."""
    uris, launches, filenames, metadata = [], [], [], []
    raw = pdf_bytes.decode("latin-1", "replace")
    for m in re.finditer(r"/URI\s*\(([^)]{0,500})\)", raw):
        uris.append(m.group(1).encode("utf-8", "replace"))
    for m in re.finditer(r"/Launch\b", raw):
        launches.append(b"/Launch")
    for m in re.finditer(r"/F\s*\(file:([^)]{0,300})\)", raw):
        filenames.append(m.group(1).encode("utf-8", "replace"))
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        md = reader.metadata or {}
        for k, v in md.items():
            if v:
                metadata.append(f"{k}={v}".encode("utf-8", "replace"))
    except Exception:
        pass
    return {"uris": uris, "launches": launches,
            "filenames": filenames, "metadata": metadata}


def scan_final_pdf(pdf_bytes: bytes, expected_domain: str = "",
                   wrong_customer_terms=None) -> dict:
    """All final-PDF hard-fail rules on the EXACT final artifact.
    Returns {clean, hard_fails, hits, sha256, bytes, visible_text_len}."""
    hard_fails, hits = [], []
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    visible = extract_visible_text_pypdf(pdf_bytes)
    vnorm = re.sub(r"\s+", " ", visible)
    vlow = vnorm.lower()
    layers = extract_pdf_layers(pdf_bytes)
    layer_hay = (" ".join(u.decode("utf-8", "replace") for u in layers["uris"]) + " " +
                 " ".join(l.decode("utf-8", "replace") for l in layers["launches"]) + " " +
                 " ".join(f.decode("utf-8", "replace") for f in layers["filenames"]) + " " +
                 " ".join(m.decode("utf-8", "replace") for m in layers["metadata"])).lower()
    hay = vlow + " || " + layer_hay

    def _hit(rule, pattern, count, samples=None):
        hits.append({"rule": rule, "pattern": pattern, "count": count,
                     **({"samples": samples} if samples else {})})
        hard_fails.append(rule)

    # INTERNAL_FILE_URI — any file: scheme anywhere
    n = len(re.findall(r"file:\s*/{0,3}", hay))
    if n:
        _hit("INTERNAL_FILE_URI", "file:", n)
    # UNSAFE_LINK_SCHEME
    bad = {}
    for u in layers["uris"]:
        m = re.match(r"^\s*([a-zA-Z][a-zA-Z0-9+.\-]*):", u.decode("utf-8", "replace"))
        if m and (m.group(1) + ":").lower() not in ALLOWED_LINK_SCHEMES:
            bad[m.group(1)] = bad.get(m.group(1), 0) + 1
    if bad:
        _hit("UNSAFE_LINK_SCHEME", str(bad), sum(bad.values()))
    # INTERNAL_PATH_LEAK
    n = sum(hay.count(p) for p in ABS_PATH_PREFIXES)
    if n:
        _hit("INTERNAL_PATH_LEAK", "absolute-path", n)
    # localhost / infra exposure
    for pat in ("localhost", "127.0.0.1", "0.0.0.0", "srv1970379"):
        n = hay.count(pat)
        if n:
            _hit("INTERNAL_INFRASTRUCTURE_EXPOSURE", pat, n)
    # PLACEHOLDER_LEAK
    n = sum(len(re.findall(p, vnorm)) for p in PLACEHOLDER_PATTERNS)
    if n:
        _hit("PLACEHOLDER_LEAK", "placeholder", n)
    # SECRET_LEAK
    for pat in SECRET_PATTERNS:
        n = len(re.findall(pat, hay))
        if n:
            samples = re.findall(pat, hay)[:3]
            _hit("SECRET_LEAK", "credential", n, [s if isinstance(s, str) else "…" for s in samples])
    # INTERNAL_ORDER_OR_PAYMENT_LEAK
    n = len(re.findall(ORDER_ID_PATTERN, vnorm))
    if n:
        _hit("INTERNAL_ORDER_OR_PAYMENT_LEAK", "order/payment id", n)
    # WRONG_CUSTOMER_OR_DOMAIN — expected domain must appear when provided
    if expected_domain and expected_domain.lower() not in vlow:
        _hit("WRONG_CUSTOMER_OR_DOMAIN", expected_domain, 1)
    # FOREIGN_CUSTOMER_CONTAMINATION — terms from other customers/business models
    for term in (wrong_customer_terms or []):
        n = vlow.count(term.lower())
        if n:
            _hit("FOREIGN_CUSTOMER_CONTAMINATION", term, n)
    # REQUIRED_FIELD_EMPTY — labels rendered with no value. A label is "empty" when
    # the value position holds nothing (end/punctuation) OR is immediately followed
    # by another known label header (its value was dropped in rendering).
    _KNOWN_LABELS = ("Definition of done", "First measurable signal", "Scale rule",
                     "Baseline", "Investment status", "Approver", "Content owner",
                     "Publisher / QA", "Review window", "Exact placement")
    empty_labels = []
    for lab in _KNOWN_LABELS:
        # value position = right after "label:" — empty when it is end/punctuation
        # or starts with ANOTHER known label header (its own value was dropped).
        _others = [l for l in _KNOWN_LABELS if l != lab]
        _alt = "|".join(re.escape(o) for o in _others)
        if re.search(re.escape(lab) + r"\s*:\s*(?:$|\s*$|(?=\s*(?:" + _alt + r")\s*:))", vnorm):
            empty_labels.append(lab)
    if empty_labels:
        _hit("REQUIRED_FIELD_EMPTY", ",".join(empty_labels), len(empty_labels))
    # TRUNCATED_CUSTOMER_TEXT
    sig = [r"\bto th\b", r"\btrust/p[rt]\b", r"tracked via [a-z]{1,6}\b",
           r"the\s+'\s*[a-z]{0,3}\s*$"]
    n = sum(len(re.findall(p, vnorm)) for p in sig)
    if n:
        _hit("TRUNCATED_CUSTOMER_TEXT", "clip", n)
    return {"clean": not hard_fails, "hard_fails": hard_fails, "hits": hits,
            "sha256": sha, "bytes": len(pdf_bytes),
            "visible_text_len": len(vnorm), "extractor": "pypdf",
            "visible_text": visible}


def prepare_verified_artifact(final_pdf_path: str, job_id: str,
                              pipeline_version: str = "legacy",
                              report_language: str = "en",
                              expected_domain: str = "",
                              wrong_customer_terms=None) -> dict:
    """Steps 1-8: scan exact artifact, create immutable .for-email.pdf copy,
    verify 3-way SHA. Returns record dict; state=DELIVERY_BLOCKED on any fail."""
    rec = {"job_id": job_id, "pipeline_version": pipeline_version,
           "report_language": report_language, "service": "verified_pdf_delivery",
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        with open(final_pdf_path, "rb") as fh:
            pdf_bytes = fh.read()
    except Exception as e:
        rec.update({"state": "DELIVERY_BLOCKED",
                    "reason": f"cannot read final pdf: {e}"})
        return rec
    rendered_sha = sha256_of(pdf_bytes)
    scan = scan_final_pdf(pdf_bytes, expected_domain=expected_domain,
                          wrong_customer_terms=wrong_customer_terms)
    rec["rendered_sha256"] = rendered_sha
    rec["scanned_sha256"] = scan["sha256"]
    rec["scanner"] = {k: v for k, v in scan.items() if k != "visible_text"}
    rec["visible_text"] = scan["visible_text"]
    if not scan["clean"]:
        rec.update({"state": "DELIVERY_BLOCKED",
                    "reason": "FINAL_PDF_HARD_FAIL: " + ",".join(scan["hard_fails"])})
        _persist(rec, final_pdf_path)
        return rec
    # step 6: immutable email artifact
    email_path = final_pdf_path + ".for-email.pdf"
    shutil.copy2(final_pdf_path, email_path)
    email_sha = sha256_of(email_path)
    rec["email_artifact_path"] = email_path
    rec["email_sha256"] = email_sha
    # step 8: 3-way verify
    if not (rendered_sha == scan["sha256"] == email_sha):
        rec.update({"state": "DELIVERY_BLOCKED",
                    "reason": f"SHA_MISMATCH rendered={rendered_sha[:16]} scanned={scan['sha256'][:16]} email={email_sha[:16]}"})
        _persist(rec, final_pdf_path)
        return rec
    rec["state"] = "VERIFIED_READY_TO_SEND"
    _persist(rec, final_pdf_path)
    return rec


def _persist(rec: dict, final_pdf_path: str):
    try:
        side = final_pdf_path + ".delivery-record.json"
        out = {k: v for k, v in rec.items() if k != "visible_text"}
        with open(side, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, ensure_ascii=False)
    except Exception:
        pass


def send_verified_pdf(job_id: str, final_pdf_path: str, expected_sha256: str,
                      recipient_email: str, report_language: str = "en",
                      subject: str = None, pipeline_version: str = "legacy",
                      expected_domain: str = "", wrong_customer_terms=None,
                      send_fn=None) -> dict:
    """THE one canonical send path. Both pipeline/ and gates/ must call this.
    Sends ONLY the verified .for-email.pdf; re-checks its SHA immediately
    before send. Any mismatch -> DELIVERY_BLOCKED, nothing is sent."""
    rec = prepare_verified_artifact(final_pdf_path, job_id,
                                    pipeline_version=pipeline_version,
                                    report_language=report_language,
                                    expected_domain=expected_domain,
                                    wrong_customer_terms=wrong_customer_terms)
    if rec["state"] != "VERIFIED_READY_TO_SEND":
        return rec
    email_path = rec["email_artifact_path"]
    # step 9: immediate pre-send SHA re-check
    pre_sha = sha256_of(email_path)
    if expected_sha256 and pre_sha != expected_sha256:
        rec.update({"state": "DELIVERY_BLOCKED",
                    "reason": f"EMAIL_ATTACHMENT_SHA_MISMATCH pre={pre_sha[:16]} expected={expected_sha256[:16]}"})
        _persist(rec, final_pdf_path)
        return rec
    if not pre_sha == rec["rendered_sha256"]:
        rec.update({"state": "DELIVERY_BLOCKED",
                    "reason": "EMAIL_ATTACHMENT_SHA_MISMATCH vs rendered"})
        _persist(rec, final_pdf_path)
        return rec
    # step 10: send ONLY the verified artifact
    if send_fn is not None:
        try:
            send_fn(email_path, recipient_email, subject or f"Your SEO report ({job_id})", None)
            rec["sent"] = True
            rec["state"] = "DELIVERED"
            rec["emailed_sha256"] = pre_sha
        except Exception as e:
            rec.update({"state": "DELIVERY_BLOCKED", "sent": False,
                        "reason": f"send failed: {str(e)[:140]}"})
    else:
        rec.update({"sent": False, "state": "VERIFIED_READY_TO_SEND",
                    "note": "verified artifact ready; no send_fn provided (safe-test mode)"})
    _persist(rec, final_pdf_path)
    return rec


def default_smtp_send(pdf_path, to_addr, subject, from_addr):
    """Default real sender: reuse pipeline_runner._smtp_send (the EXISTING
    production sender — no third sender is created). Values come from env,
    never logged."""
    from pipeline_runner import _smtp_send  # noqa: circular-safe (top-level import of constants only)
    import config as _cfg
    smtp_host = os.environ.get("SMTP_HOST", "").strip()
    smtp_port = int(os.environ.get("SMTP_PORT", "587") or 587)
    smtp_user = os.environ.get("SMTP_USER", os.environ.get("SMTP_USERNAME", "")).strip()
    smtp_pass = os.environ.get("SMTP_PASSWORD", os.environ.get("SMTP_PASS", "")).strip()
    implicit = os.environ.get("SMTP_SSL", "1").strip() == "1"
    from_addr = from_addr or os.environ.get("EMAIL_FROM", os.environ.get("EMAIL_SENDER", "")).strip()
    if not smtp_host:
        raise RuntimeError("SMTP_HOST not set")
    ok = _smtp_send(pdf_path, to_addr, subject, from_addr,
                    smtp_host, smtp_port, smtp_user, smtp_pass,
                    implicit_ssl=implicit)
    if not ok:
        raise RuntimeError("smtp send returned failure")


if __name__ == "__main__":
    print("verified_pdf_delivery: import this module; do not run directly.")
