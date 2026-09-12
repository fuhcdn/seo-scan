#!/usr/bin/env python3
"""
A8 :: AI SEO Audit -- v1 crawl + score + AI fix-list engine
===========================================================
A standalone, dependency-free (Python stdlib only) pipeline that:

  1. Reads a URL (argv[1] or interactive prompt)
  2. Crawls the page + /robots.txt and extracts 10+ on-page SEO signals
     (title, meta description, meta robots, canonical, lang, viewport,
      hreflang, JSON-LD/schema, Open Graph, H1/H2, img alt coverage,
      internal links, HTTP status, TTFB speed signal, headers, page size)
  3. Sends the condensed signal bundle to OpenRouter to produce:
        - an SEO baseline score (0-100)
        - a prioritized fix list (urgent/高/中/低), each item with:
            why_it_matters + how_to_fix + (optional) code snippet
  4. Emits a single JSON result.

Design goals:
  - Every crawl step is wrapped in try/except so one failing check or a
    dead site never kills the whole pipeline (resilience requirement).
  - No third-party deps: urllib + html.parser + json + re.
  - OpenRouter key resolution order: $OPENROUTER_API_KEY env var, then
    /opt/data/.env (same mechanism as scripts/openrouter_balance.sh).

Usage:
    python3 seo_crawler.py https://example.com/about
    echo '{"url":"https://example.com"}' | python3 seo_crawler.py
"""

import html
import ipaddress
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

USER_AGENT = ("Mozilla/5.0 (compatible; Hermes-SEO-Audit/1.0; "
              "+https://hermes-agent.nousresearch.com) applewebkit/537.36")
FETCH_TIMEOUT = 15


