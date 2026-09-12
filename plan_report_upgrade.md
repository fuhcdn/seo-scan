# Report Quality Upgrade Plan — English Master, Agency-grade

Owner: Yan — seoscanaudit.com. Goal: turn the current Cantonese flat-list report into a
top-tier English SEO-agency report that still looks professional when the AI scorer fails
(rule-based fallback path).

## Root causes found (reading the actual code/output)

1. **English is an afterthought.** `seo_report_template.py` renders everything in Cantonese
   (cover h1, lede, meta labels, KPIs, chips, priority words, data-quality rows, methodology);
   English only appears as a trailing section subtitle ("執行摘要 Executive Summary"). The
   real generated `out/hermes-agent...html` confirms it.
2. **Findings are a detached 340-line list.** `finding_cards()` emits all 5 pillar `<h2>` headers
   in a row first, then ALL cards appended after them — so cards are **not** grouped under their
   headings. No verdict opening, no dollar impact, no effort, flat priority-only ordering.
3. **Section numbering is broken.** Section 06 = Code Snippets collides with pillar 06 (本地SEO)
   and 07 = Competitor collides with pillar 07 (UX). `build_html()` order is cover, exec, pillars,
   findings, code, **top10, competitor**, data-quality, methodology — heading numbers disagree with
   body order (competitor=07 but rendered after top10=08).
4. **Rule-based fallback is canned Cantonese.** `rule_based_fixes()` in `seo_crawler.py` returns
   static strings with no real measured values and no effort/dollar fields.
5. **Brand drift.** Template brand is "SEOAudit.ai / hello@seoaudit.ai" but the business is
   SEO Scan.ai (seoscanaudit.com). Localization already follows an EN-master pattern in
   `generate_languages.py` — mirror it.

## What to change — file by file

### A. seo_crawler.py (evidence + fallback enrichment)

- **Enrich the AI prompt** (`SCORING_PROMPT`) to demand five extra fields per fix and English master:
  - `pattern`: one of CRAWLABILITY / ONPAGE / CONTENT / SPEED / LINKS / SCHEMA / LOCAL / TRUST.
  - `effort`: "quick" | "half-day" | "day" | "sprint" (with a hint sentence).
  - `dollar_impact`: an integer "potential annual revenue at risk (USD, est.)" the model derives
    from site_type + page importance + competitive set. Explicitly asked to reason conservatively.
  - `evidence`: quote the exact signal value it is responding to (e.g. "your <title> is 184 chars").
  - Change the language line to: "Write ALL explanations in English (master copy)."
  - Bump `max_tokens` 1600 -> 2400 for the larger schema.
- **Rewrite `rule_based_fixes()`** to interpolate **real measured values** instead of canned copy.
  Add a tiny template per rule that injects `{title}`, `{title_len}`, `{meta_len}`, `{h1_count}`,
  `{img_total}`, `{img_missing_alt}`, `{ttfb_ms}`, `{has_gzip}`, `{has_cache}`, `{canonical}`, etc.
  Example: missing-H1 finding becomes
  "Evidence: your page has 0 H1 tags (h2_count=12). Google reads the H1 as the page's main subject…"
  Every rule gets `pattern`, `effort`, `dollar_impact` defaults (dollar impact scaled by
  site_type weights from site_profiler, e.g. e-commerce schema/speed higher than corporate).
- Keep the `data_quality` block, but emit English labels.

### B. seo_report_template.py (the main rebuild)

Introduce an EN-master copy dictionary (mirror `generate_languages.py` structure so other
languages drop in later). Add a `L()` lookup. Every user-visible string routes through it.

**New report outline (section order fixes numbering, adds verdict + patterns):**

1. Cover — "AI SEO Audit Report" + score pill + grade + domain + date + TTFB. English only.
2. 01 Executive Summary — gauge, KPIs (Urgent / Total findings / Est. upside / Projected score),
   **and the VERDICT box** (2-3 sentences, deterministic): e.g.
   "Score 64/100 — Needs Work. Your site's top drag is Speed: TTFB 1.2s costs you ranking on
   money pages. Fixing the 4 half-day-effort speed issues is your fastest win."
