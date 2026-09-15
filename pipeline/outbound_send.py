"""outbound_send — Phase 1 (STAGING ONLY) cold-email send path.

Full gate sequence before any Resend call:
  target → DNC → duplicate → footer → approval ref → volume cap → stop → [Resend] → log append.
Resend is called ONLY when every gate passes AND DRY_RUN is false.
In dry-run the Resend function is monkey-patched with a counting stub (resend_calls stays 0).
"""
import json, os, time
import outbound_controls as oc

OUTBOUND_ENABLED = os.environ.get("OUTBOUND_ENABLED", "false").lower() == "true"

DATA_DIR = oc.DATA_DIR
LOG_PATH = oc.LOG_PATH
RESEND_CALLS = 0  # test-visible counter (real call only in non-dry-run)


def _real_resend(from_name, from_addr, to_addr, subject, text):
    """Same API shape as pipeline.resend_send but for cold-email From config."""
    assert not oc.DRY_RUN, "FAIL-CLOSED: real transport invoked in dry-run mode"
    import urllib.request
    key = os.environ.get("RESEND_API_KEY", "").strip()
    if not key:
        raise RuntimeError("resend_misconfigured")
    payload = {"from": f"{from_name} <{from_addr}>", "to": [to_addr],
               "reply_to": os.environ.get("REPLY_TO_EMAIL", "support@seoscanaudit.com"),
               "subject": subject, "text": text}
    req = urllib.request.Request("https://api.resend.com/emails",
        data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                 "User-Agent": "seoscanaudit-outbound/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, resp.read().decode()[:200]


def send_cold_email(target, footer_text, approval_ref, subject, body_text):
    global RESEND_CALLS
    if not OUTBOUND_ENABLED:
        return {"sent": False, "stage": "DISABLED", "resend_calls": 0,
                "reason": "outbound_disabled_by_default"}
    target = dict(target)
    log_base = {"event": None, "campaign_id": None, "target": {
        "prospect_id": target.get("prospect_id"), "business_name": target.get("business_name"),
        "domain": target.get("domain"), "email": target.get("email")}}

    # 1 DNC
    blocked, reason = oc.dnc_check(target)
    if blocked:
        oc._append(LOG_PATH, {**log_base, "event": "SKIP_DNC", "reason": reason})
        return {"sent": False, "stage": "DNC", "resend_calls": RESEND_CALLS, "reason": reason}

    # 2 duplicate
    dup, ref = oc.dup_check(target)
    if dup:
        oc._append(LOG_PATH, {**log_base, "event": "SKIP_DUP", "reason": ref})
        return {"sent": False, "stage": "DUP", "resend_calls": RESEND_CALLS, "reason": ref}

    # 3 footer presence (activated footer = no placeholders)
    ok, missing = oc.footer_presence_check(footer_text)
    if not ok:
        oc._append(LOG_PATH, {**log_base, "event": "ABORT_FOOTER", "reason": "missing:" + ",".join(missing)})
        return {"sent": False, "stage": "FOOTER", "resend_calls": RESEND_CALLS, "reason": missing}

    # 4 approval validation (strict record, not just non-empty)
    cfg, why = oc.load_campaign_approval(approval_ref)
    if cfg is None:
        oc._append(LOG_PATH, {**log_base, "event": "ABORT_APPROVAL", "reason": why})
        return {"sent": False, "stage": "APPROVAL", "resend_calls": RESEND_CALLS, "reason": why}

    # 5 volume cap
    capped, why = oc.volume_cap_check(cfg)
    if capped:
        oc._append(LOG_PATH, {**log_base, "event": "ABORT_CAP", "reason": why, "campaign_id": cfg["campaign_id"]})
        return {"sent": False, "stage": "CAP", "resend_calls": RESEND_CALLS, "reason": why}

    # 6 stop conditions
    stopped, why = oc.stop_condition_check(cfg)
    if stopped:
        oc._append(LOG_PATH, {**log_base, "event": "ABORT_STOP", "reason": why, "campaign_id": cfg["campaign_id"]})
        return {"sent": False, "stage": "STOP", "resend_calls": RESEND_CALLS, "reason": why}

    # 7 Resend (only here; dry-run counts without calling)
    result = {"sent": False, "stage": "SEND", "resend_calls": RESEND_CALLS}
    if oc.DRY_RUN:
        # dry-run records are deliberately distinct from SEND so downstream
        # duplicate suppression can never mistake them for a real send
        oc._append(LOG_PATH, {**log_base, "event": "DRY_RUN_WOULD_SEND",
            "campaign_id": cfg["campaign_id"],
            "owner_approval_reference": cfg["owner_approval_reference"],
            "resend_id": None, "dry_run": True})
        result.update({"would_send": True, "resend_calls": RESEND_CALLS})
        return result
    oc._append(LOG_PATH, {**log_base, "event": "SEND",
        "campaign_id": cfg["campaign_id"],
        "owner_approval_reference": cfg["owner_approval_reference"],
        "resend_id": None, "dry_run": False})
    status, resp = _real_resend("SEO Scan Audit", cfg["approved_sender"],
                                target["email"], subject, body_text + "\n\n" + footer_text)
    RESEND_CALLS += 1
    result.update({"http_status": status, "resend_calls": RESEND_CALLS})
    return result
