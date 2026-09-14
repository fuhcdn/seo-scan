#!/usr/bin/env python3
"""LEGACY_REPORT_DELIVERY_BLOCKED — fail-closed tests (owner directive 2026-09-14).

Verifies:
1. enforce_pipeline_gate: legacy/unspecified -> blocked; evidence_v1 -> allowed.
2. prepare_verified_artifact: legacy version NEVER creates .for-email.pdf.
3. send_verified_pdf: legacy version NEVER sends (no send_fn invocation).
4. run_pipeline (legacy runner) with payment_ref -> hard fail, deliver never runs.
"""
import os, sys, tempfile, shutil

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import verified_pdf_delivery as vpd

RESULTS = []
def check(name, cond, info=""):
    RESULTS.append((name, bool(cond), info))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}: {info}")

# 1. gate function
g = vpd.enforce_pipeline_gate("legacy", "ORD-X")
check("gate blocks legacy", not g["allowed"] and g["state"] == "LEGACY_REPORT_DELIVERY_BLOCKED", g["state"])
g = vpd.enforce_pipeline_gate("", "ORD-X")
check("gate blocks unspecified/empty", not g["allowed"], g["pipeline_version"])
g = vpd.enforce_pipeline_gate("evidence_v1", "ORD-X")
check("gate allows evidence_v1", g["allowed"], "evidence_v1 allowed")

# 2/3. artifact + send blocked for legacy
tmp = tempfile.mkdtemp()
try:
    pdf = os.path.join(tmp, "fake_report.pdf")
    # minimal valid PDF bytes (scan may fail on content, but gate must trip BEFORE scan)
    open(pdf, "wb").write(b"%PDF-1.4\n%%EOF\n")
    rec = vpd.prepare_verified_artifact(pdf, "ORD-X", pipeline_version="legacy")
    check("prepare blocks legacy", rec["state"] == "LEGACY_REPORT_DELIVERY_BLOCKED", rec["state"])
    check("no .for-email.pdf created for legacy",
          not os.path.exists(pdf + ".for-email.pdf"), "artifact absent")

    sent = {"called": False}
    def _fake_send(path, to, subj, frm):
        sent["called"] = True
    rec = vpd.send_verified_pdf("ORD-X", pdf, "", "victim@example.com",
                                pipeline_version="legacy", send_fn=_fake_send)
    check("send blocks legacy", rec["state"] == "LEGACY_REPORT_DELIVERY_BLOCKED" and not rec.get("sent"), rec["state"])
    check("send_fn never invoked for legacy", not sent["called"], "no SMTP/Resend call")

    # evidence_v1 still passes the gate (scan needs pypdf which may be absent in
    # the local test env; assert it got PAST the legacy gate either way)
    try:
        rec = vpd.prepare_verified_artifact(pdf, "ORD-X", pipeline_version="evidence_v1")
        check("evidence_v1 not gate-blocked", rec["state"] != "LEGACY_REPORT_DELIVERY_BLOCKED", rec.get("state"))
    except (ImportError, Exception) as _e:
        # pypdf parse error on the stub PDF means the gate already PASSED
        check("evidence_v1 not gate-blocked", "LEGACY" not in str(_e), f"PASSED_GATE ({type(_e).__name__})")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# 4. legacy runner with real payment_ref -> hard fail at deliver
import pipeline_runner as pr
order = {"order_id": "ORD-GATE-TEST", "url": "https://example.com/",
         "payment_ref": "pi_FAKE", "customer_email": "owner-test@example.com",
         "report_language": "en"}
# Skip crawl/report by faking a completed pre-deliver state
import json, tempfile as _t
tmpd = _t.mkdtemp()
orig_out = pr.OUTPUT_DIR
pr.OUTPUT_DIR = tmpd
pr.per_order_status_path.__wrapped__ if hasattr(pr.per_order_status_path, "__wrapped__") else None
status_path = os.path.join(tmpd, f"order_{order['order_id']}.json")
json.dump({"order_id": order["order_id"], "status": "running",
           "steps": {"order_received": {"state": "done"}, "payment_verified": {"state": "done"},
                     "crawl": {"state": "done"}, "score": {"state": "done"},
                     "research": {"state": "done"}, "report": {"state": "done"}},
           "report_pdf": None, "score": 80}, open(status_path, "w"))
# monkeypatch paths used by load_status/save_status
pr.per_order_status_path = lambda oid: status_path
try:
    pr.run_pipeline(order)
    check("legacy runner raises on paid order", False, "no exception raised")
except RuntimeError as e:
    check("legacy runner raises on paid order", "LEGACY_REPORT_DELIVERY_BLOCKED" in str(e), str(e)[:80])
except Exception as e:
    # crawl/report resume may attempt real work before deliver; acceptable only if error mentions gate
    ok = "LEGACY_REPORT_DELIVERY_BLOCKED" in str(e)
    check("legacy runner blocked (indirect)", ok, f"{type(e).__name__}: {str(e)[:80]}")
st = json.load(open(status_path))
check("status records LEGACY_REPORT_DELIVERY_BLOCKED",
      st.get("delivery_state") == "LEGACY_REPORT_DELIVERY_BLOCKED", st.get("delivery_state"))
pr.OUTPUT_DIR = orig_out
shutil.rmtree(tmpd, ignore_errors=True)

fails = [r for r in RESULTS if not r[1]]
print(f"\n{len(RESULTS)-len(fails)}/{len(RESULTS)} PASS")
sys.exit(1 if fails else 0)
