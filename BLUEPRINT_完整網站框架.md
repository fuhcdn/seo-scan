# BLUEPRINT — AI 全自動 SEO 審計網站「完整可執行框架」
> 整合 4 CEO（Bezos 策略 / Jobs 設計 / Musk 技術 / Jensen 營運・品質）結論。
> 用途：Yan set 一個 long-run goal 之後，AI 跟住呢份由第一日一路 done 到「真收到錢」。
> 依賴：`96_Yan一次性提供清單.md`（要 Yan 開嘅帳號）、`mvp-to-first-dollar` skill（gate/rubric 定義）、`05_評分卡.md`。
> 本文件 = long-run goal blueprint，係唯一權威版本；底下任何 roadmap 都唔可以同呢份衝突。

---

## 總目標（一句）
建一個 5 語言、Apple/Spotify 風格、內容 100% AI 自動但高質嘅 SEO 審計網站，由「貼 URL → 自動爬+評分 → AI 出 fix → 自動 PDF/email 交付」全程零人手，做到「真 Stripe 收到第一筆 US$79 收款 + 第一單真客由購入到攞 PDF 唔卡住」，用真付費客戶代替無限自審。

---

## 一、網站設計框架（視覺 / 結構 / 5 語言 UX）

### 1.1 視覺系統（Jobs 把尺：簡潔到「理所當然」）
- **美學錨**：Apple 嘅留白同剷走雜訊 ＋ Spotify 嘅深色襯鮮色 accent。唔做「AI 生成感」嘅漸變紫金。
- **基底**：深色 mode 為預設（`#0B0B0F` 諧音近黑），淺色 mode 為次要選項；一套 token 出兩種，唔准兩套分開寫死。
- **配色**：字＝近白灰階（#F5F5F7 / #AEAEB2 / #6E6E73 三級層次）；accent＝單一鮮色（Spotify 綠 #1DB954 或 Apple 藍 #0A84FF 揀一個，所有 CTA/狀態都用同一隻）。
- **字體**：系統字棧 system-ui（-apple-system / Inter / SF Pro），唔載第三方 web font（速度＋Apple 原生感）。
- **圓角/微互動**：卡片 12px 圓角、狀態點有呼吸 pulse、數字有 count-up 動畫——但要克制，Jobs 會問「呢個互動係咪令人更信，定只係得意」。
- **嚴格扣分**：任何裝飾如果唔係幫「用戶秒懂自己係咪 SEO 有問題」，一齊剷走。

### 1.2 頁面結構（一條主線，唔好堆砌）
全站只有 4 種頁面，每種一個核心任務：
1. **Landing**（一個核心 hook：「10 分鐘得到你網站 SEO 病咩 + 點修」）→ 一個 CTA「免費掃描」。
2. **Free 結果頁**（掃描完即時出：總分／top 3-5 問題標題）→ 一個 CTA「解鎖全部 47+ 項修復」，收住。
3. **付款/Checkout**（Stripe Hosted，唔自己整 payment form，少一個 PCI 面數少一份風險）。
4. **Paywall 後完整報告頁**（fix detail + code + export PDF）＋ 5 種語言嘅 PDF/email 交付。

每頁只有 1 個主 CTA（Jobs：一條主線，一個叫「去做」嘅嘢，其他喺下面 fade out）。