3. 02 Verdict at a glance — the verdict box goes here as its own section (or merges into 01).
4. 03 Scorecard by Pattern — bar rows per pattern (not per pillar): Crawlability, On-page,
   Content & E-E-A-T, Speed, Linking, Schema, Local/Trust, each with count + est. upside.
5. 04–09 Patterns & Findings — **one section per pattern**, each opens with a one-line pattern
   verdict ("Speed is your #1 drag — 4 findings, est. +9 pts"), then that pattern's cards only
   (collapsible, cap 5 per pattern on page 1 with "Show all M findings" anchor).
6. 10 Every Finding (full list) — the complete flat list grouped by pattern, for the appendix.
7. 11 Code Snippets.
8. 12 Competitive Benchmark (show real-data placeholder only, as today).
9. 13 Top-10 Priority Action Plan.
10. 14 Data Quality & Methodology.

**Finding card → agency PE framework** (this is the core ask). Each card renders five labeled
blocks, not just title+why+how:

- **Problem** — one-line title.
- **Evidence** — the real measured signal (from `evidence` field or rule interpolation); never
  canned if a real value exists.
- **Dollar impact** — "Est. annual revenue at risk: $X (modeled from site_type + page role)".
  If no basis to model it, print "Impact unquantified — see effort" rather than fake a number.
- **How to fix** — concrete steps + `code_snippet`.
- **Effort** — colored badge: `Quick (~1h)` / `Half-day` / `1–2 days` / `Sprint`, plus "Est. +N pts".
- Chips: Pattern · Priority (Urgent/High/Medium/Low, English words) · Impact · Uplift.

**Grade labels** to English: 85+ Excellent, 70+ Good, 50+ Needs Work, 30+ Weak, <30 Critical.

**Fix `finding_cards()`** so each pattern header wraps only its own cards (the current bug emits
all headers then all cards — that is the "340-line list").

**Fix numbering** — derive section numbers from an ordered list `[COVER, exec, verdict, scorecard,
*patterns, full_list, code, benchmark, action_plan, data_quality, methodology]` and emit
`0{n}` from position, killing the duplicate 06/07.

**Brand**: rename to SEO Scan.ai / hello at seoscanaudit.com, keep colors.

### C. Any other consumers
- `server.py` / `pipeline_runner.py` pass audit JSON through unchanged; the report generator must
  tolerate missing new fields (`effort`/`dollar_impact`/`pattern`) by defaulting/churning them
  from priority + site_type, so old JSONs and rule-based output both render.

## Keeping it free / no heavy deps
- All of the above stays Python stdlib (html, json, re) — deterministic, $0.
- Dollar-impact model: pure rule table keyed by site_type × pattern (e.g. e-commerce schema=high,
  corporate links=low), NOT an LLM call, so it works in the fallback path.
- Verdict: sentence templates driven by score band + top-2 patterns + counts — deterministic.

## Verification
- Run `python3 seo_report_template.py` (demo) and with a real JSON; page the HTML to confirm:
  (1) no Chinese strings except inside quoted evidence from crawled pages, (2) verdict on top,
  (3) findings grouped under pattern headers, (4) no duplicate section numbers, (5) rule-based
  report (delete OPENROUTER key) still renders full PE cards with real evidence values.

## Sample outline (illustrative, from a real crawl)
```
Cover: AI SEO Audit Report · https://site.com · 64/100 · Grade: Needs Work · Sep 12, 2026
01 Executive Summary — gauge, 4 KPIs, projected +9 pts
02 Verdict — "Speed is your biggest drag…"
03 Scorecard by Pattern — 7 bars
04 Pattern: Site Speed & Core Web Vitals — 4 findings
    • TTFB 1.24s (>600ms target)  [URGENT] [Quick] [-$18k/yr est.] — Evidence: measured 1240ms,
      no gzip, no cache-control. Fix: enable gzip + 1-yr cache on static assets.
    • No gzip/brotli ... [MEDIUM] ...
05 Pattern: Crawlability & Indexation — ...
06 Pattern: On-page Relevance (Meta & Content) — ...
07 Pattern: Schema & Structured Data — ...
08 Pattern: Internal Linking & Architecture — ...
09 Pattern: Local & Authority — ...
10 Every Finding (full grouped list)
11 Code Snippets (copy-paste fixes)
12 Competitive Benchmark
13 Top-10 Priority Action Plan
14 Data Quality & Methodology
```