# --------------------------------------------------------------------------
# Key resolution
# --------------------------------------------------------------------------
def resolve_openrouter_key():
    """Return the OpenRouter API key: env var first, then local .env."""
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        return key
    for path in ("/opt/data/.env", os.path.expanduser("~/.env")):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("OPENROUTER_API_KEY="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            continue
    return ""


# --------------------------------------------------------------------------
# HTTP layer
# --------------------------------------------------------------------------
def http_get(url, timeout=FETCH_TIMEOUT):
    """Fetch a URL, return (status, headers, body_str). Raises on hard error."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "en,zh-HK,zh-CN",
        },
    )
    start = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        status = getattr(resp, "status", 200)
        ctype = resp.headers.get("Content-Type", "")
        headers = {k.lower(): v for k, v in resp.headers.items()}
        ttf = time.time() - start
    enc = None
    m = re.search(r"charset=([\w-]+)", ctype, re.I)
    if m:
        enc = m.group(1)
    for cand in (enc, "utf-8", "utf-8-sig"):
        try:
            return status, headers, raw.decode(cand, errors="strict"), ttf, headers.get("content-encoding", "")
        except (UnicodeDecodeError, LookupError):
            continue
    return status, headers, raw.decode("utf-8", errors="replace"), ttf, headers.get("content-encoding", "")


def head_speed(url, timeout=8, pinned_ip=None, orig_host=None):
    """Quick speed probe: HEAD request, return full_time in ms or None.
    If pinned_ip is given (SSRF TOCTOU), connect to that pinned public IP and
    send the Host header as the original hostname."""
    try:
        target = url
        headers = {"User-Agent": USER_AGENT}
        if pinned_ip:
            target = _substitute_host(url, pinned_ip)
            if orig_host:
                headers["Host"] = orig_host
        req = urllib.request.Request(target, method="HEAD", headers=headers)
        start = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int((time.time() - start) * 1000)
    except Exception:
        return None


# --------------------------------------------------------------------------
# SSRF TOCTOU hardening: resolve once, pin the public IP, fetch that IP, and
# keep the original host via the Host header. Redirects are followed manually
# and every hop is re-checked to never enter private / internal space.
# --------------------------------------------------------------------------
def _public_resolve(host):
    """Resolve host and return the FIRST public (non-private) IP string.
    Returns None if host is unresolvable or only resolves to private/reserved IPs."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return None
    for _fam, _st, _p, _cn, sockaddr in infos:
        ip = sockaddr[0]
        try:
            a = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if (a.is_loopback or a.is_private or a.is_link_local or a.is_reserved
                or a.is_multicast or a.is_unspecified or ip == "169.254.169.254"):
            continue
        return ip
    return None


def _substitute_host(url, ip_str):
    """Rebuild url so connect goes to ip_str but path/query/scheme preserved."""
    o = urllib.parse.urlparse(url)
    netloc = ip_str
    if o.port:
        netloc = "%s:%d" % (ip_str, o.port)
    return urllib.parse.urlunparse((o.scheme, netloc, o.path, o.params,
                                    o.query, o.fragment))


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Stop urllib from auto-following redirects so we can re-check each hop."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


MAX_REDIRECTS = 5


def http_get_pinned(url, pinned_ip, orig_host=None, timeout=FETCH_TIMEOUT):
    """SSRF-safe fetch against a pre-pinned public IP.

    - Connects to pinned_ip (the IP validated at order time — no TOCTOU rebind).
    - Sends Host: <orig_host> so the site serves the right vhost.
    - Follows redirects manually; every hop re-resolves and only advances to a
      public IP. Returns (status, headers, body_str, ttf) or raises on block.
    """
    if orig_host is None:
        orig_host = urllib.parse.urlparse(url).hostname.lower()
    opener = urllib.request.build_opener(_NoRedirectHandler)
    current_url = url
    current_host = orig_host
    current_pin = pinned_ip
    redirs = 0

    while True:
        tgt = _substitute_host(current_url, current_pin)
        req = urllib.request.Request(
            tgt,
            headers={
                "User-Agent": USER_AGENT,
                "Host": current_host,
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                "Accept-Language": "en,zh-HK,zh-CN",
            },
        )
        start = time.time()
        try:
            with opener.open(req, timeout=timeout) as resp:
                status = getattr(resp, "status", 200)
                headers = {k.lower(): v for k, v in resp.headers.items()}
                raw = resp.read()
                loc = headers.get("location")
        except urllib.error.HTTPError as e:
            # HTTPError for 4xx/5xx — capture headers/body too
            status = e.code
            headers = {k.lower(): v for k, v in (e.headers or {}).items()}
            try:
                raw = e.read()
            except Exception:
                raw = b""
            loc = headers.get("location")
        ttf = time.time() - start

        if status in (301, 302, 303, 307, 308) and loc:
            if redirs >= MAX_REDIRECTS:
                raise RuntimeError("too_many_redirects: SSRF 防護封鎖過多重導向")
            redirs += 1
            new_url = urllib.parse.urljoin(current_url, loc)
            nhost = (urllib.parse.urlparse(new_url).hostname or "").strip().rstrip(".").lower()
            if not nhost:
                raise RuntimeError("bad_redirect: 重導向目標缺少 hostname")
            new_pin = _public_resolve(nhost)
            if new_pin is None:
                raise RuntimeError(f"SSRF blocked: 重導向目標 '{nhost}' 解析到私有/內部 IP，拒絕跟隨")
            current_url = new_url
            current_host = nhost
            current_pin = new_pin
            continue
        break

    ctype = headers.get("content-type", "")
    m = re.search(r"charset=([\w-]+)", ctype, re.I)
    enc = m.group(1) if m else None
    for cand in (enc, "utf-8", "utf-8-sig"):
        try:
            return status, headers, raw.decode(cand, errors="strict"), ttf
        except (UnicodeDecodeError, LookupError):
            continue
    return status, headers, raw.decode("utf-8", errors="replace"), ttf


# --------------------------------------------------------------------------
# HTML signal extraction (stdlib HTMLParser)
# --------------------------------------------------------------------------
class SEOSignalsParser(HTMLParser):
    """Extracts the on-page SEO signals we care about."""

    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.base_domain = urllib.parse.urlparse(base_url).netloc.lower()
        self.title = None
        self.meta_desc = None
        self.meta_robots = None
        self.canonical = None
        self.viewport = None
        self.hreflangs = []
        self.jsonld = []
        self.og = {}
        self.h1 = []
        self.h2 = []
        self.imgs = []            # list of dicts {src, alt, has_alt}
        self.internal_links = []
        self.external_links = []
        self.has_lang_attr = False

    def _abs(self, src):
        if not src:
            return None
        return urllib.parse.urljoin(self.base_url, src)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        t = tag.lower()
        if t == "title":
            return  # handled via data in handle_data
        if t == "meta":
            name = (a.get("name") or a.get("property") or "").lower()
            content = a.get("content", "").strip()
            if name == "description":
                self.meta_desc = content
            elif name == "robots":
                self.meta_robots = content
            elif name == "viewport":
                self.viewport = content
            elif name == "og:title":
                self.og["title"] = content
            elif name == "og:description":
                self.og["description"] = content
            elif name == "og:image":
                self.og["image"] = content
            elif name == "og:type":
                self.og["type"] = content
        elif t == "link":
            rel = (a.get("rel") or "").lower().split()
            if "canonical" in rel:
                self.canonical = a.get("href")
            if "alternate" in rel:
                hl = a.get("hreflang")
                if hl:
                    self.hreflangs.append({"hreflang": hl, "href": a.get("href")})
        elif t == "html":
            self.has_lang_attr = bool(a.get("lang"))
        elif t == "script":
            if (a.get("type") or "").lower() in ("application/ld+json",
                                                 "application/json"):
                self._jsonld_pending = True
            else:
                self._jsonld_pending = False
        elif t == "h1":
            self.h1.append(1)
        elif t == "h2":
            self.h2.append(1)
        elif t == "img":
            src = a.get("src") or a.get("data-src")
            self.imgs.append({"src": self._abs(src), "alt": (a.get("alt") or "").strip(),
                              "has_alt": bool((a.get("alt") or "").strip())})
        elif t == "a":
            href = a.get("href") or ""
            h = (href or "").strip().lower()
            if href and not href.startswith(("javascript:", "mailto:", "tel:", "#")):
                full = self._abs(href)
                if full and urllib.parse.urlparse(full).netloc.lower() == self.base_domain:
                    self.internal_links.append(full)
                elif full:
                    self.external_links.append(full)

    def handle_data(self, data):
        # capture text for title / jsonld fragments
        pass

    def handle_endtag(self, tag):
        pass


def extract_signals(html_str, base_url):
    p = SEOSignalsParser(base_url)
    try:
        p.feed(html_str)
    except Exception:
        pass
    p.close()

    # title
    m = re.search(r"<title[^>]*>(.*?)</title>", html_str, re.I | re.S)
    title = html.unescape(m.group(1)).strip() if m else None

    # JSON-LD blocks
    jsonld = []
    for block in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                            html_str, re.I | re.S):
        try:
            jsonld.append(json.loads(block.strip()))
        except Exception:
            jsonld.append(block.strip()[0:200])

    # h1 texts
    h1_texts = [html.unescape(x).strip() for x in
                re.findall(r"<h1[^>]*>(.*?)</h1>", html_str, re.I | re.S)]

    missing_alt = sum(1 for i in p.imgs if not i["has_alt"])
    total_imgs = len(p.imgs)

    return {
        "url": base_url,
        "title": title,
        "title_length": len(title) if title else 0,
        "meta_description": p.meta_desc,
        "meta_description_length": len(p.meta_desc) if p.meta_desc else 0,
        "meta_robots": p.meta_robots,
        "canonical": p.canonical,
        "has_lang_attr": p.has_lang_attr,
        "viewport": p.viewport,
        "hreflang": p.hreflangs,
        "json_ld": jsonld,
        "open_graph": p.og,
        "h1": h1_texts,
        "h1_count": len(h1_texts),
        "h2_count": len(p.h2),
        "img_total": total_imgs,
        "img_missing_alt": missing_alt,
        "internal_link_count": len(p.internal_links),
        "external_link_count": len(p.external_links),
        "sample_internal_links": list(dict.fromkeys(p.internal_links))[:20],
    }


