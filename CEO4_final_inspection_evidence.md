# CEO4 (Jensen) 全檢實測證據 — seoscanaudit.com
Date: 2026-09-12  UTC

## VERDICT
approve: false
fails:
  - "EMAIL_CONSENT_NO_TICK: 5種語言landing收集email均無明確consent checkbox（grep consent/checkbox=0，all 5 langs）。'Receive the report by email'加email input，無opt-in tick。Blueprint明文'email capture要consent checkbox'。私隱合規FAIL。"
  - "LEGAL_NOT_LOCALIZED: 5語言已上線(/en /zh-Hant /zh-Hans /ja /es皆200)但/legal/*只serve繁中文件（live /legal/privacy回傳繁中）。英文/日文/西文用户見中文法律文件。Blueprint gate'每加語言成套包袱齊晒先解鎖；私隱最硬'。合規FAIL。"
  - "PRICE_MISMATCH: 頁面顯示US$397（CTA button 'Unlock Full Report — US$397' 4次 + 'from US$397'），但server.checkout_price()=497（clean env實測）且Stripe PRICE_ID映射PRICE_497。顯示價≠實收價，誤導定價，首單誠信FAIL。"

## EVIDENCE (live / curl / read)
1) Legal routes (live all HTTP 200): /legal/terms /legal/privacy /legal/refund /legal/disclaimer /legal/authorization → 200
2) Landing footer links legal: /legal/privacy /legal/terms /legal/refund /legal/disclaimer each lang(disclaimer-link=1)
3) Disclaimer live doc: 明示"本公司不保證任何具體的搜尋排名、流量或收入結果" — 建議非保證
4) 授權書/ToS/私隱/退款 doc 內容實質存在（PDPO 486章引用）
5) Authority trustbar(非假認證徽章): "Aligned with Google Search Essentials / Ahrefs×Semrush audit methodology / Official Core Web Vitals metrics" — 方法論對齊聲稱,無偽造Partner/認證logo。軟黃旗:"Ahrefs×Semrush"不可驗證。
6) First-order chain E2E done (order_TEST-REAL-PAY-PIPELINE-2.json): order_received→payment_verified(真Stripe pi_3UE…US$79)→crawl→score→report(html+pdf)→deliver(SMTP送出, delivery marker寫入)。status=done。deliveries/ 有 marker。
7) Trust stats: "—"placeholder + "live count"/"connecting real data" tags, 非假數字; 無假證言。
8) PRICE: live en頁 US$397次數>US$497; checkout_price()=497 (clean env)
9) 5語種頁全部HTML有email收集欄但0 consent checkbox