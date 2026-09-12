#!/usr/bin/env python3
"""research.py — 共享公開網絡研究 + 證據帳本（Evidence Ledger）。

按 HERMES MASTER INSTRUCTION Part C：research 未建立證據帳本唔算完成。
每個 material finding 出街前必須有 >=1 evidence id。

輸出：一份 JSON：
{
  "order_id": ...,
  "website_url": ...,
  "access_date": "YYYY-MM-DD",
  "evidence_ledger": [ {evidence_id, claim, label, source_url, access_date, scope, direct_observation, confidence, notes}, ... ],
  "business": {...},   // Stage A snapshot
  "architecture": {...}, // Stage B
  "serp": [...],        // Stage C observations
  "pages_reviewed": [...], // 實際睇咗嘅 customer pages
  "limitations": [...],  // public-data limits (B3)
}
"""
import json
import os
import re
import time
import urllib.parse

import config
import seo_crawler

_ACCESS_DATE = time.strftime("%Y-%m-%d", time.gmtime())


def _clean_url(u):
    u = (u or "").strip()
    if not u:
        return ""
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    return u


class EvidenceLedger:
    def __init__(self, order_id):
        self.order_id = order_id
        self.items = []
        self._n = 0

    def add(self, claim, label, source_url, scope, direct_observation="",
            confidence="Medium", notes=""):
        if label not in ("FACT", "INFERENCE", "HYPOTHESIS TO VALIDATE",
                          "NOT VERIFIABLE WITH PUBLIC DATA"):
            label = "INFERENCE"
        self._n += 1
        eid = f"E-{self._n:03d}"
        self.items.append({
            "evidence_id": eid,
            "claim": claim,
            "label": label,
            "source_url": source_url,
            "access_date": _ACCESS_DATE,
            "scope": scope,
            "direct_observation": direct_observation,
            "confidence": confidence,
            "notes": notes,
        })
        return eid

    def to_list(self):
        return self.items


def _read_page(url, timeout=20):
    """Fetch + extract signals for a customer page. Returns (ok, signals_dict, error)."""
    try:
        status, headers, html, ttf, _enc = seo_crawler.http_get(url, timeout=timeout)
    except Exception as e:
        return False, {}, f"{type(e).__name__}: {e}"
    if status not in (200,):
        return False, {}, f"http_{status}"
    try:
        sig = seo_crawler.extract_signals(html, url)
        sig["ttfb_ms"] = int(ttf * 1000) if ttf else None
        sig["word_count"] = len(re.sub(r"<[^>]+>", " ", html or "").split())
        sig["status"] = status
        sig["url"] = url
        return True, sig, ""
    except Exception as e:
        return False, {}, f"extract: {type(e).__name__}: {e}"


def _robots_and_sitemap(root_url, ledger):
    root = urllib.parse.urlsplit(_clean_url(root_url))
    base = f"{root.scheme}://{root.netloc}"
    robots_txt = None
    sitemap_urls = []
    try:
        ok, sig, err = _read_page(f"{base}/robots.txt")
        if ok and sig.get("status") == 200:
            robots_txt = {"url": f"{base}/robots.txt", "present": True}
            ledger.add("robots.txt is accessible (present)", "FACT",
                       f"{base}/robots.txt", "site-wide", "robots.txt 200")
        else:
            robots_txt = {"present": False}
            ledger.add("robots.txt could not be read / not found", "INFERENCE",
                       f"{base}/robots.txt", "site-wide", err or "non-200")
        # sitemap
        sm = None
        for cand in ("/sitemap.xml", "/sitemap_index.xml"):
            ok2, s2, e2 = _read_page(base + cand)
            if ok2 and s2.get("status") == 200:
                sm = base + cand
                break
        if sm:
            sitemap_urls.append(sm)
            ledger.add("sitemap.xml is accessible", "FACT", sm, "site-wide",
                       f"{sm} 200")
        else:
            ledger.add("No sitemap found at common paths", "INFERENCE", base,
                       "site-wide", "sitemap.xml/sitemap_index.xml non-200")
    except Exception as e:
        ledger.add("robots.txt / sitemap read failed", "INFERENCE", base, "site-wide",
                   f"{type(e).__name__}: {e}")
    return robots_txt, sitemap_urls


