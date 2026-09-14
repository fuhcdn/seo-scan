#!/usr/bin/env python3
"""evidence_v1_pipeline — durable job runner for NEW PAID orders (owner directive 2026-09-14).

Wires the 5-gate evidence_v1 engine (gates/evidence_report_runner + gate_pipeline)
into the durable job state machine:

  payment_received -> intake_validated -> research/quality (5 gates) ->
  quality_passed (only if overall PASS + independent scorecard >=90) ->
  prepare_verified_artifact (pypdf exact-artifact scan + immutable .for-email.pdf
  + 3-way SHA) -> send_verified_pdf (pre-send SHA recheck) -> email_sent.

Hard rules:
  - pipeline_version is pinned to "evidence_v1"; NEVER legacy. No fallback.
  - Email sent ONLY if every gate passes; auditor outage = DELIVERY_BLOCKED.
  - Never duplicates email (delivery marker + verified record gate re-send).
  - Never touches Stripe/charges. Safe recipient enforced: real sends require
    ALLOW_REAL_SEND=1 AND a non-test customer email; otherwise mock/no send.
  - Input research: for live orders the structured page research + evidence
    cards are loaded from the job's research files (output/<id>_gate1_pages.py /
    <id>_evidence_cards.json) produced by the research stage; fixture customers
    (appleimprints/brunnerlaw) use the approved Golden fixtures for E2E tests.
"""
import argparse
import hashlib
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
_GATES = os.path.join(os.path.dirname(_HERE), "gates")
sys.path.insert(0, _GATES)

import gate_pipeline as gp  # noqa: E402
import verified_pdf_delivery as vpd  # noqa: E402

OUTPUT_DIR = os.path.join(_HERE, "output")
TERMINAL_OK = "email_sent"
MOCK_DOMAIN_SUFFIX = ".invalid"


def job_path(job_id):
    return os.path.join(OUTPUT_DIR, f"order_{job_id}.json")


