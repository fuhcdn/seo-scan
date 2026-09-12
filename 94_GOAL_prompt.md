# 🎯 GOAL PROMPT — seoscanaudit.com 上線到收款

> 呢個 prompt 直接套用咗 Gary Chen《讓 AI 停不下來的關鍵是 evaluation》(你 send 嘅 YouTube) 嘅 5 元素框架：
> **1. Outcome(完成係咩) / 2. Verification(點證明) / 3. Constraints(唔准掂邊啲) / 4. Iteration policy(每輪之間做咩) / 5. Error handling(幾時停)**。
> 目的：令 AI 唔偏題、唔提早收工、產出符合 Yan 品味同「要可賣錢」嘅最終目標。呢個唔係普通 prompt，係一份有明確完成標準同自檢機制嘅 goal。

---

## 1️⃣ OUTCOME — 最終要做到咩狀態（唔達標就唔算完成）

將 seoscanaudit.com 由「未上線」做到可以**立即賣錢**，並具備足夠證明顯示**80% 把握三日內收到第一筆真 US$497**。具體輸出：

- 網站 seoscanaudit.com **正常上線**(HTTP 200，無 530)，訪客入到、scan 到、付款到
- **網頁設計係頂級/最高質**：跟 CEO2 Jobs 標準——Apple 淺色風、極簡留白、單一品牌色、無 AI slop（無 tech gradient / 無三卡堆砌 / 無假數據 / 無 Emoji 亂放），可直接媲美世界級 SaaS landing page
- 5 種語言(Landing)：英文 + 繁中 + 簡中 + 日 + 西班牙，一次過齊，全部真本地化
- 權威信賴徽章喺 hero 最頂，係真
- 定價 $497 / $997 / 首50早鳥 $397(只宣傳、唔顯示已售數)
- 免費 scan → $497 → 交付，全程自動零人手
- 內容「個性化」：唔會再「攞乜網站都一樣分」
- **所有流程走得通(端到端)**:免費scan→付款→交付→email→取報告 冇一步斷，冇死路
- 4 CEO 用評分卡一致通過「可以做實」先算完成

## 2️⃣ VERIFICATION — 點證明真做到（唔靠自稱，靠證據）

每一步完成都要附上**可驗證證據**，冇證據當冇做：

- 網站上線：`curl -I https://seoscanaudit.com` 返 **200**，唔再係 530
- 收款鏈通：用 Stripe **test** 落一單 → `webhook` 收到 `checkout.session.completed` → `pipeline` 出到真 PDF → `/api/status=done`，全程 log 有記錄
- 個性化：攞兩個唔同網站(例如一間電商、一間本地服務)跑，報告 fix list **字面唔同**、各有 site-specific 數據
- 免費版界線：免費版只俾總分/問題數/Top3/1個quick-win/網站類型；「點改」鎖咗，API response 冇完整 how_to_fix
- 5 語言：每種語言頁都 200，有對應 translation key，唔漏
- 定價顯示：landing 顯示 $497/$997/$397，同 Stripe price 一致
- **頂級網頁設計**：用 design skill 自查 + 截圖睇，確認無 AI slop（無 tech gradient / 無三卡等權堆 / 無假數據 / 無 Emoji 亂放）。Apple 淺色風、留白、單一品牌色做到位。
- **流程走得通(端到端)**：真落一單由 scan→付款(test)→webhook→PDF→email→/api/status=done 全鏈跑通，中間冇 404/死路/斷 step。每一跳都有回應。

## 3️⃣ CONSTRAINTS — 唔准掂嘅嘢（防止搞壞）

- ❌ **唔准造假**：唔准 fake 統計、fake 社會證明、fake「已售數」、fake 案例、fake 權威認證
- ❌ **唔准擅自改已拍板決定**：定價 $497/$997/$397、退款(交付前退/交付後重審)、5語言、首50早鳥只宣傳唔顯示已售數 —— 呢啲唔可以改，除非 4 CEO 一致同意
- ❌ **唔准刪走權威信賴徽章 / 退款政策 / 合規文件**
- ❌ **唔准將免費版做成「示範完整版」**（一示範點修，客就唔會俾錢）
- ❌ **唔准公開 YouTube/教程噏得出嘅假數字**
- ❌ **冇 4 CEO 一致,唔准宣佈「可賣」**

## 4️⃣ ITERATION POLICY — 每輪之間做咩（唔停低咁磨）

- 每完成一步，用廣東話記低：**改咗咩 / 結果係咩 / 證據喺邊**（寫入 `troubleshoot_追蹤.md`）
- 每步由「executor」做主，由「reviewer」驗證(證據夠唔夠 / 符唔符合上面 VERIFICATION / Constraints)
- 唔合格 → 唔好扮完成，返轉頭改，之後再驗
- 4 CEO 每一位有自己把尺(見下節)，全部過先算一致性通過
- 每步迭代最多做 N 輪，做唔到就「Error handling」停止並報告

## 5️⃣ ERROR HANDLING — 幾時停、點報告（唔好無腦 loop）

遇到以下情況，**停低**並用廣東話向 Yan 報告「遇到羊阻塞，需要你決定」：
- 需要 Yan 親手做但我做唔到(例如：Stripe KYC、真 live 出貨權限、要 Yan 開私人服務)— 呢啲唔會死磨 code，會列出嚟等 Yan 開
- 同一 step 試咗 3 次都失敗(例如部署 530 解決唔到、API 權限唔夠) → 停低，記清楚試過咩、卡咩、要 Yan 俾咩
- 遇到不符合「已拍板決定」嘅位 → 唔擅自改，向 Yan 確認
- 遇到唔清楚/唔確定 → 用「要問 Yan」記錄，唔好估

---

