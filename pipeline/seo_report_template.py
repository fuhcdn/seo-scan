#!/usr/bin/env python3
"""
SEO Scan Audit :: AI SEO Audit -- Professional PDF/HTML Report Template Generator
===============================================================================
English-master, agency-grade report HTML builder. Consumes the crawler's audit
JSON (seo_crawler.py) and renders a print-ready report with:

  * Cover (score pill, grade, domain, date, TTFB)     -- English
  * 01 Executive Summary      -- gauge + 4 KPIs + verdict box
  * 02 Verdict                -- deterministic 2-3 sentence agency verdict
  * 03 Scorecard by Pattern   -- bar rows per SEO pattern (not pillars)
  * 04-11 Patterns & Findings -- one section per pattern, PE-framework cards
  * 12 Every Finding          -- complete flat grouped appendix
  * 13 Code Snippets          -- copy-paste fixes
  * 14 Competitive Benchmark  -- real-data placeholder
  * 15 Top-10 Priority Action Plan
  * 16 Data Quality & Methodology

English-master copy model
-------------------------
Every user-visible string routes through the `L(key, **fmt)` lookup against the
EN dict. Other locales can be dropped in later by supplying a translated COPY
dict (mirrors generate_languages.py), keeping English as the source of truth.
All explanations in the AI/fallback fix lists are written in English, so the
only non-English text ever in a report is quoted signal values pulled verbatim
from a crawled page's own markup.

Agency PE framework on every finding card
-----------------------------------------
  Problem  -> one-line title
  Evidence -> the real measured signal value (never canned when one exists)
  Dollar impact -> est. annual revenue at risk from a deterministic
                   site_type x pattern model; "Impact unquantified" if no basis
  How to fix -> concrete steps (+ code snippet)
  Effort -> colored Quick / Half-day / 1-2 days / Sprint badge
Chips: Pattern / Priority / Impact / Uplift.

Compatibility
-------------
build_html(), load_audit() and html_to_pdf() keep their signatures so
evidence_v1_pipeline and server.py pass report data through unchanged. The
generator tolerates audit JSONs missing the new fields (effort, dollar_impact,
pattern, evidence) by defaulting/churning them from priority + site_type, so
old JSONs and rule-based fallback output both render. A None score renders a
graceful "Score not available" instead of breaking.

Dependencies: Python stdlib only (html, json, os, re, sys, time, shutil,
subprocess). PDF conversion uses an auto-detected headless Chromium if present;
HTML generation always works without it.

Usage:
  python3 seo_report_template.py                       # demo report
  python3 seo_report_template.py <audit.json>          # real audit report
Output -> ./out/<domain>_seo_audit_report.html(.pdf)
"""

import html as _htmlmod
import json
import os
import re
import shutil
import subprocess
import sys
import time
from html import escape

_YEAR = time.strftime("%Y")

# ---------------------------------------------------------------------------
# Brand / theme (single source of truth -- change here to rebrand)
# ---------------------------------------------------------------------------
BRAND = {
    "name": "SEO Scan Audit",
    "tagline": "AI · Technical · Actionable",
    "contact": "hello@seoscanaudit.com",
    "site": "seoscanaudit.com",
    "navy": "#0f2a43",
    "navy_dark": "#081a2b",
    "accent": "#12b981",     # emerald green
    "accent2": "#f59e0b",    # amber accent
    "ink": "#24384b",
    "muted": "#5c7184",
    "bg": "#ffffff",
    "soft": "#f2f6f9",
}

CHROMIUM_CANDIDATES = [
    "/opt/hermes/.playwright/chromium_headless_shell-1243/"
    "chrome-headless-shell-linux64/chrome-headless-shell",
    "/root/.cache/ms-playwright/chromium_headless_shell-*/"
    "chrome-headless-shell-linux64/chrome-headless-shell",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
]