def save(job, **fields):
    job.update(fields)
    job["heartbeat"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(job_path(job["order_id"]), "w", encoding="utf-8") as fh:
        json.dump(job, fh, indent=1, ensure_ascii=False)
    return job


def load(job_id):
    return json.load(open(job_path(job_id), encoding="utf-8"))


def is_test_recipient(email):
    return email.lower().endswith(MOCK_DOMAIN_SUFFIX) or email.lower() in (
        "mock@safe-test.invalid",) or email == "owner-test@example.com"


def run_job(job_id, send_mode="auto"):
    job = load(job_id)
    if job.get("pipeline_version") != "evidence_v1":
        # immutable pin enforcement — never run a paid job on anything else
        return save(job, status="failed",
                    last_error="job not pinned to evidence_v1 — refusing to run")
    if job.get("status") == TERMINAL_OK:
        return job  # idempotent: already delivered, never duplicate email
    if job.get("delivery_marker"):
        return job  # already delivered previously

    customer_email = job.get("customer_email") or ""
    save(job, status="intake_validated")

    # ---- research inputs: fixture OR job-specific research files ----
    fixture = job.get("fixture_customer")  # E2E/test only
    if fixture:
        fx = os.path.join(_GATES, f"golden_evidence_cards_{fixture}.json")
        cards_file = json.load(open(fx, encoding="utf-8"))
        cards = cards_file["golden_evidence_cards"]
        customer = cards_file["customer"]
        journey = cards_file.get("customer_journey", [])
        pages_mod = os.path.join(_GATES, f"gate1_{fixture}_pages.py")
        import importlib.util
        sp = importlib.util.spec_from_file_location("g1p", pages_mod)
        g1m = importlib.util.module_from_spec(sp); sp.loader.exec_module(g1m)
        pages = g1m.structured_pages
    else:
        pages_py = job.get("gate1_pages_path")
        cards_json = job.get("evidence_cards_path")
        if not pages_py or not cards_json or not os.path.exists(pages_py) \
                or not os.path.exists(cards_json):
            # research not ready / unavailable -> durable block, retry policy owns it
            return save(job, status="research_blocked",
                        delivery_state="DELIVERY_BLOCKED",
                        last_error="evidence_v1 research inputs missing (no legacy fallback)")
        cards_file = json.load(open(cards_json, encoding="utf-8"))
        cards = cards_file.get("golden_evidence_cards") or cards_file.get("evidence_cards") or []
        customer = cards_file.get("customer") or {
            "company": job.get("company_name"), "primary_domain": job.get("url")}
        # CUSTOMER CONTEXT LOCK: bind goal/language/order from the durable job so no
        # report section renders from stale or foreign fixture context (EMPTY_GOAL_FIELD gate).
        if not (customer.get("business_goal") or "").strip():
            customer["business_goal"] = (job.get("primary_business_goal")
                                         or job.get("primary_business_goal_text")
                                         or "more " + (job.get("company_name") or "customer") + " enquiries")
        customer.setdefault("report_language", job.get("report_language") or "en")
        customer.setdefault("order_id", job.get("order_id"))
        journey = cards_file.get("customer_journey", [])
        import importlib.util
        sp = importlib.util.spec_from_file_location("g1p", pages_py)
        g1m = importlib.util.module_from_spec(sp); sp.loader.exec_module(g1m)
        pages = g1m.structured_pages

    save(job, status="research_started")

    # ---- GATE 1-4 (identical semantics to the golden 5-gate runner) ----
    g1 = gp.gate1_validate_structured_pages(pages)
    g2v = [gp.gate2_validate_evidence_card(c) for c in cards]
    valid_cards = [c for c, v in zip(cards, g2v) if v["valid"]]
    acts = gp.gate3_actions_from_evidence_cards(valid_cards, customer_context=customer)
    findings = [{"action_id": a["action_id"], "title": a["title"], "card": c,
                 "acceptance_criteria": a["acceptance_criteria"],
                 "business_mechanism": a["business_mechanism"], "audit_reason": ""}
                for a, c in zip(acts, valid_cards)]
    g4 = gp.gate4_semantic_audit(findings, acts)
    accepted = g4["accepted_findings"]

    # independent external semantic auditor MUST be available and review the
    # actual report draft (auditor outage = DELIVERY_BLOCKED, never pass-open)
    from evidence_report_runner import gate4_external_auditor, build_report
    ext_audit = gate4_external_auditor(accepted, valid_cards)
    ext_mode = ext_audit[0].get("mode") if ext_audit else "none"
    if ext_mode != "external":
        return save(job, status="quality_repairing",
                    delivery_state="DELIVERY_BLOCKED",
                    last_error=f"independent semantic auditor unavailable (mode={ext_mode})")
    for d in ext_audit[0].get("decisions", []):
        for f in accepted:
            if d.get("action_id") and d.get("action_id") == f.get("action_id"):
                f["audit_reason"] = d.get("reason", "")
    if not accepted:
        return save(job, status="insufficient_public_evidence",
                    delivery_state="DELIVERY_BLOCKED",
                    last_error="no finding survived the independent semantic audit")

    html_doc = build_report(customer, pages, accepted, acts,
                            {"accepted": accepted, "rejected": g4["rejected_findings"]},
                            cards=valid_cards, journey_rows_data=journey)

    # ---- deterministic roadmap/priority/contamination gates on rendered HTML ----
    import re as _re
    _rstart = html_doc.find("<h2>90-Day Execution Roadmap</h2>")
    _rend = html_doc.find("<h2>", _rstart + 5) if _rstart >= 0 else -1
    _rm_text = _re.sub(r"<[^>]+>", " ", html_doc[_rstart:(_rend if _rend > _rstart else _rstart + 8000)])
    rm_ok = gp.gate5_check_roadmap_status_consistency(_rm_text, acts)
    pc = gp.gate5_check_priority_consistency(acts)
    _full_html_text = _re.sub(r"<[^>]+>", " ", html_doc)
    blc = gp.gate5_check_business_logic_contamination(_full_html_text, acts, customer_context=customer)
    radc = gp.gate5_check_roadmap_action_data_consistency(_rm_text, acts)
    _blk = []
    if not rm_ok["consistent"] or not pc.get("consistent"):
        _blk.append("PRIORITY_CONSISTENCY_FAIL")
    if blc.get("contamination"):
        _blk.append("BUSINESS_LOGIC_CONTEXT_CONTAMINATION: " + "; ".join(blc["terms_found"]))
    if not radc.get("consistent"):
        _blk.append("ROADMAP_ACTION_DATA_MISMATCH")
    if _blk:
        return save(job, status="quality_repairing", delivery_state="DELIVERY_BLOCKED",
                    last_error=" | ".join(_blk))

    # ---- final PDF render ONCE ----
    save(job, status="pdf_rendering")
    domain = ((customer.get("primary_domain") or customer.get("domain") or "report")
              .lower().replace("www.", "").rstrip("/"))
    expected_domain = domain if not domain.startswith("www.") else domain[4:]
    from report_engine import html_to_pdf
    company_slug = _re.sub(r"[^A-Za-z0-9]+", "-",
                           (customer.get("company") or "Report").strip()).strip("-")
    stamp = time.strftime("%Y-%m-%d")
    out_dir = os.path.join(OUTPUT_DIR, "evidence_v1")
    os.makedirs(out_dir, exist_ok=True)
    html_path = os.path.join(out_dir, f"SEO-Opportunity-Diagnostic-{company_slug}-{stamp}-ev1.html")
    pdf_path = os.path.join(out_dir, f"SEO-Opportunity-Diagnostic-{company_slug}-{stamp}-ev1.pdf")
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(html_doc)
    if not html_to_pdf(html_path, pdf_path):
        return save(job, status="pdf_repairing", delivery_state="DELIVERY_BLOCKED",
                    last_error="pdf render failed")

    # ---- FINAL-ARTIFACT SCAN + INDEPENDENT SCORECARD (90+ hard requirement) ----
    scan = gp.gate5_scan_final_pdf(open(pdf_path, "rb").read())
    visible = gp.extract_visible_text_mature(open(pdf_path, "rb").read())
    from evidence_report_runner import evaluate_scorecard
    scorecard = evaluate_scorecard(scan, visible, acts, valid_cards, ext_audit,
                                   len(g4["rejected_findings"]), expected_domain)
    job["quality_scorecard"] = scorecard
    structural = scorecard["STRUCTURAL_COMPLETENESS_SCORE"]["value"]
    qual = scorecard["QUALITY_SCORE"]
    cats_ok = all(v["pct"] >= 90 for v in qual["categories"].values())
    qual_ok = qual["value"] >= 90 and cats_ok and structural == 100.0
    semantic_fails = scorecard.get("semantic_hard_fails") or []
    if not (scan["clean"] and not scan["hard_fails"] and qual_ok and not semantic_fails):
        fails = list(scan.get("hard_fails") or []) + list(semantic_fails)
        if not qual_ok:
            fails.append("SCORECARD: structural=%s quality=%s cats>=90=%s" % (
                structural, qual["value"], cats_ok))
        save(job, status="quality_repairing", delivery_state="DELIVERY_BLOCKED",
             hard_fails=fails)
        return job
    save(job, status="quality_passed", final_pdf=pdf_path)

    # ---- canonical verified artifact: pypdf exact scan + .for-email.pdf + 3-way SHA ----
    expected_domain = domain if not domain.startswith("www.") else domain[4:]
    rec = vpd.prepare_verified_artifact(
        pdf_path, job_id=job_id, pipeline_version="evidence_v1",
        report_language=job.get("report_language") or "en",
        expected_domain=expected_domain)
    job["verified_delivery"] = {k: v for k, v in rec.items() if k != "visible_text"}
    if rec["state"] != "VERIFIED_READY_TO_SEND":
        save(job, status="delivery_failed", delivery_state="DELIVERY_BLOCKED",
             last_error="canonical delivery: " + str(rec.get("reason")))
        return job

    # ---- send ONLY via canonical service; mock unless explicitly allowed real ----
    if send_mode == "mock" or is_test_recipient(customer_email) or \
            os.environ.get("ALLOW_REAL_SEND") != "1":
        def _send_fn(path, to, subject, frm):
            assert path.endswith(".for-email.pdf"), "mock sender got non-verified artifact"
            job["mock_email_record"] = {"to": to, "sha256": hashlib.sha256(
                open(path, "rb").read()).hexdigest(), "mock": True}
        send_fn = _send_fn
    else:
        backend = (os.environ.get("EMAIL_BACKEND", "") or "").strip().lower()
        if backend == "resend":
            import resend_send
            send_fn = resend_send.resend_send  # real send via Resend (production config)
        else:
            send_fn = vpd.default_smtp_send  # real SMTP send — evidence_v1 only
    srec = vpd.send_verified_pdf(
        job_id=job_id, final_pdf_path=pdf_path,
        expected_sha256=rec["rendered_sha256"], recipient_email=customer_email,
        report_language=job.get("report_language") or "en",
        pipeline_version="evidence_v1", expected_domain=expected_domain,
        send_fn=send_fn)
    job["email_delivery"] = {k: v for k, v in srec.items() if k != "visible_text"}
    if srec["state"] == "DELIVERED" or (send_mode == "mock" and srec.get("state") in
                                        ("VERIFIED_READY_TO_SEND", "DELIVERED")):
        save(job, status=TERMINAL_OK, delivery_state="email_sent",
             email_sha256=srec.get("emailed_sha256"),
             delivery_marker=job_path(job_id) + ".delivered")
        open(job["delivery_marker"], "w").write(json.dumps({"sha256": srec.get("emailed_sha256")}))
        return job
    save(job, status="delivery_failed", delivery_state="DELIVERY_BLOCKED",
         last_error="send blocked: " + str(srec.get("reason")))
    return job


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-id", required=True)
    ap.add_argument("--send-mode", default="auto", choices=["auto", "mock"])
    a = ap.parse_args()
    job = run_job(a.job_id, send_mode=a.send_mode)
    print(json.dumps({"order_id": job.get("order_id"), "status": job.get("status"),
                      "delivery_state": job.get("delivery_state"),
                      "pipeline_version": job.get("pipeline_version")}, indent=1))