### 1.3 5 語言 UX 框架（Bezos：機制可規模，唔靠每種語言人手執）
- **i18n 結構**：`i18n/{code}/` 每語言一個 `ui.json`（靜態 UI 文案）＋ `report_{code}_*.json`（AI 生成內容模型化）。加語言＝加一個 folder，唔使改 code。
- **語言偵測**：`Accept-Language` header 優先 → 次選 cookie/URL path `/zh-TW/` → 最後 fallback 英文。
- **預設英文（Yan 指定）**：未偵到任何線索就係英文，避免首見用戶見到唔識嘅語言而跳走。
- **語言選擇器**：放在導航右上角（地球 icon），兩層：顯示區域名稱（English / 繁體中文 / Español…）而唔係 code；揀完寫 cookie 記憶，全站持久。殘缺語系：未完成翻譯嘅語言 UI 會出「beta」徽章，唔好用半成品呃人（Jobs 唔接受打折品質）。
- **AI 內容語言**：AI 打分 prompt 注入 `target_lang`，報告/email/PDF 全部跟語言輸出；翻譯用 AI 一次過出，唔用逐句硬譯——但**每次運作要過 reviewer gate 先算數**（見第二節）。
- **RTL/數字排版**：5 種語言初版都係 LTR，暫唔處理 RTL（阿拉伯語唔入初版），edge case 寫入 roadmap。

### 1.4 User flow（客旅程零卡位）
貼 URL → 免費 scan（<120 秒）→ 出 free 結果 → 想睇全部 → Stripe 付款（一次式/4 次包）→ 自動重掃 + 完整報告 + PDF + email 原文到貨 → `/api/status` 全 done。每一步都有進度感，無死路。

---

## 二、內容品質框架（可識別嘅 rubric ＋ reviewer gate）

> Jensen 精神：AI 全自動唔等於冇人把關——用**機器 reviewer gate** 做品質保險，唔靠人手睇。

### 2.1 三層品質閘（產出唔可以直出，逐層過）
- **L1 結構閘（硬規則，機檢）**：報告每個 sections 非空、無 placeholder、無「Lorem」、無空欄、字數下限（每 fix 至少 1 句點解 + 1 句點修）、非法字元/編碼無異常、語言欄同 UI 一致。
- **L2 事實閘（機檢）**：報告內每個數字來自爬取結果/評分卡，唔可以 AI 作數；引述嘅 URL 真係喺 crawl list；「重複」「缺失」呢啲 verdict 同 raw data 對得啱。checklist 用 ground truth 打勾，唔靠 AI 自認。
- **L3 語意閘（AI reviewer——自己出完自己審）**：用第二個獨立 AI pass（唔同 temperature/prompt）做 reviewer：評「有冇一條主線 / 有冇具體到客做到 / 有冇過度承諾 / 有冇語感奇怪」。評分 < threshold 就翻工一次，仲係唔過退回 blocking，記入 log（唔好無限期重試燒錢——Musk）。

### 2.2 可辨識嘅 rubric（人一眼睇得出「咩叫做好」，得分可重複）
每份報告打分（1-3 分，全部≥2 先放行），對應 4 CEO：
- [Bezos] 可重複：同 URL scan 兩次結果一致，機制可規模。
- [Bezos] 個別問題有「點解」+「點修」，唔係堆 keyword。
- [Jobs] 一條主線：一個核心結論（「你最主要死因係 X」）領住成份報告，開頭 30 秒讀得完。
- [Jobs] 客旅程零卡位：每個 fix 具體到用戶跟得住，唔慒。
- [Jensen] 深度＝護城河：唔淨係 surface checklist，有 platform 層分析（crawl 覆蓋、competitor 對照）。
- [Musk] 唔靠簡報：證據係真 crawl log / raw data，唔係 AI 話係就係。
- [Musk] 有講「唔」：功能有 cut 過，唔係乜都做齊嘅堆砌。

### 2.3 免費 vs 付費界線（防火牆，Jobs 定性）
免費只有「總分 + top 3-5 問題標題」；完整 fix detail + code + PDF 全部喺 US$79 paywall 後。**免費絕唔洩付費內容**——security 由 row-level 權限隔離，唔靠前端 hiding。免費版本質係「有價值但唔完整」，令人想睇完整版。

### 2.4 語言品質
英文為 gold standard；其他語言由 AI 生成後，與英文版做 round-trip 對照一致性檢查（機檢）。所有 CTA/承諾字眼 5 語言同義一致，唔可以有某個語言誇大（合規＋Bezos 誠信）。