# ---------------------------------------------------------------------------
# English-master copy dictionary (all user-visible strings route through L()).
# Add translated dicts here later; L() only falls back to EN on this locale.
# ---------------------------------------------------------------------------
EN = {
    # --- cover ---
    "cover.title": "AI SEO Audit Report",
    "cover.lede": "{persona} This report is a complete technical search-engine "
                  "optimization diagnosis: 8 patterns, itemized priorities, "
                  "measurable point uplifts, and a 10-step priority action plan "
                  "you can start today.",
    "cover.type_badge": "Site type: {label} · scoring weighted for this category",
    "cover.audit_url": "Audited URL",
    "cover.http_status": "HTTP Status",
    "cover.report_date": "Report date",
    "cover.ttfb_label": "Time to first byte (TTFB)",
    "cover.foot_internal": "For internal decision-making only · disclaimer applies",
    "cover.score_lbl": "SEO SCORE",
    # --- grade bands ---
    "grade.excellent": "Excellent",
    "grade.good": "Good",
    "grade.needs_work": "Needs Work",
    "grade.weak": "Weak",
    "grade.critical": "Critical",
    "grade.na": "Score not available",
    # --- section titles ---
    "sec.exec": "Executive Summary",
    "sec.exec_sub": "At-a-glance SEO health and your biggest upside",
    "sec.verdict": "Verdict at a Glance",
    "sec.verdict_sub": "What this crawl says, in plain English",
    "sec.scorecard": "Scorecard by Pattern",
    "sec.scorecard_sub": "Issues per pattern and cumulative estimated point uplift",
    "sec.pattern": "Patterns & Findings",
    "sec.every": "Every Finding",
    "sec.every_sub": "Complete list of findings, grouped by pattern (appendix)",
    "sec.code": "Code Snippets",
    "sec.code_sub": "Copy-paste fixes you can apply directly",
    "sec.code_empty": "No issues in this audit required a code example.",
    "sec.benchmark": "Competitive Benchmark",
    "sec.benchmark_sub": "Objective gap vs. ranked competitors",
    "sec.benchmark_nodata": "Real competitive data required -- the competitor "
                            "analysis source is not connected, so no gap "
                            "comparison is available yet.",
    "sec.top10": "Top-10 Priority Action Plan",
    "sec.top10_sub": "Highest impact first -- working through this list in order "
                     "is the fastest path to visible ranking movement",
    "sec.top10.step": "Step {n}",
    "sec.dataq": "Data Quality",
    "sec.dataq_sub": "What this report is based on -- live crawl or rule estimate",
    "sec.dq_badge": "Quality badge: {label}",
    "sec.method": "Methodology & Disclaimer",
    # --- executive KPIs ---
    "kpi.urgent": "Urgent issues",
    "kpi.total": "Total findings",
    "kpi.upside": "Est. points available (top 10)",
    "kpi.projected": "Projected score after fixes*",
    "exec.lede": ("Your site currently scores <b>{score}/100 ({grade})</b>. "
                  "Working through the top 10 high-impact fixes below is expected "
                  "to lift this to <b class=\"pot\">{proj}</b> -- the "
                  "<b>{toppattern}</b> pattern offers the fastest visible wins. "
                  "<span style=\"color:{muted}\">*Projected score is an estimate, "
                  "not a guarantee.</span>"),
    "exec.na": "Score pending -- see findings below.",
    # --- scorecard ---
    "scorecard.row_pct": "{n} findings",
    "scorecard.none": "No findings",
    # --- verdict (deterministic sentence templates) ---
    "verdict.open": "Score {score}/100 -- {grade}.",
    "verdict.open_na": "The SEO score is still being calibrated for this crawl.",
    "verdict.band.excellent": "This is a strong technical baseline.",
    "verdict.band.good": "A solid foundation with a clear set of quick wins.",
    "verdict.band.needs_work": "Your site has meaningful SEO drag worth "
                               "addressing now.",
    "verdict.band.weak": "Significant technical gaps are limiting your rankings.",
    "verdict.band.critical": "Critical issues are actively blocking indexation "
                             "and ranking.",
    "verdict.drag": " Your top drag is {label}: {n} findings put an estimated "
                    "${dollar} of annual revenue at risk.",
    "verdict.drag_none": " No single problem cluster dominates this crawl.",
    "verdict.win": " Fixing the {n} quick-effort {label} issues is your fastest "
                   "win.",
    "verdict.win_none": " Start with the urgent items in the action plan below.",
    "verdict.na_tail": " The crawl data below captures the issues we can already "
                       "see.",
    # --- finding card (PE framework) ---
    "fd.problem": "Problem",
    "fd.evidence": "Evidence",
    "fd.evidence_default": "No dedicated measurement was captured for this "
                           "finding; the Data Quality table lists all signals "
                           "from this crawl.",
    "fd.dollar": "Dollar impact",
    "fd.dollar_value": "Est. annual revenue at risk: ${amt} (modeled from site "
                       "type + pattern)",
    "fd.dollar_unquantified": "Impact unquantified -- see effort",
    "fd.how": "How to fix",
    "fd.chip_pattern": "Pattern",
    "fd.chip_priority": "Priority",
    "fd.chip_impact": "Impact",
    "fd.chip_uplift": "Uplift",
    "fd.effort": "{effort} · Est. +{pts} pts",
    # --- priority / impact words ---
    "priority.urgent": "Urgent",
    "priority.high": "High",
    "priority.medium": "Medium",
    "priority.low": "Low",
    "impact.urgent": "Critical impact",
    "impact.high": "High impact",
    "impact.medium": "Medium impact",
    "impact.low": "Lower impact",
    # --- data quality table ---
    "dq.fetch": "Crawl success (fetch_ok)",
    "dq.status": "HTTP status",
    "dq.ttfb": "TTFB",
    "dq.fallback": "Rule estimate used",
    "dq.ai_err": "AI error",
    "dq.crawl_err": "Crawl issues",
    "dq.desc.fetch": "Whether the target HTML was really fetched",
    "dq.desc.status": "Response status code of the target page",
    "dq.desc.ttfb": "Time to first byte (a speed signal)",
    "dq.desc.fallback": "Whether the score/fix list came from the rule fallback",
    "dq.desc.ai_err": "Why the AI scorer failed, if it did",
    "dq.desc.crawl_err": "Any errors or omissions during the crawl",
    "dq.yes": "Yes",
    "dq.no": "No",
    "dq.na": "—",
    "dq.yes_crawl": "Live crawl",
    "dq.no_fallback": "Rule estimate (approximate)",
    "dq.note_fetch_fail": "Page fetch failed -- data below may be missing or "
                          "incomplete.",
    "dq.note_fallback": "Note: the AI scorer was unavailable, so the score and "
                        "fix list were generated by a <b>rule-based estimate</b>. "
                        "Treat results as approximate, initial guidance.",
    # --- benchmark table ---
    "bench.you": "You (this audit)",
    "bench.col_site": "Site",
    "bench.col_da": "DA",
    "bench.col_score": "SEO score",
    "bench.col_speed": "Load",
    "bench.col_note": "Note",
    # --- methodology ---
    "method.scope": "Audit scope",
    "method.scope_body": ("This report was produced by an automated AI crawler "
                          "that extracts 12+ on-page SEO signals (title, meta, "
                          "robots, canonical, hreflang, JSON-LD, H1/H2, image "
                          "alt, internal links, HTTP status, load speed, headers) "
                          "and scores them plus a prioritized fix list."),
    "method.basis": "Scoring basis",
    "method.basis_body": ("Total 0-100, weighted toward technical SEO health. "
                          "Scores are for short-term improvement tracking; search "
                          "rankings depend on competition, backlinks, and "
                          "content quality over the long term."),
    "method.disclaimer": "Disclaimer",
    "method.disclaimer_body": ("This report is auto-generated for decision-making "
                               "reference only. It is not a ranking guarantee or "
                               "legal advice. Have a qualified team review before "
                               "acting. Report (c) {year} {brand}."),
    "footer.note": "Report generated by {brand} AI platform · updated "
                   "{timestamp}",
}
COPY_MASTER = EN


def L(key, **fmt):
    """English-master copy lookup. Falls back to the key itself if missing."""
    txt = EN.get(key, key)
    if fmt:
        try:
            return txt.format(**fmt)
        except (KeyError, IndexError, ValueError):
            return txt
    return txt


def copy_for(locale):
    """Return (dict, L_func). English master now; drop-in for other locales."""
    raise NotImplementedError("Additional locales not yet shipped; use L() / EN.")


# ---------------------------------------------------------------------------
# Pattern metadata + canonical order (drives scorecard + section numbering)
# ---------------------------------------------------------------------------
PATTERNS = {
    "CRAWLABILITY": {"label": "Crawlability & Indexation", "short": "Crawlability"},
    "ONPAGE":       {"label": "On-page Relevance (Meta & Content)", "short": "On-page"},
    "CONTENT":      {"label": "Content & E-E-A-T", "short": "Content"},
    "SPEED":        {"label": "Site Speed & Core Web Vitals", "short": "Speed"},
    "LINKS":        {"label": "Internal Linking & Authority", "short": "Linking"},
    "SCHEMA":       {"label": "Schema & Structured Data", "short": "Schema"},
    "LOCAL":        {"label": "Local Search & Trust", "short": "Local"},
    "TRUST":        {"label": "Trust, Security & E-E-A-T", "short": "Trust"},
}
PATTERN_ORDER = list(PATTERNS.keys())

_PATTERN_KEYWORDS = {
    "CRAWLABILITY": ["noindex", "robots", "canonical", "redirect", "sitemap",
                     "crawl", "blocked", "index", "301", "status"],
    "ONPAGE": ["title", "meta description", "meta", "h1", "h2", "heading",
               "alt", "viewport", "lang attribute", "description"],
    "CONTENT": ["content", "thin", "word", "copy", "keyword", "text",
                "e-e-a-t", "blog", "depth", "article"],
    "SPEED": ["speed", "ttfb", "gzip", "brotli", "cache", "core web vital",
              "lazy", "load", "compression", "caching", "cdn", "first byte"],
    "LINKS": ["internal link", "backlink", "external link", "domain authority",
              "link", "anchor", "authority"],
    "SCHEMA": ["schema", "json-ld", "structured", "rich result",
               "localbusiness", "organization"],
    "LOCAL": ["local", "google business", "nap", "map pack", "gmb",
              "service area", "address"],
    "TRUST": ["https", "security", "certificate", "trust", "e-e-a-t"],
}


def classify_pattern(text):
    """Map a finding's text to one of the 8 patterns by keyword (deterministic)."""
    t = str(text or "").lower()
    if "e-e-a-t" in t and "trust" in t:
        return "TRUST"
    best, bestscore = "ONPAGE", 0
    for pat, kws in _PATTERN_KEYWORDS.items():
        s = sum(1 for k in kws if k in t)
        if s > bestscore:
            best, bestscore = pat, s
    return best


