# CHANGELOG_AGENT — 自主改動紀錄

格式:日期 | commit | 改動 | 理由 | 測試 | rollback

## 2026-09-13
### Phase 0 transparency disclosure（依 owner 指令）
- **Phase 0 audit = read-only** ✅（冇改 production code）
- **Documentation bootstrap = separate write activity（129d6f7）**，唔可以稱為「zero write」
- 建立/修改嘅 docs（全部零 secrets、零客戶資料，只含架構/風險/流程描述）：
  - 新增 11 檔：`docs/OPERATING_MANUAL.md`, `docs/SYSTEM_MAP.md`, `docs/PRODUCT_SPEC.md`, `docs/QUALITY_STANDARD.md`, `docs/PRODUCTION_RUNBOOK.md`, `docs/ARCHITECTURE_DECISIONS.md`, `docs/RISK_REGISTER.md`, `docs/CHANGELOG_AGENT.md`, `docs/BACKLOG.md`, `docs/GOLDEN_REFERENCE_REGISTRY.md`, `docs/INCIDENTS_AND_REGRESSIONS.md`
  - 其後修改 1 檔：`docs/RISK_REGISTER.md`（R-A5 定價矛盾 RESOLVED 更新）
- Secret check：docs 內容為流程/架構描述，無 API token/password/customer detail（secrets 只以「位置名稱」引用，如「VPS /deploy/seo/app/secrets.env」，無值）

### Status language correction（依 owner 指令）
正確狀態用語：
- Production evidence_v1 architecture: **INTEGRATED / STAGING-READY**
- Production evidence_v1 end-to-end delivery: **NOT VERIFIED until AP-6 passes**
- Production evidence_v1 live customer delivery: **NOT ENABLED**
- Broad customer acquisition: **NOT READY**
不得將「code integration exists」「staging/golden test pass」「unit tests pass」表述為真實 customer production delivery PASS。

| Commit | 改動 | 理由 | 測試 | Rollback |
|---|---|---|---|---|
| 96833a9 | 5-gate evidence-led rebuild | 用戶 REJECT template-led SERP shortcut | 24/24 | git revert |
| 30e3a3d | GATE5 scheme-based rules | footer `file://` leak | regression | git revert |
| 14df6a1 | `--no-pdf-header-footer` + pypdf + 3-way SHA | Chromium footer root fix | 24/24 | git revert |
| 9db4dc2 | investment_status 單一來源 + truncation 移除 | status contradiction | 24/24 | git revert |
| de29389 | 5 actions + journey + roadmap + role ownership | Apple Imprints 深度 | 24/24 | git revert |
| a0d6d2a | priority-fix + semantic scoring | ACT-004 VF + action-specific signals | 24/24 | git revert |
| 1b2ec5d | data-driven roadmap + validator | ACT-004「live DO NOW」矛盾 | 24/24 | git revert |
| 31dc945 | Golden Reference B(Brunner)+ per-customer generalisation | 跨垂直驗證 | 24/24 | git revert |
| fbe3c16 | legal placeholder email + zh-Hant 雙 selected | 4CEO R1 | live verify | backup-legal-* |
| 5d15631 | B-reject 4 項修復 + repo hygiene | Prep-Plan/context-lock/ACT-id/hygiene | 24/24 | git revert |
| e91ef39 | **canonical verified-PDF delivery service**(pipeline/verified_pdf_delivery.py);兩套 pipeline 共用;production sender 只 attach verified artifact;feature flag 記錄 | ONE shared service 規則;_send_email_attachment 缺失 | **30/30** | git revert |
| 14edc76 | .gitignore + delivery-record | runtime record 唔入 repo | - | git revert |

## 未來改動須知
- 每次 R1/R2 改動:branch → test → staging → verify → deploy → monitor → document
- 所有 autonomous 改動必須有 test 證據 + rollback reference
- 呢個檔案唔可以代替真 commit message;兩邊都要寫
