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
| 4be9d8e | 客戶 email subject 內部 order_id → customer-safe ref;Reply-To header 支持 | customer-safe | 31/31 | revert |
| 7acc233 | /sitemap.xml+/robots.txt routes;docstring 更正;品牌 inventory+proposal | AP-5 自主 | staging 200×3 | revert |
| a0a1e1b | **品牌統一 DEPLOYED**「SEO Scan Audit」(57→0) + clarification A→C state machine + watchdog 整合 + AC brand validator | owner 批 Option A + A→C | 32/32+15/15+12/12;Golden A/B PASS;production 10 routes 200 | revert→ddca49b |
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


## 2026-09-14 — ORD-BRIDGE-TEST：TECHNICAL_EMAIL_DELIVERY_TEST only（owner 裁定，非產品驗證）
- **Owner 裁定（2026-09-14，推翻之前「驗證完成」結論）**：
  - TECHNICAL_EMAIL_DELIVERY_TEST = RECEIVED / PROVIDER_ACCEPTED（僅此而已）
  - REPORT_QUALITY = FAILED（generic SERP-template findings、multi-URL action scope、generic remediation wording、truncated customer text、weak/incomplete page evidence、invalid current-market logic）
  - LEGACY_EMAIL_PATH = SECURITY/QUALITY REGRESSION
  - 呢個 artifact 係 DELIVERY_BLOCKED / NOT_A_CUSTOMER_SAMPLE / NOT_A_PRODUCT_READINESS_TEST；唔得當 evidence_v1 quality validation
- 技術事實保留：真卡 US$0.50 ×2 test-mode 付款 → legacy pipeline_runner 全鏈行畢 → Resend id 64cb2609 寄出 → owner 收到。過程修復 production bridge 缺口 5 項（SERP injection hook 時序、research minimum competitor_examples、page-level findings 1b block、SERP query dedupe、pages_reviewed string/dict）
- CHECKOUT_TEST_PRICE 已確認清走，checkout 回復真價 PRICE_397
- **Root cause**：webhook `spawn_delivery_pipeline` 永遠 spawn `pipeline_runner.py`（REPORT_PIPELINE_VERSION default='legacy'）→ evidence_v1 完全被 bypass；legacy gate 全 100 分照過（blind auditor 俾 A_evidence 20/20 基於「references customer URLs」，唔檢測 generic/truncated/multi-URL scope）；`.for-email.pdf` 由 `prepare_verified_artifact` 對任何過 scan 嘅 PDF 無條件生成
- **Fail-closed 已實施（LEGACY_REPORT_DELIVERY_BLOCKED）**：`verified_pdf_delivery.enforce_pipeline_gate` — pipeline_version≠'evidence_v1' 一律 blocked，唔會生成 .for-email.pdf、唔會 VERIFIED_READY_TO_SEND、唔會 call Resend/SMTP；`pipeline_runner.run_pipeline` 有 payment_ref 嘅單直接 hard-fail。Tests：`pipeline/test_legacy_delivery_block.py` 10/10 PASS（local+VPS）；regression 32+7+12+15 全綠；prod server 重啟後 live gate 確認 legacy→blocked、site 200
- **產品狀態更正**：first real-card E2E 交付鏈 = 只證明技術 email 鏈；產品 readiness 依然 UNVERIFIED，evidence_v1 唔可以咁樣被 bypass


## 2026-09-14 — EVIDENCE_V1 ROUTING LIVE（owner HIGHEST PRIORITY directive）
- **新 paid order routing = evidence_v1 ONLY**：`server.spawn_delivery_pipeline` → `evidence_v1_router.spawn_evidence_v1_job`（durable job `pipeline_version=evidence_v1`，immutable pin + pin_audit；zero legacy fallback）
- **`evidence_v1_pipeline.py`**：durable job 狀態機 payment_received → intake_validated → research → 5 gates（gate1-4 + gate5 final-artifact scan）→ shared scorecard（structural=100 + 每類≥90 + 總分≥90 先准發）→ canonical verified delivery（pypdf exact scan + immutable .for-email.pdf + 3-way SHA + pre-send recheck）→ email_sent；auditor outage／任何 gate fail = DELIVERY_BLOCKED（never pass-open）；delivery marker 防重複寄信；test recipients／無 ALLOW_REAL_SEND 強制 mock send
- **gate4_external_auditor 修復**：OpenRouter 400（缺 max_tokens）→ 加 `max_tokens:1500`（呢個係之前 golden runner 都會中嘅 latent bug）
- **gate5 新 hard fail `EMPTY_PDF_TEXT`**：PDF 提取唔到文字（<200 chars）一律 DELIVERY_BLOCKED — 唔可以静默過
- **Docker reproducibility fix**：`deploy/Dockerfile` 加 `pip install pypdf==6.18.1` + `COPY gates/ tests/`（之前 pypdf 係人手裝落 prod container，image 冇 — staging rebuild 即爆；而家 fresh build 自帶全部依賴）
- **驗證（staging + prod 都係真 docker compose build，唔係 docker cp）**：
  - actual-entry-point E2E（server.spawn_delivery_pipeline）：**18/18 PASS**（staging + prod）
  - prod 證據：JOB E2E-ENTRY-1789399456 → email_sent；rendered=scanned=email SHA=`f04df9cb1b1c02a0...`；scanner hard_fails=[]；pypdf 提取 35,476 chars；scorecard 100/100 全類 100%；auditor=external；mock sender 只收 .for-email.pdf
  - Persimmon legacy-style fixture：legacy artifact + send 全被 LEGACY_REPORT_DELIVERY_BLOCKED（10/10）
  - Golden A（Apple Imprints）PASS 100/100；Golden B（Brunner Law）PASS 100/100
  - 回歸：32/32 + 7/7 + 12/12 + 15/15 全綠
- **Website/checkout/pricing/Stripe 完全冇掂**：site 200、/ 顯示 US$397、PRICE_397/PRICE_997/PRICE_497 price IDs 原封不動
- Rollback：`docker tag app-seo-scan:latest app-seo-scan:rollback-<ts>`（rebuild 前 tag）


## 2026-09-14 (b) — LEGACY ENGINE PERMANENTLY DELETED（retire-legacy-report-engine）
- **DELETED executables**: pipeline_runner.py / quality_gate.py / autonomous_gate.py / research.py / pdf_scanner.py / tests that only tested them / copy/2026-09-12 stale source snapshot
- **EXTRACTED**: smtp_send.py（唯一真 SMTP sender，只可以由 evidence_v1 post-gate delivery 觸達）
- **SCRUBBED**: REPORT_PIPELINE_VERSION env flag（legacy feature flag 已不存在）；所有 webhook/worker 註釋改指 evidence_v1
- **Backup tag**: pre-legacy-retirement-backup = 51da50290cbd22364315c427c8d1e1a22caf9afd
- **Post-deletion verification（staging + prod，docker build --no-cache 乾淨 build）**: entry E2E 18/18（新增反證 checks：legacy 檔案不存在、import=ModuleNotFoundError、歷史 legacy record 拒絕重跑、legacy artifact/send 請求=LEGACY_REPORT_DELIVERY_BLOCKED）；Golden A/B PASS 100/100；7/7+12/12+15/15；site 200；US$397 不變
- Repo search：executable code 入面 legacy engine terms 只剩 blocker 常數名（LEGACY_REPORT_DELIVERY_BLOCKED）＋反證測試＋smtp_send provenance 註釋 — 冇任何可執行 legacy 路徑
