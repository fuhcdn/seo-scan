# ARCHITECTURE DECISIONS — 點解係咁

## AD-1: 唯一 canonical verified-PDF delivery service
**決定**:所有 customer PDF 只可以經 `pipeline/verified_pdf_delivery.py` verify+send。
**點解**:之前兩套 pipeline 各自 render/scan/send 唔同 artifact,曾出現 render A→scan B→email C 同 verify.for-email.pdf 但實際寄 pdf_path 嘅風險。單一 service 令 hard-fail 規則、SHA 驗證、pre-send recheck 只有一份 implementation,唔會 drift。
**Commit**:e91ef39 / 14edc76

## AD-2: pypdf exact-artifact extraction(唔准 raw-byte regex-only)
**決定**:最終 artifact 掃描必須用 pypdf(mature extractor)提取可見文字+layers。
**點解**:自訂 regex/資料夾 blocklist 曾出現假陰性(Chromium footer `file:///app/...` 走甩,被舊 agent 誤報 0 hits)。pypdf 實測捉到 6 次。用戶明令:「DO NOT ADD ANOTHER REGEX OR ANOTHER FOLDER NAME TO A BLOCKLIST」。
**Commit**:14df6a1

## AD-3: `--no-pdf-header-footer` root fix
**決定**:Chromium render 時直接唔寫 header/footer,唔靠 scanner 補救。
**點解**:之前 Chromium 默認喺 PDF 寫 source-URL footer,即使 scan 都只係下游補救;root fix 先杜絕。
**Commit**:14df6a1

## AD-4: STAGING_TEST_PASS vs READY_TO_DELIVER 分離
**決定**:`decide_delivery()` threshold<90 → STAGING_TEST_PASS(永不可交付);90+ → READY_TO_DELIVER。
**點解**:之前有「90/80」模糊格式同 test PASS 當可交付嘅矛盾。
**Commit**:f65589e

## AD-5: investment_status 單一來源 + data-driven roadmap
**決定**:每 action 一個 immutable `investment_status`;所有 section 由佢渲染;roadmap sentence 只可以由 action 自己嘅 `roadmap_preparation`/`publication_condition` 生成;有 deterministic validator 攔矛盾。
**點解**:Apple Imprints 早期 Executive Summary 同 Matrix 矛盾;之後 ACT-004 roadmap「live (DO NOW)」違反 immutable rule。
**Commit**:1b2ec5d / 5d15631

## AD-6: Business-Logic Context Lock
**決定**:每 action 持有 customer_domain/business_model/roadmap_preparation/publication_condition;validator 將跨客戶 business term 視為 HARD FAIL。
**點解**:Brunner(法律)roadmap 曾漏入 Apple(apparel)嘅「method-to-project routing」logic。
**Commit**:5d15631

## AD-7: First 7-Day Preparation Plan rule
**決定**:有 DO_NOW → 揀最高價值 eligible action 做 First 7-Day Win;零 DO_NOW → 渲染 Preparation Plan(只含 safe 非出版活動),永不將 VALIDATE_FIRST 當 quick win。
**點解**:Brunner DWI action 曾被錯誤標為 First 7-Day Win。
**Commit**:5d15631

## AD-8: External semantic auditor fail-closed
**決定**:OpenRouter 盲審出錯(空內容/HTTP 400/timeout)→ DELIVERY_BLOCKED,唔可以 PASS。
**點解**:auditor 唔在場時 generator 唔可自批(role separation 硬規則);實測 transient error 曾被誤當 clean。
**Commit**:本 repo autonomous_gate + gates/GATE4

## AD-9: Feature flag REPORT_PIPELINE_VERSION
**決定**:delivery record 記錄 legacy|evidence_v1;production 預設 legacy-safe。
**點解**:允許 staging 先行 evidence_v1,production 直至 E2E 過先切;隨時 rollback。
**Commit**:e91ef39

## AD-10: Fixtures 喺 tests/fixtures(唔係 repo 頂層)
**決定**:Golden A/B 卡+頁+scorecard 全部 sanitised 收埋 tests/fixtures/;report 輸出/whl/review scripts 全 gitignore。
**點解**:曾一次 commit ~51k 行(含 vendored pypdf src + .whl + 舊提取文本)入 production repo,被 reject。
**Commit**:5d15631