# ---------------------------------------------------------------------------
# Effort / priority / uplift metadata (deterministic)
# ---------------------------------------------------------------------------
EFFORT_META = {
    "quick":    {"label": "Quick (~1h)",      "hours": 1},
    "half-day": {"label": "Half-day",         "hours": 4},
    "day":      {"label": "1-2 days",         "hours": 12},
    "sprint":   {"label": "Sprint",           "hours": 40},
}
PRIORITY_META = {
    "urgent": {"label": "Urgent",       "impact": "Critical impact", "uplift": 6},
    "high":   {"label": "High",         "impact": "High impact",     "uplift": 4},
    "medium": {"label": "Medium",       "impact": "Medium impact",   "uplift": 2},
    "low":    {"label": "Low",          "impact": "Lower impact",    "uplift": 1},
}
_PRIO_RANK = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
_PRIO_CLS = {"urgent": "urgent", "high": "high", "medium": "medium", "low": "low"}

# Dollar-impact model (deterministic, stdlib): base annual revenue at risk per
# pattern, scaled by site type and priority. No LLM call -> works in fallback.
_DOLLAR_BY_PATTERN = {
    "CRAWLABILITY": 42000,
    "ONPAGE":       18000,
    "CONTENT":      36000,
    "SPEED":        24000,
    "LINKS":        48000,
    "SCHEMA":        9000,
    "LOCAL":        54000,
    "TRUST":        12000,
}
_SITE_TYPE_MULT = {
    "ecommerce": 1.4, "local_service": 1.2, "saas": 1.2,
    "content": 1.0, "corporate": 0.9, "unknown": 1.0,
}
_PRIO_DOLLAR_FACTOR = {"urgent": 1.5, "high": 1.0, "medium": 0.6, "low": 0.3}

# English-master persona line keyed by site_type (keeps the cover English even if
# a stored site_profile.persona_note is in another language).
EN_PERSONA = {
    "ecommerce": "Your site is an online store. Product-page schema, speed, and "
                 "crawlability decide how much you sell.",
    "content": "Your site is a content/media destination. Article depth, E-E-A-T, "
               "and internal linking decide whether your content ranks and retains readers.",
    "local_service": "Your site is a local service business. Google Business Profile, "
                     "LocalBusiness schema, and local search are your lifeline.",
    "saas": "Your site is a software/tool. Pricing-page indexability, speed, and "
            "conversion-structure directly affect how many customers you sign.",
    "corporate": "Your site is a corporate presence. Technical health, content depth, "
                 "and authority signals determine your trust in the vertical.",
    "unknown": "This report covers the full on-page technical health of the site.",
}


def dollar_for(item, site_type):
    """Est. annual revenue at risk for a finding (int) or None if no basis."""
    d = item.get("dollar_impact")
    if isinstance(d, (int, float)) and d > 0:
        return int(round(d))
    pat = item.get("pattern")
    base = _DOLLAR_BY_PATTERN.get(pat) if pat else None
    if not base:
        return None
    mult = _SITE_TYPE_MULT.get(site_type or "unknown", 1.0)
    fac = _PRIO_DOLLAR_FACTOR.get(item.get("priority", "low"), 0.3)
    return int(round(base * mult * fac / 100.0) * 100)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _effort(item):
    """Normalise an effort token -> (key, label)."""
    e = (item.get("effort") or item.get("effort_hint") or "").lower().strip()
    # map common synonyms / free text to canonical keys
    if any(k in e for k in ("quick", "1h", "~1h", "hour", "15 min")):
        key = "quick"
    elif "half" in e or "0.5" in e:
        key = "half-day"
    elif "sprint" in e or "week" in e:
        key = "sprint"
    else:
        key = "day"  # default for unknown effort tokens
    meta = EFFORT_META.get(key, EFFORT_META["day"])
    return key, meta["label"]


def _evidence_synthesis(item, data):
    """Build an evidence string from real measured signals when the finding did
    not ship its own 'evidence' field (tolerance for older JSONs)."""
    if item.get("evidence"):
        return item["evidence"]
    sigs = data.get("signals") or {}
    srv = data.get("server_signals") or {}
    pat = item.get("pattern")
    issue = str(item.get("issue") or "").lower()
    tl = sigs.get("title_length")
    if pat == "ONPAGE" and "title" in issue and isinstance(tl, int):
        return f"Measured: your <title> tag is {tl} characters."
    ml = sigs.get("meta_description_length")
    if pat == "ONPAGE" and "description" in issue and isinstance(ml, int):
        return f"Measured: your meta description is {ml} characters."
    missing = sigs.get("img_missing_alt")
    total = sigs.get("img_total")
    if isinstance(missing, int) and isinstance(total, int) and total > 0:
        return f"Measured: {missing} of {total} images are missing alt text."
    if pat == "SPEED":
        ttfb = srv.get("ttfb_ms")
        enc = srv.get("content_encoding")
        cache = srv.get("cache_control")
        bits = []
        if isinstance(ttfb, (int, float)):
            bits.append(f"TTFB {int(ttfb)} ms")
        if "gzip" in issue or "compress" in issue:
            bits.append(f"content-encoding: {enc or 'none'}")
        if "cache" in issue:
            bits.append(f"cache-control: {cache or 'none'}")
        if bits:
            return "Measured: " + "; ".join(bits) + "."
    h1c = sigs.get("h1_count")
    h2c = sigs.get("h2_count")
    if "h1" in issue and isinstance(h1c, int):
        return f"Measured: {h1c} H1 tag(s) on this page (h2_count={h2c})."
    canon = sigs.get("canonical")
    if pat == "CRAWLABILITY" and "canonical" in issue:
        return f"Measured: canonical is {'set' if canon else 'missing'} (robots: {sigs.get('meta_robots') or 'unset'})."
    return None


def enrich(item, data):
    """Attach pattern, effort, dollar impact, evidence + English labels (pure).
    Defensive: strips quote chars from any key the model/disk may have left. """
    _item = {}
    for _k, _v in dict(item).items():
        _kk = (str(_k) or "").strip().strip('"').strip("'")
        _item[_kk] = _v
    out = dict(_item)
    out["priority"] = (str(_item.get("priority") or "low")).lower().strip('"').strip("'")
    if out["priority"] not in ("urgent", "high", "medium", "low"):
        out["priority"] = "medium"
    out["pattern"] = (str(_item.get("pattern") or classify_pattern(_item.get("issue")))).upper().strip('"').strip("'")
    if out["pattern"] not in ("CRAWLABILITY", "ONPAGE", "CONTENT", "SPEED", "LINKS",
                              "SCHEMA", "LOCAL", "TRUST"):
        out["pattern"] = "ONPAGE"
    out["effort_key"], out["effort_label"] = _effort(item)
    out["impact"] = L("impact." + out["priority"])
    out["uplift"] = (item.get("uplift") or
                     int(item.get("points") or PRIORITY_META[out["priority"]]["uplift"]))
    try:
        out["uplift"] = int(out["uplift"])
    except (TypeError, ValueError):
        out["uplift"] = PRIORITY_META[out["priority"]]["uplift"]
    out["why"] = item.get("why_it_matters") or L("fd.evidence_default")
    out["how"] = item.get("how_to_fix") or "No fix steps were provided for this finding."
    out["code"] = item.get("code_snippet")
    site_type = (data.get("site_profile") or {}).get("site_type") or "unknown"
    out["dollar"] = dollar_for(out, site_type)
    out["evidence"] = _evidence_synthesis(out, data) or L("fd.evidence_default")
    out["priority_label"] = L("priority." + out["priority"])
    out["effort_hours"] = EFFORT_META.get(out["effort_key"], EFFORT_META["day"])["hours"]
    return out


