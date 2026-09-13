# BRAND-REFERENCE INVENTORY + OWNER DECISION PROPOSAL

Status: **AUDITED / OWNER APPROVAL REQUIRED**(公開品牌改動 = §2.3 需批)
本 inventory 係全數事實,proposal 喺 §2。

## 1. 品牌字串完整 inventory(實測,2026-09-13)

| 位置 | 現有品牌字串 | 檔案:行 |
|---|---|---|
| Landing og:site_name(5 語言+template) | `SEO Scan.ai` | landing_en/es/ja/zh-Hans/zh-Hant/landing_page.html + template(各3處:title/og/句尾) |
| Landing 內文引用 | `seoscanaudit.com` | 各 landing ×9(支援/連結文案,呢啲係 domain 唔係 brand 名) |
| **報告 PDF 品牌單一來源** | `BRAND["name"]="SEO Scan.ai"` | seo_report_template.py:73(**single source**——改呢度,全 PDF 跟) |
| PDF footer/標語 | `SEO Scan.ai — evidence-led AI SEO audit report`(FOOT1,各語言版) | generate_languages.py:580/678/772/866 |
| PDF copyright | `© 2026 SEO Scan.ai` | generate_languages.py:582 等 |
| Report engine 註解/docstring | `SEO Scan.ai :: AI SEO Audit` | seo_report_template.py:3(非客戶可見) |
| Email subject 簽尾 | `— seoscanaudit.com`(domain) | pipeline_runner.py Resend 路徑 |
| Email From(現狀) | env EMAIL_FROM;fallback `onboarding@resend.dev` | pipeline_runner.py:728(** Resend 未驗 domain 時 fallback,唔係 seoscanaudit.com** ⚠️) |
| Reply-To | **無**(現為 header-ready,待 REPLY_TO_EMAIL env) | pipeline_runner.py |
| 支援路線文案 | hello@seoscanaudit.com(landing/privacy)| 多處 |
| Legal 頁 | legal@/privacy@/refund@/noreply@seoscanaudit.com | pipeline/legal/* |
| Live og:site_name | `SEO Scan.ai`(= 本地一致) | live curl 驗證 |

**結論**:可見品牌 = 「SEO Scan.ai」(landing/PDF/copyright),domain = seoscanaudit.com,兩者並存但唔同。**PDF 側已 single-source**(BRAND dict)→ 統一成本低;landing 側要 6 檔 × og:site_name。

## 2. Owner decision proposal(依指令 §4.2 三選項)

| | Option A(指令傾向) | Option B | Option C |
|---|---|---|---|
| Brand | **SEO Scan Audit** | SEO Scan | SEO Scan.ai(維持現狀) |
| Domain match | ✅ 直接對應 seoscanaudit.com | ⚠️ 半對應 | ❌ .ai 同 domain 唔符 |
| 客戶信任/清晰 | 高(名字講明產品=audit) | 高但泛(security-scan 聯想) | 中 |
| 專業感 | 高 | 中 | 中(.ai 熟 AI 市場) |
| Email domain 一致性 | ✅ 同 legal 页 | 同 | ❌ |
| checkout descriptor 影響 | 要 Stripe descriptor 更新(需批) | 同 | 唔使 |
| SEO title/meta 影響 | 微(og:site_name 非排名主因) | 微 | 無 |
| 未來擴展性 | 高(audit 可延伸 997) | 中 | 中 |
| 改動風險/成本 | 低(BRAND dict 1 處+landing og 6 檔;無 domain/DNS 變) | 低 | 零 |
| Legal identity 影響 | 要確認商業登記名(現狀 legal 頁用咩名要覆查) | 同 | 無 |

**推薦:Option A「SEO Scan Audit」**(依你傾向,證據:domain 直接對應、產品本質=audit、PDF 佢一支 BRAND dict 就改到)。

**Exact before → after(待批後執行)**:
1. `seo_report_template.py:73` `"name": "SEO Scan.ai"` → `"SEO Scan Audit"`(1 處,全 PDF 跟)
2. 各 landing og:site_name/title(6 檔,各 3 處)`SEO Scan.ai` → `SEO Scan Audit`
3. generate_languages FOOT1/COPYRIGHT(4 語言 × 2-3 處)
4. Email 簽尾由 domain 改品牌名(可選)
5. Stripe checkout descriptor(需你喺 Stripe Dashboard 改,我唔掂)
6. rollback:git revert 一個 commit;PDF/landing 全可重 render

**唔執行,直到你講「批 Option A」或揀 B/C。**

## 3. 額外發現(自主可修/已修)
- ⚠️ **Email From fallback `onboarding@resend.dev`**:當 EMAIL_FROM 缺/gmail 時,客會見 resend.dev 而非 seoscanaudit.com——**呢個係交付專業度缺口**。修法係 owner 要喺 Resend 驗證 domain + 設 noreply@seoscanaudit.com(需 DNS)→ owner 項,已在 support-inbox proposal 覆蓋。
- ✅ 已修(4be9d8e):email subject 內部 order_id → customer-safe ref;Reply-To header 支持(待 env)。
