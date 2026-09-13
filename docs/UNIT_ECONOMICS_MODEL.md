# UNIT ECONOMICS MODEL — Owner-Input 模型（零 fabricated numbers）

> 指令 §7 要求:唔可以 invent 財務數字;要列清楚 owner 要俾咩 input。

## 已知/可計（系統實測）
| 項 | 現狀 | 備註 |
|---|---|---|
| 每報告 AI/research 呼叫次數 | 約 8-12 次 OpenRouter chat(高階 8 SERP+盲審+可能的修復輪) | repo 實測 |
| 每報告 crawl | 約 10-15 頁 | pipeline_runner 實測 |
| PDF render | Chromium ×1 | 實測 |
| Email | 1 封(Resend/SMTP) | 實測 |
| 重試/修復輪 | 平均 ~1.5 輪(apple loop 實測 2 輪) | 實測 |

## Owner 要提供嘅 input（我唔估）
1. **Stripe 費率**:standard 2.9%+US$0.30? 或你有咩 plan
2. **OpenRouter 實際每報告 USD 成本**:由你 OpenRouter dashboard 攞(我哋唔讀 key,你貼數字或截圖 OK)
3. **月目標單量**:3-5 之後係幾多?
4. **VPS 月費**:Hostinger 實際付緊幾多
5. **每張卡支援時數**:你有幾多分鐘跟進一單
6. **推廣時間值**:你 outreach 每小時值幾多(機會成本)

## 計算框架（拿到 input 後即刻計）
```
每單收入        = US$497（或 397 founding）
− Stripe fee    = 收入 × % + 固定
− AI 成本       = 呼叫數 × 每次平均(你提供)
− 基礎設施分攤  = VPS 月費 ÷ 月單量
− 支援成本      = 每單支援時數 × 你時值
= 每單毛利

月毛利 = 每單毛利 × 月單量 − 固定工具費
Break-even 單量 = 固定成本 ÷ 每單毛利
```

## 初步 ballpark（標明:假設值,等你核實）
以 typical Stripe 2.9%+$0.30 計:
- US$497 → fee ≈ US$14.7
- 即使 AI 成本 US$5-15/單(典型 LLM pipeline) + VPS 攤分極細
- **每單現金毛利粗估 >US$450(>90%)**——同 4-CEO 之前嘅 ~90% 毛利評估一致
- **主風險唔係 margin,係 demand(RB-1/RB-2)**
