#!/usr/bin/env bash
# Phase 2 Production Re-Deploy Card v4.7 — Fail-Closed Orchestrator, Final
set -Eeuo pipefail

# ───────── PRE-0 variables ─────────
export OUTBOUND_IMAGE='seoscanaudit/outbound:phase1-600ea0a-clean'
export EXPECTED_IMAGE_ID='sha256:41a74d56d208f624760329fdd2842225a14b50feda0ce8e8b978c1acc7f1e3f5'
export LEGACY_IMAGE_ID='sha256:57f5c9b973996159e06898f6e2ef5863eeed4bd771daafe095272b1b6fafa034'
export EXPECTED_CTRL_SHA='bed59b99505ea943a62aa403968df8bba64b48369ee638a97065eb7df6ddb16a'
export EXPECTED_SEND_SHA='0e9b7aa2c01a1d56a66656e32deca23a0974f8e0a6fca05009c25ed853ff86f9'
export EXPECTED_HARNESS_SHA='515fee0a24cd155b94da7c445c82f6f4a2890e7710917f47ec65c25ad6a8b119'
export HOST_PORT='8000'
export HOST_DATA_DIR='/deploy/seo/app/data'
export HOST_CONFIG_DIR='/deploy/seo/app/config'
export HOST_SECRETS_FILE='/deploy/seo/app/secrets.env'
export REPO_DIR='/opt/seo-repo'
export PROD_DIR='/deploy/seo/app'
export TS="$(date +%Y%m%d-%H%M%S)"
export BK_DIR='/deploy/rollback'
export REL_BASE="$REPO_DIR/deploy/docker-compose.release.yml"
export REL_PROD="$REPO_DIR/deploy/docker-compose.release.production.yml"
export LEGACY_COMPOSE="$PROD_DIR/docker-compose.yml"
export EXPECTED_H5_STRING='False INACTIVE 0 True'
export EXPECTED_H6_SUMMARY='DRY-RUN SUITE: 12/12 PASS'
export EXPECTED_H6_RESEND='RESEND API CALLS TOTAL: 0'
export EXPECTED_H6_TRANSPORT='TRANSPORT CALLS TOTAL: 0'
export EXPECTED_H6_EVENT='would=1 send=0'

BACKUP_READY=0
CUTOVER_STARTED=0
PHASE2_STARTED=0
FAIL_REASON=""
IN_ROLLBACK=0
FAIL_LOG="$BK_DIR/failure-$TS.log"

mkdir -p "$BK_DIR"
touch "$FAIL_LOG"