def sort_issues(issues):
    return sorted(issues, key=lambda x: (_PRIO_RANK.get(x["priority"], 9),))


def group_by_pattern(issues):
    groups = {p: [] for p in PATTERN_ORDER}
    for i in issues:
        groups.setdefault(i["pattern"], []).append(i)
    return groups


def load_audit(path=None):
    """Load audit JSON. If none / empty / malformed, fall back to demo."""
    if path:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and (
                    data.get("url") or data.get("domain") or data.get("signals")):
                return data
        except Exception as e:
            print(f"[warn] could not load audit ({e}); using demo data",
                  file=sys.stderr)
    demo = json.loads(json.dumps(DEMO_AUDIT))
    return demo


def grade_for(score):
    """Return (grade_label, css_class). Thread-safe for None score."""
    if score is None:
        return L("grade.na"), "na"
    if score >= 85:   return L("grade.excellent"), "good"
    if score >= 70:   return L("grade.good"), "fair"
    if score >= 50:   return L("grade.needs_work"), "fair"
    if score >= 30:   return L("grade.weak"), "weak"
    return L("grade.critical"), "weak"


def _safe_score(data):
    """Return score as int-or-None without ever letting a raw None leak out."""
    score = data.get("score")
    if score is None:
        return None
    try:
        return max(0, min(100, int(round(float(score)))))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Section numbering -- derived from a single ordered list (no duplicates).
# ---------------------------------------------------------------------------
def _section_numbers():
    nums = {}
    n = 1
    for key in ("exec", "verdict", "scorecard"):
        nums[key] = n
        n += 1
    for p in PATTERN_ORDER:
        nums["pattern:" + p] = n
        n += 1
    for key in ("every_finding", "code", "benchmark", "top10", "data_quality",
                "methodology"):
        nums[key] = n
        n += 1
    return nums


_SECTION_NUMS = _section_numbers()


