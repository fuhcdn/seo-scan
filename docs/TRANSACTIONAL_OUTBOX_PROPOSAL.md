# WORK 3 PROPOSAL — Transactional Outbox / Delivery-Verification Design

Status: **DESIGN_PROPOSAL_ONLY / OWNER_APPROVAL_REQUIRED**
未實作、未啟用。本提案解決:worker 喺「已聯絡 email provider 但未持久化成功結果」之間 crash 嘅 unknown-send state。

---

## 1. 現狀缺口(Phase 0 實測)
現有 `step_deliver`:`_smtp_send()` / Resend API call 成功後,先會寫 delivery marker(`output/deliveries/<order>_delivery.txt`)。若 process 喺「provider 已收信」同「marker 未寫」之間 crash → 下一輪 reconcile 會視 job 未交付 → **風險重複寄第二封**。

## 2. 設計:transactional outbox record

### 2.1 Outbox record schema(每個 send attempt 一條)
`output/outbox/<order_id>.outbox.json`
```json
{
  "job_id": "ORD-XXXX",
  "idempotency_key": "<sha256 of (job_id + email_artifact_sha256 + recipient)>",
  "final_pdf_sha256": "…rendered/scanned…",
  "email_artifact_path": "…pdf.for-email.pdf",
  "recipient": "customer email",
  "provider": "resend | smtp",
  "provider_message_id": null | "<id>",
  "provider_send_status": "not_started | accepted | unknown | failed",
  "attempt": 1,
  "created_at": "…",
  "updated_at": "…",
  "state": "outbox_pending | delivery_pending_verification | email_sent | delivery_failed"
}
```

### 2.2 狀態機與 no-duplicate-send 規則
```
before call:     outbox_pending   (idempotency_key written BEFORE provider call)
provider call:   (SMTP/Resend)
   ├─ clear accept (2xx / message_id) → state=email_sent, store message_id → 完結,永不重寄
   ├─ clear reject (connection refused / 5xx before accept) → state=delivery_failed → safe retry (new attempt, new key)
   └─ timeout / connection dropped / unknown
                  → state=delivery_pending_verification → DO NOT resend automatically
```

### 2.3 unknown-send 恢復(after restart)
1. Reconcile 見 `delivery_pending_verification`:
   - 若 provider 有 status API(Resend):查 message_id → 更新狀態
   - 無 message_id / 無查詢途徑 → **alert + manual_support_required**,唔自動重寄
2. 客戶無收信 + provider 無紀錄 → owner 批先可以手動補寄(用同一 verified artifact,SHA 對照)
3. 永遠用 `idempotency_key` 去重(同 SHA+收件人+job 唔會寄第二次)

### 2.4 retry condition
- `outbox_pending` + provider 未接受 → safe retry(最多 3 次,15min 間隔,依現有 DELIVERY_MAX_ATTEMPTS)
- `delivery_pending_verification` → 永不自動 retry
- `email_sent` → 永不重跑

### 2.5 alert/escalation
- unknown 狀態 >30 分鐘 → watchdog.log alert + manual_support_required
- unknown >24h → 升級 owner(人工決定)

### 2.6 record retention
- outbox records + delivery records 保留 ≥90 日(對賬/爭議)
- 每 job 一個檔,唔刪,archive 喺 owner 批後

## 3. 受影響 code paths(精確)
| File | 改動 | 風險 |
|---|---|---|
| `pipeline/pipeline_runner.py::step_deliver` | 寄前寫 outbox_pending;寄後立刻寫 accepted/failed/unknown | 中(要冇 race) |
| `pipeline/job_watchdog.py` | 認識 `delivery_pending_verification`(唔會 escalate retry) | 低 |
| `pipeline/verified_pdf_delivery.py` | 冇改 — SHA 邏輯不變 | 無 |
| `pipeline/server.py` | 冇改(webhook 不變) | 無 |

## 4. Test plan(待批准後實作)
1. mock provider accept → email_sent,不重寄
2. mock provider fail-before-accept → retry(新 idempotency_key)
3. mock provider timeout(unknown)→ delivery_pending_verification,唔重寄
4. restart 後 reconcile → unknown 狀態保留、不重寄、alert
5. email_sent job 重跑 reconcile → 完全不掂
6. 同 SHA+收件人 重複嘗試 → idempotency_key 擋

## 5. 風險評估
- **不實作風險**:unknown-send window 依然存在(現狀);重複寄信風險≈1 次 provider timeout 對 1 job
- **實作風險**:outbox 寫檔同 provider call 之間嘅 order-of-operations 要小心(key 先寫);對 Resend SMTP mode 冇 message_id query API → unknown 仍要人手
- **建議**:採用「先寫 key 後 call」模式 + Resend 作首選 provider(有 message_id)
