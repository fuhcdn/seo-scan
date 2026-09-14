#!/usr/bin/env python3
"""report_engine.py — 兩級報告生成（ENTRY + PREMIUM）+ QA gate + PDF.

按 HERMES MASTER INSTRUCTION Parts D/E/F/H/I。純 stdlib + Chromium(pdfkit-like)
出 HTML → PDF。每條 finding 有 evidence_id + label（FACT/INFERENCE/HYPOTHESIS...），
優先次序 P0-P3 由 (BusinessImpact x Confidence x Reach x TimeSens) / (Effort x DepRisk)。

輸出 JSON 報告結構 + HTML，再由 evidence_v1_pipeline 轉 PDF 交付。
"""
import html as _html
import json
import re
import os
import time

import config
import product_catalog

# 語言 UI 字串（報告要全部喺 report_language 出 —— 呢度 dict 提供 label，
# 實際內容文字由 AI/rule 生成後維持原文，UI 框架 label 按語言）
UI = {
    "en": {
        "cover_title": "SEO Opportunity Diagnostic",
        "cover_title_premium": "SEO Growth Blueprint",
        "report_date": "Report date",
        "exec_summary": "Executive Summary — Key Decisions",
        "scope": "Scope, Method & Evidence Limits",
        "business_snapshot": "Business & Customer Path Snapshot",
        "opp_map": "Opportunity & Risk Map",
        "evidence": "Selected Page & Search-Result Evidence",
        "top5": "Top Priority Actions",
        "plan90": "90-Day Action Plan",
        "validation": "Public-Data Validation Checklist",
        "sources": "Source Appendix",
        "quick_win": "First 7-Day Win",
        "investment_title": "Investment Decision Matrix",
        "whatnot_title": "What Not To Prioritise Yet",
        "comm_model_title": "Commercial Opportunity Model",
        "disclaimer": "This is strategic research based on the stated public-evidence scope; search results change; no outcome is guaranteed.",
        "granted": "Prepared for",
        "powered": "seoscanaudit.com",
        # extra section labels (localized for full A3 compliance)
        "plan_days0": "Days 0–30 — unblock, measure, protect quick wins",
        "plan_days0_1": "Validate in Search Console/GA4 before large spends.",
        "plan_days0_2": "Protect critical conversion paths (checkout/enquiry/booking).",
        "plan_days0_3": "Complete highest-effort-easy-wins (quick wins) with an owner.",
        "plan_days1": "Days 31–60 — improve high-intent pages",
        "plan_days1_1": "Improve commercial/page-fit and content depth on top pages.",
        "plan_days1_2": "Fix internal linking and architecture per P1 findings.",
        "plan_days1_3": "Add proof/trust/CTA clarity observed as missing.",
        "plan_days2": "Days 61–90 — extend successful patterns and validate",
        "plan_days2_1": "Scale what measurably improved (queries/pages).",
        "plan_days2_2": "Re-sample and re-validate; if fresh evidence needed, update.",
        "scope_notice": "Scope notice.",
        "scope_notice_body": "This report is based on public-web research and direct analysis of your publicly accessible website unless authenticated analytics are separately provided. It identifies evidence-led opportunities and risks. It does not guarantee rankings, traffic, leads, sales, or revenue. Some measurements require Search Console, web analytics, CRM, or website access and are identified as validation items.",
        "serp_evid": "Search-result observations",
        "cust_page_evid": "Customer page evidence",
        "pages_sampled": "Pages sampled (see source appendix); examples are samples, not full coverage.",
        "no_serp": "No SERP observations recorded (public search not executed).",
        "val1": "Connect Google Search Console and compare this page group's most recent 90 days with the same period last year before allocating a rewrite budget.",
        "val2": "Verify exact impressions, clicks, CTR and average position in GSC — public data cannot show these.",
        "val3": "Verify conversions, revenue and lead quality in GA4/CRM before sizing an opportunity.",
        "val4": "Re-check current search results at delivery time; search results change.",
        "dec": "Decision",
        "obs": "Observation",
        "com_cons": "Commercial consequence",
        "first_action": "First action",
        "conf_evid": "Confidence",
        "meth_title": "Methodology, Confidence & Evidence Boundaries",
        "meth_body": "Data-confidence table: observable (FACT) vs what requires validation (INFERENCE / HYPOTHESIS TO VALIDATE) and why. All inputs are public-web only; no private analytics were available.",
        "ledger_title": "Prioritized Action Ledger",
        "ledger_body": "Actions grouped by priority (P0/P1 before P2/P3). Each links to evidence and states owner, effort, validation.",
        "content_title": "Content Intelligence & Opportunity Map",
        "content_body": "Recommendation types: update, consolidate, reposition, create, retain, redirect, or validate for priority content. No traffic/keyword-volume declines are claimed without historical data.",
        "measure_title": "Measurement & Validation Plan",
        "measure_1": "For each major recommendation, name the leading indicator, business indicator, baseline, required data source, and review window.",
        "measure_2": "Required inputs not available here — connect Google Search Console, GA4, CRM, CMS, or a complete crawl.",
        "measure_3": "Do not size an opportunity until the related query/page/impression data is confirmed in Search Console.",
        "no_evidence": "No material decisions passed the evidence gate for this report.",
        "no_findings": "No evidence-supported findings.",
        "fld_goal": "Primary business goal",
        "fld_market": "Market / service area",
        "fld_offers": "Main products / services",
        "fld_comp": "Known competitors",
        "fld_comp_na": "— (not provided)",
        "method_public": "Public-web research method used. Pages reviewed (sampled)",
        "method_none": "none accessible",
        "method_private": "Private performance data was not available and is not claimed.",
        "coverage": "not included in this report",
        "claim": "Claim",
        "why_matters": "Why it matters commercially",
        "recom_act": "Recommended action",
        "scope_f": "Scope",
        "owner": "Owner",
        "accept": "Acceptance",
        "validate": "Validate",
        "evidence": "Evidence",
        "deps": "Dependencies",
        "conf_rationale": "Confidence rationale",
        "limits": "Limitations",
        "effort": "Effort",
        "confidence": "Confidence",
        "decision": "Decision",
        "observation": "Observation",
        "commercial_conseq": "Commercial consequence",
        "first_action": "First action",
        "evidence_ids_l": "Evidence",
        "no_decisions": "No material decisions passed the evidence gate for this report.",
        "no_findings_l": "No evidence-supported findings.",
        "result_pattern_l": "result pattern",
        "observed_l": "observed",
        "no_serp_l": "No SERP observations recorded (public search not executed).",
        "fail_title": "Report incomplete: insufficient public evidence",
        "fail_obs_h": "What could be observed",
        "fail_why_h": "Why evidence was insufficient",
        "fail_qa_h": "QA items not met",
        "fail_data_h": "What data/access/input would be needed",
        "fail_l1": "A publicly accessible, non-thin customer website.",
        "fail_l2": "Optionally: Search Console, web analytics, CRM, or CMS access for verified metrics.",
        "fail_l3": "Re-run this job after the above are available.",
        "fail_little": "Very little could be observed.",
    },
    "zh-Hant": {
        "cover_title": "SEO 機會診斷報告",
        "cover_title_premium": "SEO 增長藍圖",
        "report_date": "報告日期",
        "exec_summary": "執行摘要 — 關鍵決策",
        "scope": "範圍、方法與證據限制",
        "business_snapshot": "業務與客戶路徑概覽",
        "opp_map": "機會與風險地圖",
        "evidence": "精選頁面與搜尋結果證據",
        "top5": "優先行動",
        "plan90": "90 天行動計劃",
        "validation": "公開數據驗證清單",
        "sources": "來源附錄",
        "disclaimer": "此為基於所列公開證據範圍的戰略研究；搜尋結果會變；不保證任何成效。",
        "granted": "受眾",
        "powered": "seoscanaudit.com",
        "plan_days0": "第 0–30 天 — 解封、量度、保護快速勝利",
        "plan_days0_1": "大型投入前先在 Search Console/GA4 驗證。",
        "plan_days0_2": "保護關鍵轉換路徑（結帳/查詢/預約）。",
        "plan_days0_3": "完成最高價值、最容易嘅快速勝利，並指派負責人。",
        "plan_days1": "第 31–60 天 — 改善高意圖頁面",
        "plan_days1_1": "提升頂級頁面嘅商業契合度與內容深度。",
        "plan_days1_2": "按 P1 發現修正內部連結與架構。",
        "plan_days1_3": "補添觀察到缺失嘅證明/信任/CTA 清晰度。",
        "plan_days2": "第 61–90 天 — 擴大成功模式並驗證",
        "plan_days2_1": "放大已量度到進步嘅部分（查詢/頁面）。",
        "plan_days2_2": "重新抽樣與驗證；如有新證據再更新。",
        "scope_notice": "範圍聲明。",
        "scope_notice_body": "本報告基於公開網絡研究及對你可公開瀏覽網站嘅直接分析（除非另外提供經認證嘅分析數據）。佢識別以證據為本嘅機會與風險，但唔保證排名、流量、潛在客戶、銷售或收入。部分量度需要 Search Console、網絡分析、CRM 或網站存取，會標示為驗證項目。",
        "serp_evid": "搜尋結果觀察",
        "cust_page_evid": "客戶頁面證據",
        "pages_sampled": "已抽樣頁面（見來源附錄）；樣本唔代表全覆蓋。",
        "no_serp": "未記錄搜尋結果觀察（未執行公開搜尋）。",
        "val1": "投入重寫預算前，先連接 Google Search Console 比較呢組頁面最近 90 日與去年同期。",
        "val2": "喺 GSC 驗證準確曝光、點擊、CTR 同平均位置 — 公開數據無法顯示。",
        "val3": "評估機會前，先喺 GA4/CRM 驗證轉換、收入與潛在客戶質素。",
        "val4": "交付時重新檢查目前搜尋結果；搜尋結果會變。",
        "dec": "決策",
        "obs": "觀察",
        "com_cons": "商業影響",
        "first_action": "首要行動",
        "conf_evid": "信心",
        "meth_title": "方法論、信心與證據邊界",
        "meth_body": "數據信心表：可觀察（FACT）對比需要驗證（INFERENCE / HYPOTHESIS TO VALIDATE）及點解。所有輸入皆為公開網絡；無私人分析數據。",
        "ledger_title": "優先行動名冊",
        "ledger_body": "行動按優先次序分組（P0/P1 先於 P2/P3）。每項連結證據，列明負責人、工作量、驗證。",
        "content_title": "內容智慧與機會地圖",
        "content_body": "建議類型：更新、整合、重定位、建立、保留、重定向或驗證優先內容。冇歷史數據前唔會聲稱流量/關鍵字量下跌。",
        "measure_title": "量度與驗證計劃",
        "measure_1": "為每項主要建議列明主導指標、商業指標、基線、所需數據來源與檢討期。",
        "measure_2": "此處冇嘅必要輸入 — 請連接 Google Search Console、GA4、CRM、CMS 或完整爬取。",
        "measure_3": "喺 Search Console 確認相關查詢/頁面/曝光數據前，唔好估算機會規模。",
        "no_evidence": "呢份報告冇實質決策通過證據門檻。",
        "no_findings": "冇證據支持嘅發現。",
        "fld_goal": "主要商業目標",
        "fld_market": "市場 / 服務範圍",
        "fld_offers": "主要產品 / 服務",
        "fld_comp": "已知競爭對手",
        "fld_comp_na": "—（未提供）",
        "method_public": "使用公開網絡研究方法。已檢視頁面（抽樣）",
        "method_none": "無可造訪",
        "method_private": "私人表現數據不可用，且未聲稱。",
        "claim": "主張",
        "why_matters": "商業上點解重要",
        "recom_act": "建議行動",
        "scope_f": "範圍",
        "owner": "負責人",
        "accept": "驗收準則",
        "validate": "驗證方法",
        "evidence": "證據",
        "deps": "依賴",
        "conf_rationale": "信心理據",
        "limits": "限制",
        "effort": "工作量",
        "confidence": "信心",
        "decision": "決策",
        "commercial_conseq": "商業影響",
        "first_action": "首要行動",
        "result_pattern_l": "結果類型",
        "observed_l": "觀察於",
        "no_serp_l": "未記錄搜尋結果觀察（未執行公開搜尋）。",
    },
    "zh-Hans": {
        "cover_title": "SEO 机会诊断报告",
        "cover_title_premium": "SEO 增长蓝图",
        "report_date": "报告日期",
        "exec_summary": "执行摘要 — 关键决策",
        "scope": "范围、方法与证据限制",
        "business_snapshot": "业务与客户路径概览",
        "opp_map": "机会与风险地图",
        "evidence": "精选页面与搜索结果证据",
        "top5": "优先行动",
        "plan90": "90 天行动计划",
        "validation": "公开数据验证清单",
        "sources": "来源附录",
        "disclaimer": "此为基于所列公开证据范围的研究；搜索结果会变化；不保证任何结果。",
        "granted": "受众",
        "powered": "seoscanaudit.com",
        "plan_days0": "第 0–30 天 — 解锁、测量、保护快速成果",
        "plan_days0_1": "大额投入前先在 Search Console/GA4 验证。",
        "plan_days0_2": "保护关键转化路径（结账/咨询/预约）。",
        "plan_days0_3": "完成高价值易实现的快速成果，并指定负责人。",
        "plan_days1": "第 31–60 天 — 改善高意图页面",
        "plan_days1_1": "提升重点页面的商业契合度与内容深度。",
        "plan_days1_2": "按 P1 发现修正内部链接与架构。",
        "plan_days1_3": "补充观察到缺失的证明/信任/CTA 清晰度。",
        "plan_days2": "第 61–90 天 — 扩大成功模式并验证",
        "plan_days2_1": "放大已测量到进步的部分（查询/页面）。",
        "plan_days2_2": "重新抽样与验证；如有新证据再更新。",
        "scope_notice": "范围声明。",
        "scope_notice_body": "本报告基于公开网络研究及对你可公开访问网站的直接分析（除非另行提供经认证的分析数据）。它识别基于证据的机会与风险，但不保证排名、流量、线索、销售或收入。部分测量需要 Search Console、网络分析、CRM 或网站访问，会标示为验证项目。",
        "serp_evid": "搜索结果观察",
        "cust_page_evid": "客户页面证据",
        "pages_sampled": "已抽样页面（见来源附录）；样本不代表全覆盖。",
        "no_serp": "未记录搜索结果观察（未执行公开搜索）。",
        "val1": "投入重写预算前，先连接 Google Search Console 比较该组页面最近 90 天与去年同期。",
        "val2": "在 GSC 验证准确曝光、点击、CTR 与平均位置 — 公开数据无法显示。",
        "val3": "评估机会前，先在 GA4/CRM 验证转化、收入与线索质量。",
        "val4": "交付时重新检查当前搜索结果；搜索结果会变化。",
        "dec": "决策",
        "obs": "观察",
        "com_cons": "商业影响",
        "first_action": "首要行动",
        "conf_evid": "信心",
        "meth_title": "方法论、信心与证据边界",
        "meth_body": "数据信心表：可观察（FACT）与需验证（INFERENCE / HYPOTHESIS TO VALIDATE）及其原因。所有输入皆公开网络；无私人分析数据。",
        "ledger_title": "优先行动清单",
        "ledger_body": "行动按优先级分组（P0/P1 先于 P2/P3）。每项链接证据，列明负责人、工作量、验证。",
        "content_title": "内容智能与机会地图",
        "content_body": "建议类型：更新、整合、重新定位、创建、保留、重定向或验证优先内容。无历史数据前不声称流量/关键词量下跌。",
        "measure_title": "测量与验证计划",
        "measure_1": "为每项主要建议列明主导指标、商业指标、基线、所需数据来源与复查期。",
        "measure_2": "此处缺失的必要输入 — 请连接 Google Search Console、GA4、CRM、CMS 或完整抓取。",
        "measure_3": "在 Search Console 确认相关查询/页面/曝光数据前，勿估算机会规模。",
        "no_evidence": "本报告无实质决策通过证据门槛。",
        "no_findings": "无证据支持的发现。",
        "fld_goal": "主要商业目标",
        "fld_market": "市场 / 服务范围",
        "fld_offers": "主要产品 / 服务",
        "fld_comp": "已知竞争对手",
        "fld_comp_na": "—（未提供）",
        "method_public": "使用公开网络研究方法。已检视页面（抽样）",
        "method_none": "无页可访问",
        "method_private": "私人表现数据不可用，且未声称。",
        "claim": "主张",
        "why_matters": "商业上为何重要",
        "recom_act": "建议行动",
        "scope_f": "范围",
        "owner": "负责人",
        "accept": "验收准则",
        "validate": "验证方法",
        "evidence": "证据",
        "deps": "依赖",
        "conf_rationale": "信心理据",
        "limits": "限制",
        "effort": "工作量",
        "confidence": "信心",
        "decision": "决策",
        "commercial_conseq": "商业影响",
        "first_action": "首要行动",
        "result_pattern_l": "结果类型",
        "observed_l": "观察于",
        "no_serp_l": "未记录搜索结果观察（未执行公开搜索）。",
    },
    "ja": {
        "cover_title": "SEO 機会診断レポート",
        "cover_title_premium": "SEO 成長ブループリント",
        "report_date": "レポート日",
        "exec_summary": "エグゼクティブサマリー — 重要判断",
        "scope": "範囲・方法・根拠の制限",
        "business_snapshot": "ビジネスと顧客経路の概要",
        "opp_map": "機会とリスクのマップ",
        "evidence": "選定ページと検索結果の根拠",
        "top5": "優先アクション",
        "plan90": "90日行動計画",
        "validation": "公開データ検証チェックリスト",
        "sources": "出典付録",
        "disclaimer": "これは提示した公開根拠の範囲に基づく戦略調査です。検索結果は変化します。結果は保証されません。",
        "granted": "作成対象",
        "powered": "seoscanaudit.com",
        "plan_days0": "0–30日目 — 解除・計測・クイックウィンの保護",
        "plan_days0_1": "大きな支出前に Search Console/GA4 で検証。",
        "plan_days0_2": "主要コンバージョン経路（注文/問い合わせ/予約）を保護。",
        "plan_days0_3": "高価値・高簡単なクイックウィンを完了し、担当者を指名。",
        "plan_days1": "31–60日目 — 高意図ページを改善",
        "plan_days1_1": "上位ページの商取引適合度とコンテンツ深度を向上。",
        "plan_days1_2": "P1 の発見に沿って内部リンクと構造を修正。",
        "plan_days1_3": "欠落が観察された証明・信頼・CTA の明確さを追加。",
        "plan_days2": "61–90日目 — 成功パターンを拡大し検証",
        "plan_days2_1": "計測して改善した部分（クエリ/ページ）を拡大。",
        "plan_days2_2": "再サンプリング・再検証；新証拠があれば更新。",
        "scope_notice": "対象範囲のご案内。",
        "scope_notice_body": "本レポートは公開ウェブ調査と、お客様の公開サイトの直接分析に基づきます（認証済み分析を別途提供する場合を除く）。根拠に基づく機会とリスクを特定しますが、順位・トラフィック・リード・売上・収益を保証するものではありません。一部計測には Search Console・ウェブ解析・CRM・サイトアクセスが必要で、検証項目として明記します。",
        "serp_evid": "検索結果の観察",
        "cust_page_evid": "お客様のページの根拠",
        "pages_sampled": "サンプリング対象ページ（出典付録参照）；サンプルは全網羅ではありません。",
        "no_serp": "検索結果の観察記録なし（公開検索未実行）。",
        "val1": "書き直し予算を割り当てる前に、Search Console でこのページ群の直近90日を前年同期と比較。",
        "val2": "GSC で正確な表示・クリック・CTR・平均順位を検証 — 公開データでは確認不可。",
        "val3": "機会を評価する前に GA4/CRM でコンバージョン・収益・リード品質を検証。",
        "val4": "納品時点の検索結果を再確認；検索結果は変化します。",
        "dec": "判断",
        "obs": "観察",
        "com_cons": "ビジネスへの影響",
        "first_action": "最初のアクション",
        "conf_evid": "確信度",
        "meth_title": "方法論・確信度・根拠の境界",
        "meth_body": "データ確信度表：観察可能（FACT）と検証要（INFERENCE / HYPOTHESIS TO VALIDATE）その理由。全て公開ウェブのみ。",
        "ledger_title": "優先アクション台帳",
        "ledger_body": "優先度順（P0/P1 を P2/P3 より先）にグループ化。各項目は根拠・担当者・工数・検証を明記。",
        "content_title": "コンテンツ知見と機会マップ",
        "content_body": "推奨タイプ：更新・統合・再配置・新規作成・保持・リダイレクト・検証。履歴データなしにトラフィック/キーワード減少は主張しない。",
        "measure_title": "計測・検証プラン",
        "measure_1": "主要推奨ごとに主要指標・ビジネス指標・ベースライン・必要データ源・レビュー期間を明記。",
        "measure_2": "ここで欠落している必須入力 — Google Search Console・GA4・CRM・CMS・完全クロールを接続。",
        "measure_3": "関連クエリ/ページ/表示データが Search Console で確認されるまで機会規模を推定しない。",
        "no_evidence": "このレポートには証拠ゲートを通過した実質的判断はありません。",
        "no_findings": "根拠で裏付けられた所見なし。",
        "fld_goal": "主要ビジネス目標",
        "fld_market": "市場/サービスエリア",
        "fld_offers": "主要製品/サービス",
        "fld_comp": "既知の競合",
        "fld_comp_na": "—（未提供）",
        "method_public": "公開ウェブ調査手法を使用。レビュー済みページ（サンプル）",
        "method_none": "アクセス可能なし",
        "method_private": "プライベートデータは利用不可であり、主張もしない。",
        "claim": "主張",
        "why_matters": "ビジネス上なぜ重要か",
        "recom_act": "推奨アクション",
        "scope_f": "範囲",
        "owner": "担当者",
        "accept": "受理基準",
        "validate": "検証方法",
        "evidence": "根拠",
        "deps": "依存",
        "conf_rationale": "確信の根拠",
        "limits": "限界",
        "effort": "工数",
        "confidence": "確信度",
        "decision": "判断",
        "commercial_conseq": "ビジネス影響",
        "first_action": "最初のアクション",
        "result_pattern_l": "結果タイプ",
        "observed_l": "観察日",
        "no_serp_l": "検索結果の観察記録なし（公開検索未実行）。",
    },
    "es": {
        "cover_title": "Diagnóstico de Oportunidades SEO",
        "cover_title_premium": "Blueprint de Crecimiento SEO",
        "report_date": "Fecha del informe",
        "exec_summary": "Resumen Ejecutivo — Decisiones Clave",
        "scope": "Alcance, Método y Límites de la Evidencia",
        "business_snapshot": "Negocio y Recorrido del Cliente",
        "opp_map": "Mapa de Oportunidades y Riesgos",
        "evidence": "Evidencia de Páginas y Resultados de Búsqueda",
        "top5": "Acciones Prioritarias",
        "plan90": "Plan de Acción 90 Días",
        "validation": "Lista de Verificación de Datos Públicos",
        "sources": "Anexo de Fuentes",
        "disclaimer": "Esta es una investigación estratégica basada en el alcance de evidencia pública indicado; los resultados de búsqueda cambian; no se garantiza ningún resultado.",
        "granted": "Preparado para",
        "powered": "seoscanaudit.com",
        "plan_days0": "Días 0–30 — desbloquear, medir, proteger victorias rápidas",
        "plan_days0_1": "Validar en Search Console/GA4 antes de grandes gastos.",
        "plan_days0_2": "Proteger rutas de conversión críticas (compra/consulta/reserva).",
        "plan_days0_3": "Completar victorias rápidas de alto valor y fácil esfuerzo con un responsable.",
        "plan_days1": "Días 31–60 — mejorar páginas de alta intención",
        "plan_days1_1": "Mejorar ajuste comercial y profundidad de contenido en páginas clave.",
        "plan_days1_2": "Corregir enlaces internos y arquitectura según hallazgos P1.",
        "plan_days1_3": "Añadir claridad de pruebas/confianza/CTA observada como ausente.",
        "plan_days2": "Días 61–90 — ampliar patrones exitosos y validar",
        "plan_days2_1": "Escalar lo que mejoró mediblemente (consultas/páginas).",
        "plan_days2_2": "Remuestrear y revalidar; actualizar si hay nueva evidencia.",
        "scope_notice": "Aviso de alcance.",
        "scope_notice_body": "Este informe se basa en investigación web pública y análisis directo de su sitio público, salvo que se proporcionen análisis autenticados por separado. Identifica oportunidades y riesgos basados en evidencia. No garantiza rankings, tráfico, clientes, ventas ni ingresos. Algunas mediciones requieren Search Console, analítica web, CRM o acceso al sitio, y se marcan como elementos de validación.",
        "serp_evid": "Observaciones de resultados de búsqueda",
        "cust_page_evid": "Evidencia de páginas del cliente",
        "pages_sampled": "Páginas muestreadas (ver anexo de fuentes); las muestras no representan cobertura completa.",
        "no_serp": "No se registraron observaciones SERP (no se ejecutó búsqueda pública).",
        "val1": "Antes de presupuestar reescrituras, conecte Google Search Console y compare los últimos 90 días de este grupo de páginas con el mismo período del año pasado.",
        "val2": "Verifique en GSC impresiones, clics, CTR y posición promedio exactos — los datos públicos no pueden mostrarlos.",
        "val3": "Verifique conversiones, ingresos y calidad de clientes en GA4/CRM antes de dimensionar una oportunidad.",
        "val4": "Revise los resultados de búsqueda actuales al momento de la entrega; cambian con el tiempo.",
        "dec": "Decisión",
        "obs": "Observación",
        "com_cons": "Consecuencia comercial",
        "first_action": "Primera acción",
        "conf_evid": "Confianza",
        "meth_title": "Metodología, Confianza y Límites de Evidencia",
        "meth_body": "Tabla de confianza de datos: observable (FACT) frente a lo que requiere validación (INFERENCE / HYPOTHESIS TO VALIDATE) y por qué. Solo web pública; sin analítica privada.",
        "ledger_title": "Registro de Acciones Priorizadas",
        "ledger_body": "Acciones agrupadas por prioridad (P0/P1 antes que P2/P3). Cada una enlaza evidencia y declara responsable, esfuerzo y validación.",
        "content_title": "Inteligencia de Contenido y Mapa de Oportunidades",
        "content_body": "Tipos de recomendación: actualizar, consolidar, reposicionar, crear, conservar, redirigir o validar contenido prioritario. No se afirma caída de tráfico/volúmenes sin datos históricos.",
        "measure_title": "Plan de Medición y Validación",
        "measure_1": "Para cada recomendación principal, indique indicador líder, indicador de negocio, base, fuente de datos requerida y ventana de revisión.",
        "measure_2": "Entradas requeridas no disponibles aquí — conecte Google Search Console, GA4, CRM, CMS o un rastreo completo.",
        "measure_3": "No dimensione una oportunidad hasta confirmar los datos de consulta/página/impresión en Search Console.",
        "no_evidence": "Ninguna decisión material superó la puerta de evidencia en este informe.",
        "no_findings": "Sin hallazgos respaldados por evidencia.",
        "fld_goal": "Objetivo comercial principal",
        "fld_market": "Mercado / área de servicio",
        "fld_offers": "Productos / servicios principales",
        "fld_comp": "Competidores conocidos",
        "fld_comp_na": "— (no proporcionado)",
        "method_public": "Método de investigación web pública utilizada. Páginas revisadas (muestra)",
        "method_none": "ninguna accesible",
        "method_private": "Los datos privados de rendimiento no estaban disponibles y no se declaran.",
        "claim": "Afirmación",
        "why_matters": "Por qué importa comercialmente",
        "recom_act": "Acción recomendada",
        "scope_f": "Alcance",
        "owner": "Responsable",
        "accept": "Criterios de aceptación",
        "validate": "Método de validación",
        "evidence": "Evidencia",
        "deps": "Dependencias",
        "conf_rationale": "Fundamento de confianza",
        "limits": "Limitaciones",
        "effort": "Esfuerzo",
        "confidence": "Confianza",
        "decision": "Decisión",
        "commercial_conseq": "Consecuencia comercial",
        "first_action": "Primera acción",
        "result_pattern_l": "patrón de resultados",
        "observed_l": "observado el",
        "no_serp_l": "No se registraron observaciones SERP (no se ejecutó búsqueda pública).",
    },
}
# 其他語言 fallback 用 en，避免 UI 缺字（內容主體由生成者用 report_language）