def fetch_robots(root_url, pinned_ip=None, orig_host=None):
    """Fetch /robots.txt signals; never raise — return a status dict.
    When pinned_ip is given, fetch against the pinned public IP (SSRF TOCTOU)."""
    o = urllib.parse.urlparse(root_url)
    robots_url = f"{o.scheme}://{o.netloc}/robots.txt"
    out = {"robots_url": robots_url}
    try:
        if pinned_ip and o.hostname:
            st, hd, body, ttf = http_get_pinned(robots_url, pinned_ip,
                                                orig_host=orig_host or o.hostname,
                                                timeout=10)
        else:
            st, hd, body, ttf, _enc = http_get(robots_url, timeout=10)
        out["status"] = st
        out["has_sitemap_directive"] = bool(re.search(r"^\s*Sitemap:", body, re.I | re.M))
        out["has_disallow"] = bool(re.search(r"^\s*Disallow:\s*[^#]", body, re.I | re.M))
        # a sitemap file referenced? (don't fetch it, just report the reference)
        sm = re.findall(r"^\s*Sitemap:\s*(\S+)", body, re.I | re.M)
        out["sitemaps"] = sm[:5]
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out


# --------------------------------------------------------------------------
# Headers / speed signals
# --------------------------------------------------------------------------
def header_speed_signals(headers):
    gzip = headers.get("content-encoding", "")
    cache = headers.get("cache-control", "") or headers.get("expires", "")
    return {
        "content_encoding": gzip or None,
        "has_gzip_or_br": bool(gzip and gzip.lower() in ("gzip", "br", "deflate")),
        "cache_control": cache or None,
        "has_cache_headers": bool(cache),
        "server_header": headers.get("server"),
        "content_type": headers.get("content-type"),
    }


