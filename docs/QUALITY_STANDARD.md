# QUALITY STANDARD — 90+ 硬標準

## 生產底線（非談判）
- 每個 semantic category ≥90%
- INDEPENDENT_SEMANTIC_QUALITY_SCORE ≥90/100
- 零 hard fail
- rendered SHA = scanned SHA = email attachment SHA
- 任何一項不成立 → DELIVERY_BLOCKED
- <90 只可以係 STAGING_TEST_PASS,永不可交付

## 兩個分開嘅分數
1. STRUCTURAL_COMPLETENESS_SCORE = field/label presence(唔係 quality)
2. INDEPENDENT_SEMANTIC_QUALITY_SCORE = 真質素,6 categories:
   - evidence_accuracy(20) / finding_distinctness(15) / customer_specificity(15) /
     commercial_priority_quality(15) / action_executability(15) / pdf_customer_readiness(20)
   - 每 category:raw/max/%/evidence reference/deduction reason/zero-deduction explanation
   - 100/100 只有喺真嘅無合理 deduction 先可以俾

## Hard fails(全部 → DELIVERY_BLOCKED)
INTERNAL_FILE_URI · INTERNAL_PATH_LEAK · UNSAFE_LINK_SCHEME · PLACEHOLDER_LEAK ·
SECRET_LEAK · INTERNAL_ORDER_OR_PAYMENT_LEAK · WRONG_CUSTOMER_OR_DOMAIN ·
FOREIGN_CUSTOMER_CONTAMINATION · BUSINESS_LOGIC_CONTEXT_CONTAMINATION ·
REQUIRED_FIELD_EMPTY · TRUNCATED_CUSTOMER_TEXT · PRIORITY_CONSISTENCY_FAIL ·
NO_DO_NOW_BUT_QUICK_WIN · ROADMAP_ACTION_DATA_MISMATCH ·
ROADMAP_APPROVER_ROLE_MISMATCH · CUSTOMER_FACING_EVIDENCE_ID_LEAK ·
UNAPPROVED_PROFESSIONAL_CLAIM · EMAIL_ATTACHMENT_SHA_MISMATCH ·
REPOSITORY_TRANSIENT_ARTIFACT_CHECK

## 每個 action 必須嘅 chain(缺一格 = 唔可以入 customer PDF)
exact customer-owned primary URL → direct observation → buyer question →
specific gap → customer-specific mechanism → concrete action →
owner/approver/publisher-QA → publication condition → definition of done →
action-specific first signal → baseline → review window → scale rule

## Context locks
- Customer Context Lock:錯客戶/domain/URL → block
- Business-Logic Context Lock:舊客戶/舊 business model logic 漏入 → HARD FAIL
- 每 action record 必含:action_id, customer_domain, business_model,
  primary_customer_url, investment_status, action_title, approver_role,
  content_owner_role, publisher_qa_role, roadmap_preparation,
  publication_condition, required_module_fields, first_signal, baseline, scale_rule

## Report 結構要求
- 3-5 genuine customer-specific findings
- ≥5 concrete customer-owned actions(有證據先)
- 1 個真 DO NOW quick win;無 safe DO NOW 就 First 7-Day Preparation Plan
- 投資矩陣(DO NOW / VALIDATE FIRST / DEFER) + Journey Map + 90-Day Roadmap +
  Commercial model + role ownership + sources + limitations

## Forbidden customer-facing content
generic "improve SEO" / keyword list 當策略 / SEO tool log 當 decision /
SERP label 當 action target / competitor domain 當 target / 多個唔相關 URL 做一個
action / 虛構 rank/traffic/revenue/ROI / 虛構 competitor 數據 / 未批准
professional claim / 內部 evidence ID 喺 decision section / file: URI /
internal path / placeholder / blank label / truncated sentence

## 測量規則
- 每個 action 用自己 action-specific first signal(唔可以個個都係 CTA clicks)
- Scale rule 必含:baseline 對比 + 相關 signal + lead-quality guardrail(有數據先)+
  owner approval + 無數據時只做 public QA

## 測試
`.venv/bin/python tests/test_autonomous_quality_gate.py` — 30/30
(包含 §13 全部 deterministic validators + Golden A/B regression)
External auditor outage = fail-closed(唔會 pass-open)