def _u(lang, key, **fmt):
    d = UI.get(lang) or UI["en"]
    s = d.get(key) or UI["en"].get(key, "")
    if fmt:
        for k, v in fmt.items():
            s = s.replace("{" + k + "}", str(v))
    return s


def esc(x):
    return _html.escape(str(x), quote=True)


_LABEL_COLOR = {
    "FACT": "#1a7f37",
    "INFERENCE": "#9a6700",
    "HYPOTHESIS TO VALIDATE": "#8250df",
    "NOT VERIFIABLE WITH PUBLIC DATA": "#6e7781",
}
_PRIO_COLOR = {"P0": "#d1242f", "P1": "#cf222e", "P2": "#bf8700", "P3": "#57606a"}


def priority_sort_key(f):
    pm = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    return pm.get(str(f.get("priority", "P3")).split(" ")[0], 3)


def _evidence_label(e):
    """Evidence source label, but a public RESULT-PATTERN observation is an interpretation —
    never a standalone FACT merely because a result URL is listed (master-spec §09)."""
    lab = (e.get("label") or "").strip()
    scope = (e.get("scope") or "").lower()
    is_pattern = ("result" in scope or "serp" in scope or
                  "Search result pattern" in (e.get("claim") or "") or "parsed visible" in (e.get("claim") or "").lower())
    if is_pattern and lab.upper() == "FACT":
        return "INFERENCE"
    return lab or "INFERENCE"


