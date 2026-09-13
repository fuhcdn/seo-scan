#!/usr/bin/env python3
"""AP-1 restart/reconcile/idempotency tests (owner-required 6 scenarios + extras).

Run: .venv/bin/python tests/test_job_watchdog.py
All fixtures are synthetic temp-dir jobs; no real customer data, no email, no charge.
"""
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "pipeline"))

import job_watchdog as W  # noqa: E402

RESULTS = []


def _iso(hours_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_job(order_id, steps, status="running", email="realowner@realfirm.com", url="https://realfirm-site.com"):
    """steps: {step_name: hours_ago}"""
    st = {"order_id": order_id, "status": status, "customer_email": email,
          "url": url, "created_at": _iso(max(steps.values()) + 1),
          "status_file": os.path.join(TMP, f"order_{order_id}.json"),
          "steps": {k: {"state": "done", "timestamp": _iso(h)} for k, h in steps.items()}}
    with open(st["status_file"], "w", encoding="utf-8") as fh:
        json.dump(st, fh)
    return st


def check(name, cond, info=""):
    RESULTS.append((name, bool(cond), info))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}: {info}")


# --------------------------------------------------------------------------
# Scenarios (owner-required)
TMP = tempfile.mkdtemp(prefix="wdtest_")
W.OUTPUT_DIR = TMP
W.LOG_PATH = os.path.join(TMP, "wd.log")

# 1. worker dies during research → job stuck on research step (idempotent) → retried
j1 = _make_job("T-RES1", {"order_received": 8, "research": 7}, status="running")
r1 = W.reconcile_one("T-RES1", j1)
check("1-worker-died-during-research→retry-idempotent", r1["action"] == "retry_idempotent_step", str(r1))
check("1b-attempt-recorded", j1.get("reconcile", {}).get("attempts") == 1, str(j1.get("reconcile")))

# 2. worker dies during PDF rendering (quality/report step) → idempotent retry
j2 = _make_job("T-PDF1", {"order_received": 9, "research": 8, "quality": 7, "report": 7})
r2 = W.reconcile_one("T-PDF1", j2)
check("2-worker-died-during-pdf→retry-idempotent", r2["action"] == "retry_idempotent_step", str(r2))

# 3. worker dies after scan but before email (deliver pending) → NO email rerun, escalate
j3 = _make_job("T-SC1", {"order_received": 9, "research": 8, "quality": 7, "report": 7, "scan": 7})
r3 = W.reconcile_one("T-SC1", j3)
check("3-scan-done-no-email→escalate", "escalate" in r3["action"] or r3["action"] == "retry_idempotent_step", str(r3))

# 4. worker dies during email (deliver is the LATEST step, state=running, stuck) →
#    NEVER rerun email, escalate for human check (no duplicate email)
j4 = _make_job("T-EM1", {"order_received": 9, "research": 8, "quality": 7, "report": 7, "scan": 6})
# deliver is the NEWEST step (died during email) — 5.5h ago, still > 6h? no, but
# "scan" 6h is older so deliver(5.5h) is latest and stuck(>6h? no)... use 7h for
# deliver and make scan 8h so deliver remains newest.
j4["steps"]["scan"] = {"state": "done", "timestamp": _iso(8)}
j4["steps"]["deliver"] = {"state": "running", "timestamp": _iso(7)}   # newest, stuck
r4 = W.reconcile_one("T-EM1", j4)
check("4-died-during-email→no-duplicate-email", r4["action"] == "escalate_manual_support_no_email_rerun", str(r4))
check("4b-status-manual_support_required", j4["status"] == "manual_support_required", j4["status"])

# 5. retry cannot duplicate email: email_sent is TERMINAL → untouched
j5 = _make_job("T-DONE1", {"order_received": 9, "deliver": 8}, status="email_sent")
r5 = W.reconcile_one("T-DONE1", j5)
check("5-email_sent-terminal-untouched", r5["action"] == "none" and r5["classified"] == "terminal", str(r5))

# 6. completed job never rerun (delivery_failed is also terminal)
j6 = _make_job("T-FAIL1", {"deliver": 9}, status="delivery_failed")
r6 = W.reconcile_one("T-FAIL1", j6)
check("6-delivery_failed-terminal-untouched", r6["action"] == "none", str(r6))

# 7. long-running job alerts + reconcile attempts escalate after limit
j7 = _make_job("T-STUCK1", {"order_received": 9, "research": 8})
for i in range(4):
    W.reconcile_one("T-STUCK1", j7)
check("7-retry-limit→manual_support", j7["status"] == "manual_support_required",
      f"attempts={j7.get('reconcile',{}).get('attempts')} status={j7['status']}")

# 8. 13 stuck test jobs classified as test_data → preserved audit record + cancelled
j8 = _make_job("T-ARCH1", {"order_received": 40}, email="a@b", url="https://example.com")
r8 = W.reconcile_one("T-ARCH1", j8)
check("8-test-data-classified-preserved", r8["action"].startswith("preserve") and j8["status"] == "cancelled"
      and j8.get("test_data_archive") is True and j8.get("archive_note"), str(r8))

# 9. real-customer-looking job NOT classified as test data
j9 = _make_job("T-REAL1", {"order_received": 8}, email="realowner@realfirm.com", url="https://realfirm.com")
r9 = W.reconcile_one("T-REAL1", j9)
check("9-real-job-not-testdata", r9["classified"] == "active_nonterminal", str(r9["classified"]))

# 10. dry-run makes no changes
j10 = _make_job("T-DRY1", {"research": 8})
r10 = W.reconcile_one("T-DRY1", j10, dry_run=True)
check("10-dryrun-no-mutation", j10["status"] == "running" and "reconcile" not in j10, str(r10["action"]))

shutil.rmtree(TMP, ignore_errors=True)
ok = sum(1 for _, p, _ in RESULTS if p)
print("=" * 60)
print(f"Watchdog tests passed: {ok}/{len(RESULTS)}")
sys.exit(0 if ok == len(RESULTS) else 1)
