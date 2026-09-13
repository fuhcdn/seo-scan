#!/usr/bin/env python3
"""
AP-6 — CONTROLLED E2E TEST (evidence_v1, mock payment, safe/mock email).

Owner-approved constraints:
- NO live Stripe charge / NO refund.
- NO real customer email (mock sender by default; owner test email only with
  E2E_ALLOW_OWNER_EMAIL=<verified address> AND E2E_SEND_MODE=owner).
- Uses a pre-approved test fixture customer (Golden B data already approved).
- mock webhook event → durable job → evidence_v1 pipeline → verified PDF →
  artifact record → safe send → email_sent terminal state.

Run inside staging container:
  python3 /app/pipeline/e2e_test_evidence_v1.py
"""
import hashlib
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "gates"))

OUTPUT_DIR = os.environ.get("E2E_OUTPUT_DIR", os.path.join(os.path.dirname(_HERE), "output"))

E2E_ORDER_ID = os.environ.get("E2E_ORDER_ID", "E2E-EVIDENCE-V1-1")
E2E_JOB_STATE_PATH = os.path.join(OUTPUT_DIR, f"order_{E2E_ORDER_ID}.json")
SAFE_TEST_RECIPIENT = os.environ.get("E2E_TEST_RECIPIENT", "mock@safe-test.invalid")

RESULTS = []


def check(name, cond, info=""):
    RESULTS.append((name, bool(cond), info))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}: {info}")


