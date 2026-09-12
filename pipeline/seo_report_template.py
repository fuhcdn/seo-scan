#!/usr/bin/env python3
"""
A5+A8 :: AI SEO Audit -- Professional PDF/HTML Report Template Generator
=======================================================================
Builds a branded, professional SEO audit report from the crawler's JSON
output (see seo_crawler.py). Produces a print-ready HTML template and
converts it to a real PDF via headless Chromium (also gives a self-contained
demo when run without arguments).

All CEO2 (Jobs-brain) report essentials are included:
  - Total SEO score (0-100) gauge on cover + executive summary
  - 5 tiered problem pillars: 技術SEO / 內容 / 連結 / 本地SEO / UX
  - Every finding carries 優先度 + 影響力 + 可提升分數 (point uplift)
  - Code snippet section
  - Competitor comparison block
  - Top-10 priority action checklist
  - Branded cover page

Usage:
  python3 seo_report_template.py                          # demo report
  python3 seo_report_template.py ../output/<audit>.json   # real audit report
  python3 seo_report_template.py --help

Outputs (written to ./out/):
  <domain>_seo_audit_report.html   (print-ready HTML)
  <domain>_seo_audit_report.pdf    (converted via headless Chromium)
Dependencies: Python stdlib only. PDF conversion uses an auto-detected
headless Chromium binary if one is present; HTML always works without it.
"""

import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
from html import escape

# ---------------------------------------------------------------------------
# Brand / theme configuration (single source of truth — change here to rebrand)
# ---------------------------------------------------------------------------
BRAND = {
    "name": "SEOAudit.ai",
    "tagline": "AI · Technical · Actionable",
    "contact": "hello@seoaudit.ai",
    "navy": "#0f2a43",
    "navy_dark": "#081a2b",
    "accent": "#12b981",     # emerald green
    "accent2": "#f59e0b",    # amber accent
    "ink": "#24384b",
    "muted": "#5c7184",
    "bg": "#ffffff",
    "soft": "#f2f6f9",
}

# Chromium binaries to probe for HTML->PDF conversion, in preference order.
CHROMIUM_CANDIDATES = [
    "/opt/hermes/.playwright/chromium_headless_shell-1243/"
    "chrome-headless-shell-linux64/chrome-headless-shell",
    "/root/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
]