---

## 三、賺到錢嘅完成 gate（收款真通 ＋ 第一單驗證）

> Musk/Bezos：唔係「code 功能齊晒」就完——係「真收到一筆錢」先算。以下全部勾晒先算 DONE。

### 3.1 Launch gate（全勾）
- [ ] **收款真通**：真 Stripe（live）webhook 接收過 checkout.session.completed → `/api/status` 交易紀錄有實錄。sandbox 唔算；用真 test 卡跑通一次入帳。
- [ ] **付費防火牆**：免費 account 用盡方法都拎唔到 fix detail/code/PDF（權限隔離驗證過）。
- [ ] **端到端零人手**：由「貼 URL」到「email 收到 PDF」冇一步靠人，全程自動化跑通。
- [ ] **交付真出**：真客 URL（唔係自寫樣本）→ 爬+評分無空欄 → 自動 PDF → email 原文；log 有即時證據。
- [ ] **陌生人測試**：揾一個完全唔識個系統嘅人，由 landing 買到攞到 deliverable 唔卡住。

### 3.2 第一單驗證（「賺到錢」實錘，缺呢個唔計完成）
- [ ] 第一個真客戶真付款 US$79 → 真收到 PDF → email 到貨，全程無人手介入。
- [ ] 毛利 ~90% 兌現（成本只有 API/host，無人手成本）。
- [ ] 有客行過 sales ladder（$79 單次 / $350 4次包）。
- [ ] 可以大量 sell（唔靠逐個揸手）。

### 3.3 偏軌停機線（CEO4 即停）
任何畀 CEO 睇嘅任務，入場先 check：唔直接幫收入升？→ 停。人手 >50%？→ 停做更自動。客單 <US$79？→ 要解釋。唔可大量賣？→ 改。唔符 CEO 即時提醒 Yan「返返去賺錢 track」並記入 `04_決策紀錄.md`。

---

## 四、必須由 Yan 確認嘅問題（最少化；其餘全部用預設）

> Bezos：要 Yan 確認嘅愈少愈好，其餘畀死好嘅預設。以下係**確實會改變你做嘢**嘅問題，先至問。

1. **收款價格定案**：`US$79 單次 + US$350 / 4次包`（唯一個案：`96_` 清單寫 US$79，`mvp-to-first-dollar` 寫 $99/$350——要 Yan 揀死一個數字，全站/config 同步）。← 唔可以留兩個數字。
2. **5 種語言確定**：繁中 + 英文 + 我建議嘅 3 種（見第五節）。Yan 一句收定，其他全部落 i18n folder 就自動出。
3. **退款政策立場**：自動退款 vs 人手覆核（HK 冇法定冷靜期，呢個係自己定）。default＝聯絡回覆人手覆核（因為退款唔會大量發生，人手成本低，唔使造自動化）。
4. **收款法律身份**：用個人定公司收款 → 決定 invoice 點出（Jensen 合規）。
5. **付款頁**：用 Stripe Hosted Checkout（default，推薦）定自行 embed 表格。← 淨係喺有合規偏好先問，否則用 Stripe Hosted。

其餘如配色（Spotify 綠）、字體、hosting（Render/Railway 邊個都得）、email provider、免費/付費界線（4 CEO 已拍板）——**全部用本文預設，唔使問**。

---

## 五、建議嘅最常用 3 種語言（附理由）

> 前提：英文預設 + 繁中指定。以下 3 種係「最常用／最值得」嘅（Bezos：顧客價值 + 可規模 + 有錢買）。