# ───────── restore-first rollback handler (non-recursive, real assertions) ─────────
restore_and_rollback() {
  local rc="${1:-1}"
  if [ "$IN_ROLLBACK" = "1" ]; then
    echo "ROLLBACK-ALREADY-RUNNING — preserving evidence, exiting with original rc=$rc" | tee -a "$FAIL_LOG"
    exit "$rc"
  fi
  IN_ROLLBACK=1
  set +e
  echo "RESTORE_AND_ROLLBACK_START reason=[$FAIL_REASON] rc=$rc" | tee -a "$FAIL_LOG"
  echo "=== FAILURE RECORD $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" >> "$FAIL_LOG"
  echo "reason=[$FAIL_REASON] rc=$rc" >> "$FAIL_LOG"
  docker compose -p seo-production -f "$REL_BASE" -f "$REL_PROD" down 2>/dev/null || true
  if [ "$BACKUP_READY" = "1" ]; then
    tar xzf "$BK_DIR/prod-data-pre-h6-$TS.tar.gz" -C "$PROD_DIR/" \
      && echo "FH2-RESTORE-OK" \
      || echo "FH2-RESTORE-FAIL" | tee -a "$FAIL_LOG"
  else
    echo "FH2-SKIP-NO-BACKUP" | tee -a "$FAIL_LOG"
  fi
  mkdir -p "$HOST_DATA_DIR" && cd "$HOST_DATA_DIR"
  find . -type f -print0 | sort -z | xargs -0 sha256sum > "$BK_DIR/post-restore-manifest-$TS.sha256" 2>/dev/null || true
  find . -type f -print0 | sort -z | xargs -0 stat -c '%s %n' >> "$BK_DIR/post-restore-manifest-$TS.sha256" 2>/dev/null || true
  if [ "$BACKUP_READY" = "1" ] && diff "$BK_DIR/pre-h6-manifest-$TS.sha256" "$BK_DIR/post-restore-manifest-$TS.sha256" > /dev/null 2>&1; then
    echo "RESTORE-MANIFEST-MATCH" | tee -a "$FAIL_LOG"
    MANIFEST_RESULT="MATCH"
  else
    echo "R10-RESTORE-MISMATCH" | tee -a "$FAIL_LOG"
    MANIFEST_RESULT="MISMATCH"
  fi
  cd "$PROD_DIR" && docker compose -f "$LEGACY_COMPOSE" up -d --force-recreate
  sleep 6
  local legacy_health_ok="1"
  local h1 h2 h2_code
  h1="$(curl -sS -m 8 http://localhost:8000/health)" || legacy_health_ok="0"
  echo "$h1" | grep -qE '"ok": *true' || legacy_health_ok="0"
  echo "LEGACY-LOCAL-HEALTH: $h1" | tee -a "$FAIL_LOG"
  h2_code="$(curl -sS -m 8 -o /tmp/legacy_h2body -w '%{http_code}' https://seoscanaudit.com/health)" || legacy_health_ok="0"
  [ "$h2_code" = "200" ] || legacy_health_ok="0"
  grep -qE '"ok": *true' /tmp/legacy_h2body 2>/dev/null || legacy_health_ok="0"
  echo "LEGACY-PUBLIC-HEALTH: code=$h2_code body=$h2" | tee -a "$FAIL_LOG"
  if docker exec app-seo-scan-1 sh -c 'ls /app/pipeline/outbound_send.py /app/pipeline/outbound_controls.py' > /dev/null 2>&1; then
    echo "LEGACY-OUTBOUND-UNEXPECTED-PRESENT" | tee -a "$FAIL_LOG"
    legacy_health_ok="0"
  else
    echo "LEGACY-OUTBOUND-ABSENT-OK" | tee -a "$FAIL_LOG"
  fi
  echo "MANIFEST-RESULT: $MANIFEST_RESULT" | tee -a "$FAIL_LOG"
  if [ "$legacy_health_ok" = "1" ]; then
    echo "ROLLBACK-COMPLETE" | tee -a "$FAIL_LOG"
  else
    echo "ROLLBACK ATTEMPTED —" | tee -a "$FAIL_LOG"
    echo "LEGACY HEALTH FAILED —" | tee -a "$FAIL_LOG"
    echo "MANUAL INCIDENT REQUIRED" | tee -a "$FAIL_LOG"
  fi
  echo "failure evidence preserved in $FAIL_LOG" | tee -a "$FAIL_LOG"
  exit "$rc"
}

# ───────── global ERR trap (correct argument mapping) ─────────
global_err_handler() {
  local line_no="${1:-unknown}"
  local cmd="${2:-unknown}"
  local exit_code="${3:-1}"
  if [ "$IN_ROLLBACK" = "1" ]; then
    echo "ERR-DURING-ROLLBACK line=$line_no cmd=[$cmd] rc=$exit_code — not recursing" | tee -a "$FAIL_LOG"
    exit "$exit_code"
  fi
  if [ "$BACKUP_READY" != "1" ]; then
    FAIL_REASON="PREFLIGHT-ERROR line=$line_no cmd=[$cmd] rc=$exit_code"
    echo "PREFLIGHT-FAIL: $FAIL_REASON" | tee -a "$FAIL_LOG"
    exit "$exit_code"
  fi
  FAIL_REASON="RUNTIME-ERROR line=$line_no cmd=[$cmd] rc=$exit_code"
  restore_and_rollback "$exit_code"
}
trap 'global_err_handler "$LINENO" "$BASH_COMMAND" $?' ERR

preflight_fail() {
  FAIL_REASON="$1"
  echo "PREFLIGHT-FAIL: $1" | tee -a "$FAIL_LOG"
  exit 1
}

# ───────── PF-1 git sha ─────────
[ "$(cd "$REPO_DIR" && git rev-parse HEAD)" = "600ea0a26121827e8171a4ab3e6725318756870d" ] \
  || preflight_fail "PF1-GIT-SHA-MISMATCH"
echo PF1-OK

# ───────── PF-2 tag→image ─────────
[ "$(docker image inspect "$OUTBOUND_IMAGE" --format '{{.Id}}')" = "$EXPECTED_IMAGE_ID" ] \
  || preflight_fail "PF2-TAG-RESOLVES-WRONG-IMAGE"
echo PF2-OK

