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
import http.client
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
        if not cand:
            continue
        try:
            return status, headers, raw.decode(cand, errors="strict"), ttf, headers.get("content-encoding", "")
        except (UnicodeDecodeError, LookupError, TypeError):
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


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPSConnection that keeps host (SNI + Host header + cert check = original
    domain) but connects TCP to a pinned IP (SSRF-safe, no Cloudflare mismatch)."""
    def __init__(self, host, port=None, connect_ip=None, **kwargs):
        self.connect_ip = connect_ip
        super().__init__(host, port, **kwargs)

    def connect(self):
        # TCP connect to the pinned IP, but keep self.host as the SNI/Host/cert name
        target = self.connect_ip or self.host
        self.sock = self._create_connection((target, self.port), self.timeout,
                                             self.source_address)
        if self._tunnel_host:
            self._tunnel()
        self.sock = self._context.wrap_socket(self.sock,
                                              server_hostname=self.host)
        self.sock.settimeout(self.timeout)


class _PinnedHTTPSHandler(urllib.request.HTTPSHandler):
    """HTTPSHandler that connects HTTPS to a pinned IP while keeping the original
    host for SNI / Host header / cert verify. Overrides do_open to build a pinned
    connection (urllib's own do_open re-instantiates the connection class)."""
    def __init__(self, pin_map=None):
        self._pin_map = pin_map or {}  # host -> ip
        super().__init__()

    def https_open(self, req):
        return self.do_open(None, req)

    def do_open(self, http_class, req, **http_conn_args):
        import ssl as _ssl
        o = urllib.parse.urlparse(req.full_url)
        host = o.hostname or req.host
        port = o.port or (443 if o.scheme == "https" else 80)
        ip = self._pin_map.get(host)
        conn = _PinnedHTTPSConnection(host, port, connect_ip=ip,
                                      context=_ssl.create_default_context(),
                                      timeout=req.timeout)
        conn.set_debuglevel(self._debuglevel)
        headers = dict(req.unredirected_hdrs)
        headers.update({k: v for k, v in req.headers.items() if k not in headers})
        headers["Connection"] = "close"
        headers = {name.title(): val for name, val in headers.items()}
        try:
            conn.request(req.get_method(), req.selector, req.data, headers,
                         encode_chunked=req.has_header("Transfer-encoding"))
        except OSError as exc:
            raise urllib.error.URLError(exc)
        try:
            resp = conn.getresponse()
        except OSError as exc:
            raise urllib.error.URLError(exc)
        resp.url = req.get_full_url()
        resp.msg = resp.reason
        resp.request = req
        resp.connection = conn
        return resp


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
    # Use a pin-aware handler: keep original host in URL (SNI/Host/cert correct),
    # but TCP-connect to the pinned public IP (SSRF-safe, no Cloudflare mismatch).
    opener = urllib.request.build_opener(_NoRedirectHandler,
                                         _PinnedHTTPSHandler(
                                             pin_map={orig_host: pinned_ip}))
    current_url = url
    current_host = orig_host
    current_pin = pinned_ip
    redirs = 0

    while True:
        req = urllib.request.Request(
            current_url,
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
        if not cand:
            continue
        try:
            return status, headers, raw.decode(cand, errors="strict"), ttf
        except (UnicodeDecodeError, LookupError, TypeError):
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
            content = (a.get("content") or "").strip()
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
- Write ALL explanations in English (master copy).
- "score" is an integer 0-100 baseline technical SEO score.
- "fix_list" is an array. Each item MUST be: {"priority": "urgent"|"high"|"medium"|"low", "issue": "<short title, English>", "why_it_matters": "<why this matters, English>", "how_to_fix": "<concrete fix steps, English>", "code_snippet": "<optional HTML/code example or null>", "pattern": "<one of CRAWLABILITY|ONPAGE|CONTENT|SPEED|LINKS|SCHEMA|LOCAL|TRUST>", "effort": "<one of quick|half-day|day|sprint>", "dollar_impact": <integer: conservative estimated annual revenue at risk in USD derived from site_type + page importance + competitive set; use 0 if you cannot justify a figure, never null>, "evidence": "<quote the EXACT measured signal value this finding responds to, e.g. your <title> tag is 184 characters, or TTFB measured at 1240 ms with no gzip, or 17 of 24 images missing alt text>"}}
- effort guidance: quick = under ~1 hour, half-day = ~4 hours, day = 1-2 days, sprint = multi-week effort.
- Prioritize real problems actually visible in the signals. Only add a fix if the signals support it, and ALWAYS ground the evidence field in a real measured value from the signals above.

SITE PROFILE (this site is SPECIAL -- weight your recommendations toward these priorities):
- site_type: {site_type}
- Persona: {persona}
- Section weights (higher = more important for THIS kind of site): {weights}
- Unique on-page evidence count (higher = report is site-specific, not template): {evidence_count}
IMPORTANT: Because this is a {site_type_label} site, prioritize fixes in the highest-weight sections FIRST (e.g. a {site_type_label} site cares most about {top_weights}). Every finding MUST tie back to at least one real signal value above -- never invent an issue the signals don't support.

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


def _normalize_fix_list(fix_list):
    """Sanitize AI-returned fix_list: strip accidental quote chars from any key,
    whitelist priority/pattern/effort, coerce types. Returns cleaned list."""
    ok = []
    if not isinstance(fix_list, list):
        return ok
    for it in fix_list:
        if not isinstance(it, dict):
            continue
        clean = {}
        for k, v in it.items():
            kk = (k or "").strip().strip('"').strip("'")
            clean[kk] = v
        p = (clean.get("priority") or "medium").lower().strip().strip('"').strip("'")
        if p not in ("urgent", "high", "medium", "low"):
            p = "medium"
        clean["priority"] = p
        pat = (clean.get("pattern") or "").upper().strip().strip('"').strip("'")
        if pat not in ("CRAWLABILITY", "ONPAGE", "CONTENT", "SPEED", "LINKS",
                       "SCHEMA", "LOCAL", "TRUST"):
            pat = "ONPAGE"
        clean["pattern"] = pat
        eff = (clean.get("effort") or "day").lower().strip().strip('"').strip("'")
        if eff not in ("quick", "half-day", "day", "sprint"):
            eff = "day"
        clean["effort"] = eff
        if not clean.get("issue"):
            clean["issue"] = clean.get("title") or "Unnamed finding"
        ok.append(clean)
    return ok


def _extract_json_obj(text):
    """Robustly pull a JSON object out of a model reply (strips fences/padding,
    handles trailing prose, pretty/one-line JSON)."""
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.I)
    t = re.sub(r"\s*```\s*$", "", t)
    # 1) direct parse
    try:
        return json.loads(t)
    except Exception:
        pass
    # 2) find first '{' ... last '}', then progressively trim trailing junk by
    #    re-parsing; if trailing text exists, greedy {.*} includes it and fails,
    #    so work back from each '}' position.
    start = t.find("{")
    if start == -1:
        return None
    for end in range(len(t) - 1, start, -1):
        if t[end] != "}":
            continue
        cand = t[start:end + 1]
        try:
            return json.loads(cand)
        except Exception:
            # keep scanning backwards; maybe inner closes before outer
            continue
    return None