# Stage A / B / C 實作（用 seo_crawler + extract_signals 做真觀察）


def run_research(order, max_pages=12):
    """主入口。order: dict 含 website_url, company_name, primary_business_goal,
    primary_market_or_service_area, main_products_or_services, known_competitors(opt).
    回傳 research JSON + evidence ledger。"""
    url = _clean_url(order.get("website_url") or order.get("url") or "")
    company = (order.get("company_name") or "").strip()
    ledger = EvidenceLedger(order.get("order_id") or "ord")

    # ---- Stage B: architecture / sampling ----
    home_ok, home_sig, home_err = _read_page(url)
    nav_links = []
    if home_ok:
        for a in home_sig.get("links", [])[:60]:
            if a.get("anchor") and a.get("href"):
                nav_links.append(a)
        ledger.add(
            f"Homepage accessible and read (title: {home_sig.get('title') or 'n/a'})",
            "FACT", url, "homepage",
            f"http {home_sig.get('status')}, {home_sig.get('word_count')} words")

    # discover key pages from nav
    discovered = [url]
    internal = []
    for a in nav_links:
        href = a.get("href") or ""
        if href.startswith(("http://", "https://")) and urllib.parse.urlsplit(href).netloc == \
                urllib.parse.urlsplit(url).netloc:
            internal.append(href)
        elif href.startswith("/"):
            internal.append(urllib.parse.urljoin(url, href))
    # dedupe + 限定 network locality
    seen = set()
    pages_reviewed = []
    for p_url in [url] + internal:
        net = urllib.parse.urlsplit(p_url).netloc
        if net and net != urllib.parse.urlsplit(url).netloc:
            continue
        if p_url in seen:
            continue
        seen.add(p_url)
        pages_reviewed.append(p_url)
        if len(pages_reviewed) >= max_pages:
            break
    # read each sampled page, capture signals
    pages = []
    for p_url in pages_reviewed:
        ok, sig, err = _read_page(p_url)
        pages.append({
            "url": p_url,
            "ok": ok,
            "title": sig.get("title") if ok else None,
            "h1_count": len(sig.get("h1") or []) if ok else None,
            "word_count": sig.get("word_count") if ok else None,
            "http_status": sig.get("status") if ok else None,
            "error": err or None,
        })
    n_page_ok = sum(1 for p in pages if p["ok"])
    ledger.add(f"Sampled {n_page_ok}/{len(pages)} pages (homepage + internal links)",
               "FACT", url, "sampled",
               "sampled pages indicate; full crawl not performed")

    robots_txt, sitemap_urls = _robots_and_sitemap(url, ledger)

    # ---- Stage A: business snapshot (由 order + 主頁觀察) ----
    business = {
        "company_name": company,
        "website_url": url,
        "primary_business_goal": order.get("primary_business_goal"),
        "primary_market_or_service_area": order.get("primary_market_or_service_area"),
        "main_products_or_services": order.get("main_products_or_services"),
        "known_competitors": order.get("known_competitors") or [],
    }
    if home_ok:
        business["homepage_title"] = home_sig.get("title")
        business["homepage_meta_desc"] = home_sig.get("meta_desc")
        business["has_lang_attr"] = home_sig.get("has_lang_attr")
    else:
        business["homepage_error"] = home_err

    # ---- limitations (B3) ----
    limitations = [
        "Public research cannot verify exact organic clicks/impressions/CTR/position or index coverage (requires Search Console).",
        "Public research cannot verify actual rankings by location/device/language/personalisation state.",
        "Public research cannot verify conversions, revenue, margins, lead quality, pipeline, or customer lifetime value.",
        "Public research cannot verify a complete crawl, JavaScript rendering, server-side behaviour, or log files.",
        "Public research cannot verify paid-tool keyword volume, difficulty, backlink totals, or competitor traffic.",
        "Public research cannot verify historical traffic decline or content decay.",
    ]

    research = {
        "order_id": order.get("order_id"),
        "website_url": url,
        "access_date": _ACCESS_DATE,
        "evidence_ledger": ledger.to_list(),
        "business": business,
        "architecture": {
            "home_ok": home_ok,
            "nav_links_count": len(nav_links),
            "pages_reviewed": pages,
            "robots_txt": robots_txt,
            "sitemap_urls": sitemap_urls,
            "internal_link_count": len(internal),
        },
        "serp": [],  # Stage C: 由 run_serp_observations 填充
        "pages_reviewed": pages_reviewed,
        "limitations": limitations,
    }
    # ---- Stage C: real SERP observations (public DuckDuckGo HTML, no exact-rank claims) ----
    tier = order.get("report_tier") or "ENTRY_REPORT"
    is_premium = tier == "PREMIUM_REPORT"
    max_serp = 8 if is_premium else 3
    try:
        serp_obs = run_serp_observations(order, max_queries=max_serp)
        if serp_obs:
            merge_serp(research, serp_obs, ledger)
            research["evidence_ledger"] = ledger.to_list()
    except Exception as _serp_err:
        research["serp"] = research.get("serp") or []
        research["serp"].append({
            "query": "n/a", "access_date": _ACCESS_DATE,
            "result_pattern": "unavailable",
            "source_url": "", "direct_observation": f"SERP research skipped ({type(_serp_err).__name__})",
            "label": "NOT VERIFIABLE WITH PUBLIC DATA", "confidence": "Low",
        })
    # ---- competitor/result-pattern examples (public, deduped) ----
    comps = list(order.get("known_competitors") or [])
    for s in research.get("serp") or []:
        for dom in s.get("source_domains") or []:
            d = (dom or "").strip().lower()
            d = re.sub(r"^https?://(www\.)?", "", d).rstrip("/")
            if d and d not in comps:
                comps.append(d)
    research["competitors"] = comps[:6]
    return research


