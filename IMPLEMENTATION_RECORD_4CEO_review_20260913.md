# Implementation record — 4-CEO review R1 fixes (autonomous, 2026-09-13 18:30 UTC)

## Issues fixed (R1, low-risk reversible content/trust)
1. **Legal placeholder emails** — `[your-domain].com` (en masters) + `[你的域名].com` (zh-Hant root masters, default-served)
   → replaced with `seoscanaudit.com` aliases (legal@/privacy@/refund@seoscanaudit.com).
   Removed a live hard-fail "placeholder" defect visible on every legal page.
2. **Invalid double `<option selected>` in `landing_zh-Hant.html`** — both `/en` and `/zh-Hant` carried `selected`,
   so `report_language` could resolve to `/en` (English report for a 繁體中文 customer) on engines that pick the first
   selected. Now only `/zh-Hant` is selected. All other 4 languages were already single-selected.

## Evidence of defect (pre-fix)
- `grep -rn '[your-domain]' pipeline/` = 4 hits (en), `grep '\[你的域名\]' pipeline/legal/` = 4 hits (zh-Hant root).
- Live `https://seoscanaudit.com/legal/*` served `[your-domain]` / `[你的域名]` (verified via curl).
- `landing_zh-Hant.html:147-148` two `selected` attributes.
- VPS prod container `app-seo-scan-1` before rebuild: `grep -c 'value="/en" selected'` > 0, legal placeholder hits = 8.

## Fixes made (verified on disk then deployed to live)
- 7 files committed locally: `pipeline/landing_zh-Hant.html`, `pipeline/legal/en/01-terms-of-service.md`,
  `pipeline/legal/en/02-privacy-policy.md`, `pipeline/legal/en/05-refund-policy.md`,
  `pipeline/legal/01-服務條款-ToS.md`, `pipeline/legal/02-私隱政策-PDPO.md`, `pipeline/legal/05-退款政策.md`.
- Git: `fbe3c16` (clean, exactly 7 files). Pushed to `origin/master` (fuhcdn/seo-scan).
- Security hardening: `chmod 0600 secrets.env` + `secrets.env.bak` (was 0644 — live Stripe/Resend/Gmail secrets world-readable).

## Deploy (bake-in; /deploy/seo/{app,staging} are NOT git repos → SFTP bundle + docker compose rebuild)
- Backups on VPS: `/deploy/backup-legal-1789323314` (staging), `/deploy/backup-legal-1789323344` (prod) — original legal + landing files.
- Staging: SFTP 7 files → `/deploy/seo-staging/pipeline/…`; `docker compose up -d --build`; verified container
  `seo-staging-seo-staging-1`: placeholder=0, `/en selected`=0, health 200. PASS.
- Production: SFTP 7 files → `/deploy/seo/app/pipeline/…`; `docker compose up -d --build`; `app-seo-scan-1` recreated+started.
  Verified container: placeholder=0, `/en selected`=0, health 200.
- Live (via Cloudflare) after deploy: `/health` 200; home 200; all 5 languages + /success + legal pages 200;
  legal placeholder count = 0 on `/legal/privacy`, `/legal/refund`, `/legal/privacy/en`, `/legal/terms/en`;
  `/zh-Hant` serves single `selected`=`/zh-Hant`.

## Rollback
- Repo: commit `fbe3c16` (current) / prior `31dc945`. Baseline tag `baseline-good-before-quiet-authority-redesign-20260912-1900` (9f483c3).
- VPS original files: `/deploy/backup-legal-1789323344/` (prod), `/deploy/backup-legal-1789323314/` (staging).
- To roll back prod content: `cp /deploy/backup-legal-1789323344/legal/* pipeline/legal/` then `docker compose up -d --build` in /deploy/seo/app.

## Remaining risk / open items (NOT auto-fixed this cycle)
- Support mailboxes (`legal@/privacy@/refund@seoscanaudit.com`) referenced in legal pages — must confirm they are provisioned/forwarded or the emails bounce. **Owner action.**
- Several R2 structural items surfaced by 4-CEO (see report): no payment-confirmation email; fail-safe (more-info/insufficient-evidence) never delivered to customer; two-engine disconnect (certified `gates/` renderer not wired into production delivery); no watchdog/monitor for orders stuck in `running`; 13 test orders sitting `running` for ~38h; git remote PAT token in `.git/config`. These need a dedicated (non-cron) staging session.