**推薦組合：西班牙文 + 葡萄牙文 + 法文**
- **西班牙文（Español）**：全球母語/第二語言用戶超過 5 億，網絡使用量排頭幾位，覆蓋西班牙＋全部拉丁美洲（墨西哥、阿根廷、哥倫比亞等大量中小企/代理商落緊地做 SEO）——用戶基數大兼且大量 SMB 做生意要 SEO，兩樣都強。**最高優先**。
- **葡萄牙文（Português）**：巴西係全球最大葡文市場、互聯網用戶數世界級，中小企數碼化急速，每單 AOV 符合 $79 model，代理商生態活躍。**次高優先**。
- **法文（Français）**：除咗法國，仲覆蓋加拿大魁北克同成個非洲法語市場，用戶總數大 + 有高購買力市場夾雜，同西葡文互補唔重疊。

**替代方案（如果 Yan 想用「最常用 *母語人口*」計）：** 西班牙文 + 葡萄牙文 + **印地文（Hindi）**——但印度單一用戶購買力偏低，對 $79 收費 model 效益差，所以**唔建議**；或者西班牙文 + 葡萄牙文 + **日文**（高 AOV、SEO 需求大，但母語人口細，適合「高客單」路線優先）。
**我嘅 default 落盤：西+葡+法**，因為響「最多人」同「最會買 $79 報告」之間最平衡。Yan 確認一句即鎖死。

---

## 六、呢套框架點自動遵循（executor / reviewer / error-handling）

> Jensen 平台精神：一套機制，唔靠逐次人盯。每個 long-run goal 執行時，AI 自動載入下面三部分。

### 6.1 Executor（做嘢嗰層）
- 開工**即刻**抽出 `gate + rubric + 賺到錢線`（來自 `mvp-to-first-dollar`），寫入 task 開頭自動勾選清單。
- 每步只做「收錢必要」嘢，唔擴 scope（Step 2 技術債全部推去「有真客先做」）。
- 建功能一律模組化（i18n / crawler / scoring / report / payment / email 分開 module），平台複利同時俾 Musk 砍 scope。
- **必作工具**：真跑真客 URL、真爬取、真 Payment 串通——證據來自真實執行，唔係自稱。

### 6.2 Reviewer（把關嗰層）
- 交貨前自動扮 **4 CEO 靜態把尺**（預先聲明，評分唔走出嚟磨）：Bezos 機制/可逆性、Jobs 一條主線/有 cut、Musk 睇產出唔睇簡報/講樽頸、Jensen 有 platform 深度/有冇低估整合。
- 每個 review 每個維度一句話 + 1-3 分，全部≥2 先放行；任何唔達標 → 落返一項修正再跑，唔死就唔磨。
- **唔可以自稱合格**：要附證據（log、實體檔案、輸出樣本）先算數。

### 6.3 Error-handling（停低嘅規則）
- **分類**：Yan 必須自己做（無權限/無帳號：Stripe live、email sender、host 公開 URL、webhook 驗證、OpenRouter key）vs Agent 可做（純 code）vs 做唔到。
- **唔可以停「做唔到」**：要做唔到嘅嘢先記入 `troubleshoot_追蹤.md` + `04_決策紀錄.md`，繞過繼續下一項，有證據先算真阻塞。
- **Yan 一次性清單並行**：`96_` 清單所有要 Yan 開嘅嘢，開工即刻並行問攞，唔好等 code 完成先問（Musk：唔串行拖）。
- **限重試**：AI reviewer 翻工最多 1 次，仲係唔合格就退回 blocking 記 log，唔好無限期重試燒 API 錢（Musk 樽頸）。
- **回報語言**：對 Yan 用廣東話，每完成一輪即刻講「今次改進咗咩」，唔好等全部完先講。

---

### 完成軸線（由 long-run goal 一路到錢）
Step 0 策略（因果鏈 + 一次性清單並行）→ Step 1 產品（最細可賣交付）→ Step 2 技術（淨收錢必要段）→ Step 3 營運 gate（一單真收款行通全鏈）→ Step 4 收錢後 fast-follow（re-buy + 合規補全 + 技術債）——每一步逐條勾上面 gate，全勾先話 DONE，任何偏軌由 CEO 即停。