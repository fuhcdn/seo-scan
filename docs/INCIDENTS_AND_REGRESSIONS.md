# INCIDENTS AND REGRESSIONS — 事故與永久防護

每條:發生咩事 → 根本原因 → 永久 guard(而家點防)

## INC-1: Chromium footer 洩露 `file:///app/...`
- **事**:GATE5_FINAL PDF 可見 footer 係 render 嘅 source HTML 路徑;舊 agent 誤報「scanner 0 hits」
- **根因**:自訂 regex raw-byte scanner 捉唔到 Chromium 頁尾編碼;pypdf 實測 6 hits
- **永久 guard**:AD-2 pypdf exact-artifact + AD-3 `--no-pdf-header-footer` root fix + regression test 用 exact leaked string
- **教訓**:唔准自訂 regex/folder blocklist 做 final-artifact 判定

## INC-2: ACT-004 roadmap「live (DO NOW)」違反 immutable status
- **事**:Apple Imprints FINAL3 PDF roadmap 同 Executive Summary/Matrix 矛盾
- **根因**:free-text roadmap prose 自行 assign status
- **永久 guard**:AD-5 data-driven roadmap + `gate5_check_roadmap_status_consistency` validator

## INC-3: Brunner DWI action 被做 First 7-Day Win
- **事**:零 DO_NOW 時,runner 揀最低 effort 嘅 VALIDATE_FIRST 做 quick win
- **永久 guard**:AD-7 First 7-Day Preparation Plan rule + `_invalid_f7` deduction + test U/V

## INC-4: Apple business logic 漏入 Brunner roadmap
- **事**:Brunner roadmap 出現「Sales/Operations-approved method-to-project routing」
- **永久 guard**:AD-6 Business-Logic Context Lock + `gate5_check_business_logic_contamination`(test S/S3)

## INC-5: 內部 GB/EC evidence ID 漏入 customer-facing section
- **事**:Journey Map 用 GB-001..005;Implementation brief header 含 (GB-xxx)
- **永久 guard**:Journey Map card_id→action_id 映射 + brief header 剷 card id + `pdf_customer_readiness` 扣分 validator(test W)

## INC-6: scale rule 用「two positive review points」未定義
- **事**:GB-002..005 scale rule 冇 baseline/owner/confusion
- **永久 guard**:量化 scale rule 格式 + `undef_scale` validator + test K

## INC-7: 兩套 pipeline 各自 send 唔同 artifact;gates email sender 唔存在
- **事**:production 直接 attach pdf_path;gates import 嘅 `_send_email_attachment` 全 repo 冇定義
- **永久 guard**:AD-1 唯一 canonical `verified_pdf_delivery.py`;hard rule「no code path may attach mutable pdf_path」

## INC-8: Container rebuild 後假陰性 clean
- **事**:staging container rebuild 靚靚,pypdf 同 `--no-pdf-header-footer` 齊失蹤;scanner fallback 空 text → 多次誤報「clean」
- **永久 guard**:fail-closed(pypdf 缺失就 block,唔准 fallback 當 clean);RUNBOOK 提醒 rebuild 後驗證 pypdf+footer flag

## INC-9: External auditor transient error 被誤當 PASS 風險
- **事**:OpenRouter 偶發 400/空內容
- **永久 guard**:AD-8 fail-closed;retry wrapper;實測系統會正確 DELIVERY_BLOCKED

## INC-10: ~51k 行 junk 入 production repo
- **事**:_review/、pypdf.whl、vendored src、舊提取文本被 commit
- **永久 guard**:AD-10 .gitignore + tests/fixtures 最小化 + test Z(REPOSITORY_TRANSIENT_ARTIFACT_CHECK)

## INC-11: 13 條 test order 卡 running ~38h
- **事**:detached subprocess 死,冇 watchdog retrigger
- **狀態**:現有 backlog B2(durable job + reconcile)
- **暫時緩解**:人手檢查 output/order_*.json 狀態
