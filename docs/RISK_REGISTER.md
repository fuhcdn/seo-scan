# RISK REGISTER — seoscanaudit.com

| ID | WS | 嚴重性 | 風險 | 證據 | Owner | 緩解/狀態 |
|---|---|---|---|---|---|---|
| R-A1 | A | **Critical** | 真卡第一單 E2E 未跑過 — production 收錢→交付成條鏈無真實驗證 | 99_上線前檢查清單 §三.4「launch gate,缺呢個唔算賺到錢」;無 revenue_log paid 行 | **Yan** | 待 owner 親手跑真卡單+人手覆核;agent 已備 checklist |
| R-A2 | A | **High** | 孤單/死單無 watchdog — Popen 死/container 重啟冇人 retrigger;13 條 test order 卡 running ~38h | server.py spawn 為 detached subprocess;無 reconcile | agent | Phase 1 候補:durable job + watchdog reconcile(需 design) |
| R-A3 | A | **High** | 付款後黑暗期 — 無付款確認 email,客俾錢到收報告前 24h 冇聲氣 | server.py 無 confirmation email route | agent(需 approval 寄信內容) | proposal 待批 |
| R-A4 | A | **High** | fail-safe(insufficient-evidence)報告唔送客 — 客俾錢可能收到嘢都冇 | pipeline_runner 生成 fail-safe 唔 email | agent | Phase 1 候補 |
| R-A5 | A | ~~High~~ **RESOLVED(2026-09-13晚)** | live 定價顯示 79/99 vs config 497/997/397 矛盾 | **再驗證**:live `/` 同 `/en` 均 US$497/997(4CEO cron 輪部署後);本地 landing_zh-Hant 同;之前 79/99 係舊 cached 版本 | ✅ 已解 | 留意將來 deploy 後再驗一次 |
| R-A6 | A | High | 單點故障 — 全盤 build 喺 1 VPS + 1 container + JSON 檔 | 無 backup automation 現狀以外 | agent | ROLLBACK.md 有手動 backup;自動化屬 backlog |
| R-A7 | A | Medium | production post-render scanner 仍 zlib(raw)而非 pypdf-only | pipeline/pdf_scanner.py + pipeline_runner.py:509 | agent | canonical service 已有 pypdf scan喺 step_deliver 前執行(Phase 1);舊 scanner 仍喺 research step 後執行(可移除) |
| R-A8 | A | Medium | 無 security headers / /api/status 無認證 | server.py | agent | backlog P1 |
| R-A9 | A | Medium | git remote PAT token 喺 .git/config(非 gitignore) | 4CEO record 提及 | **Yan** | 建議改 SSH/credential helper;唔可 agent 自改 |
| R-A10 | A | Low | server.py docstring 過時(稱 checkout 係 placeholder) | server.py:12-25 | agent | doc fix safe,backlog |
| R-B1 | B | **Critical** | 零獲取引擎 — 首單 100% 靠 owner outreach | DECISION_4CEO 客戶獲取 3 分 | **Yan** | 需 owner 策略;agent 唔可做 outbound |
| R-B2 | B | High | 品牌唔一致 — seoscanaudit.com vs 「SEO Scan.ai」 | og:site_name/logo | **Yan** | 品牌決定,唔可 agent 自改 |
| R-B3 | B | High | 無樣本報告/社會證明(現有「Illustrative」testimonial 係假證明風險) | live landing | **Yan** | 建議出真脫敏 Golden 樣本;需批 |
| R-B4 | B | Medium | checkout 8 必填欄摩擦 | DECISION_4CEO | **Yan 批** | proposal 待批 |
| R-B5 | B | Medium | 無自家 SEO/sitemap.xml 404 | web extract | agent | safe fix backlog |
| R-B6 | B | Medium | 無監察/告警(淨 /health) | 無 uptime probe | agent | backlog |
| R-B7 | B | Low | mobile/無障礙未實測 | DECISION_4CEO | agent | backlog |
| R-B8 | B | Medium | 退款無自助化 + landing「7日全退」vs 政策條件式不一致 | cron 4CEO review | **Yan** | legal/pricing,唔可 agent 自改 |
| R-B9 | B | High | 支援信箱 legal@/privacy@/refund@ 未確認開通 — 反彈=法律風險 | IMPLEMENTATION_RECORD_4CEO | **Yan** | owner action |

## 備註
- 所有 agent 可安全修嘅(Phase 1 目標):R-A2/A3/A4/A7/A10/R-B5/R-B6
- 全部 R-B 同 R-A1/R-A5/R-A9 需 owner 決定/批准
- 更新規則:任何新發現立即加行;唔好隱藏 unresolved
