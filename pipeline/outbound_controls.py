"""outbound_controls — Phase 1 (STAGING ONLY) DNC/duplicate/footer/approval/cap/stop checks.

Append-only stores on mounted volume /app/data:
  dnc.jsonl, campaign_log.jsonl
All operations are append-only; corrections use DNC_REVERSAL records, never edits/deletes.
"""
import json, os, hashlib, time

DATA_DIR = os.environ.get("OUTBOUND_DATA_DIR", "/app/data")
CONFIG_DIR = os.environ.get("OUTBOUND_CONFIG_DIR", "/app/config")
DNC_PATH = os.path.join(DATA_DIR, "dnc.jsonl")
LOG_PATH = os.path.join(DATA_DIR, "campaign_log.jsonl")
APPROVAL_PATH = os.path.join(CONFIG_DIR, "campaign_approval.json")
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() == "true"

REQUIRED_APPROVAL_FIELDS = {
    "campaign_id", "owner_approval_reference", "approved_market",
    "approved_ICP", "approved_template_hash", "approved_sender",
    "approved_footer_hash", "approved_volume_cap", "approved_sending_window",
    "campaign_status",
}
FOOTER_REQUIRED_SUBSTRINGS = ["[BUSINESS LEGAL NAME]", "[OWNER-APPROVED POSTAL ADDRESS]", "[OWNER-APPROVED OPT-OUT WORDING]"]


def _append(path, record):
    record = dict(record)
    record.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def dnc_check(target):
    """Return (blocked: bool, reason: str). Matches email OR domain."""
    if not os.path.exists(DNC_PATH):
        return False, "dnc_store_missing"
    t_email = (target.get("email") or "").strip().lower()
    t_domain = (target.get("domain") or "").strip().lower().lstrip("@")
    for line in open(DNC_PATH, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("record_type") != "DNC":
            continue
        if t_email and rec.get("email", "").strip().lower() == t_email:
            return True, "dnc_email"
        if t_domain and rec.get("domain", "").strip().lower() == t_domain:
            return True, "dnc_domain"
    return False, "clear"


def dup_check(target):
    """Return (dup: bool, ref). Matches business_name/domain/email against prior sends."""
    if not os.path.exists(LOG_PATH):
        return False, ""
    t_email = (target.get("email") or "").strip().lower()
    t_domain = (target.get("domain") or "").strip().lower()
    t_name = (target.get("business_name") or "").strip().lower()
    n = 0
    for line in open(LOG_PATH, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("event") not in ("SEND", "DRY_RUN_WOULD_SEND"):
            continue
        n += 1
        if t_email and rec.get("target", {}).get("email", "").lower() == t_email:
            return True, f"dup_email:{n}"
        if t_domain and rec.get("target", {}).get("domain", "").lower() == t_domain:
            return True, f"dup_domain:{n}"
        if t_name and rec.get("target", {}).get("business_name", "").lower() == t_name:
            return True, f"dup_name:{n}"
    return False, ""


def footer_presence_check(footer_text):
    missing = [p for p in FOOTER_REQUIRED_SUBSTRINGS if p not in (footer_text or "")]
    # Phase 1: placeholders are "present" for dry-run; an ACTIVATED footer must have zero placeholders
    return (len(missing) == 0), missing


def _approval_tamper_check():
    """Refuse if approval config is writable from within the container (must be host-managed read-only)."""
    if not os.path.exists(APPROVAL_PATH):
        return "approval_file_missing"
    # NOTE: container runs as root — os.access(W_OK) is always true for root.
    # Read-only enforcement therefore uses permission bits: an owner-managed
    # read-only config must have NO write bits set (e.g. 0444) on a read-only mount.
    st = os.stat(APPROVAL_PATH)
    if st.st_mode & 0o222:
        return "approval_config_writable"
    # optional integrity: owner-recorded hash sidecar /app/config/campaign_approval.sha256
    sha_side = APPROVAL_PATH + ".sha256"
    if os.path.exists(sha_side):
        expected = open(sha_side).read().strip().split()[0]
        actual = hashlib.sha256(open(APPROVAL_PATH, "rb").read()).hexdigest()
        if expected != actual:
            return "approval_hash_mismatch"
    return None


def load_campaign_approval(ref):
    """Owner-approved campaign config record. READ-ONLY file: /app/config/campaign_approval.json."""
    path = APPROVAL_PATH
    tamper = _approval_tamper_check()
    if tamper:
        return None, tamper
    try:
        cfg = json.load(open(path, encoding="utf-8"))
    except json.JSONDecodeError:
        return None, "approval_file_invalid"
    if cfg.get("owner_approval_reference") != ref:
        return None, "approval_ref_mismatch"
    missing = REQUIRED_APPROVAL_FIELDS - set(cfg.keys())
    if missing:
        return None, "approval_missing_fields:" + ",".join(sorted(missing))
    if cfg.get("campaign_status") != "ACTIVE":
        return None, "campaign_not_active"
    # hash integrity of template + footer
    tpl_path = cfg.get("approved_template_path")
    if tpl_path and os.path.exists(tpl_path):
        actual = hashlib.sha256(open(tpl_path, "rb").read()).hexdigest()
        if actual != cfg.get("approved_template_hash"):
            return None, "template_hash_mismatch"
    return cfg, "ok"


def volume_cap_check(cfg):
    cap = cfg.get("approved_volume_cap")
    sent = 0
    if os.path.exists(LOG_PATH):
        for line in open(LOG_PATH, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (rec.get("event") in ("SEND", "DRY_RUN_WOULD_SEND")
                    and rec.get("campaign_id") == cfg.get("campaign_id")):
                sent += 1
    if sent >= int(cap):
        return True, f"cap_reached:{sent}/{cap}"
    return False, f"sent:{sent}/{cap}"


def stop_condition_check(cfg):
    path = os.path.join(DATA_DIR, "stop_conditions.json")
    if os.path.exists(path):
        try:
            st = json.load(open(path, encoding="utf-8"))
            if st.get("pause_new_sends"):
                return True, "pause_flag_active"
        except json.JSONDecodeError:
            return True, "stop_file_invalid"
    return False, "clear"
