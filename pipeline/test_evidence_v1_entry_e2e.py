#!/usr/bin/env python3
"""ACTUAL-ENTRY-POINT E2E test — evidence_v1 routing for new paid orders.

Proves the REAL customer path: server.spawn_delivery_pipeline(order) — the exact
function the Stripe webhook calls — routes to evidence_v1 (durable pinned job),
runs the 5-gate engine + independent semantic audit + scorecard 90+ + final
pypdf scan + immutable .for-email.pdf + 3-way SHA + mock send. NO live charge,
NO refund, NO real customer email (safe .invalid recipient / mock sender).

Also proves: (a) legacy fixture (Persimmon-style generic SERP report) is
BLOCKED; (b) evidence_v1 pipeline pinning is immutable; (c) legacy runner
hard-fails on a paid order.
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "gates"))
os.chdir(_HERE)

RESULTS = []
def check(name, cond, info=""):
    RESULTS.append((name, bool(cond), info))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}: {info}")

import server  # the ACTUAL production server module
import evidence_v1_router as router
import verified_pdf_delivery as vpd

ORDER_ID = f"E2E-ENTRY-{int(time.time())}"
SAFE_EMAIL = "mock@safe-test.invalid"
OUT = os.path.join(_HERE, "output")
os.makedirs(OUT, exist_ok=True)

# ---- 1. the ACTUAL entry point routes to evidence_v1 ----
order = {"order_id": ORDER_ID, "url": "https://thebrunnerlawfirm.com",
         "payment_ref": "cs_test_mock_entry_1", "customer_email": SAFE_EMAIL,
         "selected_product_id": "prod_seo_opportunity", "report_language": "en"}
spawn = server.spawn_delivery_pipeline(order)
check("1-entry-point-pins-evidence_v1",
      spawn.get("spawned") and spawn.get("pipeline_version") == "evidence_v1",
      json.dumps(spawn)[:120])
jobf = router.durable_job_path(ORDER_ID)
check("2-durable-job-pinned", os.path.exists(jobf),
      "pipeline_version=" + (json.load(open(jobf)).get("pipeline_version") if os.path.exists(jobf) else "?"))
check("3-pin-immutable-in-router", router.PIPELINE_VERSION == "evidence_v1"
      and router.ensure_pinned(ORDER_ID, {})["pipeline_version"] == "evidence_v1",
      "ensure_pinned always stamps evidence_v1")

# try to de-pin via ensure_pinned merge (attack simulation)
bad = router.ensure_pinned(ORDER_ID, {"pipeline_version": "legacy"})
check("4-pin-rejects-legacy-merge", bad["pipeline_version"] == "evidence_v1",
      json.dumps(bad.get("pin_audit", [])[-1:]))

# ---- 2. legacy runner cannot process a paid order ----
import pipeline_runner as pr
legacy_order = dict(order, order_id=ORDER_ID + "-LEGACY")
import json as _json
_tmp = tempfile.mkdtemp()
_orig_out = pr.OUTPUT_DIR
pr.OUTPUT_DIR = _tmp
_sp = os.path.join(_tmp, f"order_{legacy_order['order_id']}.json")
_json.dump({"order_id": legacy_order["order_id"], "status": "running",
            "steps": {"order_received": {"state": "done"}, "payment_verified": {"state": "done"},
                      "crawl": {"state": "done"}, "score": {"state": "done"},
                      "research": {"state": "done"}, "report": {"state": "done"}},
            "report_pdf": None, "score": 80}, open(_sp, "w"))
pr.per_order_status_path = lambda oid: _sp
try:
    pr.run_pipeline(legacy_order)
    check("5-legacy-paid-order-blocked", False, "no exception")
except RuntimeError as e:
    check("5-legacy-paid-order-blocked", "LEGACY_REPORT_DELIVERY_BLOCKED" in str(e), str(e)[:70])
pr.OUTPUT_DIR = _orig_out
shutil.rmtree(_tmp, ignore_errors=True)

# ---- 3. run the evidence_v1 pipeline to completion (fixture customer = Brunner) ----
import evidence_v1_pipeline as ev1
job = _json.load(open(jobf))
job["fixture_customer"] = "brunnerlaw"   # approved Golden B fixture (E2E only)
job["evidence_v1_retry_count"] = 0
_json.dump(job, open(jobf, "w"), indent=1)
t0 = time.time()
result = ev1.run_job(ORDER_ID, send_mode="mock")
dt = time.time() - t0
check("6-evidence_v1-job-terminal", result.get("status") == "email_sent",
      f"status={result.get('status')} state={result.get('delivery_state')} ({dt:.0f}s) "
      f"err={str(result.get('last_error'))[:80]}")
check("7-legacy-never-invoked", result.get("pipeline_version") == "evidence_v1"
      and "legacy" not in json.dumps(result.get("engine", "")).lower(),
      result.get("pipeline_version"))

# ---- 4. artifact + SHA evidence ----
vd = result.get("verified_delivery") or {}
ed = result.get("email_delivery") or {}
check("8-artifact-is-for-email", (vd.get("email_artifact_path") or "").endswith(".for-email.pdf"),
      vd.get("email_artifact_path", "")[-60:])
check("9-3way-sha-equal", vd.get("rendered_sha256") == vd.get("scanned_sha256") == vd.get("email_sha256")
      and ed.get("emailed_sha256") == vd.get("rendered_sha256"),
      str(vd.get("rendered_sha256"))[:24])
check("10-scanner-clean", not (vd.get("scanner") or {}).get("hard_fails"),
      str((vd.get("scanner") or {}).get("hard_fails")))

# ---- 5. scorecard 90+ ----
sc = result.get("quality_scorecard") or {}
q = sc.get("QUALITY_SCORE", {})
check("11-structural-100", sc.get("STRUCTURAL_COMPLETENESS_SCORE", {}).get("value") == 100.0,
      str(sc.get("STRUCTURAL_COMPLETENESS_SCORE", {}).get("value")))
check("12-quality-90plus", q.get("value", 0) >= 90,
      f"value={q.get('value')} per_cat={q.get('per_category_pct')}")
check("13-auditor-external", q.get("auditor_mode") == "external", q.get("auditor_mode"))

# ---- 6. pypdf visible text from the EXACT emailed artifact ----
email_pdf = vd.get("email_artifact_path")
if email_pdf and os.path.exists(email_pdf):
    import gate_pipeline as gp
    vis = gp.extract_visible_text_mature(open(email_pdf, "rb").read())
    check("14-pypdf-text-extracted", len(vis) > 2000, f"{len(vis)} chars")
    check("15-no-internal-id-in-artifact", "ORD-" not in vis.split("Source / Evidence Appendix")[0]
          and "localhost" not in vis.lower() and "file:" not in vis.lower(), "clean")
    # persist evidence artifacts for the report
    ev_dir = os.path.join(_HERE, "output", "evidence_v1")
    _json.dump({"visible_text": vis[:12000], "sha256": vd.get("rendered_sha256")},
               open(os.path.join(OUT, f"{ORDER_ID}_pypdf_extract.json"), "w"), indent=1)
else:
    check("14-pypdf-text-extracted", False, "artifact missing")

# ---- 7. mock sender received ONLY .for-email.pdf ----
mrec = result.get("mock_email_record") or {}
check("16-mock-sender-got-for-email", bool(mrec) and mrec.get("mock") is True,
      str(mrec.get("sha256", ""))[:24])

# ---- 8. legacy-style BAD PDF blocked (Persimmon regression fixture) ----
bad_pdf = os.path.join(tempfile.mkdtemp(), "persimmon_legacy.pdf")
open(bad_pdf, "wb").write(b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")
rec = vpd.prepare_verified_artifact(bad_pdf, "ORD-LEGACY-SIM", pipeline_version="legacy")
check("17-legacy-artifact-blocked", rec["state"] == "LEGACY_REPORT_DELIVERY_BLOCKED", rec["state"])
rec2 = vpd.send_verified_pdf("ORD-LEGACY-SIM", bad_pdf, "", "victim@example.com",
                             pipeline_version="legacy", send_fn=lambda *a: None)
check("18-legacy-send-blocked", rec2["state"] == "LEGACY_REPORT_DELIVERY_BLOCKED"
      and not rec2.get("sent"), rec2["state"])

fails = [r for r in RESULTS if not r[1]]
print("=" * 60)
print(f"ENTRY-POINT E2E: {len(RESULTS)-len(fails)}/{len(RESULTS)} PASS"
      + (f" — FAILURES: {[f[0] for f in fails]}" if fails else ""))
sys.exit(1 if fails else 0)
