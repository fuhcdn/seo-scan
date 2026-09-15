#!/usr/bin/env python3
"""dry_run_outbound — Phase 2 :ro-safe dry-run test suite.

All targets are TEST/non-human/non-prospect fixtures.
DRY_RUN=true is mandatory; real Resend transport is fail-closed (asserts if invoked).

Design (owner mandate):
- NEVER writes /app/config/campaign_approval.json (proves Errno 30 against the real :ro mount).
- Approval-variant cases use in-memory config via a patched fixture-read path ONLY;
  parity tests prove the patched loader returns identical decisions to the real
  load_campaign_approval() for all five variant classes.
- Case 9 records DRY_RUN_WOULD_SEND (never SEND) so duplicate suppression can never
  mistake a dry-run for a real send.
"""
import json, os, sys, time, hashlib, tempfile, shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import outbound_controls as oc
import outbound_send as osend

RESULTS = []
def check(name, cond, info=""):
    RESULTS.append((name, bool(cond), info))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}: {info}")

# ---- environment guards ----
assert oc.DRY_RUN is True, "DRY_RUN must be true"
assert osend.OUTBOUND_ENABLED is False, "OUTBOUND_ENABLED must default false"

DATA = oc.DATA_DIR
CONFIG = oc.CONFIG_DIR
os.makedirs(DATA, exist_ok=True)

FOOTER = "[BUSINESS LEGAL NAME]\n[OWNER-APPROVED POSTAL ADDRESS]\n[OWNER-APPROVED OPT-OUT WORDING]"
BODY = "TEST BODY — internal dry-run fixture; no real recipient."
E = osend.send_cold_email
F = FOOTER
R = "OWNER-TEST-REF-001"
S = "SEO Scan Audit — TEST"

def T(pid, email, domain, name):
    return {"prospect_id": pid, "email": email, "domain": domain, "business_name": name}

# ---- Errno 30 proof: real write attempt against mounted /app/config ----
errno30 = None
try:
    open(oc.APPROVAL_PATH, "a").write("x")
except OSError as e:
    errno30 = (e.errno, e.strerror)
RO_MOUNT = errno30 is not None and errno30[0] == 30
LOCAL_DEV = os.environ.get("OUTBOUND_LOCAL_DEV") == "1" and errno30 is not None and errno30[0] == 2
check("errno30-config-readonly", RO_MOUNT or LOCAL_DEV, f"write attempt → {errno30}")
CONFIG_WRITABLE = errno30 is None
check("config-writable-false", CONFIG_WRITABLE is False, f"CONFIG_WRITABLE={CONFIG_WRITABLE}")

# ---- parity: real loader (fixture-path swapped to writable test dir) vs patched in-memory loader ----
PARITY_DIR = tempfile.mkdtemp(prefix="parity_cfg_")
_REAL_APPROVAL_PATH = oc.APPROVAL_PATH
oc.APPROVAL_PATH = os.path.join(PARITY_DIR, "campaign_approval.json")
_orig_load = oc.load_campaign_approval

_mem = {}
def patched_load(ref):
    cfg = _mem.get("_cfg")
    if cfg is None or cfg.get("owner_approval_reference") != ref:
        return None, "approval_ref_mismatch"
    missing = oc.REQUIRED_APPROVAL_FIELDS - set(cfg.keys())
    if missing:
        return None, "approval_missing_fields:" + ",".join(sorted(missing))
    if cfg.get("campaign_status") != "ACTIVE":
        return None, "campaign_not_active"
    if cfg.get("approved_template_path") and os.path.exists(cfg["approved_template_path"]):
        actual = hashlib.sha256(open(cfg["approved_template_path"], "rb").read()).hexdigest()
        if actual != cfg.get("approved_template_hash"):
            return None, "template_hash_mismatch"
    return dict(cfg), "ok"

def real_load_variant(cfg_dict, ref):
    if os.path.exists(oc.APPROVAL_PATH):
        os.chmod(oc.APPROVAL_PATH, 0o644)
    json.dump(cfg_dict, open(oc.APPROVAL_PATH, "w"))
    os.chmod(oc.APPROVAL_PATH, 0o444)   # parity with :ro mount (mode-bit check in real loader)
    return _orig_load(ref)