def _sec_h2(key, title, sub=None):
    num = _SECTION_NUMS[key]
    inner = f'<span class="num">{num:02d}</span>{escape(title)}'
    sub_html = f'<div class="secsub">{escape(sub)}</div>' if sub else ""
    return f'<h2 class="sec">{inner}</h2>{sub_html}'


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
def css():
    b = BRAND
    return f"""
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial,
                     sans-serif; color: {b['ink']}; background: {b['soft']};
          font-size: 13px; line-height: 1.55; }}
  .page {{ max-width: 820px; margin: 0 auto; background: {b['bg']}; }}
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
  .cover h1 {{ font-size: 32px; font-weight: 800; line-height: 1.15; }}
  .cover .lede {{ margin-top: 14px; color: #cfe0ec; font-size: 13.5px; max-width: 500px; }}
  .cover .type-badge {{ margin-top: 16px; display: inline-block; padding: 6px 14px;
    border-radius: 999px; background: rgba(255,255,255,0.10);
    border: 1px solid rgba(255,255,255,0.25); font-size: 12px; font-weight: 600;
    color: #e6f2fa; letter-spacing: 0.5px; }}
  .cover .meta {{ margin-top: 46px; display: grid; grid-template-columns: 1fr 1fr; gap: 10px 26px;
                  font-size: 12px; color: #aac3d6; }}
  .cover .meta b {{ color: #fff; font-weight: 700; }}
  .cover .foot {{ position: absolute; bottom: 40px; left: 52px; right: 52px;
                  display: flex; justify-content: space-between; font-size: 11px;
                  color: #7fa0ba; border-top: 1px solid rgba(255,255,255,.18);
                  padding-top: 12px; }}
  .score-pill {{ position: absolute; top: 48px; right: 52px; text-align: center;
                 background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.25);
                 padding: 14px 20px; border-radius: 14px; }}
  .score-pill .num {{ font-size: 30px; font-weight: 800; color: {b['accent']}; }}
  .score-pill .lbl {{ font-size: 10px; letter-spacing: 1.5px; color: #bfd4e3; }}
  .verdict-pill {{ display: inline-block; margin-top: 8px; background: {b['accent']};
              color: #03281a; font-weight: 800; font-size: 11px; padding: 4px 12px;
              border-radius: 20px; }}

  /* ---------- h2 section titles ---------- */
  h2.sec {{ font-size: 18px; color: {b['navy']}; font-weight: 800; margin-bottom: 4px;
            display: flex; align-items: center; gap: 10px; }}
  h2.sec .num {{ background: {b['navy']}; color: #fff; width: 26px; height: 26px;
                 border-radius: 7px; display: inline-flex; align-items: center;
                 justify-content: center; font-size: 12px; }}
  .secsub {{ color: {b['muted']}; font-size: 12px; margin-bottom: 20px; }}
  .hline {{ width: 100%; height: 1px; background: #e5edf3; margin: 16px 0; }}

  /* ---------- gauge + exec summary ---------- */
  .exec {{ display: grid; grid-template-columns: 220px 1fr; gap: 34px; align-items: center; }}
  .gauge {{ width: 200px; height: 200px; border-radius: 50%;
            background: conic-gradient({b['accent']} calc(var(--p)*1%), #e6eef4 0);
            display: grid; place-items: center; position: relative; margin: 6px auto; }}
  .gauge::before {{ content: ""; position: absolute; inset: 18px; border-radius: 50%;
                    background: #fff; }}
  .gauge .center {{ position: relative; text-align: center; }}
  .gauge .big {{ font-size: 44px; font-weight: 800; color: {b['navy']}; line-height: 1; }}
  .gauge .of {{ font-size: 12px; color: {b['muted']}; }}
  .gauge .grade {{ position: absolute; bottom: 40px; left: 0; right: 0; text-align: center;
                   font-size: 12px; font-weight: 700; color: {b['accent']}; }}
  .kpis {{ display: flex; gap: 12px; flex-wrap: wrap; }}
  .kpi {{ background: {b['soft']}; border: 1px solid #e3ebf1; border-radius: 12px;
         padding: 12px 14px; flex: 1; min-width: 108px; }}
  .kpi .v {{ font-size: 24px; font-weight: 800; color: {b['navy']}; }}
  .kpi .k {{ font-size: 10.5px; color: {b['muted']}; }}
  .pot {{ color: {b['accent']}; font-weight: 800; }}

  /* ---------- verdict box ---------- */
  .verdict-box {{ border: 1px solid #dbe6ee; border-left: 5px solid {b['accent']};
                  border-radius: 12px; padding: 16px 20px; background: #f6faf6; }}
  .verdict-box .v-head {{ font-weight: 800; color: {b['navy']}; font-size: 14px;
                          margin-bottom: 6px; }}

  /* ---------- scorecard rows ---------- */
  .scrow {{ display: grid; grid-template-columns: 210px 1fr 96px; align-items: center;
            gap: 14px; background: {b['soft']}; border: 1px solid #e3ebf1;
            border-radius: 12px; padding: 12px 16px; margin-bottom: 9px; }}
  .scrow .pn {{ font-weight: 800; color: {b['navy']}; font-size: 12.5px; }}
  .scrow .pn small {{ display: block; font-weight: 400; color: #7c93a6; font-size: 10.5px; }}
  .bar {{ height: 10px; background: #dfe8ef; border-radius: 6px; overflow: hidden; }}
  .bar > span {{ display: block; height: 100%; border-radius: 6px;
                 background: linear-gradient(90deg, {b['accent']}, #2dd4a7); }}
  .scrow .pv {{ text-align: right; font-weight: 800; color: {b['navy']}; font-size: 12.5px; }}

  /* ---------- findings ---------- */
  .finding {{ border: 1px solid #e7eef3; border-left: 4px solid {b['accent']};
             border-radius: 10px; padding: 14px 18px; margin-bottom: 14px; background: #fff; }}
  .finding.urgent {{ border-left-color: #ef4444; }}
  .finding.high {{ border-left-color: #f59e0b; }}
  .finding.medium {{ border-left-color: #facc15; }}
  .finding.low {{ border-left-color: #94a3b8; }}
  .finding.na {{ border-left-color: {b['muted']}; }}
  .f-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }}
  .f-title {{ font-weight: 800; color: {b['navy']}; font-size: 13.5px; }}
  .prio {{ background: {b['muted']}; color: #fff; font-size: 10px; font-weight: 800;
           padding: 3px 9px; border-radius: 5px; white-space: nowrap; }}
  .prio.urgent {{ background: #ef4444; }}
  .prio.high {{ background: #f59e0b; color: #3d2c00; }}
  .prio.medium {{ background: #f0c400; color: #3d3000; }}
  .prio.low {{ background: #94a3b8; }}
  .prio.na {{ background: {b['muted']}; }}
  .chips {{ display: flex; gap: 8px; margin: 10px 0 10px; flex-wrap: wrap; }}
  .chip {{ font-size: 10px; font-weight: 800; padding: 4px 10px; border-radius: 20px;
           letter-spacing: .3px; }}
  .chip.pat {{ background: #e6eef4; color: {b['navy']}; }}
  .chip.pri {{ background: #eef4ee; color: #0f6b46; }}
  .chip.imp {{ background: #f3eef4; color: #6b2d8e; }}
  .chip.up {{ background: #e7f0e8; color: #127a43; }}
  .pe-lab {{ font-size: 10px; font-weight: 900; color: {b['muted']}; text-transform: uppercase;
             letter-spacing: .6px; margin: 8px 0 3px; }}
  .f-body {{ font-size: 12.5px; color: {b['ink']}; max-width: 660px; }}
  .effort {{ display: inline-block; margin-top: 10px; padding: 4px 12px; border-radius: 20px;
             font-size: 11px; font-weight: 800; }}
  .effort.quick {{ background: {b['accent']}22; color: #0f6b46; }}
  .effort.half-day {{ background: #e5f2e5; color: #1a7d3a; }}
  .effort.day {{ background: #fdf3d7; color: #92500e; }}
  .effort.sprint {{ background: #fdecec; color: #b3372b; }}
  pre.code {{ background: {b['navy_dark']}; color: #d3e6f5; border-radius: 8px;
              padding: 12px 14px; font-family: ui-monospace, SFMono-Regular, Menlo,
              Consolas, monospace; font-size: 11.5px; overflow-x: auto; margin-top: 8px;
              white-space: pre-wrap; line-height: 1.5; }}

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
             justify-content: center; font-weight: 800; font-size: 13px;
             content: counter(act); }}
  .act .n::after {{ }}
  .act .t {{ font-weight: 700; color: {b['navy']}; font-size: 13px; }}
  .act .u {{ text-align: right; color: {b['accent']}; font-weight: 800; font-size: 12px; }}

  .note {{ font-size: 11px; color: {b['muted']}; line-height: 1.6; }}
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


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------
def cover_html(data):
    b = BRAND
    p = data.get("server_signals") or {}
    ts = data.get("timestamp") or ""
    score = _safe_score(data)
    grade, gclass = grade_for(score)
    prof = data.get("site_profile") or {}
    st = prof.get("site_type", "unknown")
    labels = prof.get("labels") or ["Website"]
    persona = EN_PERSONA.get(st, EN_PERSONA["unknown"])
    label_en = labels[-1] if labels else "Website"
    type_badge = L("cover.type_badge", label=escape(label_en))
    score_num = str(score) if score is not None else "N/A"
    ttfb = p.get("ttfb_ms")
    ttfb_txt = f"{ttfb} ms" if isinstance(ttfb, (int, float)) else "—"
    return f"""
  <div class="cover">
    <div class="brand"><span class="logo-dot"></span>{escape(b['name'])}
      <span class="subtitle">{escape(b['tagline'])}</span></div>
    <div class="score-pill"><div class="num">{score_num}</div>
      <div class="lbl">{escape(L('cover.score_lbl'))}</div>
      <div class="verdict-pill">{escape(grade)}</div></div>
    <div class="rule"></div>
    <h1>{escape(L('cover.title'))}</h1>
    <div class="type-badge">{type_badge}</div>
    <div class="lede">{escape(L('cover.lede', persona=persona))}</div>
    <div class="meta">
      <div><b>{escape(L('cover.audit_url'))}</b><br>{escape(str(data.get('url','')))}</div>
      <div><b>{escape(L('cover.http_status'))}</b><br>{p.get('http_status','—')}</div>
      <div><b>{escape(L('cover.report_date'))}</b><br>{escape(ts)}</div>
      <div><b>{escape(L('cover.ttfb_label'))}</b><br>{ttfb_txt}</div>
    </div>
    <div class="foot">
      <span>© {_YEAR} {escape(b['name'])} · {escape(b['contact'])}</span>
      <span>{escape(L('cover.foot_internal'))}</span>
    </div>
  </div>
"""


def gauge_html(score):
    if score is None:
        return (f'<div class="gauge" style="--p:0"><div class="center">'
                f'<div class="big">—</div><div class="of">/ 100</div>'
                f'<div class="grade">{escape(L("grade.na"))}</div></div></div>')
    return (f'<div class="gauge" style="--p:{score}"><div class="center">'
            f'<div class="big">{score}</div><div class="of">/ 100</div></div></div>')


def exec_summary_html(data):
    b = BRAND
    issues = [enrich(x, data) for x in data.get("fix_list") or []]
    urgent = sum(1 for i in issues if (i.get("priority") or "") == "urgent")
    pot = sum(i["uplift"] for i in sort_issues(issues)[:10])
    score = _safe_score(data)
    new_score = (min(100, score + pot)) if score is not None else None
    grade, _ = grade_for(score)
    groups = group_by_pattern(issues)
    topp = max(PATTERN_ORDER, key=lambda p: len(groups[p]))
    top_label = PATTERNS[topp]["label"] if topp and groups.get(topp) else PATTERNS["ONPAGE"]["label"]
    if score is None:
        lede = L("exec.na")
    else:
        lede = L("exec.lede", score=score, grade=grade,
                 proj=("N/A" if new_score is None else new_score),
                 toppattern=escape(top_label), muted=b["muted"])
    return f"""
  <div class="section">
    {_sec_h2('exec', L('sec.exec'), L('sec.exec_sub'))}
    <div class="hline"></div>
    <div class="exec">
      {gauge_html(score)}
      <div>
        <div class="kpis">
          <div class="kpi"><div class="v">{urgent}</div><div class="k">{escape(L('kpi.urgent'))}</div></div>
          <div class="kpi"><div class="v">{len(issues)}</div><div class="k">{escape(L('kpi.total'))}</div></div>
          <div class="kpi"><div class="v pot">+{pot}</div><div class="k">{escape(L('kpi.upside'))}</div></div>
          <div class="kpi"><div class="v pot">{'N/A' if new_score is None else new_score}</div>
              <div class="k">{escape(L('kpi.projected'))}</div></div>
        </div>
        <p style="margin-top:16px;font-size:13px;color:{b['ink']}">{lede}</p>
      </div>
    </div>
  </div>
