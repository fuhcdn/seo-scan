# 💎 4 CEO 完整方案整合 + 權威基準 = 最終新版 blueprint

## 背景
Yan 完整要求（質量唔夠/個性化死症/免費10-20%/target係已有生意想改善/定價要HK$2-3k/跟權威模板/Apple淺色風/5語言西葡法/零服務/5種一次齊）。
4 CEO 已由完整脈絡做埋方案，權威基準已搜晒。

## 新定位
幫「已經有網站、有自己生意、想改善 SEO 提升收入」嘅人。
免費 = 診斷（證明我識嘢）；付費 = 執行藍圖（即刻改好）。

## 定價（4 CEO 最終一致：US$497 主力）
- Free（誘餌，俾 10-20% 診斷，唔俾執行）
- **Standard 主力 US$497 ≈ HK$3,900**（全站完整執行藍圖）——企住 HK$2-3k 下限
- **Growth US$997 ≈ HK$7,800**（4 條錢頁 page-level 深挖，企業續租）
- Agency/Retainer US$2,500+/月（唔擺面頁沖淡主軸）
- **刪走 US$79/99 +「首20客」低錨**（CEO1 明文反折扣語言）
- 分歧已解：CEO1 新錨 $497 vs CEO2/3/4 舊錨 $99 → 按 Yan「HK$2-3k 下限」採納 CEO1
- 高單價先撐得起深度 LLM 成本（每單 <$3，$497 margin 充足）

## 免費版 10-20% 界線（全 CEO 共識：分界喺「價值類型」唔係份量）
**俾（診斷，10-20%洞見，0%執行）：**
- 總分 gauge /100、問題總數+緊急數
- 五大支柱分佈
- Top 3 問題完整講解（標題+點解+影響+可提分）
- 預期修後分數（+18分）
- 1 個真實 quick-win 修法
- 網站類型識別（「你係水電公司」→證明唔係模板）
- 免費 PDF 摘要（攞 email 做 lead）

**收（執行，80-90%）：**
- 每個問題「點樣修/how_to_fix」← 解鎖位
- 第4條以後所有講解、全部 code snippet
- 競爭對手差距表、Top-10 優先行動計劃、90日 roadmap

**技術硬邊界：** 鎖定項 server 端控制，唔喺 /api/scan 傳完整 how_to_fix；免費 PDF 用獨立 free template（唔由付費裁）

## 質素提升（針對「一樣分數」死症）
4 CEO 技術共識（CEO3 2份 + CEO2）：
- **Site Fingerprint**：開頭偵測網站原型（電商/content/本地/SaaS/blog）+ 技術棧 + 規模 + 競爭玩法
- **兩級評分**：Stage1 通用底層（對齊權威）→ Stage2 個性化層（權重向量逐站計，拉高該站關鍵維度）
- **深度指標**全程式化（零LLM）：字數/H1樹/薄內容/alt覆蓋/schema錯誤/孤兒頁
- **爬取 adaptive**：免費5-10頁，付費100-500頁
- **數字全部計出嚟**：固定權重×維度，兩個站同分含義唔同
- **每條 finding 咬實**：真實URL + 實測數字 + 計出嚟嘅價值

## 報告模板（跟權威 agency 7-8 sections）
01 Verdict/老闆摘要（≤2頁，一句+總分+Top3）→ 02 Performance baseline → 03 技術健康 → 04 內容+意圖 → 05 架構+內鏈 → 06 Backlinks → 07 優先行動計劃（Impact×Effort / Quick wins / 30-60-90日）→ 08 方法論附錄

**每條 finding 7格：** 標題+嚴重度 / 證據(真URL) / 點解蝕錢(生意損失) / 點改 / 點解咁改 / 預期效果 / 成本(時長+難度)
**Priority Score = (影響×覆蓋×概率)÷努力** — 自動計，唔靠人排

## 質量 Gate（Jensen 5道，已入評分卡）
A獨特資訊（每finding≥1個實測證據，冇就剔除）/ B深度（≥N條page-level）/ C非模板（>30%重複判fail重跑）/ D再現性 / E抽樣QC（每10抽1）

## 收款監控（補漏）
收入日誌 revenue_log.csv（session_id/event/金額/語言/事件型/webhook_id冪等）；三層監控：收入日誌有paid行=收到錢、交付完成=交付咗、日誌總和=Stripe dashboard對得上

## 多語言合規
Phase1 英文+繁中先上（5份合規文件齊）→ 每加語言成套包袱齊晒先解鎖；私隱最硬無得延遲；email capture 要 consent checkbox；退款承諾寫入每語言ToS

## i18n（5語言）
英文 master → 5 locale .json + glossary鎖術語；靜態模板stable ID；動態findings原語言審計最後批次翻；CI強制5語key齊

## 執行優先序（CEO3）
1) 指紋+adaptive權重+爬取伸縮 2) 程式化深度指標 3) 引用URL fix生成 4) 競爭對比 5) i18n 6) 成本調校
先做最值：免費界線落地 + Gate A(獨特資訊) + 收入日誌（+定價確認）

## 要 Yan 拍板
1. 定價：497 vs 149+追蹤 vs 訂閱
2. 免費 Top3 vs Top5 A/B
3. 確認開始實作（我已 ready 落 code）