# CHANGELOG_AGENT — 自主改動紀錄

格式:日期 | commit | 改動 | 理由 | 測試 | rollback

## 2026-09-13
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