"""


def verdict_html(data):
    issues = [enrich(x, data) for x in data.get("fix_list") or []]
    score = _safe_score(data)
    grade, _ = grade_for(score)
    groups = group_by_pattern(issues)
    ranked = sorted(PATTERN_ORDER, key=lambda p: -len(groups[p]))
    top = ranked[0] if ranked and groups.get(ranked[0]) else None
    top2 = ranked[1] if len(ranked) > 1 and groups.get(ranked[1]) else None

    if score is None:
        head = L("verdict.open_na")
    else:
        head = L("verdict.open", score=score, grade=grade)
    # band sentence from score band
    if score is None:
        band = L("verdict.na_tail")
    elif score >= 85:
        band = L("verdict.band.excellent")
    elif score >= 70:
        band = L("verdict.band.good")
    elif score >= 50:
        band = L("verdict.band.needs_work")
    elif score >= 30:
        band = L("verdict.band.weak")
    else:
        band = L("verdict.band.critical")

    if top is not None:
        dollars = sorted((dollar_for(i, (data.get("site_profile") or {}).get("site_type"))
                          for i in groups[top] if dollar_for(i, (data.get("site_profile") or {}).get("site_type"))),
                         reverse=True)
        d = dollars[0] if dollars else 0
        drag = L("verdict.drag", label=PATTERNS[top]["label"], n=len(groups[top]),
                 dollar=f"{d:,}" if d else d)
        win_pool = [i for p in (top, top2) if p for i in groups.get(p, [])
                    if i["effort_key"] == "quick"]
        win = (L("verdict.win", n=len(win_pool), label=PATTERNS[top]["label"])
               if win_pool else L("verdict.win_none"))
    else:
        drag = L("verdict.drag_none")
        win = L("verdict.win_none")

    para = head + band + drag + win + ("" if score is not None else L("verdict.na_tail"))
    return f"""
  <div class="section">
    {_sec_h2('verdict', L('sec.verdict'), L('sec.verdict_sub'))}
    <div class="hline"></div>
    <div class="verdict-box"><div class="v-head">{escape(grade)}</div>
      <div class="f-body">{escape(para)}</div></div>
  </div>
"""


def scorecard_html(data):
    issues = [enrich(x, data) for x in data.get("fix_list") or []]
    groups = group_by_pattern(issues)
    maxn = max((len(g) for g in groups.values()), default=1) or 1
    rows = []
    for p in PATTERN_ORDER:
        lst = groups.get(p, [])
        n = len(lst)
        if n == 0:
            rows.append(f"""
      <div class="scrow">
        <div class="pn">{escape(PATTERNS[p]['label'])}<small>{escape(L('scorecard.none'))}</small></div>
        <div class="bar"><span style="width:0%"></span></div>
        <div class="pv" style="color:#9aa8b6">—</div>
      </div>""")
            continue
        bar = int(round(n / maxn * 100))
        sub = sum(i["uplift"] for i in lst)
        rows.append(f"""
      <div class="scrow">
        <div class="pn">{escape(PATTERNS[p]['label'])}
          <small>{escape(L('scorecard.row_pct', n=n))}</small></div>
        <div class="bar"><span style="width:{bar}%"></span></div>
        <div class="pv">{'+' + str(sub)}</div>
      </div>""")
    return f"""
  <div class="section">
    {_sec_h2('scorecard', L('sec.scorecard'), L('sec.scorecard_sub'))}
    <div class="hline"></div>
    {''.join(rows)}
  </div>
"""


def _finding_card(idx, item):
    i = item
    prio_cls = _PRIO_CLS.get(i["priority"], "na")
    code = ""
    if i["code"]:
        code = f'<pre class="code">{escape(i["code"])}</pre>'
    if i["dollar"] is not None:
        dollar = L("fd.dollar_value", amt=f"{i['dollar']:,}")
    else:
        dollar = L("fd.dollar_unquantified")
    effort = f'<span class="effort {escape(i["effort_key"])}">{escape(L("fd.effort", effort=i["effort_label"], pts=i["uplift"]))}</span>'
    return f"""
      <div class="finding {prio_cls}">
        <div class="f-head">
          <div class="f-title">#{idx} {escape(i['issue'])}</div>
          <span class="prio {prio_cls}">{escape(i['priority_label'])}</span>
        </div>
        <div class="chips">
          <span class="chip pat">{escape(L('fd.chip_pattern'))}: {escape(PATTERNS.get(i['pattern'], {}).get('short', i['pattern']))}</span>
          <span class="chip pri">{escape(L('fd.chip_priority'))}: {escape(i['priority_label'])}</span>
          <span class="chip imp">{escape(i['impact'])}</span>
          <span class="chip up">{escape(L('fd.chip_uplift'))}: +{i['uplift']} pts</span>
        </div>
        <div class="pe-lab">{escape(L('fd.problem'))}</div>
        <div class="f-body">{escape(i['issue'])}</div>
        <div class="pe-lab">{escape(L('fd.evidence'))}</div>
        <div class="f-body">{escape(i['evidence'])}</div>
        <div class="pe-lab">{escape(L('fd.dollar'))}</div>
        <div class="f-body">{escape(dollar)}</div>
        <div class="pe-lab">{escape(L('fd.how'))}</div>
        <div class="f-body">{escape(i['how'])}</div>
        {code}
        {effort}
      </div>
"""


def pattern_section_html(pat, issues):
    """One section per pattern, wrapping ONLY its own cards (grouping fix)."""
    caps = issues[:5]
    cards = "".join(_finding_card(j + 1, i) for j, i in enumerate(caps))
    total = len(issues)
    sub = (f"{PATTERNS[pat]['label']} -- {total} finding(s), priority + "
           f"impact ordered. "
           f"{('Showing first 5; see Every Finding for all ' + str(total) + '.') if total > 5 else ''}")
    return f"""
  <div class="section" data-pattern="{escape(pat)}">
    {_sec_h2('pattern:' + pat, L('sec.pattern') + ': ' + PATTERNS[pat]['label'], sub)}
    <div class="hline"></div>
    {cards}
  </div>