# --------------------------------------------------------------------------
# OpenRouter scoring + fix list
# --------------------------------------------------------------------------
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

SCORING_PROMPT = """You are a senior technical SEO auditor. Analyze the crawled on-page signals below and return STRICT JSON only (no markdown fences, no prose).

Rules:
- "score" is an integer 0-100 baseline technical SEO score.
- "fix_list" is an array. Each item: {{"priority": "urgent"|"high"|"medium"|"low", "issue": "<short title>", "why_it_matters": "<why this matters for rankings/user experience>", "how_to_fix": "<concrete fix>", "code_snippet": "<optional HTML/code example or null>"}}
- Prioritize real problems actually visible in the signals. Only add a fix if the signals support it.
- Use the language the audit is being presented in (write fix explanations in Traditional Chinese unless instructions say otherwise).

SIGNALS (JSON):
{sigs_json}
"""


def openrouter_chat(key, payload, timeout=120):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OPENROUTER_ENDPOINT, data=data,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://hermes-agent.nousresearch.com",
            "X-Title": "A8-SEO-Audit",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _coerce_msg_content(content):
    """OpenRouter sometimes returns content=None or a list of parts."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict):
                parts.append(p.get("text") or p.get("content") or "")
            else:
                parts.append(str(p))
        return "".join(parts)
    return None


def _extract_json_obj(text):
    """Robustly pull a JSON object out of a model reply (strips fences/padding)."""
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.I)
    t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t)
    except Exception:
        pass
    m = re.search(r"\{.*\}", t, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return None


def ai_score(sigs, model="deepseek/deepseek-v4-flash-0731"):
    """Call OpenRouter. Returns (score:int|None, fix_list:list, error:str|None)."""
    key = resolve_openrouter_key()
    if not key:
        return None, [], "no OPENROUTER_API_KEY found (env or /opt/data/.env)"
    sigs_json = json.dumps(sigs, ensure_ascii=False, default=str)
    messages = [{"role": "user",
                 "content": SCORING_PROMPT.format(sigs_json=sigs_json)}]

    # try with explicit JSON mode first, fall back to plain chat if content=null
    attempts = [
        {"model": model, "messages": messages, "temperature": 0.2,
         "max_tokens": 1600, "response_format": {"type": "json_object"}},
        {"model": model, "messages": messages, "temperature": 0.2,
         "max_tokens": 1600},
    ]
    last_txt = None
    for payload in attempts:
        try:
            body = openrouter_chat(key, payload)
        except Exception:
            last_txt = None
            continue  # try next attempt
        if body.get("error"):
            last_txt = f"OpenRouter error: {body['error']}"
            continue
        content = _coerce_msg_content(body.get("choices", [{}])[0].get("message", {}).get("content"))
        if not content:
            last_txt = None
            continue  # empty/none content -> try without response_format
        last_txt = content
        break

    parsed = _extract_json_obj(last_txt)
    if parsed is None:
        return None, [], last_txt or "OpenRouter returned empty/unparsable content"
    score = parsed.get("score")
    fix_list = parsed.get("fix_list", [])
    if score is not None:
        try:
            score = int(round(max(0, min(100, float(score)))))
        except (TypeError, ValueError):
            score = None
    return score, fix_list, None


# --------------------------------------------------------------------------
# Rule-based fallback（AI 失敗時嘅保險網）
# --------------------------------------------------------------------------
def rule_based_fixes(result):
    """AI 評分失敗（score=None）或回傳空 fix_list 時，直接用 signals 規則判定。

    用已抓取嘅 on-page 訊號（title/meta/canonical/H1/img alt/robots/ttfb 等）
    直接產生 concrete 嘅修復項，保證客戶最起碼攞到 5-8 項建議，唔會拎到空報告。
    Return: list[dict]，每項含 priority/issue/why_it_matters/how_to_fix/code_snippet。
    """
    sigs = result.get("signals") or {}
    srv  = result.get("server_signals") or {}
    robots = result.get("robots") or {}
    fixes = []

    def add(priority, issue, why, how, code=None):
        fixes.append({
            "priority": priority,
            "issue": issue,
            "why_it_matters": why,
            "how_to_fix": how,
            "code_snippet": code,
        })

    title = sigs.get("title")
    meta  = sigs.get("meta_description")
    canon = sigs.get("canonical")
    h1    = sigs.get("h1_count", 0)
    h2    = sigs.get("h2_count", 0)

    # --- base meta / robots ---
    if not title:
        add("urgent", "缺少 Meta Title（<title>）",
            "Title 係搜尋引擎判斷頁面主題嘅首要訊號，缺咗幾乎無可能取得好排名。",
            "為每個頁面寫一個唯一、包含主要關鍵字嘅 50-70 字元 <title>。",
            "<title>你的主要關鍵字 — 品牌名</title>")
    elif not (15 <= sigs.get("title_length", 0) <= 70):
        add("high", "Title 長度不當",
            "過短/過長嘅 Title 會被截斷或稀釋關鍵字，影響點擊率同排名。",
            "調整 <title> 至 50-70 字元，前面放主要關鍵字。")

    if not meta:
        add("urgent", "缺少 Meta Description",
            "Description 影響搜尋結果嘅點擊率（CTR），缺咗 Google 會亂抽頁面文字。",
            "寫 120-160 字元、包含關鍵字同行動呼籲嘅描述。",
            '<meta name="description" content="簡短吸引嘅頁面描述，含關鍵字">')
    elif not (50 <= sigs.get("meta_description_length", 0) <= 160):
        add("medium", "Meta Description 長度不當",
            "過短唔夠資訊、過長會被截斷，兩者都拉低點擊率。",
            "調整 description 至 120-160 字元，確保結尾包含行動呼籲。",
            '<meta name="description" content="...約120-160字元...">')

    if not canon:
        add("high", "缺少 rel=canonical",
            "Canonical 可避免重複內容稀釋權重，缺咗多個網址可能搶同一個排名。",
            "每個頁面加一個指向正本網址嘅 canonical。",
            '<link rel="canonical" href="https://example.com/此頁正本網址" />')

    robots_val = (sigs.get("meta_robots") or "").lower()
    if "noindex" in robots_val:
        add("urgent", "頁面被 noindex（禁止收錄）",
            "noindex 會令頁面完全唔會喺 Google 出現，等於放棄嗰頁嘅所有流量。",
            "若此頁本身需要被收錄，移除 meta robots 嘅 noindex。",
            '<meta name="robots" content="index, follow" />')

    # --- language / mobile ---
    if not sigs.get("has_lang_attr"):
        add("medium", "缺少 html lang 屬性",
            "冇 lang 屬性會影響多語言地區嘅搜尋理解同屏幕閱讀器語音。",
            "喺 <html> 標籤加入 lang 屬性。",
            '<html lang="zh-HK">')
    if not sigs.get("viewport"):
        add("high", "缺少 mobile viewport",
            "冇 viewport 會令手機瀏覽器縮細整個頁面，重創手機 SEO 同 UX。",
            "喺 <head> 加入 viewport meta。",
            '<meta name="viewport" content="width=device-width, initial-scale=1" />')

    # --- heading hierarchy ---
    if h1 == 0:
        add("high", "冇 H1 標題",
            "H1 係頁面主題嘅最重要結構訊號，缺咗令搜尋引擎難判權重同讀者難掃讀。",
            "為頁面加一個唯一嘅 H1，包含主要關鍵字。")
    elif h1 > 1:
        add("high", "多個 H1（頁面有多個主標題）",
            "頁面應該只有一個 H1 去明確主主題，多個會稀釋語意權重。",
            "保留一個 H1，其餘改成 H2/H3。")
    if h2 == 0:
        add("low", "冇任何 H2",
            "冇 H2 會令長內容結構唔清，影響可讀性同關鍵字覆蓋。",
            "按段落主題加入 H2，自然放入次要關鍵字。")

    # --- images ---
    total_imgs = sigs.get("img_total", 0)
    missing_alt = sigs.get("img_missing_alt", 0)
    if total_imgs > 0 and missing_alt > 0:
        add("medium", f"{missing_alt} 張圖片缺少 alt 文字",
            "Alt 幫助搜尋引擎理解圖片同改善圖片搜索，缺咗喺圖片 SEO 同無障礙都弱。",
            "為每張有資訊意義嘅圖加描述性 alt；純裝飾圖可留空但在 attrs 標明。",
            '<img src="product.jpg" alt="產品名 — 簡短描述" />')

    # --- speed / server ---
    ttfb = srv.get("ttfb_ms") or srv.get("head_response_ms")
    if isinstance(ttfb, (int, float)) and ttfb > 600:
        add("high", "伺服器回應時間偏慢（TTFB）",
            "TTFB 慢會拖慢成個頁面載入，直接影響 Core Web Vitals 同排名。",
            "檢查主機、啟用 CDN/快取、優化後端查詢去降低 TTFB。")
    if srv.get("http_status") and srv.get("http_status") != 200:
        add("urgent", f"頁面回傳 HTTP {srv.get('http_status')}",
            "非 200 狀態（例如 404/500）會令頁面無法正常被收錄或體驗破裂。",
            "修正伺服器/頁面狀態，令核心頁面穩定回傳 200。")
    if srv.get("has_gzip_or_br") is False:
        add("low", "未啟用 gzip/brotli 壓縮",
            "冇壓縮會令頁面傳輸更大、載入更慢。",
            "喺伺服器啟用 gzip 或 brotli 壓縮 HTML/CSS/JS。")
    if srv.get("has_cache_headers") is False:
        add("low", "缺少 cache-control/expires 快取頭",
            "冇快取頭令重訪用戶每次都重新下載全部資源，拖慢速度。",
            "為靜態資源設定 cache-control 同 expires。")

    # --- robots / crawl ---
    robots_err = robots.get("error")
    if robots_err:
        add("medium", "robots.txt 抓取失敗",
            "robots.txt 異常可能阻礙搜尋引擎抓取你嘅頁面。",
            f"檢查 robots.txt 可否公開讀取（錯誤：{robots_err}）。")
    elif robots and robots.get("has_sitemap_directive") is False:
        add("low", "robots.txt 沒有指向 Sitemap",
            "Sitemap 幫搜尋引擎更快發現新頁面；喺 robots.txt 註明可加速收錄。",
            "喺 robots.txt 加入 Sitemap 指向。",
            "Sitemap: https://example.com/sitemap.xml")
    if result.get("crawl_errors"):
        add("medium", "發生抓取/解析錯誤",
            "部分頁面訊號未能完整取得，可能漏報問題。", "重新審計或檢查頁面是否正常回應。")

    # 兜底：一個訊號都冇觸到都要至少有嘢講，唔好出空清單。
    if not fixes:
        add("low", "未能偵測到明顯技術錯誤",
            "主流 on-page 技術訊號大致齊全，仍需要內容品質與外鏈審計先可以全面提升。",
            "用 Search Console 持續監控，並定期做站點審計複核。")
    return fixes


def _estimate_score(fixes):
    """喺 AI 失效時，用修復項優先次序粗估 0-100 基準分（由 100 扣）。
    只係 fallback 估算，等報告唔會冇分數。"""
    penalty = 0
    for f in fixes:
        p = f.get("priority")
        if p == "urgent":
            penalty += 15
        elif p == "high":
            penalty += 8
        elif p == "medium":
            penalty += 4
        else:
            penalty += 2
    return max(0, min(100, 100 - penalty))


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------
def run(url, pinned_ip=None):
    result = {
        "url": url,
        "server_signals": {},
        "robots": {},
        "signals": {},
        "score": None,
        "fix_list": [],
        "ai_error": None,
        "crawl_errors": [],
        "fetch_ok": False,
        "fallback_used": False,
        "score_is_estimate": False,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    orig_host = (urllib.parse.urlparse(url).hostname or "").lower()

    # --- page fetch (hard-fail only here) ---
    try:
        if pinned_ip and orig_host:
            status, headers, body, ttf = http_get_pinned(url, pinned_ip,
                                                         orig_host=orig_host)
        else:
            status, headers, body, ttf, _enc = http_get(url)
        result["server_signals"]["http_status"] = status
        result["server_signals"]["ttfb_ms"] = int(ttf * 1000)
        result["server_signals"]["page_size_bytes"] = len(body.encode("utf-8", "replace"))
        result["server_signals"].update(header_speed_signals(headers))
        result["server_signals"]["head_response_ms"] = head_speed(url, pinned_ip=pinned_ip,
                                                                  orig_host=orig_host)
        result["fetch_ok"] = True
    except Exception as e:
        result["crawl_errors"].append(f"page_fetch: {type(e).__name__}: {e}")
        # still try to score on what we have (site may still have robots info)
        result["signals"] = {"url": url}
    else:
        # --- signals extraction (each isolated) ---
        try:
            result["signals"] = extract_signals(body, url)
        except Exception as e:
            result["crawl_errors"].append(f"extract: {e}")
            result["signals"] = {"url": url}

        # --- robots.txt (isolated) ---
        try:
            result["robots"] = fetch_robots(url, pinned_ip=pinned_ip, orig_host=orig_host)
        except Exception as e:
            result["crawl_errors"].append(f"robots: {e}")

    # --- AI score + fix list (isolated; fallback to rule-based notes on fail) ---
    try:
        _score, _fixes, _err = ai_score(result["signals"])
        result["score"] = _score
        result["fix_list"] = _fixes or []
        result["ai_error"] = _err
    except Exception as e:
        result["ai_error"] = f"ai_score: {type(e).__name__}: {e}"
        result["score"] = None
        result["fix_list"] = []

    # Round2：規則式 fallback —— 當 AI 評分失敗（score=None）或回傳空 fix_list 時，
    # 用 signals 直接規則判定，至少出 5-8 項 concrete fix，唔好俾客拎到空報告。
    # 同時用規則估一個 0-100 基準分，等報告唔會冇分數。
    if result["score"] is None or not result["fix_list"]:
        rb_fixes = rule_based_fixes(result)
        result["fix_list"] = rb_fixes
        result["score"] = _estimate_score(rb_fixes)
        result["fallback_used"] = True
        result["score_is_estimate"] = True
        result["ai_error"] = ((result["ai_error"] or "AI unavailable") +
                              " [used rule-based fallback]")

    # Task7：data-quality 徽章 —— 將「資料係咪真實抓取定係規則估算」講清楚，
    # 避免客戶以為規則估算分數係精確審計結果。
    srv = result["server_signals"] or {}
    result["data_quality"] = {
        "fetch_ok": bool(result.get("fetch_ok")),
        "http_status": srv.get("http_status"),
        "ttfb_ms": srv.get("ttfb_ms"),
        "fallback_used": bool(result.get("fallback_used")),
        "ai_error": (result.get("ai_error") or "").split(" [used rule")[0],
        "crawl_errors": list(result.get("crawl_errors") or []),
        "score_is_estimate": bool(result.get("score_is_estimate")),
        "label": ("規則估算非精確（AI 未能評分）" if result.get("score_is_estimate")
                  else "真實抓取審計"),
    }

    return result


def main():
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        try:
            raw = sys.stdin.read()
            if raw.strip():
                url = json.loads(raw).get("url", "").strip()
            else:
                url = input("URL: ").strip()
        except Exception:
            url = input("URL: ").strip()

    if not url.startswith("http"):
        url = "https://" + url
    try:
        urllib.parse.urlparse(url)
    except Exception:
        pass

    out = run(url)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    # also persist to output dir for the business record
    try:
        os.makedirs("/opt/data/seo-audit-business/output", exist_ok=True)
        safe = re.sub(r"[^\w.-]", "_", urllib.parse.urlparse(url).netloc)
        path = f"/opt/data/seo-audit-business/output/{safe}_{int(time.time())}.json"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)
        print(f"\n[info] result saved -> {path}", file=sys.stderr)
    except Exception as e:
        print(f"\n[info] could not persist: {e}", file=sys.stderr)

    sys.exit(0 if out["score"] is not None or not out["crawl_errors"] or not out.get("score") is None else 0)


if __name__ == "__main__":
    main()