# ---------------------------------------------------------------------------
# Demo audit data (showcase the template with realistic findings)
# ---------------------------------------------------------------------------
DEMO_AUDIT = {
    "url": "https://acme-local-plumbing.com",
    "domain": "acme-local-plumbing.com",
    "timestamp": "2026-09-11T12:00:00Z",
    "score": 64,
    "server_signals": {"http_status": 200, "ttfb_ms": 1240, "page_size_bytes": 214000},
    "fix_list": [
        {"priority": "urgent", "issue": "首頁圖片無 alt 文字（31 張）",
         "why_it_matters": "圖片缺 alt 令 Google 無法理解影像內容，亦影響視障用戶無障礙體驗，直接削弱圖片搜尋及整體相關性。",
         "how_to_fix": "為每張 <img> 補上描述性 alt 屬性；裝飾性圖片用 alt=\"\"。", 
         "code_snippet": "<img src=\"pump-install.jpg\" alt=\"熱水爐安裝工程圖片\" loading=\"lazy\">"},
        {"priority": "urgent", "issue": "HTTPS 啟用但無強制 HTTP→HTTPS 301",
         "why_it_matters": "讓 HTTP 與 HTTPS 版本並存會造成重複內容及分薄權重，令排名訊號分散。",
         "how_to_fix": "伺服器加入 301 永久重導向，全站統一 HTTPS canonical。",
         "code_snippet": "RewriteEngine On\nRewriteCond %{HTTPS} off\nRewriteRule ^(.*)$ https://%{HTTP_HOST}/$1 [R=301,L]"},
        {"priority": "high", "issue": "每個頁面只有 1 個 H1，但重點服務頁無描述性標題",
         "why_it_matters": "標題係最重要嘅排名因素之一，關鍵字放太後會令 Google 低估頁面主題。",
         "how_to_fix": "標題改用『主關鍵詞 — 品牌』結構，控制喺 55-60 字符內。",
         "code_snippet": "<title>水喉維修 | 緊急通渠 Acme 水電 | 24小時服務</title>"},
        {"priority": "high", "issue": "Meta Description 超長（170+ 字符）且無 CTA",
         "why_it_matters": "過長描述會被截斷，削弱點擊率；冇 CTA 令搜尋者冇誘因入網站。",
         "how_to_fix": "改寫為 150 字符內，包含主關鍵詞 + 明確行動呼籲。",
         "code_snippet": "<meta name=\"description\" content=\"快速上門水喉維修，30分鐘到達，報價透明。立即致電查詢！\">"},
        {"priority": "high", "issue": "內容單薄：服務頁平均僅 180 字",
         "why_it_matters": "內容太短令網站難以建立主題權威，Google 傾向將排名俾內容更充實嘅頁面。",
         "how_to_fix": "每個服務頁擴充至 800+ 字，加入 FAQ、案例、報價流程、價格資訊。",
         "code_snippet": None},
        {"priority": "medium", "issue": "內部連結 SKU 缺失：首頁→服務頁無直接連結",
         "why_it_matters": "冇強內部連結令權重唔識流向重要頁面，降低全站抓取深度。",
         "how_to_fix": "在頁尾 + 首頁正文加入錨文本內部連結，指到各核心服務頁。",
         "code_snippet": "<a href=\"/services/emergency-pump\">緊急水泵維修服務</a>"},
        {"priority": "medium", "issue": "本地 NAP 資訊不一致",
         "why_it_matters": "Google Business Profile 同網站地址/電話唔一致會令本地排名（map pack）受罰，本地客戶搵唔到你。",
         "how_to_fix": "網站 footer、Contact 頁、結構化資料統一使用同一 NAP 格式。",
         "code_snippet": "\"address\": {\"streetAddress\": \"12 Queen's Road, Central\", \"addressLocality\": \"Hong Kong\"}"},
        {"priority": "medium", "issue": "Google Business Profile 未連到網站或服務區域設定唔完整",
         "why_it_matters": "未設定服務區域與類別會令本地搜尋曝光大幅流失。",
         "how_to_fix": "補齊 GBP 服務區域、服務類別，並喺網站加 LocalBusiness schema。",
         "code_snippet": None},
        {"priority": "low", "issue": "移動端可讀性：字體 14px 以下，點擊目標過細",
         "why_it_matters": "Google 用 mobile-first index，可讀性差會推高跳出率、拖低UX訊號。",
         "how_to_fix": "正文調至至少 16px，點擊目標高度至少 44px。",
         "code_snippet": "body { font-size: 16px; }\nbutton, a { min-height: 44px; }"},
        {"priority": "low", "issue": "後備連結：無外鏈策略，用戶望唔到信任背書",
         "why_it_matters": "缺乏高質量外鏈令網域權威(DA)偏低，上限封頂，難以同大站搶排名。",
         "how_to_fix": "建立目錄、本地媒體、商會、供應商回連，每月新增 3-5 條可信外鏈。",
         "code_snippet": None},
        {"priority": "low", "issue": "缺乏 JSON-LD LocalBusiness 結構化資料",
         "why_it_matters": "冇 schema 令 Google 較難理解業務實體同納入 rich result。",
         "how_to_fix": "加入 LocalBusiness / PlumbingBusiness JSON-LD。",
         "code_snippet": "<script type=\"application/ld+json\">\n{\"@context\":\"https://schema.org\",\"@type\":\"PlumbingBusiness\",...}\n</script>"},
        {"priority": "urgent", "issue": "網頁載入 1.24s（TTFB），未啟用 Gzip/快取",
         "why_it_matters": "慢載入推高跳出率並直接影響 Core Web Vitals 排名因素。",
         "how_to_fix": "啟用 gzip/br 壓縮 + 瀏覽器快取 + CDN，目標 TTFB <400ms。",
         "code_snippet": "AddOutputFilterByType DEFLATE text/html\nCache-Control: public, max-age=604800"},
    ],
}

# Competitor benchmark table for the comparison section (demo).
DEMO_COMPETITORS = [
    {"name": "Acme 水電（你）", "da": 8, "score": 64, "speed": "1.24s", "note": "本次審計"},
    {"name": "快通水喉", "da": 34, "score": 78, "speed": "0.61s", "note": "頁面1搜尋結果"},
    {"name": "HK 通渠達人", "da": 27, "score": 71, "speed": "0.83s", "note": "頁面1搜尋結果"},
    {"name": "城市水務維修", "da": 12, "score": 55, "speed": "1.92s", "note": "你嘅差距"},
]

# Keyword -> pillar classification for mapping unstructured fixes into
# the 5 required report pillars.
PILLAR_KEYWORDS = {
    "技術SEO": ["canonical", "hreflang", "schema", "json-ld", "robots", "sitemap",
                 "meta", "title", "redirect", "https", "structured", "robot"],
    "內容": ["content", "h1", "heading", "copy", "blog", "keyword", "word", "字",
             "內容", "標題", "文案", "信息", "text"],
    "連結": ["backlink", "external link", "internal link", "link", "外鏈", "回連",
             "內部連結", "連結", "domain authority", "da"],
    "本地SEO": ["local", "nap", "google business", "map pack", "服務區域", "gmb",
                "本地", "neighborhood", "address", "phone"],
    "UX": ["mobile", "speed", "ttfb", "viewport", "core web vital", "gzip",
           "cache", "載入", "速度", "font", "click", "lazy", "ux"],
}