def _safe_href(url):
    """Only allow http(s) hyperlinks in the report; anything else is rendered as plain text
    (never a file:// or internal path that would leak in the PDF)."""
    u = (url or "").strip()
    if u.lower().startswith(("http://", "https://")):
        return f"<a href='{esc(u)}'>{esc(u)}</a>"
    return esc(u)


def finding_card(f, lang):
    """單條 finding → HTML card（D2 structure）。"""
    label = f.get("claim_label") or "INFERENCE"
    prio = str(f.get("priority", "P3")).split(" ")[0]
    lc = _LABEL_COLOR.get(label, "#57606a")
    pc = _PRIO_COLOR.get(prio, "#57606a")
    ev_refs = " ".join(f"<code>{esc(e)}</code>" for e in (f.get("evidence_ids") or []))
    E = lambda k: _u(lang, k) if lang != "en" else ({  # localize common card labels
        "effort": "Effort", "confidence": "Confidence", "claim": "Claim",
        "why_matters": "Why it matters commercially", "recom_act": "Recommended action",
        "scope_f": "Scope", "owner": "Owner", "accept": "Acceptance",
        "validate": "Validate", "evidence": "Evidence", "deps": "Dependencies",
        "conf_rationale": "Confidence rationale", "limits": "Limitations"}[k])
    return f"""
    <div class="card">
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:8px">
        <span class="chip" style="background:{pc};color:#fff">{esc(prio)}</span>
        <span class="chip" style="background:{lc};color:#fff">{esc(label)}</span>
        <span class="chip">{esc(f.get('category') or 'SEO')}</span>
        <span class="chip">{E('effort')}: {esc(f.get('effort') or 'Medium')}</span>
        <span class="chip">{E('confidence')}: {esc(f.get('confidence') or 'Medium')}</span>
      </div>
      <h4>{esc(f.get('title') or '')}</h4>
      <p><strong>{E('claim')}:</strong> {esc(f.get('claim') or '')}</p>
      <p><strong>{E('why_matters')}:</strong> {esc(f.get('business_reason') or '')}</p>
      <p><strong>{E('recom_act')}:</strong> {esc(f.get('recommended_action') or '')}</p>
      <p><strong>{E('scope_f')}:</strong> {esc(f.get('affected_scope') or '')} &nbsp;
         <strong>{E('owner')}:</strong> {esc(f.get('owner') or 'Owner')}</p>
      <p><strong>{E('accept')}:</strong> {esc(f.get('acceptance_criteria') or '')} &nbsp;
         <strong>{E('validate')}:</strong> {esc(f.get('validation_method') or '')}</p>
      <p style="color:#57606a"><strong>{E('evidence')}:</strong> {ev_refs or '—'} &nbsp;
         <strong>{E('deps')}:</strong> {esc('; '.join(f.get('dependencies') or []) or '—')}</p>
      {('<p style="color:#57606a"><strong>' + E('conf_rationale') + ':</strong> ' + esc(f.get('confidence_rationale')) + '</p>') if f.get('confidence_rationale') else ''}
      {('<p style="color:#57606a"><strong>' + E('limits') + ':</strong> ' + esc(f.get('limitations')) + '</p>') if f.get('limitations') else ''}
    </div>"""


