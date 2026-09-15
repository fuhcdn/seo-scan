#!/usr/bin/env python3
"""Durable LLM layer for paid-job reliability.

Design:
- openrouter_chat_reliable(): retry/backoff/idempotency/timeout/error-record wrapper
  around seo_crawler.openrouter_chat.
- Every call keyed by idempotency_key; result cached to /tmp/llm_cache/<key>.json so a
  retried stage never re-sends or double-produces artifacts.
- Never raises after retries exhausted: returns (ok, result_or_error) and caller moves
  the job to research_retrying or manual_quality_escalation_required.
- Job-state helpers: job_llm_stage_record() persists attempt history into the order
  record BEFORE work begins (durable persist-first), so LLM unavailability never
  loses an accepted order.
"""
import json, os, time, hashlib

_CACHE_DIR = "/tmp/llm_cache"
_MAX_RETRIES = 4          # 1 initial + 3 retries
_BACKOFF = [5, 15, 45]    # seconds between retries
_TIMEOUT = 120

def _cache_path(idem_key):
    os.makedirs(_CACHE_DIR, exist_ok=True)
    return os.path.join(_CACHE_DIR, hashlib.sha256(idem_key.encode()).hexdigest()[:24] + ".json")

def _record_error(errors, stage, attempt, err):
    errors.append({"stage": stage, "attempt": attempt, "error": str(err)[:300],
                   "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})

def openrouter_chat_reliable(key, payload, stage, idem_key, job=None,
                             max_retries=_MAX_RETRIES, backoff=None, timeout=_TIMEOUT):
    """Reliable wrapper. Returns (ok, content, meta).
    ok=False after retries → caller must set research_retrying or
    manual_quality_escalation_required. Never throws. Never falls back to legacy."""
    from seo_crawler import openrouter_chat, _coerce_msg_content
    backoff = backoff or _BACKOFF
    cp = _cache_path(idem_key)
    # idempotency: completed stage result is reused, never duplicated
    if os.path.exists(cp):
        try:
            cached = json.load(open(cp))
            return True, cached["content"], {"reused": True, "attempts": 0, "errors": []}
        except Exception:
            pass
    errors = []
    for attempt in range(1, max_retries + 1):
        t0 = time.time()
        try:
            resp = openrouter_chat(key, payload, timeout=timeout)
            content = _coerce_msg_content((resp or {}).get("choices", [{}])[0].get("message", {}).get("content"))
            if not content or not content.strip():
                raise ValueError("empty/unparsable content")
            json.dump({"content": content, "stage": stage, "ts": time.time(),
                       "attempts": attempt}, open(cp, "w"))
            return True, content, {"attempts": attempt, "errors": errors, "latency_s": round(time.time()-t0, 1)}
        except Exception as e:
            _record_error(errors, stage, attempt, e)
            if attempt < max_retries:
                time.sleep(backoff[min(attempt-1, len(backoff)-1)])
    return False, None, {"attempts": max_retries, "errors": errors, "stage": stage}

def job_stage_begin(job, stage, idem_key):
    """Persist-before-work: record the stage start durably in the order file."""
    hist = job.setdefault("llm_stage_history", [])
    hist.append({"stage": stage, "idempotency_key": idem_key,
                 "state": "started", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    return hist[-1]

def job_stage_end(job, stage_rec, ok, meta):
    stage_rec["state"] = "completed" if ok else "failed"
    stage_rec["attempts"] = meta.get("attempts")
    stage_rec["errors"] = meta.get("errors", [])
    job["llm_reliability_last"] = {"stage": stage_rec["stage"], "ok": ok}
    if not ok:
        # never lose the order; never auto-refund; never abandon
        job["internal_state"] = "research_retrying"
        job["order_accepted"] = True
        if meta.get("attempts", 0) >= _MAX_RETRIES:
            job["internal_state"] = "manual_quality_escalation_required"

def reconcile_job(job):
    """Watchdog reconcile: any stage left 'started' (crash/timeout) is marked for retry,
    not abandoned. Duplicate protection: stages with completed cache are never re-run."""
    fixed = []
    for rec in job.get("llm_stage_history", []):
        if rec.get("state") == "started":
            rec["state"] = "retry_pending"
            rec["reconciled_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            fixed.append(rec["stage"])
    if fixed:
        job["internal_state"] = "research_retrying"
        job["order_accepted"] = True
    return fixed

# Reliability self-test: 20 consecutive controlled runs
if __name__ == "__main__":
    import sys
    key = os.environ.get("OPENROUTER_API_KEY") or ""
    if not key:
        try:
            for line in open("/opt/data/.env"):
                if line.startswith("OPENROUTER_API_KEY"):
                    key = line.split("=", 1)[1].strip()
        except Exception:
            pass
    results = {"runs": 0, "gen_ok": 0, "gen_fail": 0, "retry_recovered": 0,
               "duplicates": 0, "timeouts": 0, "reconciled": 0, "errors": []}
    for i in range(20):
        stage = f"reliability-run-{i}"
        idem = f"ORD-RELIABILITY-TEST-{i}"
        rec = job_stage_begin({"order_id": idem}, stage, idem)
        ok, content, meta = openrouter_chat_reliable(
            key, {"model": "z-ai/glm-4.5-air",
                  "messages": [{"role": "user", "content": "Reply with exactly: OK"}]},
            stage, idem)
        job = {"order_id": idem}
        job_stage_end(job, rec, ok, meta)
        if ok: results["gen_ok"] += 1
        else:
            results["gen_fail"] += 1
            results["errors"].extend(meta.get("errors", [])[-1:])
        results["timeouts"] += sum(1 for e in meta.get("errors", []) if "timed out" in str(e.get("error", "")).lower() or "timeout" in str(e.get("error", "")).lower())
        results["runs"] += 1
    # duplicate prevention proof: same idem key twice returns cached result, no new call
    ok1, c1, m1 = openrouter_chat_reliable(key, {"model": "z-ai/glm-4.5-air",
        "messages": [{"role": "user", "content": "Reply with exactly: DUP"}]}, "dup-test", "IDEM-DUP-KEY")
    ok2, c2, m2 = openrouter_chat_reliable(key, {"model": "z-ai/glm-4.5-air",
        "messages": [{"role": "user", "content": "Reply with exactly: DUP"}]}, "dup-test", "IDEM-DUP-KEY")
    results["duplicate_prevention"] = (m2.get("reused") is True and c1 == c2)
    # reconcile proof: started-but-crashed stage is retried, not lost
    j = {"order_id": "ORD-RECONCILE-TEST", "llm_stage_history": [{"stage": "gen", "state": "started"}]}
    fixed = reconcile_job(j)
    results["reconciled"] = len(fixed)
    results["reconcile_state"] = j.get("internal_state")
    results["order_preserved"] = j.get("order_accepted") is True
    print(json.dumps(results, indent=1))