PILLAR_ORDER = ["技術SEO", "內容", "連結", "本地SEO", "UX"]

# Estimated uplift (points) by priority tier — used when real data lacks one.
UPLIFT_BY_PRIORITY = {"urgent": 6, "high": 4, "medium": 2, "low": 1}
IMPACT_LABEL = {"urgent": "很高", "high": "高", "medium": "中", "low": "低"}
PRIORITY_FULL = {"urgent": "緊急", "high": "高", "medium": "中", "low": "低"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def classify(issue_text):
    """Map a fix's text to one of the 5 pillars by keyword matching."""
    t = issue_text.lower()
    scores = {p: 0 for p in PILLAR_ORDER}
    for pillar, kws in PILLAR_KEYWORDS.items():
        scores[pillar] = sum(1 for k in kws if k.lower() in t)
    best = max(PILLAR_ORDER, key=lambda p: scores[p])
    return best if scores[best] > 0 else "技術SEO"


def sort_issues(items):
    order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(items, key=lambda x: (order.get(x.get("priority", "low"), 9)))


def enrich(item):
    """Attach pillar + impact + uplift + rank to a raw fix dict (pure fn)."""
    out = dict(item)
    out["pillar"] = classify(str(item.get("issue", "")))
    out["priority"] = (item.get("priority") or "low").lower()
    out["impact"] = IMPACT_LABEL.get(out["priority"], "中")
    out["uplift"] = UPLIFT_BY_PRIORITY.get(out["priority"], 1)
    out["why"] = item.get("why_it_matters") or "（未提供原因）"
    out["how"] = item.get("how_to_fix") or "（未提供修復建議）"
    out["code"] = item.get("code_snippet")
    return out


def load_audit(path=None):
    """Load audit JSON. If none / empty / malformed, fall back to demo."""
    if path:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            # 真審計檔案即使 fix_list 為空都照用（例如 AI 評分暫時失敗），
            # 唔可以偷換成 demo 公司資料——嗰個係另一間公司嘅報告。
            if isinstance(data, dict) and (data.get("url") or data.get("domain") or data.get("signals")):
                return data
        except Exception as e:
            print(f"[warn] could not load audit ({e}); using demo data", file=sys.stderr)
    demo = json.loads(json.dumps(DEMO_AUDIT))  # deep copy
    demo["url"] = demo["url"]
    return demo


# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------
def css():
    b = BRAND
    return f"""
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial,
                     "PingFang HK", "Microsoft JhengHei", sans-serif;
          color: {b['ink']}; background: {b['soft']}; font-size: 13px; line-height: 1.55; }}
  .page {{ max-width: 800px; margin: 0 auto; background: {b['bg']}; }}
  .pad {{ padding: 38px 44px; }}
  .section {{ padding: 30px 44px; }}

  /* ---------- cover ---------- */
  .cover {{ background: linear-gradient(150deg, {b['navy_dark']} 0%, {b['navy']} 60%, #1a4b6d 100%);
            color: #fff; padding: 56px 52px 48px; page-break-after: always; position: relative; }}
  .cover .brand {{ display: flex; align-items: center; gap: 10px; font-weight: 800;
                   letter-spacing: .5px; font-size: 20px; }}
  .cover .logo-dot {{ width: 16px; height: 16px; border-radius: 50%;
                      background: {b['accent']}; box-shadow: 0 0 0 4px rgba(18,185,129,.25); }}
  .cover .subtitle {{ margin-left: 26px; font-size: 12px; color: #bfd4e3; letter-spacing: 2.5px; }}
  .cover .rule {{ width: 60px; height: 4px; background: {b['accent']}; margin: 34px 0 22px;
                  border-radius: 2px; }}
  .cover h1 {{ font-size: 34px; font-weight: 800; line-height: 1.15; }}
  .cover .lede {{ margin-top: 14px; color: #cfe0ec; font-size: 14px; max-width: 460px; }}
  .cover .meta {{ margin-top: 46px; display: grid; grid-template-columns: 1fr 1fr; gap: 10px 26px;
                  font-size: 12px; color: #aac3d6; }}
  .cover .meta b {{ color: #fff; font-weight: 700; }}
  .cover .foot {{ position: absolute; bottom: 40px; left: 52px; right: 52px;
                  display: flex; justify-content: space-between; font-size: 11px;
                  color: #7fa0ba; border-top: 1px solid rgba(255,255,255,.18); padding-top: 12px; }}
  .score-pill {{ position: absolute; top: 48px; right: 52px; text-align: center;
                 background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.25);
                 padding: 14px 20px; border-radius: 14px; }}
  .score-pill .num {{ font-size: 30px; font-weight: 800; color: {b['accent']}; }}
  .score-pill .lbl {{ font-size: 10px; letter-spacing: 1.5px; color: #bfd4e3; }}
  .verdict {{ display: inline-block; margin-top: 8px; background: {b['accent']};
              color: #03281a; font-weight: 800; font-size: 11px; padding: 4px 12px; border-radius: 20px; }}

  /* ---------- h2 section titles ---------- */
  h2.sec {{ font-size: 18px; color: {b['navy']}; font-weight: 800; margin-bottom: 4px;
            display: flex; align-items: center; gap: 10px; }}
  h2.sec .num {{ background: {b['navy']}; color: #fff; width: 26px; height: 26px; border-radius: 7px;
                 display: inline-flex; align-items: center; justify-content: center; font-size: 13px; }}
  .secsub {{ color: {b['muted']}; font-size: 12px; margin-bottom: 20px; }}
  .hline {{ width: 100%; height: 1px; background: #e5edf3; margin: 16px 0; }}

  /* ---------- gauge + score summary ---------- */
  .exec {{ display: grid; grid-template-columns: 220px 1fr; gap: 34px; align-items: center; }}
  .gauge {{ width: 200px; height: 200px; border-radius: 50%;
            background: conic-gradient({b['accent']} calc(var(--p)*1%), #e6eef4 0);
            display: grid; place-items: center; position: relative; margin: 6px auto; }}
  .gauge::before {{ content: ""; position: absolute; inset: 18px; border-radius: 50%; background: #fff; }}
  .gauge .center {{ position: relative; text-align: center; }}
  .gauge .big {{ font-size: 46px; font-weight: 800; color: {b['navy']}; line-height: 1; }}
  .gauge .of {{ font-size: 12px; color: {b['muted']}; }}
  .gauge .grade {{ position: relative; position: absolute; bottom: 40px; left: 0; right: 0; text-align: center;
                   font-size: 12px; font-weight: 700; color: {b['accent']}; }}
  .kpis {{ display: flex; gap: 14px; flex-wrap: wrap; }}
  .kpi {{ background: {b['soft']}; border: 1px solid #e3ebf1; border-radius: 12px; padding: 12px 16px;
         flex: 1; min-width: 110px; }}
  .kpi .v {{ font-size: 26px; font-weight: 800; color: {b['navy']}; }}
  .kpi .k {{ font-size: 11px; color: {b['muted']}; }}
  .pot {{ color: {b['accent']}; font-weight: 800; }}

  /* ---------- pillar rows ---------- */
  .pillar {{ display: grid; grid-template-columns: 90px 1fr 90px; align-items: center; gap: 16px;
             background: {b['soft']}; border: 1px solid #e3ebf1; border-radius: 12px;
             padding: 14px 18px; margin-bottom: 12px; }}
  .pillar .pn {{ font-weight: 800; color: {b['navy']}; font-size: 13px; }}
  .bar {{ height: 10px; background: #dfe8ef; border-radius: 6px; overflow: hidden; }}
  .bar > span {{ display: block; height: 100%; border-radius: 6px;
                 background: linear-gradient(90deg, {b['accent']}, #2dd4a7); }}
  .pillar .pv {{ text-align: right; font-weight: 800; color: {b['navy']}; font-size: 13px; }}

  /* ---------- findings ---------- */
  .finding {{ border: 1px solid #e7eef3; border-left: 4px solid {b['accent']};
             border-radius: 10px; padding: 14px 18px; margin-bottom: 14px; background: #fff; }}
  .finding.top {{ border-left-color: {b['accent2']}; }}
  .finding.urgent {{ border-left-color: #ef4444; }}
  .finding.high {{ border-left-color: #f59e0b; }}
  .finding.medium {{ border-left-color: #facc15; }}
  .finding.low {{ border-left-color: #94a3b8; }}
  .f-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }}
  .f-title {{ font-weight: 800; color: {b['navy']}; font-size: 14px; }}
  .chips {{ display: flex; gap: 8px; margin: 10px 0 8px; flex-wrap: wrap; }}
  .chip {{ font-size: 10px; font-weight: 800; padding: 4px 10px; border-radius: 20px;
           letter-spacing: .3px; }}
  .chip.pri {{ background: #eef4ee; color: #0f6b46; }}
  .chip.imp {{ background: #f3eef4; color: #6b2d8e; }}
  .chip.up {{ background: #e7f0e8; color: #127a43; }}
  .chip.urgent {{ background: #fdecec; color: #c0392b; }}
  .f-lab {{ font-size: 11px; font-weight: 800; color: {b['muted']}; text-transform: uppercase;
            letter-spacing: .5px; margin: 8px 0 3px; }}
  .f-body {{ font-size: 12.5px; color: {b['ink']}; max-width: 640px; }}
  pre.code {{ background: {b['navy_dark']}; color: #d3e6f5; border-radius: 8px; padding: 12px 14px;
              font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
              font-size: 11.5px; overflow-x: auto; margin-top: 8px; white-space: pre-wrap; line-height: 1.5; }}
  .prio {{ background: {b['muted']}; color: #fff; font-size: 10px; font-weight: 800;
           padding: 3px 9px; border-radius: 5px; }}
  .prio.urgent {{ background: #ef4444; }}
  .prio.high {{ background: #f59e0b; color: #3d2c00; }}
  .prio.medium {{ background: #facc15; color: #3d3000; }}
  .prio.low {{ background: #94a3b8; }}

  /* ---------- tables ---------- */
  table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
  th {{ text-align: left; background: {b['navy']}; color: #fff; font-weight: 700;
        padding: 10px 12px; font-size: 11px; letter-spacing: .3px; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #e7eef3; vertical-align: top; }}
  tr:nth-child(even) td {{ background: #f7fafc; }}
  .you {{ background: rgba(18,185,129,.08) !important; font-weight: 800; }}

  /* ---------- top10 ---------- */
  .toplist {{ counter-reset: act; }}
  .act {{ display: grid; grid-template-columns: 34px 1fr auto; gap: 14px; align-items: center;
          padding: 12px 0; border-bottom: 1px solid #edf2f6; }}
  .act .n {{ counter-increment: act; width: 30px; height: 30px; border-radius: 50%;
             background: {b['navy']}; color: #fff; display: inline-flex; align-items: center;
             justify-content: center; font-weight: 800; font-size: 13px; }}
  .act .t {{ font-weight: 700; color: {b['navy']}; font-size: 13px; }}
  .act .u {{ text-align: right; color: {b['accent']}; font-weight: 800; font-size: 12px; }}

  .note {{ font-size: 11px; color: {b['muted']}; line-height: 1.6; }}
  /* ---------- data quality badge ---------- */
  .dq-badge {{ display: inline-block; font-weight: 800; font-size: 12px; padding: 7px 16px;
               border-radius: 20px; margin-bottom: 16px; }}
  .dq-badge.dq-ok {{ background: #e7f0e8; color: #127a43; }}
  .dq-badge.dq-est {{ background: #fef3c7; color: #92400e; }}
  .dq-badge.dq-warn {{ background: #fdecec; color: #c0392b; }}
  .footer-note {{ margin-top: 26px; padding-top: 14px; border-top: 1px solid #e5edf3;
                  font-size: 10.5px; color: #8ba0b3; line-height: 1.6; }}
  @media print {{ body {{ background: #fff; }} .page {{ max-width: none; }} }}
</style>
"""


def cover_html(data):
    b = BRAND
    p = data["server_signals"] or {}
    ts = data.get("timestamp", "")
    grade, gclass = grade_for(data["score"])
    return f"""
  <div class="cover">
    <div class="brand"><span class="logo-dot"></span>{escape(b['name'])}
      <span class="subtitle">{escape(b['tagline'])}</span></div>
    <div class="score-pill"><div class="num">{data['score']}</div><div class="lbl">SEO 得分</div>
      <div class="verdict">{grade}</div></div>
    <div class="rule"></div>
    <h1>AI SEO 審計報告</h1>
    <div class="lede">完整技術搜尋引擎優化診斷：5 大支柱、逐項優先度、可量化提升分數，
      以及你現在就要做嘅 10 步優先行動，助你喺搜尋結果快速搶佔位置。</div>
    <div class="meta">
      <div><b>審計網址</b><br>{escape(data['url'])}</div>
      <div><b>HTTP 狀態</b><br>{p.get('http_status', '—')}</div>
      <div><b>報告日期</b><br>{ts}</div>
      <div><b>頁面載入 (TTFB)</b><br>{p.get('ttfb_ms', '—')} ms</div>
    </div>
    <div class="foot">
      <span>© {time.strftime('%Y')} {escape(b['name'])} · {escape(b['contact'])}</span>
      <span>僅供內部決策用途 · 附有免責聲明</span>
    </div>
  </div>
"""


def grade_for(score):
    if score is None: return "暫未評分 · N/A", "weak"
    if score >= 85:   return "優良 · Good", "good"
    if score >= 70:   return "良好 · Fair", "fair"
    if score >= 50:   return "有待改善 · Needs Work", "fair"
    if score >= 30:   return "薄弱 · Weak", "weak"
    return "嚴重落後 · Critical", "weak"


def gauge_html(score):
    return f"""
  <div class="gauge" style="--p:{score}"><div class="center">
    <div class="big">{score}</div><div class="of">/ 100</div></div></div>
"""


def exec_summary_html(data):
    b = BRAND
    issues = [enrich(x) for x in data["fix_list"]]
    urgent = sum(1 for i in issues if i["priority"] == "urgent")
    pot = sum(i["uplift"] for i in issues[:10])
    new_score = min(100, int(data.get("score") or 0) + pot)
    score_label = "N/A" if data.get("score") is None else int(data.get("score"))
    return f"""
  <div class="section">
    <h2 class="sec"><span class="num">01</span>執行摘要 Executive Summary</h2>
    <div class="secsub">一眼睇清你嘅 SEO 健康狀況與最大改善空間</div>
    <div class="hline"></div>
    <div class="exec">
      {gauge_html(data['score'])}
      <div>
        <div class="kpis">
          <div class="kpi"><div class="v">{urgent}</div><div class="k">緊急問題</div></div>
          <div class="kpi"><div class="v">{len(issues)}</div><div class="k">全部發現</div></div>
          <div class="kpi"><div class="v pot">+{pot}</div><div class="k">首10項可提升</div></div>
          <div class="kpi"><div class="v pot">{new_score}</div><div class="k">預期修後得分*</div></div>
        </div>
        <p style="margin-top:16px;font-size:13px;color:{b['ink']}">
          你嘅網站目前 <b>SEO 得分 {score_label}/100</b>。只要依次處理首 10 項高影響力修正，
          預期可將得分推升至 <b class="pot">{new_score}</b>——尤其係 {PILLAR_ORDER[0]} 支柱
          嘅修正能最快見到排名變化。<span style="color:{b['muted']}">*預期修後得分為估算，非保證。</span></p>
      </div>
    </div>
  </div>
"""


def pillar_html(data):
    issues = [enrich(x) for x in data["fix_list"]]
    by_pillar = {p: [] for p in PILLAR_ORDER}
    for i in issues:
        by_pillar[i["pillar"]].append(i)
    maxn = max((len(v) for v in by_pillar.values()), default=1) or 1
    rows = []
    for p in PILLAR_ORDER:
        lst = by_pillar[p]
        if not lst:
            continue
        n = len(lst)
        bar = int(round(n / maxn * 100))
        sub = sum(i["uplift"] for i in lst)
        rows.append(f"""
      <div class="pillar">
        <div class="pn">{p}<br><span style="font-weight:400;color:#7c93a6;font-size:11px">{n} 項</span></div>
        <div class="bar"><span style="width:{bar}%"></span></div>
        <div class="pv">+{sub}</div>
      </div>""")
    return f"""
  <div class="section">
    <h2 class="sec"><span class="num">02</span>五大支柱概覽 Pillars</h2>
    <div class="secsub">按問題數量分佈並顯示各支柱可累計提升嘅分數</div>
    <div class="hline"></div>
    {''.join(rows)}
  </div>
"""


def finding_cards(data):
    issues = [enrich(x) for x in data["fix_list"]]
    issues = sort_issues(issues)
    cards = []
    for idx, i in enumerate(issues):
        rank = idx + 1
        top = "top" if rank <= 3 else ""
        up = "+" + str(i["uplift"])
        code = ""
        if i["code"]:
            code = f'<pre class="code">{escape(i["code"])}</pre>'
        cards.append(f"""
      <div class="finding {top} {i['priority']}">
        <div class="f-head">
          <div class="f-title">#{rank}　{escape(i['issue'])}</div>
          <span class="prio {i['priority']}">{escape(PRIORITY_FULL.get(i['priority'], i['priority']))}</span>
        </div>
        <div class="chips">
          <span class="chip pri">支柱：{i['pillar']}</span>
          <span class="chip imp">影響力：{i['impact']}</span>
          <span class="chip up">可提升：+{i['uplift']} 分</span>
        </div>
        <div class="f-lab">點解重要</div>
        <div class="f-body">{escape(i['why'])}</div>
        <div class="f-lab">點樣修</div>
        <div class="f-body">{escape(i['how'])}</div>
        {code}
      </div>""")
    head = "".join(f"""
        <h2 class="sec" data-pillar="{p}"><span class="num">0{i+3}</span>{p}· 發現與修復</h2>
        <div class="secsub">{p} 支柱 —— 優先度、影響力與可提升分數</div>
        <div class="hline"></div>""" for i, p in enumerate(PILLAR_ORDER))
    return head + "".join(cards), issues


def code_section_html(data):
    issues = [enrich(x) for x in data["fix_list"]]
    with_code = [i for i in issues if i["code"]]
    blocks = []
    for i in with_code:
        blocks.append(f"""
      <div class="finding {i['priority']}">
        <div class="f-title" style="margin-bottom:4px">{escape(i['issue'])}</div>
        <pre class="code">{escape(i['code'])}</pre>
      </div>""")
    if not blocks:
        blocks = ['<div class="f-body">本次審計未偵測到需要示例代碼嘅問題。</div>']
    return f"""
  <div class="section">
    <h2 class="sec"><span class="num">06</span>代碼範例 Code Snippets</h2>
    <div class="secsub">可直接複製執行嘅修復範例</div>
    <div class="hline"></div>
    {''.join(blocks)}
  </div>
"""


def competitor_html(data):
    comps = data.get("competitors")
    if not comps:
        rows = ('<tr><td colspan="5" style="text-align:center;color:#5c7184;font-weight:700">'
                '需要真實競爭數據 —— 未連接競爭對手分析數據源，暫未能提供差距對比。</td></tr>')
    else:
        rows = []
        for c in comps:
            name = c.get("name", "")
            you = " you" if isinstance(name, str) and "你" in name else ""
            rows.append(f"""
      <tr class="{you}"><td>{escape(str(name))}</td><td>{c.get('da','—')}</td>
        <td>{c.get('score','—')}</td><td>{escape(str(c.get('speed','—')))}</td><td>{escape(str(c.get('note','')))}</td></tr>""")
        rows = "".join(rows)
    return f"""
  <div class="section">
    <h2 class="sec"><span class="num">07</span>競爭對比 Competitive Benchmark</h2>
    <div class="secsub">同搜尋結果首頁對手嘅客觀差距 {'' if comps else '（暫無數據）'}</div>
    <div class="hline"></div>
    <table>
      <thead><tr><th>網站</th><th>DA</th><th>SEO 得分</th><th>載入</th><th>備註</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
"""


def top10_html(data):
    issues = [enrich(x) for x in data["fix_list"]]
    issues = sort_issues(issues)[:10]
    rows = []
    for i in issues:
        rows.append(f"""
      <div class="act">
        <div class="n"></div>
        <span class="t">{escape(i['issue'])}</span>
        <span class="u">+{i['uplift']} 分</span>
      </div>""")
    return f"""
  <div class="section">
    <h2 class="sec"><span class="num">08</span>頂 10 項優先行動 Top-10 Action Plan</h2>
    <div class="secsub">由高影響力到低，依次做齊即可見到排名提升</div>
    <div class="hline"></div>
    <div class="toplist">{''.join(rows)}</div>
  </div>
"""


def appendix_html(data):
    return f"""
  <div class="section" style="padding-top:8px">
    <h2 class="sec"><span class="num">10</span>方法與免責聲明 Methodology</h2>
    <div class="hline"></div>
    <div class="note">
      <b>審計範圍</b>：本報告由 AI 自動爬取目標頁面並抽取 10+ 項 on-page SEO 訊號
      （標題、Meta、robots、canonical、hreflang、JSON-LD、H1/H2、圖片 alt、內部連結、
      HTTP 狀態、載入速度等），再經大語言模型評分與產出優先修正清單。<br><br>
      <b>基準</b>：總分 0–100，權重偏向技術 SEO 健康度；分數僅供短期改善追蹤用，
      搜尋排名受競爭度、外鏈、內容質素等長期因素影響。<br><br>
      <b>免責聲明</b>：本報告由自動化工具生成，僅供決策參考，不構成排名保證或法律意見。
      具體執行前請由專業團隊覆核。報告 © {time.strftime('%Y')} {escape(BRAND['name'])}。
    </div>
  </div>
"""


def data_quality_html(data):
    dq = data.get("data_quality") or {}
    srv = data.get("server_signals") or {}
    if not dq:
        # 舊 / demo audit：由現有欄位推導
        dq = {
            "fetch_ok": bool(srv.get("http_status")),
            "http_status": srv.get("http_status"),
            "ttfb_ms": srv.get("ttfb_ms"),
            "fallback_used": bool(data.get("fallback_used")),
            "ai_error": data.get("ai_error"),
            "crawl_errors": data.get("crawl_errors") or [],
            "score_is_estimate": bool(data.get("score_is_estimate") or data.get("fallback_used")),
            "label": ("規則估算非精確（AI 未能評分）"
                      if (data.get("score_is_estimate") or data.get("fallback_used"))
                      else "真實抓取審計"),
        }
    fetch_ok = bool(dq.get("fetch_ok"))
    fallback = bool(dq.get("fallback_used"))
    status = dq.get("http_status")
    ttfb = dq.get("ttfb_ms")
    ai_err = dq.get("ai_error")
    crawl_errs = dq.get("crawl_errors") or []
    label = dq.get("label") or (
        "規則估算非精確（AI 未能評分）" if (fallback or dq.get("score_is_estimate"))
        else ("真實抓取審計" if fetch_ok else "抓取未完整"))
    badge_cls = "dq-ok" if (fetch_ok and not fallback) else ("dq-est" if fallback else "dq-warn")
    badge_txt = escape(str(label))
    status_txt = str(status) if status is not None else "—"
    ttfb_txt = (str(ttfb) + " ms") if isinstance(ttfb, (int, float)) else "—"
    errs = escape("；".join(
        [str(a) if not isinstance(a, str) else (a.split(" [used rule")[0]) for a in crawl_errs])) or \
        (escape(str(ai_err).split(" [used rule")[0]) if ai_err else "")
    row = ""
    if not fetch_ok:
        row = f'<div class="f-body" style="color:#c0392b">⚠️ 頁面抓取失敗，以下數據可能有遺漏/不完整。</div>'
    if fallback:
        row += ('<div class="f-body" style="color:#92400e">注意：AI 未能評分，'
                '本報告分數與修復清單由<b>規則估算</b>生成，屬估算非精確結果，'
                '僅供初步參考。</div>')
    return f"""
  <div class="section">
    <h2 class="sec"><span class="num">09</span>數據品質 Data Quality</h2>
    <div class="secsub">這個報告基於咩數據 —— 真實抓取定規則估算</div>
    <div class="hline"></div>
    <div class="dq-badge {badge_cls}">品質徽章：{badge_txt}</div>
    <table>
      <thead><tr><th>指標</th><th>數值</th><th>說明</th></tr></thead>
      <tbody>
        <tr><td>抓取成功 (fetch_ok)</td><td>{'✅ 是' if fetch_ok else '❌ 否'}</td>
            <td>頁面有否真實抓到 HTML</td></tr>
        <tr><td>HTTP 狀態</td><td>{status_txt}</td><td>目標頁面回應狀態碼</td></tr>
        <tr><td>TTFB</td><td>{ttfb_txt}</td><td>伺服器首字節回應時間（速度訊號）</td></tr>
        <tr><td>規則估算</td><td>{'是（非精確）' if fallback else '否'}</td>
            <td>分數/修復清單是否由規則 fallback 生成</td></tr>
        <tr><td>AI 錯誤</td><td>{escape(str(ai_err)) if ai_err else '—'}</td>
            <td>AI 評分失敗原因（如有）</td></tr>
        <tr><td>抓取問題</td><td>{errs if errs else '—'}</td>
            <td>過程中有否發生錯誤/遺漏</td></tr>
      </tbody>
    </table>
    {row}
  </div>
"""


def build_html(data):
    # 競爭數據：淨係喺真審計有真數據時先顯示，唔好再硬塞 demo 競爭公司入真報告。
    # 真實審計靠 audit JSON 內嘅 "competitors" 欄位提供；冇就顯示「需要真實競爭數據」佔位。
    pillar_block, _ = finding_cards(data)
    parts = [
        "<!DOCTYPE html><html lang=\"zh-HK\"><head><meta charset=\"utf-8\">",
        "<title>SEO 審計報告</title>",
        css(), "</head><body><div class=\"page\">",
        cover_html(data),
        exec_summary_html(data),
        pillar_html(data),
        pillar_block,
        code_section_html(data),
        top10_html(data),
        competitor_html(data),
        data_quality_html(data),
        appendix_html(data),
        '<div class="footer-note" style="padding:0 44px 34px">'
        f"本報告由 {escape(BRAND['name'])} AI 平台自動生成 · 更新於 {escape(data.get('timestamp',''))}</div>",
        "</div></body></html>",
    ]
    return "\n".join(parts)


def find_chromium():
    for c in CHROMIUM_CANDIDATES:
        if "*" in c:
            import glob
            hits = sorted(glob.glob(c))
            if hits:
                return hits[-1]
        elif os.path.exists(c):
            return c
    return shutil.which("chromium") or shutil.which("google-chrome")


def html_to_pdf(html_path, pdf_path, chromium=None):
    if not chromium:
        chromium = find_chromium()
    if not chromium:
        print("[warn] no headless Chromium found — HTML generated only, no PDF",
              file=sys.stderr)
        return False
    cmd = [chromium, "--headless", "--no-sandbox", "--disable-gpu",
           "--no-margins", "--print-to-pdf=" + pdf_path,
           "file://" + os.path.abspath(html_path)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 1000
    except Exception as e:
        print(f"[warn] PDF conversion failed: {e}", file=sys.stderr)
        return False


def main():
    args = [a for a in sys.argv[1:] if a not in ("--help", "-h")]
    data = load_audit(args[0] if args else None)

    domain = data.get("domain") or re.sub(r"[^\w.-]", "",
                 (data.get("url", "demo") or "").split("//")[-1].split("/")[0]) or "demo"
    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    os.makedirs(outdir, exist_ok=True)

    html_path = os.path.join(outdir, f"{domain}_seo_audit_report.html")
    pdf_path = os.path.join(outdir, f"{domain}_seo_audit_report.pdf")

    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(build_html(data))
    print(f"[ok] HTML -> {html_path}")

    pdf_ok = html_to_pdf(html_path, pdf_path)
    print(f"[{'ok' if pdf_ok else 'skip'}] PDF -> {pdf_path}"
          + ("" if pdf_ok else "  (Chromium not found)"))

    return html_path, pdf_path if pdf_ok else None


if __name__ == "__main__":
    main()