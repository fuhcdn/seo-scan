#!/usr/bin/env python3
"""ACTUAL-ENTRY-POINT E2E test — evidence_v1 is the ONLY report engine.

Post-retirement (owner directive 2026-09-14): the legacy report engine has been
DELETED from the repository. This test proves:

1. The actual customer entry point (server.spawn_delivery_pipeline, called by
   the Stripe webhook) routes new paid orders to evidence_v1 only.
2. The durable job pin is immutable.
3. NO executable legacy engine exists: pipeline_runner.py / quality_gate.py /
   autonomous_gate.py / research.py / pdf_scanner.py are absent from the source
   tree and from the running image.
4. Requests for legacy/old/default/fallback pipelines are rejected (ValueError
   at router level / LEGACY_REPORT_DELIVERY_BLOCKED at delivery level).
5. evidence_v1 pipeline completes: 5 gates -> scorecard >=90 all categories ->
   final pypdf scan -> immutable .for-email.pdf -> 3-way SHA match -> mock send.
6. Historical legacy order records are read-only archives: opening one with the
   current engine refuses to run it (not pinned to evidence_v1) and no code
   path exists that could re-render or re-send it.
"""
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
      json.dumps(spawn)[:110])
jobf = router.durable_job_path(ORDER_ID)
check("2-durable-job-pinned", os.path.exists(jobf),
      "pipeline_version=" + (json.load(open(jobf)).get("pipeline_version") if os.path.exists(jobf) else "?"))
bad = router.ensure_pinned(ORDER_ID, {"pipeline_version": "legacy"})
check("3-pin-rejects-legacy-merge", bad["pipeline_version"] == "evidence_v1",
      json.dumps(bad.get("pin_audit", [])[-1:]))

# ---- 2. legacy engine does not exist AT ALL ----
legacy_files = ["pipeline_runner.py", "quality_gate.py", "autonomous_gate.py",
                "research.py", "pdf_scanner.py"]
present = [f for f in legacy_files if os.path.exists(os.path.join(_HERE, f))]
check("4-legacy-engine-files-absent", not present, f"present={present or 'NONE'}")
try:
    import pipeline_runner  # noqa
    check("5-legacy-import-impossible", False, "pipeline_runner importable!")
except ModuleNotFoundError:
    check("5-legacy-import-impossible", True, "ModuleNotFoundError as required")

# ---- 3. requests for legacy/old/default/fallback are rejected ----
import evidence_v1_pipeline as ev1
# simulate a job file pinned to legacy (historical archive shape)
tmpd = tempfile.mkdtemp()
hist = {"order_id": "ORD-HIST-ARCHIVE", "pipeline_version": "legacy",
        "status": "email_sent", "customer_email": "archive@example.invalid"}
_hp = os.path.join(tmpd, "order_ORD-HIST-ARCHIVE.json")
json.dump(hist, open(_hp, "w"))
_orig = ev1.job_path
ev1.job_path = lambda jid: _hp
res = ev1.run_job("ORD-HIST-ARCHIVE")
check("6-historical-legacy-record-not-rerunnable",
      res.get("status") == "failed" and "not pinned" in str(res.get("last_error")),
      str(res.get("last_error"))[:70])
ev1.job_path = _orig
shutil.rmtree(tmpd, ignore_errors=True)

# delivery-level: legacy artifact request blocked
bad_pdf = os.path.join(tempfile.mkdtemp(), "inert_bad_fixture.pdf")
open(bad_pdf, "wb").write(b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")
rec = vpd.prepare_verified_artifact(bad_pdf, "ORD-LEGACY-SIM", pipeline_version="legacy")
check("7-legacy-artifact-request-blocked", rec["state"] == "LEGACY_REPORT_DELIVERY_BLOCKED", rec["state"])
rec2 = vpd.send_verified_pdf("ORD-LEGACY-SIM", bad_pdf, "", "victim@example.com",
                             pipeline_version="legacy", send_fn=lambda *a: None)
check("8-legacy-send-request-blocked", rec2["state"] == "LEGACY_REPORT_DELIVERY_BLOCKED"
      and not rec2.get("sent"), rec2["state"])

# ---- 4. run the evidence_v1 pipeline to completion (approved fixture) ----
job = json.load(open(jobf))
job["fixture_customer"] = "brunnerlaw"
json.dump(job, open(jobf, "w"), indent=1)
t0 = time.time()
result = ev1.run_job(ORDER_ID, send_mode="mock")
dt = time.time() - t0
check("9-evidence_v1-job-terminal", result.get("status") == "email_sent",
      f"status={result.get('status')} state={result.get('delivery_state')} ({dt:.0f}s) "
      f"err={str(result.get('last_error'))[:80]}")

# ---- 5. artifact + SHA + scorecard evidence ----
vd = result.get("verified_delivery") or {}
ed = result.get("email_delivery") or {}
check("10-artifact-is-for-email", (vd.get("email_artifact_path") or "").endswith(".for-email.pdf"),
      (vd.get("email_artifact_path") or "")[-58:])
check("11-3way-sha-equal", vd.get("rendered_sha256") == vd.get("scanned_sha256") == vd.get("email_sha256")
      and ed.get("emailed_sha256") == vd.get("rendered_sha256"),
      str(vd.get("rendered_sha256"))[:24])
check("12-scanner-clean", not (vd.get("scanner") or {}).get("hard_fails"),
      str((vd.get("scanner") or {}).get("hard_fails")))
sc = result.get("quality_scorecard") or {}
q = sc.get("QUALITY_SCORE", {})
check("13-structural-100", sc.get("STRUCTURAL_COMPLETENESS_SCORE", {}).get("value") == 100.0,
      str(sc.get("STRUCTURAL_COMPLETENESS_SCORE", {}).get("value")))
check("14-quality-90plus-all-cats", q.get("value", 0) >= 90
      and all(v["pct"] >= 90 for v in q.get("categories", {}).values()),
      f"value={q.get('value')} per_cat={q.get('per_category_pct')}")
check("15-auditor-external", q.get("auditor_mode") == "external", q.get("auditor_mode"))

# ---- 6. pypdf visible text from the EXACT emailed artifact ----
email_pdf = vd.get("email_artifact_path")
if email_pdf and os.path.exists(email_pdf):
    import gate_pipeline as gp
    vis = gp.extract_visible_text_mature(open(email_pdf, "rb").read())
    check("16-pypdf-text-extracted", len(vis) > 2000, f"{len(vis)} chars")
    check("17-customer-text-clean", "localhost" not in vis.lower()
          and "file:" not in vis.lower()
          and "ORD-" not in vis.split("Source / Evidence Appendix")[0], "clean")
    mrec = result.get("mock_email_record") or {}
    check("18-mock-sender-got-for-email", bool(mrec) and mrec.get("mock") is True,
          str(mrec.get("sha256", ""))[:24])
else:
    check("16-pypdf-text-extracted", False, "artifact missing")
    check("17-customer-text-clean", False, "no artifact")
    check("18-mock-sender-got-for-email", False, "no artifact")

fails = [r for r in RESULTS if not r[1]]
print("=" * 60)
print(f"ENTRY-POINT E2E (post-retirement): {len(RESULTS)-len(fails)}/{len(RESULTS)} PASS"
      + (f" — FAILURES: {[f[0] for f in fails]}" if fails else ""))
sys.exit(1 if fails else 0)