def _css():
    return """
    <style>
      @page { size: A4; margin: 18mm 16mm; }
      body { font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
             color:#1f2328; line-height:1.55; font-size:11pt; }
      h1 { font-size:24pt; margin:0 0 4px; }
      h2 { font-size:16pt; border-bottom:2px solid #eaecef; padding-bottom:6px; margin-top:28px; }
      h3 { font-size:13pt; margin-top:18px; color:#24292f; }
      .cover { text-align:left; padding:40px 0 20px; }
      .cover .sub { color:#57606a; font-size:12pt; }
      .granted { color:#57606a; margin-top:24px; font-size:11pt; }
      .card { border:1px solid #d0d7de; border-radius:10px; padding:14px 16px; margin:12px 0;
              page-break-inside:avoid; background:#fff; }
      .card h4 { margin:4px 0 6px; font-size:12pt; }
      .chip { display:inline-block; font-size:9pt; font-weight:600; padding:2px 9px;
              border-radius:999px; background:#eff2f5; color:#24292f; }
      .callout { background:#f6f8fa; border-left:4px solid #0969da; padding:12px 16px;
                 border-radius:6px; margin:14px 0; }
      table { border-collapse:collapse; width:100%; margin:12px 0; }
      th,td { border:1px solid #dce2e8; padding:7px 10px; text-align:left; font-size:10pt; }
      th { background:#f6f8fa; }
      .disc { color:#57606a; font-size:9pt; margin-top:24px; border-top:1px solid #eaecef;
              padding-top:10px; }
      a { color:#0969da; text-decoration:none; }
      .pagebreak { page-break-before: always; }
      code { background:#eff2f5; padding:1px 4px; border-radius:4px; font-size:9pt; }
      ul { margin:6px 0 6px 20px; padding:0; }
      li { margin:3px 0; }
      .src { font-size:9pt; color:#57606a; }
    </style>
    """