# ───────── PF-3 release compose preflight ─────────
CF_OUT="$(docker compose -p seo-production -f "$REL_BASE" -f "$REL_PROD" config 2>&1)" \
  || preflight_fail "PF3-COMPOSE-EXIT-FAIL"
[ -n "$CF_OUT" ] || preflight_fail "PF3-NO-RENDERED-CONFIG"
echo "$CF_OUT" | grep -qiE 'unset|empty|warning' && preflight_fail "PF3-EMPTY-VAR-FAIL" || true
echo "$CF_OUT" | grep -q 'source: /deploy/seo/app/data' || preflight_fail "PF3-DATA-MOUNT-FAIL"
echo "$CF_OUT" | grep -q 'source: /deploy/seo/app/config' || preflight_fail "PF3-CONFIG-MOUNT-FAIL"
echo "$CF_OUT" | grep -q 'read_only: true' || preflight_fail "PF3-READONLY-FAIL"
echo PF3-OK

# ───────── PF-4 legacy compose preflight (must assert legacy image) ─────────
[ -f "$LEGACY_COMPOSE" ] || preflight_fail "PF4-NO-LEGACY-COMPOSE"
LG_OUT="$(cd "$PROD_DIR" && docker compose -f "$LEGACY_COMPOSE" config 2>&1)" \
  || preflight_fail "PF4-LEGACY-CONFIG-FAIL"
LG_IMG_REF="$(echo "$LG_OUT" | grep 'image:' | head -1 | sed 's/.*image: *//; s/["'"'"']//g')"
[ -n "$LG_IMG_REF" ] || preflight_fail "PF4-NO-LEGACY-IMAGE-REF"
LG_IMG_ID="$(docker image inspect "$LG_IMG_REF" --format '{{.Id}}')" \
  || preflight_fail "PF4-LEGACY-IMAGE-INSPECT-FAIL"
[ "$LG_IMG_ID" = "$LEGACY_IMAGE_ID" ] || preflight_fail "PF4-LEGACY-IMAGE-MISMATCH:$LG_IMG_ID"
echo "$LG_OUT" | grep -q 'seo-scan' || preflight_fail "PF4-NO-SEO-SCAN-SERVICE"
command -v curl > /dev/null || preflight_fail "PF4-NO-CURL"
echo PF4-OK

# ───────── PF-5 read-only preflight of production data/config (no writes) ─────────
for f in "$HOST_CONFIG_DIR/campaign_approval.json" \
         "$HOST_CONFIG_DIR/campaign_approval.json.sha256" \
         "$HOST_DATA_DIR/dnc.jsonl" \
         "$HOST_DATA_DIR/campaign_log.jsonl" \
         "$HOST_DATA_DIR/stop_conditions.json"; do
  [ -f "$f" ] || preflight_fail "PF5-MISSING:$f"
done
cd "$HOST_CONFIG_DIR"
[ "$(sha256sum campaign_approval.json | cut -d' ' -f1)" = "$(cat campaign_approval.json.sha256 | cut -d' ' -f1)" ] \
  || preflight_fail "PF5-APPROVAL-HASH-MISMATCH"
[ "$(stat -c '%a' "$HOST_CONFIG_DIR/campaign_approval.json")" = "444" ] \
  || preflight_fail "PF5-APPROVAL-NOT-444"
SC_OK="$(cat "$HOST_DATA_DIR/stop_conditions.json")"
[ "$SC_OK" = '{"pause_new_sends": true}' ] || preflight_fail "PF5-STOP-CONDITIONS-UNSAFE:$SC_OK"
APR_INACTIVE="$(python3 -c "import json; c=json.load(open('$HOST_CONFIG_DIR/campaign_approval.json')); print(c['campaign_status'], c['approved_volume_cap'])")"
[ "$APR_INACTIVE" = "INACTIVE 0" ] || preflight_fail "PF5-APPROVAL-UNSAFE:$APR_INACTIVE"
for f in "$HOST_DATA_DIR/dnc.jsonl" "$HOST_DATA_DIR/campaign_log.jsonl"; do
  [ -r "$f" ] || preflight_fail "PF5-DATA-UNREADABLE:$f"
done
echo PF5-ALL-OK