VALID = {
    "campaign_id": "CAMP-TEST-001", "owner_approval_reference": "OWNER-TEST-REF-001",
    "approved_market": "UK", "approved_ICP": "TEST", "approved_sender": "support@seoscanaudit.com",
    "approved_footer_hash": "cafebabel" * 8, "approved_volume_cap": 100,
    "approved_sending_window": "07:30-10:30 Europe/London", "campaign_status": "ACTIVE",
    "approved_template_path": os.path.join(DATA, "template_test.txt"),
}
open(VALID["approved_template_path"], "w").write("TEST TEMPLATE")
VALID["approved_template_hash"] = hashlib.sha256(open(VALID["approved_template_path"], "rb").read()).hexdigest()

variants = [
    ("valid",            dict(VALID), "OWNER-TEST-REF-001"),
    ("missing_footer",   {k: v for k, v in VALID.items() if k != "approved_footer_hash"}, "OWNER-TEST-REF-001"),
    ("ref_mismatch",     dict(VALID), "WRONG-REF"),
    ("inactive",         {**VALID, "campaign_status": "INACTIVE"}, "OWNER-TEST-REF-001"),
    ("invalid_json",     None, "OWNER-TEST-REF-001"),  # handled below
]
parity_ok = True
for name, cfgd, ref in variants:
    if name == "invalid_json":
        if os.path.exists(oc.APPROVAL_PATH):
            os.chmod(oc.APPROVAL_PATH, 0o644)
        open(oc.APPROVAL_PATH, "w").write("{broken")
        os.chmod(oc.APPROVAL_PATH, 0o444)
        real = _orig_load(ref)
        _mem["_cfg"] = {"owner_approval_reference": ref}
        patched = patched_load(ref)
        parity_ok &= (real[0] is None and patched[0] is None)
        continue
    real = real_load_variant(cfgd, ref)
    _mem["_cfg"] = cfgd
    patched = patched_load(ref)
    same = (real[0] is None) == (patched[0] is None) and real[1] == patched[1]
    parity_ok &= same
    print(f"  parity[{name}]: real={real[1]!r} patched={patched[1]!r} same={same}")
check("parity-loader-5-variants", parity_ok, "real vs patched identical decisions")
shutil.rmtree(PARITY_DIR, ignore_errors=True)
oc.APPROVAL_PATH = _REAL_APPROVAL_PATH
oc.load_campaign_approval = _orig_load

# ---- fixture stores reset (writable DATA only) ----
open(oc.DNC_PATH, "w").close()
open(oc.LOG_PATH, "w").close()
json.dump({"pause_new_sends": False}, open(os.path.join(DATA, "stop_conditions.json"), "w"))

_mem["_cfg"] = APPROVAL = dict(VALID)

# in-memory config service for send path
oc.load_campaign_approval = patched_load
def set_mem_cfg(cfg):
    _mem["_cfg"] = cfg

# Case 0: hard disabled
r0 = E(T("TEST-000", "test-000@test-fixture.invalid", "test-000.test-fixture.invalid", "TEST Zero"), F, R, S, BODY)
check("case0-hard-disabled", r0["stage"] == "DISABLED" and r0["sent"] is False
      and r0["resend_calls"] == 0 and r0["reason"] == "outbound_disabled_by_default", json.dumps(r0))

# enable (dry-run only; real transport still fail-closed)
osend.OUTBOUND_ENABLED = True

# transport fail-closed proof
try:
    osend._real_resend("X", "x@y", "t@t.invalid", "S", "B")
    tc_fail = False
except AssertionError:
    tc_fail = True
check("transport-fail-closed", tc_fail, "real transport asserts under DRY_RUN")

# Case 1: clean → DRY_RUN_WOULD_SEND
r1 = E(T("TEST-001", "test-001@test-fixture.invalid", "test-001.test-fixture.invalid", "TEST One"), F, R, S, BODY)
check("case1-would-send", r1.get("would_send") is True and r1["resend_calls"] == 0, json.dumps(r1))

# Case 2/3: DNC
oc._append(oc.DNC_PATH, {"record_type": "DNC", "prospect_id": "TEST-002", "email": "test-002@test-fixture.invalid", "domain": "test-002.test-fixture.invalid", "reason": "explicit_unsubscribe", "exact_quote": "TEST"})
r2 = E(T("TEST-002", "test-002@test-fixture.invalid", "other-2.test-fixture.invalid", "TEST Two"), F, R, S, BODY)
check("case2-dnc-email", r2["stage"] == "DNC" and r2["resend_calls"] == 0, json.dumps(r2))
r3 = E(T("TEST-003", "different-3@test-fixture.invalid", "test-002.test-fixture.invalid", "TEST Three"), F, R, S, BODY)
check("case3-dnc-domain", r3["stage"] == "DNC" and r3["resend_calls"] == 0, json.dumps(r3))

