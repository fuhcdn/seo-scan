# AP-3 PROPOSAL — Insufficient-Evidence / Delivery-Failure Policy

Status: **PROPOSAL_ONLY / OWNER_APPROVAL_REQUIRED**
零退款、零法律修改、零客戶電郵、零 public policy 改動。本文件係決策提案俾 owner。

---

## 1. Customer-safe states (state machine)

| State | Exact trigger | 自動系統動作 | Research retries? | Max retry/時限 | 客戶溝通 | 報告交付狀態 | Remedy options | Owner decision | 財務/支援風險 | Legal/policy 依賴 |
|---|---|---|---|---|---|---|---|---|---|---|
| **intake_incomplete** | 必填 intake 欄位缺失/格式錯(如 email invalid、URL 空) | Webhook 唔會 spawn;order 標 failed;唔收下游 | 否 — 需客戶補料 | 無(等人補) | 需要:請客戶補齊(若已付款) | NOT DELIVERED | 補料後重跑 / 退款(退前) | 退款批唔批 | 低(未交付無成本) | 退款政策 §條款 |
| **website_unreachable** | crawl 連續 N 次無法連到客戶網站(DNS/timeout/5xx) | 記 website_unreachable;自動重試 crawl | 是 — 指數退避,最多 3 次/24h | 3 次/24h | 需要:通知「網站暫時無法訪問」 | NOT DELIVERED | 等網站回來重跑 / 換 URL / 退款 | 換 URL 係咪免費重跑 | 中(crawl 成本已支出) | 退款政策 |
| **website_not_customer_owned** | URL domain 與 order 提交嘅公司資料明顯不符(SSRF/競爭對手/第三方) | 即刻 STOP;標 manual_support_required | 否 | — | 需要:請客戶確認正確 URL | NOT DELIVERED | 提供正確 URL 重跑 | 邊個部門判 ownership | 低 | 私隱/授權書 |
| **insufficient_public_evidence** | research 完成但 <頁數/SERP 門檻(如 $497 需最少有效 SERP 數未達) | 生成 fail-safe 誠實文件;唔寄當正常報告 | 是 — 可加查詢/擴頁(3 次) | 3 次/24h | 需要:誠實說明 + remedy 選項 | **NOT DELIVERED(等 remedy 決定)** | 見 §2 選項表 | **Yan 揀 remedy** | 中 | 退款政策 |
| **research_source_blocked** | SERP/搜尋來源 429/bot-block(無法攞真實 SERP) | injection hook 試外部 SERP;否則標 blocked | 是 — 換 source/退避 | 3 次/6h | 需要延遲通知 | NOT DELIVERED | 等重試 / 補資料 / 退款 | 退/換 | 低-中 | 無 |
| **quality_gate_failed** | 90 閘/盲審 <90 或 hard fail | 系統自動 QUALITY_REPAIRING(唔寄) | 是 — 修復循環 | 最多 3 修復輪 | 唔需要(內部) | NOT DELIVERED | 若最終失敗→見 §2 | 失敗後 remedy | 中(AI 成本) | 無 |
| **temporary_delivery_failure** | email 發送失敗(SMTP/Resend 錯誤) | canonical sender retry(3 次) | 是 | 3 次/15min | 需要(如最終失敗):通知交付延遲 | PENDING→FAILED | 手動補寄 / 退款 | 補寄人手批唔批 | 低 | 無 |
| **manual_support_required** | watchdog/escalation 觸發(重試耗盡、未知狀態) | Job 標記;通知 owner;唔自動再做 | 停 | — | 需要:人手跟進 | HELD | 人手處理 | 每單人手決 | 低-中 | 無 |

**Terminal states**:(依 AP-1)`email_sent` / `delivery_failed` / `insufficient_public_evidence` / `manual_support_required` / `cancelled`。

---

## 2. INSUFFICIENT_PUBLIC_EVIDENCE — Remedy 選項表(3-5 個,不選擇,不實作)

| # | Option | 客戶體驗 | 執行成本 | 財務影響 | 法律/policy 風險 | 適用場景 |
|---|---|---|---|---|---|---|
| O1 | **客戶補充澄清/額外 URL** | 要客戶再做一步(摩擦) | 低 | 零 | 低(冇承諾新嘢) | 客戶有姊妹站/明確網站範圍未講清 |
| O2 | **允許替換為另一個合資格網站** | 客戶揀第二個網站重跑 | 中(re-run research) | 零(單次重跑) | 低(要一句「同價更換」) | 客戶入錯 URL/網站真係太小 |
| O3 | **縮窄範圍嘅 public-web snapshot 報告** | 客收到嘢但範圍細(可能覺得唔抵) | 中 | 零 | 中(要清楚標示 scope 限制,避免「俾少咗」感) | 證據夠做一個較窄但誠實嘅報告 |
| O4 | **客戶 credit/免費 re-run** | 客戶保留價值感 | 中-高 | 犧牲一次報告成本 | 中(要界定 credit 期限/次數) | 客戶網站短期維修中/問題喺我哋 |
| O5 | **全額退款** | 最乾淨,信任保護 | 低 | 直接損失一單收入 | 高(要跟退款政策 §條款;自動 vs 人手批) | 證據完全唔夠+客戶不滿 |

**建議 default(待 owner 揀)**:階梯式 — 先 O1,若客戶唔回應/唔可行 → O2;O3 只作明示縮範圍客戶同意;O4/O5 需 owner 個案批。

## 3. 決策點(owner)
1. 揀 default remedy 順序
2. 每個 remedy 嘅客戶溝通 wording(要人手寫定,唔可以即興)
3. 自動化程度:O1-O2 可否自動提出(但唔可以自動退款)
4. 退款邊個環節要人手批(建議:全部退款需 owner approve)
5. 政策文案更新到 refund policy page(需 legal review)

## 4. 明確唔做
- 唔揀任何 option
- 唔實作任何退款
- 唔修改 legal/refund 頁面
- 唔發任何客戶電郵
