# BACKLOG — 按優先排序嘅未完成工作

## Phase 1 剩餘(agent 可自主,safe/reversible)
- [x] B2. ✅ Watchdog/durable job reconcile — DONE(AP-1,12/12 tests,stuck test orders archived)
- [x] B5. ✅ server.py docstring 更新 — DONE(7acc233)
- [x] B6. ✅ /sitemap.xml + robots.txt — DONE(staging 200 驗證,7acc233;production deploy 待下輪 bundle)
- [ ] B1. 移除 pipeline_runner 內舊 zlib post-render scan — **保留**(owner 指示:legacy scanner 作 secondary defense-in-depth 直至 evidence_v1 approved rollout)
- [ ] B7. Security headers(CSP/HSTS/X-Frame-Options 等)
- [ ] B8. /api/status 認證(token or order-id-bound)
- [ ] B9. Uptime probe + 基本告警(external free tier 可)
- [ ] B10. Automated backup cron(order json + reports + legal)

## Phase 2 候選(需 owner 批先開始)
- [ ] P2-1. 第三 Golden Reference(另一 genuinely 唔同 SME business model)→ generalisation 驗證
- [ ] P2-2. evidence_v1 完全接管 production(需 E2E)
- [ ] P2-3. 樣本報告 gallery(真脫敏 Golden A/B)
- [ ] P2-4. US$997 Growth Blueprint implementation(明確規格:實質更深,唔係 497 加頁數)

## Owner 決定/批准 needed
- [ ] O1. 真卡第一單人手覆核(launch gate)
- [ ] O2. live 定價 79/99 vs 497/997/397 矛盾排查+統一
- [ ] O3. 品牌統一(seoscanaudit.com vs SEO Scan.ai)
- [ ] O4. 支援信箱開通(legal@/privacy@/refund@)
- [ ] O5. 退款政策統一(7日 vs 條件式)+ 自助化
- [ ] O6. Checkout 欄位精簡
- [ ] O7. git remote PAT → SSH/credential helper
- [ ] O8. 獲取策略(outbound/content/SEO)

## 完成定義
每項:branch → test → staging → verify → deploy → monitor → document → rollback-ready
