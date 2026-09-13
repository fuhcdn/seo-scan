#!/usr/bin/env python3
"""Owner-decision A→C insufficient-evidence state machine tests (staging/mock).

Run: .venv/bin/python tests/test_clarification_flow.py
All synthetic; no email sent; no refund; no real customer data.
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "pipeline"))
import clarification_flow as CF  # noqa: E402

RESULTS = []
TMP = tempfile.mkdtemp(prefix="clr_")


def check(name, cond, info=""):
    RESULTS.append((name, bool(cond), info))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}: {info}")


def mkjob(oid="CLR-1"):
    st = {"order_id": oid, "status": "research_started",
          "status_file": os.path.join(TMP, f"order_{oid}.json"),
          "customer_email": "realowner@realfirm-site.com"}
    return CF.save(st)


# 1. insufficient → clarification_required with minimum-missing list
st = mkjob()
st = CF.enter_clarification_required(st, ["website", "goal"])
check("1-clarification_required", st["status"] == "clarification_required", st["status"])
check("1b-missing-recorded", st["clarification"]["missing"] == ["website", "goal"], str(st["clarification"]["missing"]))

# 2. clarification request draft (mock only) asks ONLY for the missing minimum
req = CF.build_clarification_request(st, report_language="en")
check("2-request-mock-only", req["mock_only"] is True and req["live_send_enabled"] is False, "no live send")
check("2b-asks-minimum", "website" in req["body"] and "blocked" not in req["body"], "only missing items")
check("2c-all-5-languages", all(
    CF.build_clarification_request(st, lang)["mock_only"] for lang in ("en", "zh-Hant", "zh-Hans", "ja", "es")), "5 langs OK")

# 3. awaiting state + window (3 business days)
st = CF.awaiting_customer_clarification(st)
check("3-awaiting", st["status"] == "awaiting_customer_clarification", st["status"])
check("3b-window-not-expired-now", CF.check_window_expired(st) is False, "just entered")

# 4. reply sufficient → resume pipeline
st2 = CF.reply_received(json.loads(json.dumps(st)), reply_sufficient=True)
check("4-reply-sufficient-resume", st2["status"] == "running" and st2["clarification"]["outcome"] == "evidence_sufficient_resumed", st2["status"])

# 5. reply still insufficient → manual_support_required (owner rule 8)
st3 = CF.reply_received(json.loads(json.dumps(st)), reply_sufficient=False)
check("5-reply-insufficient-manual", st3["status"] == "manual_support_required", st3["status"])
check("5b-no-autoflow", "refund" not in json.dumps(st3) and "credit" not in json.dumps(st3), "no auto refund/credit")

# 6. window expiry (3 business days) → manual_support_required + owner record
st4 = json.loads(json.dumps(st))
st4["clarification"]["awaiting_since"] = (datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
check("6-window-expired-detected", CF.check_window_expired(st4) is True, "5 days elapsed")
st5 = CF.window_expired(st4)
check("6b-manual-after-expiry", st5["status"] == "manual_support_required", st5["status"])
check("6c-owner-record-preserved", st5.get("owner_support_record", {}).get("audit_preserved") is True, "audit kept")
check("6d-order-data-not-deleted", st5.get("order_id") == "CLR-1", "data intact")

# 7. exactly 3 business days: Friday -> Monday = 1 business day gap; test helper
fri = datetime(2026, 9, 11, tzinfo=timezone.utc)   # Friday
mon = datetime(2026, 9, 14, tzinfo=timezone.utc)   # Monday
check("7-business-days-fri-to-mon", CF.business_days_between(fri, mon) == 1, "weekend not counted")

ok = sum(1 for _, p, _ in RESULTS if p)
print("=" * 60)
print(f"Clarification-flow tests: {ok}/{len(RESULTS)}")
sys.exit(0 if ok == len(RESULTS) else 1)