def merge_serp(research, serp_observations, ledger):
    """將 SERP 觀察（真實搜尋結果）併入 research + ledger。"""
    research.setdefault("serp", [])
    for obs in serp_observations:
        research["serp"].append(obs)
        eid = ledger.add(
            f"SERP observation: '{obs.get('query')}' results are mostly {obs.get('result_pattern') or 'n/a'}",
            obs.get("label", "INFERENCE"),
            obs.get("source_url") or obs.get("query_url") or obs.get("query"),
            "serp", obs.get("direct_observation") or "",
            obs.get("confidence", "Medium"))
        obs["evidence_id"] = eid
    return research


_SERP_QUERY_TEMPLATES = [
    # 用公司名/品牌 + 主服務 + 市場（每個 query 對應一個可觀察意圖）
    "{brand}",
    "{brand} {products}",
    "{products} {area}",
]


def run_serp_observations(order, max_queries=3, timeout=20):
    """Part C Stage C：用公開 DuckDuckGo HTML 搜尋做真 SERP 觀察。
    每個 query 記錄：query / access_date / result_pattern / source_url / direct_observation。
    唔會 claim 確切排名（無 verified rank source）——淨係記錄結果類型 pattern。
    Return: list[dict] observations."""
    brand = (order.get("company_name") or "").strip().split()[0] if (order.get("company_name") or "").strip() else ""
    products_raw = (order.get("main_products_or_services") or "").strip()
    area = (order.get("primary_market_or_service_area") or "").strip()
    action = (order.get("primary_customer_action") or "").strip()
    # 拆 products 做獨立詞（第一個產品為主，兼顧多服務情況）
    product_terms = [p.strip() for p in products_raw.split(",") if p.strip()][:4]

    query_bank = []
    if brand:
        query_bank.append(f'"{brand}"')
    if brand and product_terms:
        query_bank.append(f"{brand} {product_terms[0]}")
        query_bank.append(f"{brand} {product_terms[0]} {area}")
    for pt in product_terms:
        query_bank.append(f"{pt}")
        if area:
            query_bank.append(f"{pt} {area}")
    if action:
        if product_terms:
            query_bank.append(f"{product_terms[0]} {action}")
        elif brand:
            query_bank.append(f"{brand} {action}")
    # fallback
    if not query_bank:
        query_bank = [products_raw or area or brand or ""]
    # dedupe + trim to requested count
    seen = set(); uniq = []
    for q in query_bank:
        q = q.replace("  ", " ").strip()
        if q and q.lower() not in seen:
            seen.add(q.lower()); uniq.append(q)
    base_queries = uniq[:max_queries]

    observations = []
    for q in base_queries:
        url = "https://lite.duckduckgo.com/lite/?q=" + urllib.parse.quote(q)
        try:
            import urllib.request as _ur
            req = _ur.Request(url, headers={"User-Agent": seo_crawler.USER_AGENT})
            with _ur.urlopen(req, timeout=timeout) as resp:
                html_txt = resp.read().decode("utf-8", "replace")
            # DDG lite markup: <a ... class='result-link'>Title</a> + following result-snippet
            titles = re.findall(r"class=['\"]result-link['\"][^>]*>(.*?)</a>", html_txt, re.S)
            clean_titles = [re.sub(r"<[^>]+>", "", t).strip() for t in titles[:5]]
            links = re.findall(r"<a[^>]+class=['\"]result-link['\"][^>]*href=['\"]([^'\"]+)['\"]", html_txt)
            clean_links = [u for u in links[:5]]
            # result snippet text
            snippets = re.findall(r"class=['\"]result-snippet['\"][^>]*>(.*?)</td>", html_txt, re.S)
            clean_snips = [re.sub(r"<[^>]+>", "", s).strip()[:120] for s in snippets[:3]]
            # 結果類型 pattern（粗略：有冇 commercial/informational 特徵）
            seen = []
            for t in clean_titles:
                tl = t.lower()
                if any(w in tl for w in ("price", "compare", "cost", "buy", "vs", "review", "top ", "best ")) and "commercial" not in seen:
                    seen.append("commercial")
                if any(w in tl for w in ("how to", "guide", "what is", "examples", "directory")) and "informational" not in seen:
                    seen.append("informational")
            sources = clean_links[:3] or ["(no result parsed)"]
            observations.append({
                "query": q,
                "access_date": _ACCESS_DATE,
                "result_pattern": ", ".join(seen or ["mixed"]),
                "source_url": url,
                "source_domains": sources,
                "direct_observation": f"Top results: {'; '.join(clean_titles[:3]) if clean_titles else 'none parsed'} — links: {'; '.join(sources)}; snippets: {'; '.join(clean_snips)}",
                "label": "INFERENCE",
                "confidence": "Medium",
                "note": "General web-search observation is NOT exact rank data (B3/C5).",
            })
        except Exception as e:
            observations.append({
                "query": q,
                "access_date": _ACCESS_DATE,
                "result_pattern": "unavailable",
                "source_url": url,
                "source_domains": [],
                "direct_observation": f"Search could not be executed ({type(e).__name__})",
                "label": "NOT VERIFIABLE WITH PUBLIC DATA",
                "confidence": "Low",
                "note": "Public search unavailable at access time.",
            })
    return observations


def save(research, order_id, out_dir=None):
    out_dir = out_dir or os.path.join(config._HERE, "research")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"research_{order_id}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(research, fh, ensure_ascii=False, indent=2)
    return path


if __name__ == "__main__":
    import sys
    u = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    ord_ = {"order_id": "DEMO-RESEARCH", "website_url": u,
            "company_name": "Demo Co", "primary_business_goal": "leads",
            "primary_market_or_service_area": "HK",
            "main_products_or_services": "demo services"}
    r = run_research(ord_)
    p = save(r, "DEMO-RESEARCH")
    print("saved", p)
    print("evidence items:", len(r["evidence_ledger"]))
    for e in r["evidence_ledger"][:8]:
        print(" ", e["evidence_id"], e["label"], "|", e["claim"][:60])