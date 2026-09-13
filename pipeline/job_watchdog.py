#!/usr/bin/env python3
"""
Durable job watchdog / reconcile — AP-1.

Design (per owner approval):
- Durable state = the per-order status JSON (output/order_<id>.json) already
  persisted by pipeline_runner; nothing depends on Popen/process memory.
- On worker/container restart, jobs in non-terminal states are recovered
  by re-running the IDEMPOTENT pipeline entry from its last completed step
  (pipeline_runner already supports step-level resume via status["steps"]).
- Jobs running longer than WATCHDOG_STUCK_HOURS (default 6) are inspected;
  idempotent steps are safely retried; email is NEVER duplicated (a delivery
  marker + verified-delivery record gate re-send); charges are never touched.
- Terminal states: email_sent, delivery_failed, insufficient_public_evidence,
  manual_support_required (cancelled supported as alias).
- All transitions/alerts are logged to docs-side log + job record; this module
  NEVER sends customer emails and NEVER touches Stripe.

Usage:
  python3 pipeline/job_watchdog.py                # one reconcile pass
  python3 pipeline/job_watchdog.py --max-hours 6  # custom threshold
  python3 pipeline/job_watchdog.py --dry-run      # inspect only, no changes
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

OUTPUT_DIR = os.environ.get("WATCHDOG_OUTPUT_DIR",
                            os.path.join(os.path.dirname(_HERE), "output"))
LOG_PATH = os.environ.get("WATCHDOG_LOG",
                          os.path.join(os.path.dirname(_HERE), "output", "watchdog.log"))

# Job state machine (superset mapping of the owner-required states)
JOB_STATES = [
    "payment_received", "intake_validated", "research_started", "research_blocked",
    "quality_repairing", "pdf_rendering", "pdf_repairing", "quality_passed",
    "ready_to_deliver", "email_queued", "email_sent",
    "delivery_failed", "insufficient_legacy_public_evidence",
    "insufficient_public_evidence", "manual_support_required",
    "cancelled", "failed", "running", "pending", "test_data",
]
TERMINAL_STATES = {"email_sent", "delivery_failed", "insufficient_public_evidence",
                   "insufficient_legacy_public_evidence",
                   "manual_support_required", "cancelled"}
# Stages that are safe to re-run (idempotent: pure computation, no email/charge)
IDEMPOTENT_STAGES = {"order_received", "research", "quality", "report", "scan"}
NEVER_RERUN_STAGES = {"deliver"}          # email send is NOT idempotent
ALERT_STUCK_HOURS = 6.0
# Test-data classification: obviously fake recipient domains / URLs
TEST_EMAIL_RE = re.compile(
    r"^[^@\s]+@(a?2?b|example\.(com|org)|test\.com|invalid|mailinator\.com|"
    r"mail\.test|localhost)$", re.I)
TEST_URL_RE = re.compile(r"definitely-not-a-real-site|\.invalid|example\.com$|localhost")


def log(msg: str):
    line = f"{now_iso()} {msg}"
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        print(line)
    except Exception:
        print(line)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(ts: str):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _step_time(status: dict, step: str):
    info = (status.get("steps") or {}).get(step) or {}
    return parse_iso(info.get("timestamp") or "") or parse_iso(status.get("created_at") or "")


def age_hours_since(dt: datetime) -> float:
    return (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0


def classify(order_id: str, status: dict) -> str:
    """Classify a job's durable state. Never deletes data."""
    email = (status.get("customer_email") or "").strip().lower()
    url = (status.get("url") or "").strip().lower()
    if TEST_EMAIL_RE.match(email) or TEST_URL_RE.match(url or ""):
        return "test_data"
    if (status.get("status") in TERMINAL_STATES
            or status.get("delivery_state") in TERMINAL_STATES):
        return "terminal"
    return "active_nonterminal"


def classify_archive_action(status: dict) -> str:
    """For test_data jobs: archive-close, not delete. Returns action description."""
    return ("preserve-audit-record; mark status=cancelled; "
            "prevent customer-facing processing; keep order JSON as test archive")


