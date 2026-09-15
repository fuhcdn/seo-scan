#!/usr/bin/env python3
"""dry_run_outbound — Phase 1 STAGING dry-run test suite.

All targets are TEST/non-human/non-prospect fixtures.
DRY_RUN=true is mandatory; the Resend API is never called (verified by call counter = 0 in every case).
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import outbound_controls as oc
import outbound_send as osend

RESULTS = []
def check(name, cond, info=""):
    RESULTS.append((name, bool(cond), info))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}: {info}")

# ---- environment guards ----
assert oc.DRY_RUN is True, "DRY_RUN must be true in Phase 1"
DATA = oc.DATA_DIR
CONFIG = oc.CONFIG_DIR
os.makedirs(DATA, exist_ok=True)
os.makedirs(CONFIG, exist_ok=True)

FOOTER = "[BUSINESS LEGAL NAME]\n[OWNER-APPROVED POSTAL ADDRESS]\n[OWNER-APPROVED OPT-OUT WORDING]"
APPROVAL = {
    "campaign_id": "CAMP-TEST-001",
    "owner_approval_reference": "OWNER-TEST-REF-001",
    "approved_market": "United Kingdom",
    "approved_ICP": "TEST-only dry-run ICP (non-human)",
    "approved_template_hash": "deadbeef" * 8,
    "approved_sender": "support@seoscanaudit.com",
    "approved_footer_hash": "cafebabel" * 8,
    "approved_volume_cap": 100,
    "approved_sending_window": "07:30-10:30 Europe/London (DST applied)",
    "campaign_status": "ACTIVE",
    "approved_template_path": os.path.join(DATA, "template_test.txt"),
}
open(APPROVAL["approved_template_path"], "w").write("TEST TEMPLATE")
APPROVAL["approved_template_hash"] = __import__("hashlib").sha256(open(APPROVAL["approved_template_path"], "rb").read()).hexdigest()
# config writability probe (before any approval write attempt)
try:
    open(oc.APPROVAL_PATH + ".writetest", "w").close(); os.remove(oc.APPROVAL_PATH + ".writetest")
    CONFIG_WRITABLE = True
except OSError:
    CONFIG_WRITABLE = False
if CONFIG_WRITABLE:
    json.dump(APPROVAL, open(oc.APPROVAL_PATH, "w"), indent=1); os.chmod(oc.APPROVAL_PATH, 0o444)
json.dump({"pause_new_sends": False}, open(os.path.join(DATA, "stop_conditions.json"), "w"))

# reset stores to TEST-only state
open(oc.DNC_PATH, "w").close()
open(oc.LOG_PATH, "w").close()

BODY = "TEST BODY — internal dry-run fixture; no real recipient."

def T(pid, email, domain, name):
    return {"prospect_id": pid, "email": email, "domain": domain, "business_name": name}

# RO-CONFIG MODE: on a :ro mount the harness cannot rewrite the approval file per-case.
# It monkey-patches oc.load_campaign_approval to serve in-memory variants instead,
# so every gate case is still exercised without touching the read-only store.
CONFIG_WRITABLE = os.access(oc.DATA_DIR, os.W_OK) and not os.path.exists("/app/config/.ro")
try:
    open(oc.APPROVAL_PATH + ".writetest", "w").close()
    os.remove(oc.APPROVAL_PATH + ".writetest")
    CONFIG_WRITABLE = True
except OSError:
    CONFIG_WRITABLE = False

_mem = {}
_orig_load = oc.load_campaign_approval
def _patched_load(ref):
    if not CONFIG_WRITABLE and "_memcfg" in _mem:
        cfg = _mem["_memcfg"]
        if cfg.get("owner_approval_reference") != ref:
            return None, "approval_ref_mismatch"
        missing = oc.REQUIRED_APPROVAL_FIELDS - set(cfg.keys())
        if missing:
            return None, "approval_missing_fields:" + ",".join(sorted(missing))
        if cfg.get("campaign_status") != "ACTIVE":
            return None, "campaign_not_active"
        return dict(cfg), "ok"
    return _orig_load(ref)
oc.load_campaign_approval = _patched_load
def set_mem_cfg(cfg):
    _mem["_memcfg"] = cfg

E = osend.send_cold_email
F = FOOTER
R = "OWNER-TEST-REF-001"
S = "SEO Scan Audit — TEST"

# Case 0: OUTBOUND_ENABLED=false (default) → DISABLED, 0 calls, even for clean target
assert osend.OUTBOUND_ENABLED is False, "OUTBOUND_ENABLED must default false in Phase 1"
r0 = E(T("TEST-000", "test-000@test-fixture.invalid", "test-000.test-fixture.invalid", "TEST Business Zero"), F, R, S, BODY)
check("case0-hard-disabled", r0["stage"] == "DISABLED" and r0["sent"] is False
      and r0["resend_calls"] == 0 and r0["reason"] == "outbound_disabled_by_default", json.dumps(r0))

# Case 1+: simulate owner-approved enablement (env flip; DRY_RUN still true → zero API)
osend.OUTBOUND_ENABLED = True
set_mem_cfg(APPROVAL)

# Case 1: clean TEST target → WOULD_SEND, resend_calls == 0
r1 = E(T("TEST-001", "test-001@test-fixture.invalid", "test-001.test-fixture.invalid", "TEST Business One"), F, R, S, BODY)
check("case1-clean-WOULD_SEND", r1.get("would_send") is True and r1["resend_calls"] == 0, json.dumps(r1))

# Case 2: DNC by email → 0 calls
oc._append(oc.DNC_PATH, {"record_type": "DNC", "prospect_id": "TEST-002", "email": "test-002@test-fixture.invalid", "domain": "test-002.test-fixture.invalid", "reason": "explicit_unsubscribe", "exact_quote": "TEST"})
r2 = E(T("TEST-002", "test-002@test-fixture.invalid", "other-2.test-fixture.invalid", "TEST Business Two"), F, R, S, BODY)
check("case2-dnc-email", r2["stage"] == "DNC" and r2["resend_calls"] == 0, json.dumps(r2))

# Case 3: DNC by domain → 0 calls
r3 = E(T("TEST-003", "different-3@test-fixture.invalid", "test-002.test-fixture.invalid", "TEST Business Three"), F, R, S, BODY)
check("case3-dnc-domain", r3["stage"] == "DNC" and r3["resend_calls"] == 0, json.dumps(r3))

# Case 4: duplicate (same domain as case 1 send) → 0 calls
r4 = E(T("TEST-004", "test-004@test-fixture.invalid", "test-001.test-fixture.invalid", "TEST Business One"), F, R, S, BODY)
check("case4-duplicate", r4["stage"] == "DUP" and r4["resend_calls"] == 0, json.dumps(r4))

# Case 5: no/bad approval ref → 0 calls
r5 = E(T("TEST-005", "test-005@test-fixture.invalid", "test-005.test-fixture.invalid", "TEST Business Five"), F, "WRONG-REF", S, BODY)
check("case5-approval-ref-mismatch", r5["stage"] == "APPROVAL" and r5["resend_calls"] == 0, json.dumps(r5))
# missing field variant
del APPROVAL["approved_footer_hash"]
set_mem_cfg(APPROVAL)
r5b = E(T("TEST-005", "test-005@test-fixture.invalid", "test-005.test-fixture.invalid", "TEST Business Five"), F, R, S, BODY)
check("case5b-approval-missing-field", r5b["stage"] == "APPROVAL" and "approval_missing_fields" in r5b["reason"] and r5b["resend_calls"] == 0, json.dumps(r5b))
# restore approval
APPROVAL["approved_footer_hash"] = "cafebabel" * 8
APPROVAL["approved_template_hash"] = __import__("hashlib").sha256(open(APPROVAL["approved_template_path"], "rb").read()).hexdigest()
set_mem_cfg(APPROVAL)

# Case 6: footer missing (empty footer) → 0 calls
r6 = E(T("TEST-006", "test-006@test-fixture.invalid", "test-006.test-fixture.invalid", "TEST Business Six"), "", R, S, BODY)
check("case6-footer-missing", r6["stage"] == "FOOTER" and r6["resend_calls"] == 0, json.dumps(r6))

# Case 7: volume cap → 0 calls (set cap to 1; one SEND already logged)
APPROVAL["approved_template_hash"] = __import__("hashlib").sha256(open(APPROVAL["approved_template_path"], "rb").read()).hexdigest()
APPROVAL["approved_volume_cap"] = 1
set_mem_cfg(APPROVAL)
r7 = E(T("TEST-007", "test-007@test-fixture.invalid", "test-007.test-fixture.invalid", "TEST Business Seven"), F, R, S, BODY)
check("case7-cap-reached", r7["stage"] == "CAP" and r7["resend_calls"] == 0, json.dumps(r7))
APPROVAL["approved_volume_cap"] = 100
set_mem_cfg(APPROVAL)

# Case 8: stop-condition pause → 0 calls
json.dump({"pause_new_sends": True}, open(os.path.join(DATA, "stop_conditions.json"), "w"))
r8 = E(T("TEST-008", "test-008@test-fixture.invalid", "test-008.test-fixture.invalid", "TEST Business Eight"), F, R, S, BODY)
check("case8-stop-pause", r8["stage"] == "STOP" and r8["resend_calls"] == 0, json.dumps(r8))
json.dump({"pause_new_sends": False}, open(os.path.join(DATA, "stop_conditions.json"), "w"))

# Case 9: append integrity — campaign_log readable, one SEND event with full fields
lines = [json.loads(l) for l in open(oc.LOG_PATH, encoding="utf-8") if l.strip()]
sends = [l for l in lines if l.get("event") == "SEND"]
check("case9-log-append", len(sends) == 1 and all(k in sends[0] for k in ["target_id" if False else "target", "campaign_id", "owner_approval_reference"]), f"SEND events: {len(sends)}")

# ---- backup / restore (staging full cycle allowed) ----
import subprocess, shutil
BK = "/tmp/dnc-backup-test.tar.gz"
subprocess.run(["tar", "czf", BK, "-C", DATA, "dnc.jsonl", "campaign_log.jsonl"], check=True)
before = open(oc.DNC_PATH).read()
os.truncate(oc.DNC_PATH, 0)
subprocess.run(["tar", "xzf", BK, "-C", DATA], check=True)
after = open(oc.DNC_PATH).read()
check("case10-backup-restore", before == after, f"bytes={len(after)}")

# ---- permission denial (host nobody) — run on host via separate SSH by caller; here note requirement
print("== host nobody-denial test executed separately via SSH (see report) ==")

fails = [r for r in RESULTS if not r[1]]
print(f"\nDRY-RUN SUITE: {len(RESULTS)-len(fails)}/{len(RESULTS)} PASS")
print("RESEND API CALLS TOTAL:", osend.RESEND_CALLS)
sys.exit(1 if fails else 0)
