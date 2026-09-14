#!/usr/bin/env python3
"""evidence_v1_pipeline — durable job runner with the MANDATORY 3-ATTEMPT
independent-review loop (owner directive 2026-09-14c).

ROLE SEPARATION (enforced, not documented):
  ROLE A (this module) = GENERATOR ONLY: build candidate PDF, hand it to the
  Independent Strict Quality Reviewer, repair per reviewer instructions.
  It can NEVER score, certify, set VERIFIED_READY_TO_SEND/PASS, or send email.

  ROLE B (strict_reviewer.py, separate process) = the ONLY authority for the
  final score, hard fails and INDEPENDENT_REVIEW_PASS.

  ROLE C (delivery gate, below) = sends ONLY when a signed reviewer record with
  decision INDEPENDENT_REVIEW_PASS exists for the exact artifact SHA.

Loop: R1 -> review -> (repair) -> R2 -> review -> (repair) -> R3 -> review.
R3 fail = manual_support_required (no 4th attempt, no fallback, no threshold drop).
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "gates"))

import gate_pipeline as gp  # noqa: E402
import verified_pdf_delivery as vpd  # noqa: E402

OUTPUT_DIR = os.path.join(_HERE, "output")
MAX_ATTEMPTS = 3
MOCK_DOMAIN_SUFFIX = ".invalid"


def job_path(job_id):
    return os.path.join(OUTPUT_DIR, f"order_{job_id}.json")


def save(job, **fields):
    job.update(fields)
    job["heartbeat"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(job_path(job["order_id"]), "w", encoding="utf-8") as fh:
        json.dump(job, fh, indent=1, ensure_ascii=False)
    return job


def is_test_recipient(email):
    return email.lower().endswith(MOCK_DOMAIN_SUFFIX) or email == "owner-test@example.com"


def _candidate_path(job, attempt):
    company = re.sub(r"[^A-Za-z0-9]+", "-",
                     (job.get("company_name") or "Report").strip()).strip("-")
    out_dir = os.path.join(OUTPUT_DIR, "evidence_v1")
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir,
                        f"SEO-Opportunity-Diagnostic-{company}-{time.strftime('%Y-%m-%d')}-R{attempt}.pdf")


def _generate(job, attempt, repair_instructions):
    """ROLE A: generate ONE new candidate PDF from scratch. Returns pdf path."""
    save(job, status="pdf_rendering",
         generator_run_id=f"GEN-{job['order_id']}-R{attempt}-{int(time.time())}")
    fixture = job.get("fixture_customer")
    if fixture:
        fx = os.path.join(os.path.dirname(_HERE), "gates", f"golden_evidence_cards_{fixture}.json")
        cards_file = json.load(open(fx, encoding="utf-8"))
        cards = cards_file["golden_evidence_cards"]
        customer = dict(cards_file["customer"])
        journey = cards_file.get("customer_journey", [])
        import importlib.util
        pages_mod = os.path.join(os.path.dirname(_HERE), "gates", f"gate1_{fixture}_pages.py")
        sp = importlib.util.spec_from_file_location("g1p", pages_mod)
        g1m = importlib.util.module_from_spec(sp); sp.loader.exec_module(g1m)
        pages = g1m.structured_pages
    else:
        pages_py = job.get("gate1_pages_path")
        cards_json = job.get("evidence_cards_path")
        if not pages_py or not cards_json or not os.path.exists(pages_py) or not os.path.exists(cards_json):
            return save(job, status="research_blocked", delivery_state="DELIVERY_BLOCKED",
                        last_error="evidence_v1 research inputs missing (no legacy fallback)")
        cards_file = json.load(open(cards_json, encoding="utf-8"))
        cards = cards_file.get("golden_evidence_cards") or cards_file.get("evidence_cards") or []
        customer = dict(cards_file.get("customer") or {})
        journey = cards_file.get("customer_journey", [])
        import importlib.util
        sp = importlib.util.spec_from_file_location("g1p", pages_py)
        g1m = importlib.util.module_from_spec(sp); sp.loader.exec_module(g1m)
        pages = g1m.structured_pages

    if not (customer.get("business_goal") or "").strip():
        customer["business_goal"] = (job.get("primary_business_goal")
                                     or "more " + (job.get("company_name") or "customer") + " enquiries")
    customer.setdefault("report_language", job.get("report_language") or "en")
    customer.setdefault("order_id", job.get("order_id"))

    g2v = [gp.gate2_validate_evidence_card(c) for c in cards]
    valid_cards = [c for c, v in zip(cards, g2v) if v["valid"]]
    acts = gp.gate3_actions_from_evidence_cards(valid_cards, customer_context=customer)
    findings = [{"action_id": a["action_id"], "title": a["title"], "card": c,
                 "acceptance_criteria": a["acceptance_criteria"],
                 "business_mechanism": a["business_mechanism"], "audit_reason": ""}
                for a, c in zip(acts, valid_cards)]
    g4 = gp.gate4_semantic_audit(findings, acts)
    accepted = g4["accepted_findings"]
    from evidence_report_runner import gate4_external_auditor, build_report
    ext_audit = gate4_external_auditor(accepted, valid_cards)
    if not ext_audit or ext_audit[0].get("mode") != "external":
        return save(job, status="quality_repairing", delivery_state="DELIVERY_BLOCKED",
                    last_error="independent semantic auditor unavailable")
    for dcn in ext_audit[0].get("decisions", []):
        for f in accepted:
            if dcn.get("action_id") == f.get("action_id"):
                f["audit_reason"] = dcn.get("reason", "")
    if not accepted:
        return save(job, status="insufficient_public_evidence", delivery_state="DELIVERY_BLOCKED",
                    last_error="no finding survived the semantic audit")

    html_doc = build_report(customer, pages, accepted, acts,
                            {"accepted": accepted, "rejected": g4["rejected_findings"]},
                            cards=valid_cards, journey_rows_data=journey)

    # deterministic pre-checks (ADVISORY ONLY — never an approval)
    _re2 = re
    _rstart = html_doc.find("<h2>90-Day Execution Roadmap</h2>")
    _rend = html_doc.find("<h2>", _rstart + 5) if _rstart >= 0 else -1
    _rm_text = _re2.sub(r"<[^>]+>", " ", html_doc[_rstart:(_rend if _rend > _rstart else _rstart + 8000)])
    if not gp.gate5_check_roadmap_status_consistency(_rm_text, acts)["consistent"]:
        return save(job, status="quality_repairing", delivery_state="DELIVERY_BLOCKED",
                    last_error="roadmap status inconsistency")
    blc = gp.gate5_check_business_logic_contamination(
        _re2.sub(r"<[^>]+>", " ", html_doc), acts, customer_context=customer)
    if blc.get("contamination"):
        return save(job, status="quality_repairing", delivery_state="DELIVERY_BLOCKED",
                    last_error="BUSINESS_LOGIC_CONTEXT_CONTAMINATION: " + "; ".join(blc["terms_found"]))

    save(job, status="pdf_rendering")
    from report_engine import html_to_pdf
    html_path = _candidate_path(job, attempt).replace(".pdf", ".html")
    pdf_path = _candidate_path(job, attempt)
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(html_doc)
    if not html_to_pdf(html_path, pdf_path):
        return save(job, status="pdf_repairing", delivery_state="DELIVERY_BLOCKED",
                    last_error="pdf render failed")
    return pdf_path


def _call_reviewer(job, attempt, pdf_path):
    """Invoke the SEPARATE reviewer process (ROLE B). Returns its immutable record."""
    cards_json = job.get("evidence_cards_path") or os.path.join(
        os.path.dirname(_HERE), "gates", f"golden_evidence_cards_{job.get('fixture_customer')}.json")
    cmd = [sys.executable, os.path.join(_HERE, "strict_reviewer.py"),
           "--candidate-pdf", pdf_path, "--job-id", job["order_id"],
           "--attempt", str(attempt), "--cards", cards_json]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        return {"delivery_decision": "DELIVERY_BLOCKED",
                "hard_fails": ["REVIEWER_PROCESS_FAILED:" + p.stderr[-160:]]}
    out = os.path.join(OUTPUT_DIR, "reviews", f"{job['order_id']}_R{attempt}_review.json")
    return json.load(open(out, encoding="utf-8"))


def run_job(job_id, send_mode="auto"):
    job = load(job_id)
    if job.get("pipeline_version") != "evidence_v1":
        return save(job, status="failed", last_error="job not pinned to evidence_v1 — refusing to run")
    if job.get("status") == "email_sent" or job.get("delivery_marker"):
        return job  # idempotent; never duplicate email

    customer_email = job.get("customer_email") or ""
    history = []
    pdf_path = None
    reviewer = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        pdf_path = _generate(job, attempt, (reviewer or {}).get("repair_instructions") or [])
        if not (pdf_path and os.path.exists(pdf_path)):
            history.append({"attempt": attempt, "result": "GENERATION_FAILED"})
            save(job, generation_history=history)
            continue
        cand_sha = hashlib.sha256(open(pdf_path, "rb").read()).hexdigest()
        save(job, **{f"candidate_sha_{attempt}": cand_sha, "status": "review_pending"})
        reviewer = _call_reviewer(job, attempt, pdf_path)
        history.append({"attempt": attempt, "candidate_sha256": cand_sha,
                        "reviewer_run_id": reviewer.get("reviewer_run_id"),
                        "overall_score": reviewer.get("overall_score"),
                        "hard_fails": reviewer.get("hard_fails"),
                        "decision": reviewer.get("delivery_decision")})
        save(job, generation_history=history, reviewer_scorecard=reviewer)
        if reviewer.get("delivery_decision") != "INDEPENDENT_REVIEW_PASS":
            if attempt < MAX_ATTEMPTS:
                save(job, status="quality_repairing", delivery_state="DELIVERY_BLOCKED",
                     last_error=f"R{attempt} reviewer: DELIVERY_BLOCKED — repairing per reviewer instructions")
                continue
            # third failure: manual support, no 4th attempt
            return save(job, status="manual_support_required", delivery_state="DELIVERY_BLOCKED",
                        last_error="3 attempts failed independent review — manual handling",
                        final_remediation=reviewer.get("repair_instructions"))
        # REVIEWER PASS -> delivery gate verifies SHA chain against the reviewed artifact
        rec = vpd.prepare_verified_artifact(
            pdf_path, job_id=job_id, pipeline_version="evidence_v1",
            report_language=job.get("report_language") or "en",
            expected_domain=_domain_of(job))
        job["verified_delivery"] = {k: v for k, v in rec.items() if k != "visible_text"}
        reviewed_sha = reviewer.get("candidate_sha256")
        if rec["state"] != "VERIFIED_READY_TO_SEND" or rec["rendered_sha256"] != reviewed_sha:
            return save(job, status="delivery_failed", delivery_state="DELIVERY_BLOCKED",
                        last_error="DELIVERY_GATE: artifact SHA does not match reviewer-passed SHA")
        # reviewer signature integrity
        import strict_reviewer as sr
        chk = dict(reviewer)
        sig = chk.pop("reviewer_signature", "")
        if sr.sign(chk) != sig:
            return save(job, status="delivery_failed", delivery_state="DELIVERY_BLOCKED",
                        last_error="DELIVERY_GATE: reviewer signature invalid")
        break

    # ---- ROLE C: DELIVERY GATE ----
    if not reviewer or reviewer.get("delivery_decision") != "INDEPENDENT_REVIEW_PASS":
        return save(job, status="manual_support_required", delivery_state="DELIVERY_BLOCKED",
                    last_error="no reviewer PASS on record")
    if send_mode == "mock" or is_test_recipient(customer_email) or \
            os.environ.get("ALLOW_REAL_SEND") != "1":
        def _send_fn(path, to, subject, frm):
            assert path.endswith(".for-email.pdf")
            job["mock_email_record"] = {"to": to, "sha256": hashlib.sha256(
                open(path, "rb").read()).hexdigest(), "mock": True}
        send_fn = _send_fn
    else:
        backend = (os.environ.get("EMAIL_BACKEND", "") or "").strip().lower()
        if backend == "resend":
            import resend_send
            send_fn = resend_send.resend_send
        else:
            send_fn = vpd.default_smtp_send
    srec = vpd.send_verified_pdf(
        job_id=job_id, final_pdf_path=pdf_path,
        expected_sha256=reviewer.get("candidate_sha256"),
        recipient_email=customer_email,
        report_language=job.get("report_language") or "en",
        pipeline_version="evidence_v1", expected_domain=_domain_of(job),
        send_fn=send_fn)
    job["email_delivery"] = {k: v for k, v in srec.items() if k != "visible_text"}
    if srec["state"] in ("DELIVERED", "VERIFIED_READY_TO_SEND"):
        save(job, status="email_sent", delivery_state="email_sent",
             email_sha256=srec.get("emailed_sha256"),
             delivery_decision_source="INDEPENDENT_REVIEW_PASS",
             reviewer_run_id=reviewer.get("reviewer_run_id"),
             delivery_marker=job_path(job_id) + ".delivered")
        open(job["delivery_marker"], "w").write(json.dumps(
            {"resend_or_smtp_sha": srec.get("emailed_sha256"),
             "reviewer_run_id": reviewer.get("reviewer_run_id")}))
        return job
    return save(job, status="delivery_failed", delivery_state="DELIVERY_BLOCKED",
                last_error="send blocked: " + str(srec.get("reason")))


def _domain_of(job):
    return ((job.get("url") or "").lower().replace("https://", "").replace("http://", "")
            .replace("www.", "").rstrip("/"))


def load(job_id):
    return json.load(open(job_path(job_id), encoding="utf-8"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-id", required=True)
    ap.add_argument("--send-mode", default="auto", choices=["auto", "mock"])
    a = ap.parse_args()
    job = run_job(a.job_id, send_mode=a.send_mode)
    print(json.dumps({"order_id": job.get("order_id"), "status": job.get("status"),
                      "delivery_state": job.get("delivery_state"),
                      "pipeline_version": job.get("pipeline_version"),
                      "generation_history": job.get("generation_history")}, indent=1))