def reconcile_one(order_id: str, status: dict, dry_run: bool = False,
                  max_hours: float = ALERT_STUCK_HOURS) -> dict:
    """Reconcile one job. Returns an action record; never emails, never charges."""
    action = {"job_id": order_id, "before_status": status.get("status"),
              "classified": classify(order_id, status), "action": "none"}
    if action["classified"] == "test_data" and status.get("status") not in TERMINAL_STATES:
        # Documented cleanup path for the 13 stuck test jobs: preserve minimal audit
        # record, prevent customer-facing processing, close as cancelled (archive).
        action["action"] = classify_archive_action(status)
        if not dry_run:
            status["status"] = "cancelled"
            status["test_data_archive"] = True
            status["archive_note"] = ("classified test_data by watchdog; "
                                      "audit record preserved; not customer-facing")
            status["archived_at"] = now_iso()
            _save(status)
        return action
    if action["classified"] != "active_nonterminal":
        return action
    # Stuck detection: prefer the currently-RUNNING step (the one that was being
    # executed when the worker died); fall back to the newest timestamp.
    steps = status.get("steps") or {}
    last_ts = None
    last_step = None
    running_step = None
    running_ts = None
    for name, info in steps.items():
        ts = parse_iso(info.get("timestamp") or "")
        if info.get("state") == "running" and ts:
            if running_ts is None or ts > running_ts:
                running_step, running_ts = name, ts
        if ts and (last_ts is None or ts > last_ts):
            last_ts, last_step = ts, name
    if running_step:
        last_step, last_ts = running_step, running_ts
    if last_ts is None:
        return action
    age_h = age_hours_since(last_ts)
    action["age_hours"] = round(age_h, 2)
    action["last_step"] = last_step
    if age_h < max_hours:
        return action
    # Stuck: alert + safe retry decision
    log(f"ALERT stuck job {order_id} last_step={last_step} age={age_h:.1f}h")
    action["alert"] = True
    if last_step in IDEMPOTENT_STAGES:
        action["action"] = "retry_idempotent_step"
        # safe retry = reset that step's state so resume path re-runs it
        if not dry_run:
            steps[last_step]["state"] = "pending"
            status.setdefault("reconcile", {"attempts": 0})
            status["reconcile"]["attempts"] = int(status["reconcile"].get("attempts", 0)) + 1
            status["reconcile"]["last_reconcile_at"] = now_iso()
            if status["reconcile"]["attempts"] > 3:
                action["action"] = "escalate_manual_support"
                status["status"] = "manual_support_required"
            else:
                status["status"] = "running"
            status["reconcile"]["last_action"] = action["action"]
            _save(status)
    elif last_step in NEVER_RERUN_STAGES:
        # deliver stuck: do NOT re-send blindly; escalate for human check
        action["action"] = "escalate_manual_support_no_email_rerun"
        if not dry_run:
            status["status"] = "manual_support_required"
            status["reconcile"] = status.get("reconcile", {})
            status["reconcile"]["last_action"] = action["action"]
            status["reconcile"]["last_reconcile_at"] = output = now_iso()
            _save(status)
    else:
        action["action"] = "escalate_manual_support"
        if not dry_run:
            status["status"] = "watchdog_escalated"
            status["reconcile"] = status.get("reconcile", {})
            status["reconcile"]["last_action"] = action["action"]
            status["reconcile"]["last_reconcile_at"] = now_iso()
            _save(status)
    return action


def _save(status: dict):
    path = status.get("status_file") or os.path.join(OUTPUT_DIR, f"order_{status.get('order_id','')}.json")
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(status, fh, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"ERROR saving {path}: {e}")


def reconcile_all(dry_run: bool = False, max_hours: float = ALERT_STUCK_HOURS) -> dict:
    """One reconcile pass over all order files."""
    summary = {"scanned": 0, "test_data_archived": 0, "stuck_alerted": 0,
               "retried": 0, "escalated": 0, "actions": []}
    try:
        files = [f for f in os.listdir(OUTPUT_DIR)
                 if f.startswith("order_") and f.endswith(".json")
                 and not f.endswith(".delivery-record.json")]
    except Exception as e:
        log(f"ERROR listing {OUTPUT_DIR}: {e}")
        return summary
    for f in sorted(files):
        path = os.path.join(OUTPUT_DIR, f)
        try:
            with open(path, encoding="utf-8") as fh:
                status = json.load(fh)
        except Exception as e:
            log(f"ERROR reading {f}: {e}")
            continue
        summary["scanned"] += 1
        rec = reconcile_one(status.get("order_id", f), status, dry_run=dry_run,
                            max_hours=max_hours)
        summary["actions"].append(rec)
        if rec["action"].startswith("preserve"):
            summary["test_data_archived"] += 1
        elif rec.get("alert"):
            summary["stuck_alerted"] += 1
            if rec["action"].startswith("retry"):
                summary["retried"] += 1
            else:
                summary["escalated"] += 1
    log(f"RECONCILE dry_run={dry_run} scanned={summary['scanned']} "
        f"test_archived={summary['test_data_archived']} "
        f"stuck={summary['stuck_alerted']} retried={summary['retried']} escalated={summary['escalated']}")
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-hours", type=float, default=ALERT_STUCK_HOURS)
    args = ap.parse_args()
    reconcile_all(dry_run=args.dry_run, max_hours=args.max_hours)