"""


def every_finding_html(data):
    issues = [enrich(x, data) for x in data.get("fix_list") or []]
    issues = sort_issues(issues)
    groups = group_by_pattern(issues)
    blocks = []
    idx = 0
    for p in PATTERN_ORDER:
        lst = groups[p]
        if not lst:
            continue
        blocks.append(f"""
      <h3 style="font-size:14px;color:#0f2a43;font-weight:800;margin:14px 0 6px">{escape(PATTERNS[p]['label'])} <span style="font-weight:400;color:#7c93a6;font-size:11px">({len(lst)})</span></h3>""")
        for i in sort_issues(lst):
            idx += 1
            blocks.append(_finding_card(idx, i))
    if not blocks:
        blocks = ['<div class="f-body">No findings captured for this audit.</div>']
    return f"""
  <div class="section">
    {_sec_h2('every_finding', L('sec.every'), L('sec.every_sub'))}
    <div class="hline"></div>
    {''.join(blocks)}
  </div>
"""


def code_section_html(data):
    issues = [enrich(x, data) for x in data.get("fix_list") or []]
    blocks = []
    for i in issues:
        if i["code"]:
            blocks.append(f"""
      <div class="finding {_PRIO_CLS.get(i['priority'], 'na')}">
        <div class="f-title" style="margin-bottom:4px">{escape(i['issue'])}</div>
        <pre class="code">{escape(i['code'])}</pre>
      </div>""")
    if not blocks:
        blocks = [f'<div class="f-body">{escape(L("sec.code_empty"))}</div>']
    return f"""
  <div class="section">
    {_sec_h2('code', L('sec.code'), L('sec.code_sub'))}
    <div class="hline"></div>
    {''.join(blocks)}
  </div>
"""


def competitor_html(data):
    comps = data.get("competitors")
    if not comps:
        rows = (f'<tr><td colspan="5" style="text-align:center;color:#5c7184;font-weight:700">'
                f'{escape(L("sec.benchmark_nodata"))}</td></tr>')
        note = L("sec.benchmark_sub")
    else:
        rows = []
        for c in comps:
            name = c.get("name", "")
            you = " you" if (isinstance(name, str) and "SEO Scan" in name) else ""
            rows.append(f"""
      <tr class="{you}"><td>{escape(str(name))}</td><td>{c.get('da','—')}</td>
        <td>{c.get('score','—')}</td><td>{escape(str(c.get('speed','—')))}</td>
        <td>{escape(str(c.get('note','')))}</td></tr>""")
        rows = "".join(rows)
        note = L("sec.benchmark_sub")
    return f"""
  <div class="section">
    {_sec_h2('benchmark', L('sec.benchmark'), note)}
    <div class="hline"></div>
    <table>
      <thead><tr><th>{escape(L('bench.col_site'))}</th><th>{escape(L('bench.col_da'))}</th>
        <th>{escape(L('bench.col_score'))}</th><th>{escape(L('bench.col_speed'))}</th>
        <th>{escape(L('bench.col_note'))}</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
"""


def top10_html(data):
    issues = sort_issues([enrich(x, data) for x in data.get("fix_list") or []])[:10]
    rows = []
    for i in issues:
        rows.append(f"""
      <div class="act">
        <div class="n">{len(rows) + 1}</div>
        <span class="t">{escape(i['issue'])}</span>
        <span class="u">+{i['uplift']} pts</span>
      </div>""")
    return f"""
  <div class="section">
    {_sec_h2('top10', L('sec.top10'), L('sec.top10_sub'))}
    <div class="hline"></div>
    <div class="toplist">{''.join(rows)}</div>
  </div>
"""


def data_quality_html(data):
    dq = data.get("data_quality") or {}
    srv = data.get("server_signals") or {}
    if not dq:
        dq = {
            "fetch_ok": bool(srv.get("http_status")),
            "http_status": srv.get("http_status"),
            "ttfb_ms": srv.get("ttfb_ms"),
            "fallback_used": bool(data.get("fallback_used")),
            "ai_error": data.get("ai_error"),
            "crawl_errors": data.get("crawl_errors") or [],
            "score_is_estimate": bool(data.get("score_is_estimate") or data.get("fallback_used")),
            "label": "",
        }
    fetch_ok = bool(dq.get("fetch_ok"))
    fallback = bool(dq.get("fallback_used"))
    status = dq.get("http_status")
    ttfb = dq.get("ttfb_ms")
    ai_err = dq.get("ai_error")
    crawl_errs = dq.get("crawl_errors") or []
    fallback_label = L("dq.no_fallback") if fallback else L("dq.yes_crawl")
    if dq.get("label"):
        label = str(dq.get("label"))
        # any non-English (e.g. legacy CJK) label -> map to an English label
        if re.search(r"[\u3400-\u9fff]", label):
            label = fallback_label if fallback else (L("dq.yes_crawl") if fetch_ok else "Crawl incomplete")
    else:
        label = fallback_label if fallback else (L("dq.yes_crawl") if fetch_ok else "Crawl incomplete")
    badge_cls = "dq-ok" if (fetch_ok and not fallback) else ("dq-est" if fallback else "dq-warn")
    status_txt = str(status) if status is not None else L("dq.na")
    ttfb_txt = (str(ttfb) + " ms") if isinstance(ttfb, (int, float)) else L("dq.na")
    # clean rule-fallback suffixes from AI error / crawl errors
    def _clean(x):
        return str(x).split(" [used rule")[0]
    errs = " ; ".join([_clean(a) for a in crawl_errs]) if crawl_errs else ""
    if not errs and ai_err:
        errs = _clean(ai_err)
    ai_txt = _clean(ai_err) if ai_err else L("dq.na")
    row = ""
    if not fetch_ok:
        row += f'<div class="f-body" style="color:#c0392b">⚠️ {escape(L("dq.note_fetch_fail"))}</div>'
    if fallback:
        row += f'<div class="f-body" style="color:#92400e">{L("dq.note_fallback")}</div>'
    yes = L("dq.yes")
    no = L("dq.no")
    yn = yes if fetch_ok else no
    yn2 = yes if fallback else no
    return f"""
  <div class="section">
    {_sec_h2('data_quality', L('sec.dataq'), L('sec.dataq_sub'))}
    <div class="hline"></div>
    <div class="dq-badge {badge_cls}">{escape(L('sec.dq_badge', label=label))}</div>
    <table>
      <thead><tr><th>Metric</th><th>Value</th><th>Detail</th></tr></thead>
      <tbody>
        <tr><td>{escape(L('dq.fetch'))}</td><td>{yn}</td><td>{escape(L('dq.desc.fetch'))}</td></tr>
        <tr><td>{escape(L('dq.status'))}</td><td>{status_txt}</td><td>{escape(L('dq.desc.status'))}</td></tr>
        <tr><td>{escape(L('dq.ttfb'))}</td><td>{ttfb_txt}</td><td>{escape(L('dq.desc.ttfb'))}</td></tr>
        <tr><td>{escape(L('dq.fallback'))}</td><td>{yn2}</td><td>{escape(L('dq.desc.fallback'))}</td></tr>
        <tr><td>{escape(L('dq.ai_err'))}</td><td>{escape(ai_txt) if ai_txt else L('dq.na')}</td>
            <td>{escape(L('dq.desc.ai_err'))}</td></tr>
        <tr><td>{escape(L('dq.crawl_err'))}</td><td>{escape(errs) if errs else L('dq.na')}</td>
            <td>{escape(L('dq.desc.crawl_err'))}</td></tr>
      </tbody>
    </table>
    {row}
  </div>
