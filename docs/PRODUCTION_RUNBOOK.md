# PRODUCTION RUNBOOK — seoscanaudit.com

## 環境
| Env | 位置 | Container | Port |
|---|---|---|---|
| Production | VPS /deploy/seo/app/ | app-seo-scan-1 | 8000 |
| Staging | VPS /deploy/seo-staging/ | seo-staging-seo-staging-1 | 8080 |
- VPS: 187.53.137.215 (srv1970379.hstgr.cloud), Ubuntu 24.04 + Docker + Traefik
- Traefik: seoscanaudit.com → 8000 (TLS letsencrypt);staging 未指 DNS
- SSH: paramiko (venv /tmp/deployenv);root password 於 secrets(VPS_ROOT_PW)

## Deploy 步驟
1. 本地改 code + py_compile + tests(`.venv/bin/python tests/test_autonomous_quality_gate.py`)
2. tar 打包 pipeline/ + gates/ + tests/fixtures/
3. SFTP 上 VPS `/deploy/` → tar 解壓
4. `docker cp ... staging:/app/{pipeline,gates}/` → 驗證 → `docker compose up -d --build`
5. 同樣流程 production(必須 staging 驗證通過先上)
6. Deploy 後 smoke test:/health、/、5 語言、/success、/legal 全 200

## ⚠️ Container rebuild 注意
- Rebuild 會**重置**手動 pip install(例如 pypdf)
- 修法:確保 requirements.txt 係 source of truth;rebuild 後即刻
  `docker exec <c> pip install -r /app/requirements.txt` 或 Dockerfile 內加裝
- Rebuild 亦可能帶返舊版 pipeline 檔案 — deploy 時必須全量 docker cp

## Rollback
- Git:tag `baseline-good-before-quiet-authority-redesign-20260912-1900`(9f483c3)
- VPS backup:`/deploy/backup-legal-*`(legal)、`/backups/seo-scan/20260912-1900/`(全套)
- 指引:ROLLBACK.md(完整)

## Job 重試 / 交付失敗
- Order 狀態:output/order_<id>.json,每 step 有 status
- 交付 retry:DELIVERY_MAX_ATTEMPTS 內 email 重試(現有)
- 卡死 order:現無 watchdog;backlog B2
- 手動 re-trigger:pipeline_runner 可單獨重跑(order id 作參數)

## Monitoring / Alerts(現狀薄弱)
- 只有 GET /health
- 建議:UptimeRobot/外部 probe + 每日 cron 檢查 running>6h orders + email 失敗告警

## Health check 快速指令
```
curl -s https://seoscanaudit.com/health   # {"ok":true,...}
curl -s https://seoscanaudit.com/ -o /dev/null -w '%{http_code}\n'  # 200
```

## 升級/escalation
- 真實訂單 DELIVERY_BLOCKED → 立即通知 owner
- Stripe webhook 連續失敗 → 檢查 secrets.env + Stripe dashboard
- 付款後 24h 無交付 → 視為 incident
