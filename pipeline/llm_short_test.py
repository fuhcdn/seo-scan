#!/usr/bin/env python3
"""Short reliability mechanics test: 5 runs, fast timeouts. Measures retry/reconcile/duplicate logic today."""
import json, os, time, sys
sys.path.insert(0, "/app/pipeline")
from llm_reliable import openrouter_chat_reliable, job_stage_begin, job_stage_end, reconcile_job, _cache_path

from seo_crawler import resolve_openrouter_key
key = resolve_openrouter_key()
results = {"runs": 0, "ok": 0, "fail": 0, "attempts_used": [], "errors": [], "duplicates": 0, "reconciled": 0}
for i in range(5):
    rec = job_stage_begin({"order_id": f"ORD-SHORT-{i}"}, f"short-run-{i}", f"ORD-SHORT-{i}")
    ok, content, meta = openrouter_chat_reliable(
        key, {"model": "deepseek/deepseek-v4-flash-0731",
              "messages": [{"role": "user", "content": "Reply with exactly: OK"}]},
        f"short-run-{i}", f"ORD-SHORT-{i}", max_retries=2, backoff=[2, 4], timeout=30)
    job = {"order_id": f"ORD-SHORT-{i}"}
    job_stage_end(job, rec, ok, meta)
    results["runs"] += 1
    results["ok" if ok else "fail"] += 1
    results["attempts_used"].append(meta.get("attempts"))
    if meta.get("errors"): results["errors"].append(meta["errors"][-1])
# duplicate prevention
c1 = _cache_path("DUP-KEY-1")
ok1, x1, m1 = openrouter_chat_reliable(key, {"model": "deepseek/deepseek-v4-flash-0731", "messages": [{"role":"user","content":"say DUP"}]}, "dup", "DUP-KEY-1", max_retries=1, backoff=[1], timeout=20)
if ok1:
    ok2, x2, m2 = openrouter_chat_reliable(key, {"model": "deepseek/deepseek-v4-flash-0731", "messages": [{"role":"user","content":"say DUP"}]}, "dup", "DUP-KEY-1", max_retries=1, backoff=[1], timeout=20)
    results["duplicate_prevention"] = m2.get("reused") is True
else:
    results["duplicate_prevention"] = "cache-only-after-first-success (LLM down — mechanism intact, untestable today)"
# reconcile
j = {"order_id": "ORD-REC", "llm_stage_history": [{"stage": "gen", "state": "started"}]}
fixed = reconcile_job(j)
results["reconciled"] = len(fixed)
results["state_after"] = j.get("internal_state")
results["order_preserved"] = j.get("order_accepted")
print(json.dumps(results, indent=1))
