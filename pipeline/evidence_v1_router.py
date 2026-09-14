#!/usr/bin/env python3
"""evidence_v1 job router — the ONLY delivery path for new paid customer orders.

Owner directive (2026-09-14, HIGHEST PRIORITY):
  Every new paid order must be handled by the evidence_v1 report engine.
  Legacy report output must NEVER create a customer email artifact.

Design:
  - spawn_evidence_v1_job(order): called by server.py webhook in place of the
    legacy spawn. Creates/updates a DURABLE job file output/order_<id>.json
    pinned (immutably) to pipeline_version="evidence_v1", then runs
    evidence_v1_pipeline.run_job() in a detached subprocess.
  - Pinning is enforced on read: if a durable job file exists without
    pipeline_version="evidence_v1" and has a payment_ref (a real paid order),
    ensure_pinned() stamps it — the legacy runner's fail-closed gate
    (verified_pdf_delivery.enforce_pipeline_gate) independently blocks any
    non-evidence_v1 delivery, so even a stale/legacy job file can never email.
  - No fallback to legacy. Ever. On evidence_v1 failure the job stays durable
    (payment recorded), safe/idempotent stages may retry via job_watchdog
    reconcile, and after the retry policy it becomes manual_support_required.
    The customer never receives a legacy/generic PDF.
"""
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

OUTPUT_DIR = os.path.join(_HERE, "output")
PIPELINE_VERSION = "evidence_v1"   # the ONLY permitted value for new paid jobs


def durable_job_path(order_id: str) -> str:
    return os.path.join(OUTPUT_DIR, f"order_{order_id}.json")


def ensure_pinned(order_id: str, order: dict) -> dict:
    """Create or load the durable job file and pin pipeline_version=evidence_v1.

    Returns the durable job state dict. The pin is immutable: any attempt to
    change pipeline_version away from evidence_v1 is rejected/overwritten and
    logged into job['pin_audit'].
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = durable_job_path(order_id)
    state = {}
    if os.path.exists(path):
        try:
            state = json.load(open(path, encoding="utf-8"))
        except Exception:
            state = {}
    prev = state.get("pipeline_version")
    if prev and prev != PIPELINE_VERSION:
        state.setdefault("pin_audit", []).append({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event": "pin_repair",
            "was": prev, "now": PIPELINE_VERSION})
    elif not prev:
        state.setdefault("pin_audit", []).append({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event": "pinned_at_job_creation",
            "now": PIPELINE_VERSION})
    state["pipeline_version"] = PIPELINE_VERSION
    state["engine"] = "evidence_v1"
    # merge order fields (never overwrite pin fields)
    for k, v in (order or {}).items():
        if k not in ("pipeline_version", "engine"):
            state[k] = v
    state.setdefault("evidence_v1_retry_count", 0)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=1, ensure_ascii=False)
    return state


def spawn_evidence_v1_job(order: dict) -> dict:
    """Webhook entry point: persist durable job pinned to evidence_v1, then run
    the evidence_v1 pipeline in a detached subprocess. Never falls back to
    legacy; on spawn failure the durable job keeps the payment record and the
    watchdog/reconcile path owns recovery."""
    order_id = (order or {}).get("order_id") or ""
    if not order_id:
        return {"spawned": False, "error": "missing order_id"}
    if not (order or {}).get("payment_ref"):
        return {"spawned": False, "note": "no paid payment_ref — nothing to deliver"}
    state = ensure_pinned(order_id, order)
    state["status"] = state.get("status") if state.get("status") in (
        "email_sent",) else "payment_received"
    state["delivery_state"] = None
    with open(durable_job_path(order_id), "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=1, ensure_ascii=False)
    env = dict(os.environ)
    env["REPORT_PIPELINE_VERSION"] = PIPELINE_VERSION   # belt-and-braces pin
    env["EVIDENCE_V1_JOB_ID"] = order_id
    cmd = [sys.executable, os.path.join(_HERE, "evidence_v1_pipeline.py"),
           "--job-id", order_id]
    try:
        import subprocess
        subprocess.Popen(cmd, cwd=_HERE, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        return {"spawned": True, "pipeline_version": PIPELINE_VERSION,
                "durable_job": durable_job_path(order_id)}
    except Exception as e:
        # durable job already saved — payment/job NOT lost; watchdog reconciles
        state["status"] = state.get("status") or "payment_received"
        state["spawn_error"] = f"{type(e).__name__}: {e}"
        with open(durable_job_path(order_id), "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=1, ensure_ascii=False)
        return {"spawned": False, "pipeline_version": PIPELINE_VERSION,
                "durable_job": durable_job_path(order_id),
                "error": f"{type(e).__name__}: {e}",
                "note": "job durably pinned; recovery via job_watchdog reconcile"}


if __name__ == "__main__":
    print(json.dumps({"module": "evidence_v1_router",
                      "pipeline_version": PIPELINE_VERSION,
                      "note": "import and call spawn_evidence_v1_job(order) from server.py"}))
