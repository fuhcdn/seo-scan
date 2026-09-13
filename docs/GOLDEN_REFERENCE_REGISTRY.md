# GOLDEN REFERENCE REGISTRY

| Ref | Customer | Domain | 產品 | 語言 | Business model | Status | 用途 |
|---|---|---|---|---|---|---|---|
| **A** | Apple Imprints | appleimprints.com | US$497 | English | Quote-based custom-product/service SME(apparel print/embroidery) | **FROZEN — SAFE_STAGING_PROTOTYPE_PASS** | shared-change regression fixture only |
| **B** | The Brunner Law Firm | thebrunnerlawfirm.com | US$497 | English | Professional legal service / consultation conversion | **PASS(Phase 1 regenerate,canonical delivery)** | 跨垂直 generalisation regression |
| C | (候補) | — | US$497 | English | 第三 genuinely 唔同 SME(Phase 2) | NOT STARTED | generalisation 驗證 |

## 規則
- Golden A **唔准再 tune**,除非 shared change 發現真 regression
- 任何 shared pipeline 改動後,A+B 都要跑 regression
- 新 Golden 候選必須:真實 SME、公開可爬、有真轉換 route、business model 與現有 materially 唔同、有足夠 public evidence
- Fixture 檔案:tests/fixtures/golden_evidence_cards_{appleimprints,brunnerlaw}.json + gate1_{...}_pages.py

## Apple Imprints 特性(回歸檢查用)
- ACT-003 = DO NOW(gallery captions)
- ACT-001/002/004/005 = VALIDATE_FIRST
- ACT-004 係 method-to-project routing(需要 Sales/Operations 批)
- road map Days 0-7 淨 ACT-003 live

## Brunner 特性(回歸檢查用)
- 全部 5 actions = VALIDATE_FIRST(法律內容需 attorney 批)
- First 7-Day Preparation Plan(唔係 Quick Win)
- Journey Map 用 ACT-001..005(唔係 GB-)
- roadmap 由每 action 自己 roadmap_preparation/publication_condition 生成
- Approver:Lead Attorney / Owner-Service Manager