# ───────── DEPLOY-1 backup + manifest (before any mutation) ─────────
mkdir -p "$BK_DIR"
cd "$HOST_DATA_DIR"
find . -type f -print0 | sort -z | xargs -0 sha256sum > "$BK_DIR/pre-h6-manifest-$TS.sha256"
find . -type f -print0 | sort -z | xargs -0 stat -c '%s %n' >> "$BK_DIR/pre-h6-manifest-$TS.sha256"
tar czf "$BK_DIR/prod-data-pre-h6-$TS.tar.gz" -C "$PROD_DIR" data
[ -s "$BK_DIR/prod-data-pre-h6-$TS.tar.gz" ] || preflight_fail "BACKUP-FAILED"
BACKUP_READY=1
echo "DEPLOY1-OK backup=$BK_DIR/prod-data-pre-h6-$TS.tar.gz"

# ───────── DEPLOY-2 cutover ─────────
CUTOVER_STARTED=1
docker inspect app-seo-scan-1 > "$BK_DIR/app-seo-scan-1-inspect-$TS.json"
docker stop app-seo-scan-1
docker rename app-seo-scan-1 "app-seo-scan-rollback-$TS"
cd "$REPO_DIR"
HOST_PORT="$HOST_PORT" HOST_DATA_DIR="$HOST_DATA_DIR" \
HOST_CONFIG_DIR="$HOST_CONFIG_DIR" HOST_SECRETS_FILE="$HOST_SECRETS_FILE" \
OUTBOUND_IMAGE="$OUTBOUND_IMAGE" \
docker compose -p seo-production -f "$REL_BASE" -f "$REL_PROD" up -d
sleep 6
PHASE2_STARTED=1
echo DEPLOY2-OK

# ───────── verify_h1_h5 (fail-closed, auto-rollback) ─────────
verify_h1_h5() {
  local h1 h2 h3 h4 h5
  h1="$(curl -sS -m 8 http://localhost:8000/health)" \
    || { FAIL_REASON="H1-CURL-FAIL"; restore_and_rollback 1; }
  echo "$h1" | grep -qE '"ok": *true' \
    || { FAIL_REASON="H1-JSON-FAIL:$h1"; restore_and_rollback 1; }
  echo "H1-OK"
  local h2_code
  h2_code="$(curl -sS -m 8 -o /tmp/h2body -w '%{http_code}' https://seoscanaudit.com/health)" \
    || { FAIL_REASON="H2-CURL-FAIL"; restore_and_rollback 1; }
  [ "$h2_code" = "200" ] || { FAIL_REASON="H2-CODE-FAIL:$h2_code"; restore_and_rollback 1; }
  grep -qE '"ok": *true' /tmp/h2body || { FAIL_REASON="H2-JSON-FAIL"; restore_and_rollback 1; }
  echo "H2-OK"
  h3="$(docker inspect seo-production-seo-scan-1 --format '{{.Image}}')"
  [ "$h3" = "$EXPECTED_IMAGE_ID" ] || { FAIL_REASON="H3-IMAGE-FAIL:$h3"; restore_and_rollback 1; }
  echo "H3-OK"
  h4="$(docker exec seo-production-seo-scan-1 sha256sum /app/pipeline/outbound_controls.py /app/pipeline/outbound_send.py /app/pipeline/dry_run_outbound.py)"
  echo "$h4" | grep -q "$EXPECTED_CTRL_SHA" || { FAIL_REASON="H4-CTRL-SHA-FAIL"; restore_and_rollback 1; }
  echo "$h4" | grep -q "$EXPECTED_SEND_SHA" || { FAIL_REASON="H4-SEND-SHA-FAIL"; restore_and_rollback 1; }
  echo "$h4" | grep -q "$EXPECTED_HARNESS_SHA" || { FAIL_REASON="H4-HARNESS-SHA-FAIL"; restore_and_rollback 1; }
  echo "H4-OK"
  h5="$(docker exec seo-production-seo-scan-1 python3 -c "import sys; sys.path.insert(0,'/app/pipeline'); import outbound_send as o, json; print(o.OUTBOUND_ENABLED, json.load(open('/app/config/campaign_approval.json'))['campaign_status'], json.load(open('/app/config/campaign_approval.json'))['approved_volume_cap'], json.load(open('/app/data/stop_conditions.json'))['pause_new_sends'])")"
  [ "$h5" = "$EXPECTED_H5_STRING" ] || { FAIL_REASON="H5-FAIL:$h5"; restore_and_rollback 1; }
  echo "H5-OK"
}