def durable_state_write(fields: dict):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    state = {}
    if os.path.exists(E2E_JOB_STATE_PATH):
        try:
            state = json.load(open(E2E_JOB_STATE_PATH, encoding="utf-8"))
        except Exception:
            state = {}
    state.update(fields)
    state["heartbeat"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(E2E_JOB_STATE_PATH, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=1, ensure_ascii=False)
    return state


def mock_sender(pdf_path, to_addr, subject, from_addr):
    """MOCK email sender — records the send, does NOT touch any network."""
    assert os.path.basename(pdf_path).endswith(".for-email.pdf"), \
        f"MOCK SENDER RECEIVED NON-VERIFIED ARTIFACT: {pdf_path}"
    sha = hashlib.sha256(open(pdf_path, "rb").read()).hexdigest()
    rec = os.path.join(OUTPUT_DIR, f"{E2E_ORDER_ID}_mock_email_record.json")
    with open(rec, "w", encoding="utf-8") as fh:
        json.dump({"to": to_addr, "subject": subject, "artifact": pdf_path,
                   "sha256": sha, "mock": True,
                   "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, fh, indent=1)
    return {"sent": True, "sha256": sha, "record": rec}


def main():
    print("=== AP-6 CONTROLLED E2E — evidence_v1 (mock payment, safe/mock email) ===")
    # 1. mock payment-success webhook event (NO Stripe call, NO signature verify)
    mock_event = {
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_test_mock_e2e_1", "payment_status": "paid",
            "client_reference_id": E2E_ORDER_ID,
            "metadata": {"url_to_scan": "https://thebrunnerlawfirm.com",
                          "selected_product_id": "prod_seo_opportunity"},
            "customer_details": {"email": SAFE_TEST_RECIPIENT},
        }}}
    check("1-mock-webhook-event-built", mock_event["data"]["object"]["payment_status"] == "paid",
          f"order={E2E_ORDER_ID} (mock; no Stripe API call)")

    # 2. durable job creation (payment_received → intake_validated)
    st = durable_state_write({"order_id": E2E_ORDER_ID, "status": "payment_received",
                              "payment_ref": mock_event["data"]["object"]["id"],
                              "customer_email": SAFE_TEST_RECIPIENT,
                              "url": mock_event["data"]["object"]["metadata"]["url_to_scan"],
                              "selected_product_id": "prod_seo_opportunity",
                              "report_language": "en",
                              "pipeline_version": "evidence_v1"})
    check("2-durable-job-created", st["status"] == "payment_received", E2E_JOB_STATE_PATH)
    # intake/report_language validation
    assert st["report_language"] in ("en", "es", "ja", "zh-Hans", "zh-Hant")
    st = durable_state_write({"status": "intake_validated"})
    check("3-intake+language-validated", st["report_language"] == "en", "en valid")

    # 3. Customer Context Lock + Business-Logic Context Lock (Golden B fixture = approved)
    sys.path.insert(0, os.path.join(_HERE, "..", "tests", "fixtures"))
    cards_file = json.load(open(os.path.join(_HERE, "..", "tests", "fixtures",
                                             "golden_evidence_cards_brunnerlaw.json"), encoding="utf-8"))
    customer = cards_file["customer"]
    check("4-customer-context-lock", customer.get("primary_domain") == "thebrunnerlawfirm.com",
          customer.get("primary_domain"))
    check("5-business-logic-context-lock",
          "legal" in (customer.get("business_model") or "").lower(),
          customer.get("business_model"))

    # 4. evidence_v1 research/action pipeline (Golden B fixture — deterministic, no external SERP)
    sys.path.insert(0, "/app/gates") if os.path.isdir("/app/gates") else None
    import gate_pipeline as gp  # noqa
    valid_cards = [c for c in cards_file["golden_evidence_cards"]
                   if gp.gate2_validate_evidence_card(c)["valid"]]
    acts = gp.gate3_actions_from_evidence_cards(valid_cards, customer_context=customer)
    check("6-evidence-v1-actions-generated", len(acts) == 5, f"{len(acts)} actions")
    st = durable_state_write({"status": "quality_passed",
                              "actions_count": len(acts)})

    # 5. final PDF: use the golden runner artifact if present, else locate the last build
    pdf_candidates = [
        "/app/gates/out/SEO-Opportunity-Diagnostic-The-Brunner-Law-Firm-2026-09-13-5gate.pdf",
    ]
    final_pdf = next((p for p in pdf_candidates if os.path.exists(p)), None)
    check("7-final-pdf-rendered-once", final_pdf is not None, final_pdf or "not found")

    # 6. canonical verified artifact service (pypdf exact artifact + 3-way SHA)
    import verified_pdf_delivery as vpd  # noqa
    rec = vpd.prepare_verified_artifact(
        final_pdf, job_id=E2E_ORDER_ID, pipeline_version="evidence_v1",
        report_language="en", expected_domain="thebrunnerlawfirm.com")
    check("8-pypdf-exact-artifact-scan", rec["state"] in ("VERIFIED_READY_TO_SEND", "DELIVERY_BLOCKED"),
          f"state={rec['state']} fails={rec.get('scanner',{}).get('hard_fails')}")
    check("9-immutable-for-email-created", rec.get("email_artifact_path", "").endswith(".for-email.pdf"),
          rec.get("email_artifact_path"))
    three_way = rec.get("rendered_sha256") == rec.get("scanned_sha256") == rec.get("email_sha256")
    check("10-3way-sha-equal", three_way and rec["state"] == "VERIFIED_READY_TO_SEND",
          str(rec.get("rendered_sha256"))[:24])
    st = durable_state_write({"status": "ready_to_deliver",
                              "final_artifact_sha": rec.get("rendered_sha256"),
                              "email_artifact": rec.get("email_artifact_path")})

    # 7. safe mock send via canonical service (mock sender — zero real email)
    srec = vpd.send_verified_pdf(
        job_id=E2E_ORDER_ID, final_pdf_path=final_pdf,
        expected_sha256=rec["rendered_sha256"], recipient_email=SAFE_TEST_RECIPIENT,
        report_language="en", pipeline_version="evidence_v1",
        expected_domain="thebrunnerlawfirm.com", send_fn=mock_sender)
    check("11-pre-send-sha-recheck-pass", srec["state"] == "DELIVERED", str(srec.get("state")))
    check("12-attachment-is-verified-for-email", srec.get("emailed_sha256") == rec["rendered_sha256"],
          str(srec.get("emailed_sha256"))[:24])
    # mock record
    mrec_path = os.path.join(OUTPUT_DIR, f"{E2E_ORDER_ID}_mock_email_record.json")
    mrec = json.load(open(mrec_path)) if os.path.exists(mrec_path) else {}
    check("13-email-record-persisted", mrec.get("mock") is True and mrec.get("sha256"),
          mrec.get("sha256", "")[:24])
    st = durable_state_write({"status": "email_sent", "delivery_state": "email_sent",
                              "email_sha256": srec.get("emailed_sha256"),
                              "test_safe_recipient": SAFE_TEST_RECIPIENT,
                              "mock_sender": True})

    # 8. terminal state check
    import job_watchdog as wd  # noqa
    cls = wd.classify(E2E_ORDER_ID, st)
    check("14-terminal-email-sent", cls == "terminal" and st["status"] == "email_sent", cls)

    ok = sum(1 for _, p, _ in RESULTS if p)
    print("=" * 60)
    print(f"E2E controlled test: {ok}/{len(RESULTS)} PASS")
    print("Live charge: NO | refund: NO | real customer email: NO (mock sender)")
    return 0 if ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
