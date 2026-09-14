# REVENUE BLOCKER REGISTER

| ID | Sev | Funnel stage | Blocker | 實證 | Safe next / smallest test | Success metric | Owner approval? |
|---|---|---|---|---|---|---|---|
| RB-1 | **Critical** | Acquisition | 零 outbound engine——首單 100% 靠 owner 手工 | pipeline 零 lead loop;leads.csv 只有 22 條舊手揀 | 3 日 demand test(已規劃) | ≥2 qualified replies | **YES(outreach send)** |
| RB-2 | **Critical** | Trust | 零 case study/testimonial/樣本——客無從判斷品質 | landing 全 Illustrative 標示;無真客 | 建一頁「Sample Report」用 Golden B 非敏感節錄(safe, reversible) | sample 頁瀏覽→checkout 進入率 | NO(可自主,屬網站 safe copy) |
| RB-3 | **High** | Pricing/offer | 「首50 US$397」無真 scarcity 機制——唔可以 fake;但亦無「為何現在買」誠實理由 | live landing | 提案:誠實 founding-cohort 條款(見 OFFER_EXPERIMENTS) | 轉化不跌+信任升 | YES(price/offer) |
| RB-4 | **High** | Trust | Email identity 專業缺口:EMAIL_FROM fallback=onboarding@resend.dev(客會見 resend.dev) | code: pipeline_runner.py:728 | owner 做 Resend domain 驗證+信箱(需 DNS) | From 變 noreply@seoscanaudit.com | **YES(DNS/mailbox)** |
| RB-5 | High | Checkout | 8 必填欄摩擦(4-CEO 評過) | landing intake | 提案精簡至 4-5 欄(唔可自改) | form start→submit 提升 | **YES(欄位變更)** |
| RB-6 | High | Delivery | 真卡 E2E | **RESOLVED** — owner 確認已親自跑過真卡(2026-09-13) | owner 聲明 | 待 revenue_log/Stripe dashboard 對賬核實 | ✅ |
| RB-7 | Medium | Lead quality | 冇明確 ICP 定位喺網站——「邊個應該買我哋」唔清晰 | landing copy | 自主:safe copy 說明適合對象(quote/enquiry-based SME) | bounce rate↓ | NO |
| RB-8 | Medium | Report | 報告深度被 4-CEO 評「generic」——已多輪修,但缺乏第三方第三方驗證嘅 customer voice | Golden samples only | 首個真客 feedback → case study | 1 個真客 quote | YES(真客通訊) |
| RB-9 | Medium | Ops | 單點故障:1 VPS+JSON,無 backup automation | RISK_REGISTER R-A6 | backup cron(自主,零 external) | 每日 backup 存在 | NO |
| RB-10 | Low | Post-sale | 退款無自助化 | refund policy | proposal 等批 | - | YES |

## Top 3 優先(RB-1/2/4)
最小行動:
1. RB-2 sample 頁——**我而家可做**（用 Golden B 內容,唔含客戶敏感）
2. RB-1 outreach package——**等你批**
3. RB-4 mailbox/domain——你親手(指引可寫)