## 👔 4 CEO 驗收準則（質量超高質 = 你要嘅產品）

每位 CEO 用自己把尺逐條 check，**全部合格先算一致通過**。

**[Bezos–機制/收款/規模]**
- [ ] 收款鏈真通：Stripe→checkout→webhook→交付，無人手，有收入日誌+冪等
- [ ] 顯示價 = 實收款(頁面 $497 就收 $497)
- [ ] 唔呃人數字(首50只宣傳唔顯示已售數、冇假deadline)
- [ ] 可大量賣(有 re-scan/升級/4次包 入口)
- [ ] 退款政策真可行(交付前退/交付後重審)，寫入 ToS+checkout

**[Jobs–產品/深度/品味]**
- [ ] 主線清晰(一份報告一個核心訊息：「有咩問題、優先執三樣」)
- [ ] 改進方法具體到客可跟(點改+點解+預期效果+幾多功夫，唔係「改善SEO」)
- [ ] 個性化(兩網站報告唔同，有 site-specific 數據)
- [ ] 免費版 10-20%(俾診斷/鎖執行)
- [ ] 權威信賴徽章係真、放 hero 最頂
- [ ] 5 語言真本地化(非機翻，繁中正字/日文敬語/當地慣例，數字URL唔郁)
- [ ] **網頁設計係頂級**：無 AI slop，媲美世界級 SaaS landing page(Apple簡潔/留白/單一品牌色)
- [ ] **端到端流程走得通**：scan→付款→交付→email 全鏈無斷路，真單跑通

**[Musk–技術/成本/性能]**
- [ ] 真引擎(crawl 真網→真評分→真 fix，唔 hardcode 樣本)
- [ ] 成本受控(每單 LLM < US$3，毛利 ~90%)
- [ ] 性能(landing 快、scan <30秒)
- [ ] 5 語言架構正確(英文 master→locale，hreflang/canonical)
- [ ] 可 scale(SSRF/rate-limit 防護喺)

**[Jensen–營運/合規/信任]**
- [ ] 5 份合規文件(ToS/私隱/退款/免責/授權書)，退款&私隱立場一致
- [ ] email consent(明確 tick，唔預設勾)
- [ ] 信任(徽章/案例/聲稱全部真實可驗證)
- [ ] 免責(報告係建議非保證排名，AI 出錯有免責)
- [ ] 首單真支付→交付→人工覆核，有證據先當「賺到錢」

## 🔑 你要嘅產品(一句總結，4 CEO 對住判)
> 幫「已有網站有生意想改善 SEO」嘅人、收 $497、質量超高質(個性化+具體改進方法+權威基準)、5 語言、全自動零人手、誠實唔呃人(真徽章/真退款/真數字)、可 3 日內透過 warm-lead 收到第一筆真錢。

## ⚙️ 執行架構(跟 Gary Chen 個片：executor + reviewer)
- **Executor**：做任務(部署/改 code/生成內容)，產出證據
- **Reviewer**：每輪檢查(證據夠唔夠 / 符唔符 Outcome/Constraints / 4 CEO 尺過唔過)，唔過就 reject 返 executor 改
- 你(主 agent)同時扮演 executor + 收集 4 CEO 把尺做 reviewer
- **4 CEO 全檢未過，一律唔准宣布「可賣」**

## 📦 已就緒資料(直接用，唔使再問)
- Stripe：key 喺 `/opt/data/seo-audit-business/secrets.env`；3 price=$497/price_1UEr9ZPHGhgirSOryPB39nin、$997/price_1UEr9pPHGhgirSOrckEVvel8、$397/price_1UEr9pPHGhgirSOrgzKbo2SX；webhook 已接 https://seoscanaudit.com/webhook/stripe
- VPS：`srv1970379.hstgr.cloud` IP `187.53.137.215`，Ubuntu24.04+Docker+Traefik，running
- Hostinger：用 @hostinger/mcp
- 定價：$497/$997/$397；退款：交付前退/交付後重審；實體：個人
- 網站：seoscanaudit.com(530→200)；Apple淺色；5語言；個性化深度v1
- 技能：seo-audit / web-design-guidelines / claude-design / popular-web-designs / design-md / web-perf

## 📦 三日內第一單計劃（Warm-Lead，非有機流量）
三日內第一單唔可以靠自然流量（網站啱啱上線零排名）。要用 Warm-Lead 主動收第一筆：
1. **揀 3-5 間真實目標**：香港/華語區有網站、有生意、SEO 明顯有改善空間嘅中小企（餐廳/美容/補習/電商/Freelancer 等），逐間填返名單 `leads.csv`（網站URL + 聯絡方式）
2. **逐間免費 scan**：用我哋個真人 crawler 幫佢個真實網站跑一次免費診斷（出總分 + Top3 + 網站類型識別先，唔洩完整「點改」）
3. **Send 個性化診斷 + 直接付款 link**：帶住佢個網站真實問題（「你主頁載入6.8秒、有34條死link、呢個keyword排第9」）＋早鳥 $397 一次性 Stripe Payment Link，直接 WhatsApp/email 俾對方
4. **目標**：5 間入面收返 1-3 單 = 三日內第一筆真錢
5. **驗證**：真單 → Stripe 收到 → webhook → 交付 → 人工覆核 → 記錄 revenue_log
- 呢步可以同部署並行做，但**網站未上線優先部署**，確保客撳付款 link 有嘢睇到

## 4️⃣ 首單人工覆核（Jensen 驗收，硬性）
- 第一筆真支付：Stripe 收到 → pipeline 出 PDF → email 送到 → **Yan 人手睇一次**確認份報告對得住 $497
- 未完成首單人工覆核前，唔准當「賺到錢」
- 之後再測一單壞路徑(bad email / SSRF / 重複ref)確認 production 韌