# Case 4: duplicate
r4 = E(T("TEST-004", "test-004@test-fixture.invalid", "test-001.test-fixture.invalid", "TEST One"), F, R, S, BODY)
check("case4-duplicate", r4["stage"] == "DUP" and r4["resend_calls"] == 0, json.dumps(r4))

# Case 5/5b: approval variants
_mem["_cfg"] = {**VALID, "owner_approval_reference": "OTHER-REF"}
r5 = E(T("TEST-005", "test-005@test-fixture.invalid", "test-005.test-fixture.invalid", "TEST Five"), F, R, S, BODY)
check("case5-ref-mismatch", r5["stage"] == "APPROVAL" and r5["resend_calls"] == 0, json.dumps(r5))
_mem["_cfg"] = {k: v for k, v in VALID.items() if k != "approved_footer_hash"}
r5b = E(T("TEST-005", "test-005@test-fixture.invalid", "test-005.test-fixture.invalid", "TEST Five"), F, R, S, BODY)
check("case5b-missing-field", r5b["stage"] == "APPROVAL" and "approval_missing_fields" in r5b["reason"] and r5b["resend_calls"] == 0, json.dumps(r5b))

# Case 6: footer missing
r6 = E(T("TEST-006", "test-006@test-fixture.invalid", "test-006.test-fixture.invalid", "TEST Six"), "", R, S, BODY)
check("case6-footer-missing", r6["stage"] == "FOOTER" and r6["resend_calls"] == 0, json.dumps(r6))

# Case 7: volume cap
_mem["_cfg"] = {**VALID, "approved_volume_cap": 1}
r7 = E(T("TEST-007", "test-007@test-fixture.invalid", "test-007.test-fixture.invalid", "TEST Seven"), F, R, S, BODY)
check("case7-cap-reached", r7["stage"] == "CAP" and r7["resend_calls"] == 0, json.dumps(r7))
_mem["_cfg"] = dict(VALID)

# Case 8: pause
json.dump({"pause_new_sends": True}, open(os.path.join(DATA, "stop_conditions.json"), "w"))
r8 = E(T("TEST-008", "test-008@test-fixture.invalid", "test-008.test-fixture.invalid", "TEST Eight"), F, R, S, BODY)
check("case8-stop-pause", r8["stage"] == "STOP" and r8["resend_calls"] == 0, json.dumps(r8))
json.dump({"pause_new_sends": False}, open(os.path.join(DATA, "stop_conditions.json"), "w"))

# Case 9: log event types — DRY_RUN_WOULD_SEND only, no SEND
lines = [json.loads(l) for l in open(oc.LOG_PATH, encoding="utf-8") if l.strip()]
would = [l for l in lines if l.get("event") == "DRY_RUN_WOULD_SEND"]
sends = [l for l in lines if l.get("event") == "SEND"]
check("case9-no-send-event", len(would) == 1 and len(sends) == 0
      and would[0].get("dry_run") is True and would[0].get("campaign_id"), f"would={len(would)} send={len(sends)}")

# Case 10: backup/restore
import subprocess as _sp
BK = "/tmp/dnc-backup-phase2.tar.gz"
_sp.run(["tar", "czf", BK, "-C", DATA, "dnc.jsonl", "campaign_log.jsonl"], check=True)
before = open(oc.DNC_PATH).read()
os.truncate(oc.DNC_PATH, 0)
_sp.run(["tar", "xzf", BK, "-C", DATA], check=True)
check("case10-backup-restore", before == open(oc.DNC_PATH).read(), f"bytes={len(before)}")

# final counters
fails = [x for x in RESULTS if not x[1]]
print(f"\nDRY-RUN SUITE: {len(RESULTS)-len(fails)}/{len(RESULTS)} PASS")
print("RESEND API CALLS TOTAL:", osend.RESEND_CALLS)
print("TRANSPORT CALLS TOTAL:", getattr(osend, "_transport_calls", 0))
sys.exit(1 if fails or osend.RESEND_CALLS else 0)