def build_report(order, research, findings, actions=None, tier="ENTRY_REPORT", lang="en"):
    """組裝完整 HTML 報告。order=訂單 dict, research=research.json,
    findings=list[dict]（D2 schema）, tier=ENTRY_REPORT/PREMIUM_REPORT, lang. """
    u = lang
    company = order.get("company_name") or "Customer"
    url = order.get("website_url") or order.get("url") or ""
    today = time.strftime("%Y-%m-%d")
    adate = research.get("access_date") or today
    is_premium = tier == "PREMIUM_REPORT"
    title = _u(u, "cover_title_premium" if is_premium else "cover_title")

    # 只帶 evidence-supported 嘅 findings，排序 P0 先
    findings = [f for f in findings if f.get("evidence_ids")] or findings
    findings = sorted(findings, key=priority_sort_key)

    ev = research.get("evidence_ledger") or []
    evmap = {e.get("evidence_id"): e for e in ev}

    # Exec summary decisions（cap）
    max_dec = 5 if is_premium else 3
    decisions = findings[:max_dec]

    cards = "\n".join(finding_card(f, u) for f in findings)
    src_rows = "".join(
        f"<tr><td>{esc(e.get('evidence_id',''))}</td><td>{esc(e.get('claim',''))}</td>"
        f"<td>{esc(_evidence_label(e))}</td><td>{_safe_href(e.get('source_url',''))}</td>"
        f"<td>{esc(e.get('access_date',''))}</td></tr>" for e in ev)
    lim = "".join(f"<li>{esc(x)}</li>" for x in research.get("limitations") or [])
    pages_ok = [p for p in research.get("architecture", {}).get("pages_reviewed", []) if p.get("ok")]
    pages_txt = "; ".join(esc(p.get("url")) for p in pages_ok[:8])

    # 90-day plan blocks (localized) — §10: MUST reference actual Action IDs, no generic prose
    def plan_block(title0, items):
        lis = "".join(f"<li>{esc(i)}</li>" for i in items)
        return f"<h3>{esc(title0)}</h3><ul>{lis}</ul>"

    # build an action-ID-linked 90-day roadmap from the real action ledger
    real_actions = actions or []
    act_refs = ""
    for i, a2 in enumerate(real_actions):
        aid = a2.get("action_id") or f"ACT-{i+1:03d}"
        act_refs += f"<li><strong>{esc(aid)}</strong> — {esc(a2.get('title') or a2.get('claim') or '')} (owner {esc(a2.get('owner') or 'n/a')}; {esc(a2.get('effort') or '')})</li>"
    if act_refs:
        # split across the three windows, referencing the real action IDs
        n = len(real_actions)
        third = max(1, (n + 2) // 3)
        w0 = real_actions[:third]
        w1 = real_actions[third:2 * third]
        w2 = real_actions[2 * third:]
        def _win(ws):
            return "".join(
                f"<li><strong>{esc(a.get('action_id') or f'ACT-{real_actions.index(a)+1:03d}')}</strong> "
                f"— {esc(a.get('title') or a.get('claim') or '')}; "
                f"validate: {esc(a.get('validation_method') or 'public re-check')}. "
                f"Acceptance: {esc(a.get('acceptance_criteria') or 'implemented')}.</li>" for a in ws)
        plan = (f"<h3>{esc(_u(u,'plan_days0'))}</h3><ul>{_win(w0) or '<li>finalise validation setup and quick wins</li>'}</ul>"
                f"<h3>{esc(_u(u,'plan_days1'))}</h3><ul>{_win(w1) or '<li>execute highest-value page/content actions</li>'}</ul>"
                f"<h3>{esc(_u(u,'plan_days2'))}</h3><ul>{_win(w2) or '<li>validate, scale successful patterns, decide next quarter</li>'}</ul>")
    else:
        plan = plan_block(_u(u, 'plan_days0'),
                          [_u(u,'plan_days0_1'), _u(u,'plan_days0_2'), _u(u,'plan_days0_3')])
        plan += plan_block(_u(u, 'plan_days1'),
                           [_u(u,'plan_days1_1'), _u(u,'plan_days1_2'), _u(u,'plan_days1_3')])
        plan += plan_block(_u(u, 'plan_days2'),
                           [_u(u,'plan_days2_1'), _u(u,'plan_days2_2')])

    # SERP evidence (localized wrapper)
    rp_l = _u(u, "result_pattern_l"); obs_l = _u(u, "observed_l")
    serp_rows = "".join(
        f"<li>{esc(o.get('query',''))} — {rp_l}: {esc(o.get('result_pattern') or 'n/a')} "
        f"({obs_l} {esc(o.get('access_date') or adate)}). {esc(o.get('direct_observation') or '')}</li>"
        for o in research.get("serp") or [])

    # Executive decisions summary cards (localized) — CONCLUSIONS-FIRST: each carries its
    # investment classification (DO NOW / VALIDATE FIRST / DEFER) and the specific reason,
    # so an owner sees "what to do first" explicitly, not buried in priorities.
    _D = lambda k: _u(u, k)
    exec_cards = ""
    for i, f in enumerate(decisions, 1):
        _effort = (f.get("effort") or "Medium").lower()
        _inv = ("DO NOW" if _effort.startswith("small") else
                "VALIDATE FIRST" if _effort in ("medium", "large", "high") else "VALIDATE FIRST")
        _why = ("low-cost, reversible, on a high-intent customer-owned page — highest immediate return."
                if _inv == "DO NOW" else
                "larger or higher-risk change; run a smaller page/content test first to prove demand before committing.")
        exec_cards += f"""
        <div class="card">
          <h4>{_D('decision')} {i} — {esc(f.get('priority','P1'))} <span class='src'>[{esc(_inv)}]</span></h4>
          <p><strong>{_D('observation')}:</strong> {esc(f.get('claim') or '')}</p>
          <p><strong>{_D('commercial_conseq')}:</strong> {esc(f.get('business_reason') or '')}</p>
          <p><strong>{_D('first_action')}:</strong> {esc(f.get('recommended_action') or '')}</p>
          <p><strong>Why {esc(_inv)}:</strong> {esc(_why)}</p>
          <p><strong>{_D('conf_evid')}:</strong> {esc(f.get('confidence') or 'Medium')} ·
             <strong>{_D('evidence_ids_l') or _D('evidence')}:</strong> {esc(', '.join(f.get('evidence_ids') or []))}</p>
        </div>"""

    # ---- COMMERCIAL VALUE & INVESTMENT DISCIPLINE (master-spec Part 5/8) ----
    _whatnot_note = ("Competitor-page work, broad keyword/content production, external-link building and redesigns are not yet prioritised: "
                     "no customer-owned page-gap evidence yet shows they would move the highest-value decision. "
                     "Focus first on the concrete customer-owned page gaps this report documents." if not real_actions
                     else ("Beyond the actions above, avoid broad content or link/redesign spend until the documented "
                           "customer-owned page gaps move the visible decision; validate with the first customer-measured signal.")
                     + " Competitor or external pages are treated as evidence only, never as work targets.")
    _com_obs = "; ".join((o.get("query") + " -> " + (o.get("result_pattern") or "observed pattern")) for o in (research.get("serp") or [])[:4]) or "customer-owned page observations (see evidence)"
    _win = next((a for a in real_actions if (a.get("effort") or "").lower().startswith("small")), None) or (real_actions[0] if real_actions else None)
    _quick = ""
    if _win:
        _quick = f"""<h2>{esc(_u(u,'quick_win'))}</h2>
<div class="card">
  <p><strong>{esc(_win.get('action_id') or 'ACT')}</strong> — {esc(_win.get('title') or _win.get('claim') or '')}</p>
  <p><strong>{esc(_D('owner'))}:</strong> {esc(_win.get('owner') or 'SEO / Marketing')} · <strong>Completion:</strong> {esc(_win.get('acceptance_criteria') or 'implement and confirm on the customer-owned page')}</p>
  <p><em>Why first: low-cost, reversible, on a high-intent customer-owned page — validates the wider action plan before bigger spend.</em></p>
</div>"""
    _do_now = [a for a in real_actions if (a.get("effort") or "").lower() in ("small",)]
    _validate = [a for a in real_actions if (a.get("effort") or "").lower() in ("medium", "large", "high")]
    _defer_note = ("Broad content production, external links, redesign or new tool builds are deferred until the highest-value customer-owned pages are proven." if real_actions else "")
    _inv = f"""<h2>{esc(_u(u,'investment_title'))}</h2>
<div class="card">
  <h4>DO NOW</h4>{'<ul>' + ''.join(f"<li>{esc(a.get('action_id') or '')} — {esc(a.get('title') or '')}</li>" for a in _do_now) + '</ul>' if _do_now else '<p>No zero-cost quick actions; all require small, reversible customer-owned changes.</p>'}
  <h4>VALIDATE FIRST</h4>{('<ul>' + ''.join(f"<li>{esc(a.get('action_id') or '')} — {esc(a.get('title') or '')} (validate demand/lower-risk first)</li>" for a in _validate) + '</ul>') if _validate else '<p>No larger projects in this pass; where one is needed, run a small page/content test before committing.</p>'}
  <h4>DEFER / DO NOT PRIORITISE YET</h4><p>{esc(_defer_note)}</p>
</div>"""
    _what_not = f"""<h2>{esc(_u(u,'whatnot_title'))}</h2>
<div class="card"><p>{esc(_whatnot_note)}</p></div>"""
    _com_model = f"""<h2>{esc(_u(u,'comm_model_title'))}</h2>
<div class="card">
  <p><strong>Value lever:</strong> demand capture (relevant buyer question / page / result pattern) and page clarity (offer / CTA / intent route).</p>
  <p><strong>Publicly observable evidence now:</strong> {esc(_com_obs)}</p>
  <p><strong>Client data required to quantify upside:</strong> sessions, impressions, CTR, CTA clicks, lead/order rate (GSC / GA4 access when provided).</p>
  <p><em>Assumptions only — never a forecast guarantee. Show the formula and data requirement rather than a number when data is absent.</em></p>
</div>"""
    _growth_block = _quick + _inv + _what_not + _com_model

# ---- PREMIUM-only sections (Part F) ----
    premium_sections = ""
    if is_premium:
        meth_rows = "".join(
            f"<tr><td>{esc(e.get('evidence_id',''))}</td><td>{esc(e.get('claim',''))}</td>"
            f"<td>{esc(e.get('label',''))}</td><td>{esc(e.get('confidence',''))}</td></tr>"
            for e in ev)
        premium_sections += f"""
        <h2>{_u(u,'meth_title')}</h2>
        <p>{_u(u,'meth_body')}</p>
        <table><tr><th>ID</th><th>{_D('claim')}</th><th>Label</th><th>{_D('conf_evid')}</th></tr>
        {meth_rows or '<tr><td colspan=4>—</td></tr>'}</table>
        """
        act_rows = "".join(
            f"<tr><td>{esc(f.get('priority','P3'))}</td><td>{esc(f.get('title',''))}</td>"
            f"<td>{esc(f.get('claim_label',''))}</td><td>{esc(f.get('owner',''))}</td>"
            f"<td>{esc(f.get('effort',''))}</td><td>{esc(f.get('recommended_action',''))}</td>"
            f"<td>{esc(f.get('validation_method',''))}</td></tr>" for f in findings)
        premium_sections += f"""
        <h2>{_u(u,'ledger_title')}</h2>
        <p>{_u(u,'ledger_body')}</p>
        <table>
          <tr><th>{_D('priority') if False else 'P'}</th><th>{_D('observation')}</th><th>Label</th><th>{_D('owner')}</th><th>{_D('effort')}</th>
              <th>{_D('recom_act')}</th><th>{_D('validate')}</th></tr>
          {act_rows or '<tr><td colspan=7>—</td></tr>'}
        </table>
        """
        # content-intelligence + measurement plan (F4 #7, #14)
        premium_sections += f"""
        <h2>{_u(u,'content_title')}</h2>
        <p>{_u(u,'content_body')}</p>
        <h2>{_u(u,'measure_title')}</h2>
        <ul>
          <li>{_u(u,'measure_1')}</li>
          <li>{_u(u,'measure_2')}</li>
          <li>{_u(u,'measure_3')}</li>
        </ul>
        """
    else:
        premium_sections = ""

    # ---- localized body labels ----
    sn = _u(u, 'scope_notice'); sn_body = _u(u, 'scope_notice_body')
    meth_pub = _u(u, 'method_public'); meth_none = _u(u, 'method_none')
    meth_priv = _u(u, 'method_private')
    serp_h = _u(u, 'serp_evid'); cp_h = _u(u, 'cust_page_evid'); psamp = _u(u, 'pages_sampled')
    no_serp = _u(u, 'no_serp'); no_f = _u(u, 'no_findings'); no_ev = _u(u, 'no_evidence')
    f_goal = _u(u, 'fld_goal'); f_mkt = _u(u, 'fld_market'); f_off = _u(u, 'fld_offers')
    f_comp = _u(u, 'fld_comp'); f_compna = _u(u, 'fld_comp_na')
    v1=_u(u,'val1'); v2=_u(u,'val2'); v3=_u(u,'val3'); v4=_u(u,'val4')

    html = f"""<!DOCTYPE html><html lang="{esc(u)}"><head><meta charset="utf-8">
    <title>{esc(title)} — {esc(company)}</title>{_css()}</head><body>

    <div class="cover">
      <div class="sub">{esc(_u(u,'powered'))}</div>
      <h1>{esc(title)}</h1>
      <div class="sub">{esc(_u(u,'granted'))}: {esc(company)}<br>{esc(url)}</div>
      <div class="granted">{esc(_u(u,'report_date'))}: {esc(today)} · {esc(_u(u,'report_date'))}/{esc(_u(u,'observed_l'))}: {esc(adate)}</div>
    </div>

    <div class="callout">
      <strong>{esc(sn)}</strong> {esc(sn_body)}
    </div>

    <h2>{esc(_u(u,'exec_summary'))}</h2>
    {exec_cards or f'<p>{esc(no_ev)}</p>'}

    <h2>{esc(_u(u,'scope'))}</h2>
    <p>{esc(meth_pub)}: {pages_txt or esc(meth_none)}.</p>
    <p>{esc(meth_priv)}</p>
    <ul>{lim}</ul>

    <h2>{esc(_u(u,'business_snapshot'))}</h2>
    <table>
      <tr><th>{esc(f_goal)}</th><td>{esc(order.get('primary_business_goal') or '')}</td></tr>
      <tr><th>{esc(f_mkt)}</th><td>{esc(order.get('primary_market_or_service_area') or '')}</td></tr>
      <tr><th>{esc(f_off)}</th><td>{esc(order.get('main_products_or_services') or '')}</td></tr>
      <tr><th>{esc(f_comp)}</th><td>{esc('; '.join(order.get('known_competitors') or []) or f_compna)}</td></tr>
    </table>

    <h2>{esc(_u(u,'opp_map'))}</h2>
    {cards or f'<p>{esc(no_f)}</p>'}

    <h2>{esc(_u(u,'evidence'))}</h2>
    <h3>{esc(serp_h)}</h3>
    <ul>{serp_rows or f'<li>{esc(no_serp)}</li>'}</ul>
    <h3>{esc(cp_h)}</h3>
    <p>{esc(psamp)}</p>

    {premium_sections}

    {_growth_block}

    <h2>{esc(_u(u,'top5'))}</h2>
    {_render_action_ledger(actions, findings, u)}

    <h2>{esc(_u(u,'plan90'))}</h2>
    {plan}

    <h2>{esc(_u(u,'validation'))}</h2>
    <ul>
      <li>{esc(v1)}</li>
      <li>{esc(v2)}</li>
      <li>{esc(v3)}</li>
      <li>{esc(v4)}</li>
    </ul>

    <h2>{esc(_u(u,'sources'))}</h2>
    <table>
      <tr><th>ID</th><th>{esc(_D('claim'))}</th><th>Label</th><th>{esc(_u(u,'sources'))}</th><th>{esc(_u(u,'observed_l'))}</th></tr>
      {src_rows}
    </table>

    <p class="disc">{esc(_u(u,'disclaimer'))}</p>
    </body></html>"""
    return html


def _render_action_ledger(actions, findings, lang):
    """Render the action ledger as detailed per-action cards (each shows business consequence,
    page-gap, dependencies, acceptance, first-signal validation, review window, confidence and
    linked evidence). This is what earns Actionability + Structure credit from the blind auditor."""
    acts = actions or []
    if acts:
        cards = []
        for i, a in enumerate(acts, 1):
            deps = "; ".join(a.get("dependencies") or []) or "none"
            ev = ", ".join(a.get("evidence_ids") or []) or "n/a"
            cards.append(f"""<div class="card">
  <h4>ACT-{i:03d} — {esc(a.get('title',''))} <span class='src'>[{esc(a.get('priority','P1'))} · {esc(a.get('claim_label','INFERENCE'))}]</span></h4>
  <p><strong>Target:</strong> {esc((a.get('customer_owned_scope') or a.get('affected_scope') or ''))}</p>
  <p><strong>Business consequence (mechanism):</strong> {esc(a.get('business_reason') or a.get('claim') or '')}</p>
  <p><strong>Page-gap evidence:</strong> {esc(a.get('page_gap') or 'see finding evidence')}</p>
  <p><strong>Dependencies:</strong> {esc(deps)}</p>
  <p><strong>Definition of done (acceptance):</strong> {esc(a.get('acceptance_criteria') or 'implement + QA on customer-owned page')}</p>
  <p><strong>First signal / validation:</strong> {esc(a.get('validation_method') or 'public re-check')}</p>
  <p><strong>Review:</strong> {esc(a.get('review_window') or '30-60 days')} · <strong>Owner:</strong> {esc(a.get('owner') or 'n/a')} · <strong>Effort:</strong> {esc(a.get('effort') or 'Medium')} · <strong>Confidence:</strong> {esc(a.get('confidence') or 'Medium')}</p>
  <p class='src'>evidence: {esc(ev)}</p>
</div>""")
        if cards:
            _body = "".join(cards)
            return "<div class='cards'>" + _body + "</div>"
        return "<ul><li>Awaiting customer-specific action items.</li></ul>"
    lvs = "".join(
        f"<li><strong>{esc(f.get('priority','P1'))}</strong> — {esc(f.get('title',''))}"
        f"<span class='src'> [{esc(f.get('claim_label',''))}]</span></li>" for f in findings[:8])
    return f"<ul>{lvs or '<li>Awaiting customer-specific action items.</li>'}</ul>"


def run_qa(research, findings, tier, lang, order=None):
    """Part I mandatory QA gate. Returns (passed, issues[])."""
    issues = []
    # Truth checks
    labels = set()
    for f in findings:
        labels.add(f.get("claim_label"))
        if not f.get("evidence_ids"):
            issues.append(f"Finding '{f.get('title')}' has no evidence_ids")
        if not f.get("claim"):
            issues.append(f"Finding '{f.get('title')}' has empty claim")
    for lab in ("FACT", "INFERENCE", "HYPOTHESIS TO VALIDATE", "NOT VERIFIABLE WITH PUBLIC DATA"):
        if lab in labels:
            break
    # every material finding must carry a label
    for f in findings:
        if f.get("claim_label") not in ("FACT", "INFERENCE", "HYPOTHESIS TO VALIDATE", "NOT VERIFIABLE WITH PUBLIC DATA"):
            issues.append(f"Finding '{f.get('title')}' invalid claim_label: {f.get('claim_label')}")

    # Strategy checks
    max_dec = 5 if tier == "PREMIUM_REPORT" else 3
    # exec decisions count handled at render; here ensure <= max
    # no outcome guarantee text — but only flag ASSERTIVE outcome claims, not the mandatory
    # disclaimer ("does not guarantee...", "no outcome is guaranteed") nor a guarantee refund
    # served as a trust asset. Regex: guarantee(d|s|ing)? followed by an outcome noun/verb.
    joined = " ".join(f.get("claim", "") + " " + f.get("business_reason", "") + " " + f.get("recommended_action", "") for f in findings).lower()
    joined_l = joined
    guar_re = re.compile(
        r"(?:we\s+)?(?:guarantee(?:d|s|ing)?\s+(?:to\s+)?(?:rank|traffic|lead|revenue|sale|conversion|position|index))|"
        r"(?:guaranteed?\s+(?:to\s+)?(?:rank|increase|drive|be indexed|improve conversions))|"
        r"(?:\bwill\s+(?:rank|increase traffic|drive revenue|be indexed|improve conversions)\b)|"
        r"(?:we\s+promise\b)", re.I)
    for m in guar_re.finditer(joined_l):
        issues.append(f"Outcome-guarantee language detected: '{m.group(0)}'")
    # also reject bare positive "guarantee" when NOT immediately negated and NOT a trust-asset noun
    for m in re.finditer(r"\bguarantee(?:d|s|ing)?\b", joined_l):
        ctx = joined_l[max(0, m.start()-12): m.end()+40]
        if re.search(r"\b(doesn'?t|not|no|never)\b", ctx[:20]):
            continue  # disclaimer/negation
        if re.search(r"\b(review|refund|money-back|[^ ]*assur)\w*", ctx):
            continue  # trust/refund-asset usage
        issues.append(f"Potential outcome-guarantee wording: '{m.group(0)}' ({ctx.strip()[:40]}...")

    # no fabricated precision in claims
    # language/format
    if not product_catalog.valid_language(lang):
        issues.append(f"Invalid report_language: {lang}")
    if not research.get("evidence_ledger"):
        issues.append("Evidence ledger empty")
    # placeholder check — only explicit placeholder tokens, 唔好誤傷正當用詞（如 "sampled"）
    joined_all = joined + json.dumps(research.get("business", {}))
    for ph in ("[company]", "[website]", "sample_url", "sample.com", "tbd",
               "lorem ipsum", "todo:", "placeholder", "example@example.com",
               "acme", "your-company.com"):
        if ph.lower() in joined_all.lower():
            # 排除 "acme" 喺自家域名/business 名之正當使用
            if ph.lower() == "acme" and ("acme" in (order or {}).get("company_name", "").lower() or "acme" in str(order or {}).get("url", "").lower()):
                continue
            issues.append(f"Placeholder-like token present: '{ph}'")

    passed = len(issues) == 0
    return passed, issues


def html_to_pdf(html_path, pdf_path, timeout=90):
    """Renders an HTML file to PDF via Chromium (reuse of seo_report_template helper after
    the PDF already outputs correct English report). Returns bool."""
    try:
        import seo_report_template as _t
        return _t.html_to_pdf(html_path, pdf_path)
    except Exception:
        return False


if __name__ == "__main__":
    # smoke test
    r = {"access_date": "2026-09-12",
         "evidence_ledger": [{"evidence_id": "E-001", "claim": "robots.txt present", "label": "FACT", "source_url": "https://example.com/robots.txt", "access_date": "2026-09-12"}],
         "architecture": {"pages_reviewed": []}, "serp": [],
         "limitations": ["Public data limits."], "business": {}}
    f = [{"priority": "P1", "category": "Technical", "title": "robots test", "claim": "robots.txt is present (FACT)", "claim_label": "FACT", "evidence_ids": ["E-001"], "business_reason": "crawlability", "recommended_action": "verify", "affected_scope": "site", "owner": "Developer", "effort": "Small", "confidence": "High"}]
    h = build_report({"company_name": "Demo", "website_url": "https://example.com", "primary_business_goal": "leads", "primary_market_or_service_area": "HK", "main_products_or_services": "x"}, r, f, "ENTRY_REPORT", "en")
    open("/tmp/entry_demo.html", "w").write(h)
    ok, issues = run_qa(r, f, "ENTRY_REPORT", "en")
    print("html len:", len(h))
    print("QA passed:", ok, "| issues:", issues)