"""


def methodology_html(data):
    b = BRAND
    return f"""
  <div class="section" style="padding-top:8px">
    {_sec_h2('methodology', L('sec.method'))}
    <div class="hline"></div>
    <div class="note">
      <b>{escape(L('method.scope'))}:</b> {escape(L('method.scope_body'))}<br><br>
      <b>{escape(L('method.basis'))}:</b> {escape(L('method.basis_body'))}<br><br>
      <b>{escape(L('method.disclaimer'))}:</b> {escape(L('method.disclaimer_body', year=_YEAR, brand=b['name']))}
    </div>
  </div>
"""


def build_html(data):
    issues = [enrich(x, data) for x in data.get("fix_list") or []]
    groups = group_by_pattern(issues)
    parts = [
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">',
        f"<title>{escape(L('cover.title'))}</title>",
        css(), "</head><body><div class=\"page\">",
        cover_html(data),
        exec_summary_html(data),
        verdict_html(data),
        scorecard_html(data),
    ]
    for p in PATTERN_ORDER:
        if groups.get(p):
            parts.append(pattern_section_html(p, sort_issues(groups[p])))
    parts += [
        every_finding_html(data),
        code_section_html(data),
        competitor_html(data),
        top10_html(data),
        data_quality_html(data),
        methodology_html(data),
        (f'<div class="footer-note" style="padding:0 44px 34px">'
         f'{escape(L("footer.note", brand=BRAND["name"], timestamp=data.get("timestamp", "")))}</div>'),
        "</div></body></html>",
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# PDF (optional; HTML always works)
# ---------------------------------------------------------------------------
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
        print("[warn] no headless Chromium found -- HTML generated only, no PDF",
              file=sys.stderr)
        return False
    cmd = [chromium, "--headless", "--no-sandbox", "--disable-gpu",
           "--no-margins", "--no-pdf-header-footer", "--print-to-pdf=" + pdf_path,
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


# ---------------------------------------------------------------------------
# Demo audit data (English; shows rich PE cards with measured-style values)
# ---------------------------------------------------------------------------
DEMO_AUDIT = {
    "url": "https://acme-local-plumbing.com",
    "domain": "acme-local-plumbing.com",
    "timestamp": "2026-09-12T12:00:00Z",
    "score": 64,
    "server_signals": {"http_status": 200, "ttfb_ms": 1240, "page_size_bytes": 214000,
                       "content_encoding": None, "has_gzip_or_br": False,
                       "cache_control": None, "has_cache_headers": False},
    "signals": {"title_length": 61, "meta_description_length": 175, "h1_count": 0,
                "h2_count": 12, "img_total": 31, "img_missing_alt": 31,
                "canonical": None, "has_lang_attr": True, "viewport": "width=device-width,initial-scale=1"},
    "site_profile": {"site_type": "local_service",
                     "labels": ["Local Business", "Service & Repair"],
                     "weights": {"local": 0.25, "schema": 0.20, "technical": 0.15}},
    "fix_list": [
        {"priority": "urgent", "pattern": "SCHEMA", "effort": "half-day",
         "issue": "Missing LocalBusiness JSON-LD schema",
         "evidence": "Measured: 0 JSON-LD blocks on this page; Google has no structured entity for your business.",
         "why_it_matters": "Without LocalBusiness schema Google cannot reliably surface your business in the local map pack.",
         "how_to_fix": "Add a LocalBusiness / PlumbingBusiness JSON-LD block to the homepage.",
         "code_snippet": "<script type=\"application/ld+json\">\n{\"@context\": \"https://schema.org\", \"@type\": \"PlumbingBusiness\", \"name\": \"Acme Plumbing\", \"areaServed\": \"Central\"}\n</script>"},
        {"priority": "urgent", "pattern": "CRAWLABILITY", "effort": "quick",
         "issue": "HTTP and HTTPS both serve content (no forced 301)",
         "evidence": "Measured: canonical is missing; 2 live protocol variants split ranking signals.",
         "why_it_matters": "Parallel HTTP/HTTPS creates duplicate content and dilutes link equity.",
         "how_to_fix": "Add a 301 permanent redirect from HTTP to HTTPS and set one canonical.",
         "code_snippet": "RewriteEngine On\nRewriteCond %{HTTPS} off\nRewriteRule ^(.*)$ https://%{HTTP_HOST}/$1 [R=301,L]"},
        {"priority": "high", "pattern": "ONPAGE", "effort": "quick",
         "issue": "No H1 tag found on the page",
         "evidence": "Measured: 0 H1 tags (h2_count=12). Google reads H1 as the page's main subject.",
         "why_it_matters": "A missing H1 leaves search engines guessing the page topic and hurts scannability.",
         "how_to_fix": "Add one unique H1 containing the primary keyword.",
         "code_snippet": "<h1>24-Hour Emergency Plumbing & Drain Cleaning</h1>"},
        {"priority": "high", "pattern": "SPEED", "effort": "quick",
         "issue": "TTFB is slow at 1240 ms with no gzip or cache-control",
         "evidence": "Measured: TTFB 1240 ms (>600 ms target); content-encoding: none; cache-control: none.",
         "why_it_matters": "Slow time-to-first-byte and uncompressed assets inflate Core Web Vitals and raise bounce rate.",
         "how_to_fix": "Enable gzip/brotli, set long cache-control on static assets, and add a CDN.",
         "code_snippet": "AddOutputFilterByType DEFLATE text/html\nCache-Control: public, max-age=604800"},
        {"priority": "high", "pattern": "CONTENT", "effort": "day",
         "issue": "Thin content: service pages average ~180 words",
         "evidence": "Measured: average body copy ~180 words on sampled service templates.",
         "why_it_matters": "Thin pages struggle to establish topic authority against fuller competitors.",
         "how_to_fix": "Expand each service page to 800+ words with FAQ, case studies, and pricing.", "code_snippet": None},
        {"priority": "medium", "pattern": "ONPAGE", "effort": "quick",
         "issue": "31 of 31 images missing alt text",
         "evidence": "Measured: 31 of 31 images have no alt attribute.",
         "why_it_matters": "Missing alt hurts image search, accessibility, and on-page relevance.",
         "how_to_fix": "Add descriptive alt to informative images; use alt=\"\" for decorative ones.",
         "code_snippet": "<img src=\"pump-install.jpg\" alt=\"Emergency hot-water tank installation\" loading=\"lazy\">"},
        {"priority": "medium", "pattern": "LINKS", "effort": "half-day",
         "issue": "No internal links from homepage to core service pages",
         "evidence": "Measured: homepage ships 0 internal links to /services/* pages.",
         "why_it_matters": "Missing internal links trap PageRank and limit crawl depth.",
         "how_to_fix": "Add anchor-text internal links in footer and body pointing to each core service page.",
         "code_snippet": "<a href=\"/services/emergency-pump\">Emergency Pump Repair</a>"},
        {"priority": "low", "pattern": "TRUST", "effort": "sprint",
         "issue": "No external link-building strategy in place",
         "evidence": "Measured: domain authority ~8; 0 detectable referring domains in your niche.",
         "why_it_matters": "Low authority caps rankings against stronger competitors on money pages.",
         "how_to_fix": "Earn 3-5 credible links monthly from directories, media, and suppliers.",
        "code_snippet": None},
    ],
}


if __name__ == "__main__":
    main()