# ───────── verify_h6 (fail-closed, single full production run) ─────────
verify_h6() {
  local h6_out rc
  h6_out="$(docker exec -e DRY_RUN=true seo-production-seo-scan-1 \
    sh -c 'cd /app/pipeline && python3 dry_run_outbound.py 2>&1')" \
    && rc=0 || rc=$?
  printf '%s\n' "$h6_out" > "$BK_DIR/h6-evidence-$TS.log"
  [ "$rc" = "0" ] || { FAIL_REASON="H6-EXIT-NONZERO:$rc"; restore_and_rollback "$rc"; }
  echo "$h6_out" | grep -qF "$EXPECTED_H6_SUMMARY" \
    || { FAIL_REASON="H6-NOT-12-12"; restore_and_rollback 1; }
  local a
  for a in errno30-config-readonly config-writable-false transport-fail-closed parity-loader-5-variants; do
    echo "$h6_out" | grep -qF "[PASS] $a" \
      || { FAIL_REASON="H6-EXTRA-MISSING:$a"; restore_and_rollback 1; }
  done
  echo "$h6_out" | grep -qF "$EXPECTED_H6_RESEND" \
    || { FAIL_REASON="H6-RESEND-NONZERO"; restore_and_rollback 1; }
  echo "$h6_out" | grep -qF "$EXPECTED_H6_TRANSPORT" \
    || { FAIL_REASON="H6-TRANSPORT-NONZERO"; restore_and_rollback 1; }
  echo "$h6_out" | grep -qF "$EXPECTED_H6_EVENT" \
    || { FAIL_REASON="H6-EVENT-FAIL"; restore_and_rollback 1; }
  echo "$h6_out" | grep -qF '[FAIL]' \
    && { FAIL_REASON="H6-FAIL-ROWS-PRESENT"; restore_and_rollback 1; } || true
  local c
  for c in case0-hard-disabled case1-would-send case2-dnc-email case3-dnc-domain \
           case4-duplicate case5-ref-mismatch case5b-missing-field case6-footer-missing \
           case7-cap-reached case8-stop-pause case9-no-send-event case10-backup-restore; do
    echo "$h6_out" | grep -qF "[PASS] $c" \
      || { FAIL_REASON="H6-CASE-MISSING:$c"; restore_and_rollback 1; }
  done
  # explicit real-send event rejection (exact event-field pattern; cannot match DRY_RUN_WOULD_SEND)
  if echo "$h6_out" | grep -qE '"event": *"SEND"'; then
    FAIL_REASON="H6-REAL-SEND-EVENT-PRESENT"
    restore_and_rollback 1
  fi
  echo "H6-OK 12/12 — resend=0 transport=0 — no real send event"
}

# ───────── EXECUTION ─────────
verify_h1_h5
verify_h6

# ───────── SUCCESS-PATH: unconditional restore + manifest + restart Phase 2 ─────────
docker compose -p seo-production -f "$REL_BASE" -f "$REL_PROD" down
tar xzf "$BK_DIR/prod-data-pre-h6-$TS.tar.gz" -C "$PROD_DIR/"
cd "$HOST_DATA_DIR"
find . -type f -print0 | sort -z | xargs -0 sha256sum > "$BK_DIR/post-restore-manifest-$TS.sha256"
find . -type f -print0 | sort -z | xargs -0 stat -c '%s %n' >> "$BK_DIR/post-restore-manifest-$TS.sha256"
diff "$BK_DIR/pre-h6-manifest-$TS.sha256" "$BK_DIR/post-restore-manifest-$TS.sha256" > /dev/null \
  || { FAIL_REASON="R10-RESTORE-MISMATCH"; restore_and_rollback 1; }
echo "RESTORE-MANIFEST-MATCH"
cd "$REPO_DIR"
HOST_PORT="$HOST_PORT" HOST_DATA_DIR="$HOST_DATA_DIR" \
HOST_CONFIG_DIR="$HOST_CONFIG_DIR" HOST_SECRETS_FILE="$HOST_SECRETS_FILE" \
OUTBOUND_IMAGE="$OUTBOUND_IMAGE" \
docker compose -p seo-production -f "$REL_BASE" -f "$REL_PROD" up -d
sleep 6
verify_h1_h5

# ───────── FINAL ─────────
echo "PHASE 2 RE-DEPLOY COMPLETE —"
echo "FULL H6 12/12 PASS —"
echo "RESEND 0 —"
echo "RESTORE VERIFIED —"
echo "PRODUCTION HEALTHY"