def ai_score(sigs, model="deepseek/deepseek-v4-flash-0731", profile=None):
    """Call OpenRouter. Returns (score:int|None, fix_list:list, error:str|None)."""
    key = resolve_openrouter_key()
    if not key:
        return None, [], "no OPENROUTER_API_KEY found (env or /opt/data/.env)"
    sigs_json = json.dumps(sigs, ensure_ascii=False, default=str)

    # 個性化：用 site profiler 判斷網站類型 + 權重（殺死「一樣分」）
    profiler = None
    try:
        from site_profiler import classify_site, unique_evidence_count
        profiler = classify_site(sigs)
    except Exception:
        pass
    if profiler is None:
        profiler = {
            "site_type": "unknown", "labels": ["網站", "Website"],
            "weights": {}, "persona_note": "你係一個網站。",
        }
    weights = profiler.get("weights") or {}
    top_weights = ", ".join(f"{k}({v:.0%})" for k, v in
                            sorted(weights.items(), key=lambda x: -x[1])[:3]) or "content"
    site_label = profiler.get("labels") or ["網站", "Website"]
    evidence_count = 0
    try:
        from site_profiler import unique_evidence_count as _uec
        evidence_count = _uec(sigs)
    except Exception:
        evidence_count = sum(1 for k in sigs if sigs.get(k) not in (None, "", [], {})) // 2

    prompt = (SCORING_PROMPT
              .replace("{sigs_json}", sigs_json)
              .replace("{site_type}", profiler.get("site_type", "unknown"))
              .replace("{persona}", profiler.get("persona_note", ""))
              .replace("{weights}", json.dumps(weights, ensure_ascii=False))
              .replace("{evidence_count}", str(evidence_count))
              .replace("{site_type_label}", site_label[0])
              .replace("{top_weights}", top_weights))
    messages = [{"role": "user", "content": prompt}]

    # try with explicit JSON mode first, fall back to plain chat if content=null
    # temperature=0 for deterministic scoring: same site + same signals = same score
    attempts = [
        {"model": model, "messages": messages, "temperature": 0,
         "max_tokens": 2400, "response_format": {"type": "json_object"}},
        {"model": model, "messages": messages, "temperature": 0,
         "max_tokens": 2400},
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
    fix_list = _normalize_fix_list(parsed.get("fix_list", []))
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
    """AI scorer failed (score is None) or returned an empty fix list, so we
    derive concrete fixes straight from the measured on-page signals.

    Every rule interpolates the REAL measured value (title length, H1 count,
    image-alt count, TTFB, gzip/cache status, canonical ...) into its evidence
    string -- never canned copy -- and ships pattern/effort/dollar_impact on
    each finding so the report's PE framework renders fully in the fallback
    path. English master only.
    """
    sigs = result.get("signals") or {}
    srv = result.get("server_signals") or {}
    robots = result.get("robots") or {}
    struct = result.get("site_profile") or {}
    site_type = struct.get("site_type", "unknown")
    fixes = []

    def add(priority, pattern, effort, issue, evidence, why, how, code=None):
        fixes.append({
            "priority": priority,
            "pattern": pattern,
            "effort": effort,
            "issue": issue,
            "evidence": evidence,
            "why_it_matters": why,
            "how_to_fix": how,
            "code_snippet": code,
            "dollar_impact": _dollar_for(pattern, priority, site_type),
        })

    title = sigs.get("title")
    meta = sigs.get("meta_description")
    canon = sigs.get("canonical")
    h1 = sigs.get("h1_count", 0)
    h2 = sigs.get("h2_count", 0)
    title_len = sigs.get("title_length")
    meta_len = sigs.get("meta_description_length")

    # --- base meta / robots ---
    if not title:
        add("urgent", "ONPAGE", "quick",
            "Missing meta title (<title>)",
            "Measured: the <title> tag is empty or absent on this page.",
            "The title is the primary signal search engines use to judge a "
            "page's subject. With none present, ranking for meaningful terms "
            "is effectively impossible.",
            "Write a unique 50-70 character <title> for every page, placing "
            "the primary keyword first.",
            "<title>Primary Keyword - Brand Name</title>")
    elif isinstance(title_len, int) and not (15 <= title_len <= 70):
        add("high", "ONPAGE", "quick",
            f"Title length is {title_len} characters (target 50-70)",
            f"Measured: your <title> tag is {title_len} characters.",
            "Titles that are too short or too long get truncated or dilute the "
            "keyword, hurting both click-through rate and rankings.",
            "Rewrite the <title> to 50-70 characters with the primary keyword "
            "at the front.")

    if not meta:
        add("urgent", "ONPAGE", "quick",
            "Missing meta description",
            "Measured: no meta description is present on this page.",
            "The description drives click-through rate in search results; "
            "without one Google excerpts arbitrary page text.",
            "Write a 120-160 character description with the keyword and a "
            "clear call to action.",
            '<meta name="description" content="Short, compelling page description with keyword">')
    elif isinstance(meta_len, int) and not (50 <= meta_len <= 160):
        add("medium", "ONPAGE", "quick",
            f"Meta description is {meta_len} characters (target 120-160)",
            f"Measured: your meta description is {meta_len} characters.",
            "Descriptions that are too short under-sell, and ones that are "
            "too long get truncated -- both depress click-through rate.",
            "Tighten the description to 120-160 characters ending with a "
            "call to action.")

    if not canon:
        add("high", "CRAWLABILITY", "half-day",
            "Missing rel=canonical tag",
            "Measured: no canonical tag was detected; multiple URLs can "
            "compete for the same ranking.",
            "A canonical prevents duplicate-content dilution of ranking "
            "signals across near-identical URLs.",
            "Add a self-referencing canonical pointing to the canonical "
            "version of each page.",
            '<link rel="canonical" href="https://example.com/this-page" />')

    robots_val = (sigs.get("meta_robots") or "").lower()
    if "noindex" in robots_val:
        add("urgent", "CRAWLABILITY", "quick",
            "Page is set to noindex (blocked from search)",
            f"Measured: meta robots = \"{sigs.get('meta_robots')}\" -- "
            "noindex present.",
            "noindex removes this page from Google entirely, throwing away "
            "all of its potential traffic.",
            "If this page should rank, remove noindex from the meta robots tag.",
            '<meta name="robots" content="index, follow" />')

    # --- language / mobile ---
    if not sigs.get("has_lang_attr"):
        add("medium", "ONPAGE", "quick",
            "Missing html lang attribute",
            "Measured: the <html> tag has no lang attribute.",
            "Without a lang attribute, multilingual search understanding and "
            "screen-reader pronunciation both suffer.",
            "Add a lang attribute to the <html> tag.",
            '<html lang="en">')

    if not sigs.get("viewport"):
        add("high", "ONPAGE", "quick",
            "Missing mobile viewport meta",
            "Measured: no viewport meta tag is present.",
            "Without a viewport, mobile browsers zoom the whole page out, "
            "hurting mobile SEO and usability at once.",
            "Add the viewport meta tag to <head>.",
            '<meta name="viewport" content="width=device-width, initial-scale=1" />')

    # --- heading hierarchy ---
    if h1 == 0:
        add("high", "ONPAGE", "half-day",
            "No H1 heading found on the page",
            f"Measured: 0 H1 tags on this page (h2_count={h2}). Google reads "
            "H1 as the page's main subject.",
            "The H1 is the strongest on-page signal of a page's topic; "
            "missing it leaves search engines guessing and hurts readers too.",
            "Add one unique H1 containing the primary keyword.")
    elif isinstance(h1, int) and h1 > 1:
        add("high", "ONPAGE", "half-day",
            f"Multiple H1 headings ({h1} found)",
            f"Measured: {h1} H1 tags on this page; best practice is exactly one.",
            "A page should have a single H1 to state its main topic clearly; "
            "multiple H1s dilute semantic weight.",
            "Keep one H1 and promote the rest to H2/H3.")
    if h2 == 0:
        add("low", "CONTENT", "day",
            "No H2 subheadings on a long page",
            "Measured: h2_count = 0 on this page.",
            "Without H2s, longer content lacks structure, hurting readability "
            "and keyword coverage.",
            "Break the page into H2 sections with natural secondary keywords.")

    # --- images ---
    total_imgs = sigs.get("img_total", 0)
    missing_alt = sigs.get("img_missing_alt", 0)
    if isinstance(total_imgs, int) and total_imgs > 0 and missing_alt:
        add("medium", "ONPAGE", "quick",
            f"{missing_alt} of {total_imgs} images are missing alt text",
            f"Measured: {missing_alt} of {total_imgs} images have no alt "
            "attribute.",
            "Missing alt text hides image meaning from Google and visually "
            "impaired users, weakening image SEO and accessibility together.",
            "Add descriptive alt to every informative image; use alt=\"\" "
            "for purely decorative ones.",
            '<img src="product.jpg" alt="Product name - short description" />')

    # --- speed / server ---
    ttfb = srv.get("ttfb_ms") or srv.get("head_response_ms")
    if isinstance(ttfb, (int, float)) and ttfb > 600:
        add("high", "SPEED", "half-day",
            f"Server response time (TTFB) is slow at {ttfb} ms",
            f"Measured: TTFB {ttfb} ms (target is under 600 ms).",
            "A slow time-to-first-byte drags down the whole page load, "
            "directly hurting Core Web Vitals and rankings.",
            "Investigate hosting, enable CDN/caching, and optimize backend "
            "queries to cut TTFB.")
    if srv.get("http_status") and srv.get("http_status") != 200:
        add("urgent", "CRAWLABILITY", "quick",
            f"Page returns HTTP {srv.get('http_status')}",
            f"Measured: HTTP status {srv.get('http_status')} (target 200).",
            "A non-200 status (e.g. 404/500) prevents proper indexation or "
            "breaks the user experience.",
            "Fix the server/page status so core pages reliably return 200.")
    if srv.get("has_gzip_or_br") is False:
        enc = srv.get("content_encoding") or "none"
        add("low", "SPEED", "quick",
            "gzip/brotli compression is not enabled",
            f"Measured: content-encoding = {enc}; no gzip/brotli detected.",
            "Without compression, the page ships larger and loads slower, "
            "especially on mobile connections.",
            "Enable gzip or brotli for HTML/CSS/JS on the server.",
            "AddOutputFilterByType DEFLATE text/html text/css application/javascript")
    if srv.get("has_cache_headers") is False:
        add("low", "SPEED", "quick",
            "Missing cache-control/expires headers",
            "Measured: no cache-control or expires header was returned.",
            "Without caching headers, repeat visitors re-download every "
            "resource, slowing each visit.",
            "Set cache-control and expires on static assets.",
            "Cache-Control: public, max-age=604800")

    # --- robots / crawl ---
    robots_err = robots.get("error")
    if robots_err:
        add("medium", "CRAWLABILITY", "half-day",
            "Unable to read robots.txt",
            f"Measured: robots.txt returned an error ({robots_err}).",
            "A failing robots.txt can block crawlers from reaching your pages.",
            f"Make robots.txt publicly readable (error: {robots_err}).")
    elif robots and robots.get("has_sitemap_directive") is False:
        add("low", "CRAWLABILITY", "quick",
            "robots.txt does not point to a sitemap",
            "Measured: robots.txt has no Sitemap directive.",
            "A sitemap reference helps search engines discover new pages faster.",
            "Add a Sitemap line to robots.txt.",
            "Sitemap: https://example.com/sitemap.xml")
    if result.get("crawl_errors"):
        errs = "; ".join(str(e).split(" [used rule")[0] for e in result["crawl_errors"])
        add("medium", "CRAWLABILITY", "half-day",
            "Crawl or parse errors during the audit",
            f"Measured: {errs}.",
            "Some signals could not be fully collected, so issues may be "
            "under-reported.",
            "Re-run the audit or confirm the page responds normally.")

    # Fallback: guarantee the report is never empty.
    if not fixes:
        add("low", "ONPAGE", "day",
            "No obvious technical errors detected",
            "Measured: core on-page signals (title, meta, H1, alt, canonical, "
            "TTFB) are all within healthy ranges.",
            "Healthy technical signals still leave room for content quality "
            "and authority work to lift rankings.",
            "Monitor via Search Console and schedule a periodic site audit.")
    return fixes


_DOLLAR_BY_PATTERN = {
    "CRAWLABILITY": 42000, "ONPAGE": 18000, "CONTENT": 36000, "SPEED": 24000,
    "LINKS": 48000, "SCHEMA": 9000, "LOCAL": 54000, "TRUST": 12000,
}
_SITE_TYPE_MULT = {
    "ecommerce": 1.4, "local_service": 1.2, "saas": 1.2,
    "content": 1.0, "corporate": 0.9, "unknown": 1.0,
}
_PRIO_DOLLAR_FACTOR = {"urgent": 1.5, "high": 1.0, "medium": 0.6, "low": 0.3}


def _dollar_for(pattern, priority, site_type):
    """Deterministic est. annual revenue at risk (USD) for the fallback path."""
    base = _DOLLAR_BY_PATTERN.get(pattern)
    if not base:
        return 0
    mult = _SITE_TYPE_MULT.get(site_type or "unknown", 1.0)
    fac = _PRIO_DOLLAR_FACTOR.get((priority or "low").lower(), 0.3)
    return int(round(base * mult * fac / 100.0) * 100)


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
def run(url, pinned_ip=None, skip_ai=False):
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
        "skip_ai": bool(skip_ai),
        "_skip_ai": bool(skip_ai),
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
        # TTFB: take the MEDIAN of 3 samples to remove network jitter so the same
        # site scores consistently across scans (owner requirement: 次次同分).
        _ttfb_samples = [ttf]
        for _ in range(2):
            try:
                if pinned_ip and orig_host:
                    _s2, _h2, _b2, _t2 = http_get_pinned(url, pinned_ip, orig_host=orig_host)
                else:
                    _s2, _h2, _b2, _t2, _e2 = http_get(url)
                _ttfb_samples.append(_t2)
            except Exception:
                continue
        _ttfb_samples.sort()
        _ttfb_median = _ttfb_samples[len(_ttfb_samples) // 2]
        result["server_signals"]["ttfb_ms"] = int(_ttfb_median * 1000)
        result["server_signals"]["ttfb_samples_ms"] = [int(t * 1000) for t in _ttfb_samples]
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

    # --- site profile (個性化：判斷網站類型,報告 header 用) ---
    try:
        from site_profiler import classify_site, unique_evidence_count
        _prof = classify_site(result["signals"])
        _prof["unique_evidence_count"] = unique_evidence_count(result["signals"])
        result["site_profile"] = _prof
    except Exception as e:
        result["site_profile"] = {
            "site_type": "unknown", "labels": ["網站", "Website"],
            "weights": {}, "persona_note": "你係一個網站。",
            "unique_evidence_count": 0,
        }

    # --- AI score + fix list (isolated; fallback to rule-based notes on fail) ---
    # FREE tier (skip_ai=True)：唔行 LLM，直接規則快算 —— 令免費 scan 快 + 慳成本。
    if not result.get("_skip_ai"):
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
    # Free tier（skip_ai）都會行呢度出規則 fix + 估分。
    if result["score"] is None or not result["fix_list"]:
        rb_fixes = rule_based_fixes(result)
        result["fix_list"] = _normalize_fix_list(rb_fixes)
        result["score"] = _estimate_score(result["fix_list"])
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
        "label": ("Rule estimate (approximate) - AI scoring unavailable"
                  if result.get("score_is_estimate")
                  else "Live crawl audit"),
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