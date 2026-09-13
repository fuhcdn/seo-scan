#!/usr/bin/env python3
"""
A8 :: SEO Audit — real HTTP server (stdlib only).

Round 3 fix: gives the landing page a REAL backend instead of the demo stub.

Routes:
  GET  /                     -> serves landing_page.html (live site entry)
  GET  /landing              -> alias for landing_page.html
  GET  /robots.txt           -> static robots (blocks /api/, /webhook/, /success)
  GET  /sitemap.xml          -> minimal sitemap of public pages
  POST /api/scan             -> {url} -> runs seo_crawler.run(url),
                                   returns REAL score + top-5 issues + fix_count.
  POST /api/create-checkout  -> creates a REAL Stripe Checkout Session via
                                   stripe_lib.create_checkout_session and returns
                                   its redirect_url (product-routed price id).
  POST /webhook/stripe       -> verifies the Stripe signature, confirms paid via
                                   re-retrieve, then spawns pipeline_runner to
                                   deliver the report automatically.

Run:
    python3 server.py            # binds 0.0.0.0:8000 (PORT env to override)
    PORT=8010 python3 server.py
"""
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import time
import uuid
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)  # so `import seo_crawler` works regardless of cwd
import seo_crawler  # noqa: E402

LANDING_PATH = os.path.join(_HERE, "landing_page.html")
OUTPUT_DIR = os.path.join(os.path.dirname(_HERE), "output")  # 同 pipeline_runner 一致

# Round11：多語言 landing —— `/` (EN master)、`/landing` 用 landing_page.html；
# 子路徑 /en /zh-Hant /zh-Hans /ja /es 各自 serve 對應語言檔案。
LANDING_LANGS = {
    "/en":        "landing_en.html",
    "/zh-Hant":   "landing_zh-Hant.html",
    "/zh-Hans":   "landing_zh-Hans.html",
    "/ja":        "landing_ja.html",
    "/es":        "landing_es.html",
}

# Round8：靜態法律文件路由 —— pipeline/legal/*.md，經 /legal/<name> 提供。
LEGAL_DIR = os.path.join(_HERE, "legal")
# 語意名 -> 實際檔名（footer 用語意名；亦支援直接數檔名）
LEGAL_ROUTES = {
    "privacy":       "02-私隱政策-PDPO.md",
    "terms":         "01-服務條款-ToS.md",
    "disclaimer":    "04-免責聲明.md",
    "refund":        "05-退款政策.md",
    "authorization": "03-網站審計授權書.md",
}
# Round8b：英文 legal master —— pipeline/legal/en/*.md。非繁中語言 fallback 到英文。
LEGAL_DIR_EN = os.path.join(LEGAL_DIR, "en")
LEGAL_ROUTES_EN = {
    "privacy":       "02-privacy-policy.md",
    "terms":         "01-terms-of-service.md",
    "disclaimer":    "04-disclaimer.md",
    "refund":        "05-refund-policy.md",
    "authorization": "03-website-audit-authorization.md",
}
# 語言 token -> legal 子目錄。繁中 token 用 root（原本繁中檔），其他語言（簡中/日/西/英）
# 一律用英文 en/ 作 fallback；未知 token 亦 fallback 英文。
LEGAL_LANG_DIR = {
    "en": LEGAL_DIR_EN,      "eng": LEGAL_DIR_EN,
    "en-us": LEGAL_DIR_EN,   "en-gb": LEGAL_DIR_EN,
    "zh": LEGAL_DIR_EN,      "zh-hans": LEGAL_DIR_EN,   "zh-cn": LEGAL_DIR_EN,
    "ja": LEGAL_DIR_EN,      "ja-jp": LEGAL_DIR_EN,
    "es": LEGAL_DIR_EN,      "es-es": LEGAL_DIR_EN,     "es-419": LEGAL_DIR_EN,
    "zh-hant": LEGAL_DIR,    "zh-hk": LEGAL_DIR,        "zh-tw": LEGAL_DIR,
}

# 統一 email 格式驗證 regex（/api/order 前置驗證用；交付時 pipeline 會再驗一次）
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def is_valid_email(email):
    return bool(EMAIL_RE.match((email or "").strip()))


# ---------------------------------------------------------------------------
# Round5：SSRF 防護 + per-IP rate limit（集中在 /api/scan）
# ---------------------------------------------------------------------------
RATE_LIMIT = 10          # user-supplied approximate: ~10 requests
RATE_WINDOW = 60         # per 60 seconds
_rate_hits = defaultdict(deque)   # ip -> [timestamps]
_rate_lock = __import__("threading").Lock()


def _client_ip(handler):
    return (handler.client_address or ("0.0.0.0", 0))[0]


def rate_limited(client_ip):
    """Sliding-window per-IP rate limit. Returns (allowed: bool, retry_after: int)."""
    now = time.time()
    with _rate_lock:
        q = _rate_hits[client_ip]
        while q and now - q[0] > RATE_WINDOW:
            q.popleft()
        if len(q) >= RATE_LIMIT:
            retry = int(RATE_WINDOW - (now - q[0])) + 1
            return False, retry
        q.append(now)
        # 清理太久冇請求嘅 IP，避免 dict 無限長大
        if len(_rate_hits) > 10000:
            for k in [k for k, d in _rate_hits.items() if not d]:
                del _rate_hits[k]
        return True, 0


def _resolve_all(host):
    """Resolve a hostname to all IPs (A/AAAA). Returns list of IP strings + errors."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return [], f"無法解析 host: {host}"
    seen = set()
    for fam, _, _, _, sockaddr in infos:
        ip = sockaddr[0]
        if ip not in seen:
            seen.add(ip)
    return list(seen), None


def _is_private_ip(ip_str):
    """True if the IP is loopback / private / link-local / reserved / metadata. (SSRF guard)"""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # 唔似合法 IP → 當唔安全，拒絕
    if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved \
            or ip.is_multicast or ip.is_unspecified:
        return True
    # 特別攔 cloud metadata（Tailscale / ECS / GCP / Azure 常見 169.254.169.254）
    if ip_str == "169.254.169.254":
        return True
    return False


# 一定唔畀 scan 嘅 hostname（就算 DNS 解析到，都唔可以當成普通網站）
_FORBIDDEN_HOSTS = {"localhost", "localhost.localdomain", "metadata.google.internal",
                    "metadata", "instance-data", "169.254.169.254",
                    "0.0.0.0", "127.0.0.1", "::1", "[::1]"}


def validate_scan_url(raw):
    """Validate a scan URL against SSRF. Returns (normalized_url, pinned_ip, error).

    Rules (Round5, TOCTOU-hardened in Round7):
      - only http/https schemes allowed
      - host must resolve; all IPs must be public (rejects localhost/private/link-local/cloud metadata)
      - dangerous hostnames are blocked even if resolvable
      - returns a PINNED public IP. The caller MUST use that exact IP for the actual
        network fetch (with the original domain as the Host header) so a DNS rebind
        between validate-time and fetch-time cannot redirect us to a private target.
    """
    url = (raw or "").strip()
    if not url:
        return None, None, "missing 'url'"
    if "://" not in url:
        url = "https://" + url

    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        return None, None, f"唔支援嘅 scheme: '{scheme}'（只准 http/https）"

    host = (parsed.hostname or "").strip().rstrip(".").lower()
    if not host:
        return None, None, "invalid url: 缺少 hostname"

    if host in _FORBIDDEN_HOSTS or host.endswith(".local") or host.endswith(".internal"):
        return None, None, f"SSRF blocked: 唔准 scan 內部/保留 host '{host}'"

    ips, err = _resolve_all(host)
    if err:
        return None, None, err
    if not ips:
        return None, None, f"resolve failed for host '{host}'"

    for ip in ips:
        if _is_private_ip(ip):
            return None, None, f"SSRF blocked: '{host}' 解析到內部/私有 IP ({ip}) —— 唔准 scan"

    # Round7 TOCTOU：挑一個公開 IP 做 pin，fetch 直接用呢個 IP 連（見 seo_crawler.run(..., pinned_ip=...)）
    pinned_ip = seo_crawler._public_resolve(host) or ips[0]
    return url, pinned_ip, None


def top_issues(result, n=5):
    """Flatten fix_list into lightweight {priority, issue} rows for the landing page."""
    fixes = result.get("fix_list") or []
    return [{"priority": (f.get("priority") or "medium"),
             "issue": (f.get("issue") or "")} for f in fixes[:n]]


def run_scan(url, pinned_ip=None):
    """Run the real crawler; always return a JSON-serializable dict.
    Passes the pinned public IP so seo_crawler connects to that exact IP
    (Host header = original domain) — closes the SSRF TOCTOU rebind window."""
    start = time.time()
    try:
        # 免費 scan：skip_ai=True（唔行 LLM）+ 唔用 pinned IP（避免 HTTPS+IP 嘅 TLS 驗證問題）——
        # SSRF 防護已經喺 server 層由 validate_scan_url() 做咗（URL 必須公開 IP）。
        result = seo_crawler.run(url, pinned_ip=None, skip_ai=True)
    except Exception as e:  # hard safety net
        result = {"url": url, "score": None, "fix_list": [],
                  "ai_error": f"server: {type(e).__name__}: {e}"}
    result["version"] = "real-backend-v1"
    result["elapsed_ms"] = int((time.time() - start) * 1000)
    result["top_issues"] = top_issues(result)
    # Round4: dynamic fix_count for the landing page limit (lower in result panel, which
    # replaces the hard-coded 「42項」). Full count lives in fix_list.
    result["fix_count"] = len(result.get("fix_list") or [])
    return result


def checkout_price():
    """收費單價唯一來源 —— 現在係首 50 早鳥期，收 EARLY_PRICE_USD(397)。
    唔信 client 傳咩，夾死 config。Early 期結束先轉返正價 497。"""
    try:
        import config as _cfg
        return int(_cfg.EARLY_PRICE_USD)
    except Exception:
        return 397


def shape_scan_response(result):
    """Round9：將 crawler result 收窄至 landing 需要嘅輕量欄位（免費 scan）。

    唔再對外回傳 full `fix_list`（只留 score + fix_count + top_issues），
    避免免費 tier 洩漏完整付費報告內容。回復式：{url, score, fix_count,
    top_issues, ai_error, fallback_used, signals, server_signals, version}。
    """
    return {
        "url": result.get("url"),
        "score": result.get("score"),
        "fix_count": result.get("fix_count", len(result.get("fix_list") or [])),
        "top_issues": result.get("top_issues"),
        "ai_error": result.get("ai_error"),
        "fallback_used": result.get("fallback_used"),
        "signals": {
            "title": (result.get("signals") or {}).get("title"),
            "meta_description": (result.get("signals") or {}).get("meta_description"),
            "h1_count": (result.get("signals") or {}).get("h1_count"),
            "h2_count": (result.get("signals") or {}).get("h2_count"),
        },
        "server_signals": result.get("server_signals"),
        "version": result.get("version"),
    }


def spawn_delivery_pipeline(order):
    """Spawn pipeline_runner for a paid order (auto-delivery entry point).

    Called by /webhook/stripe once a Checkout Session is verified as paid.
    Requires a real payment_ref; otherwise it returns a note (no-op).
    Runs pipeline_runner.py in a detached subprocess so the HTTP request
    returns immediately; the runner does crawl → PDF → email delivery.
    """
    if not order.get("payment_ref"):
        return {"spawned": False,
                "note": "no paid Stripe payment_ref — nothing to deliver"}
    if not order.get("url") or order["url"] in ("", "demo"):
        return {"spawned": False, "error": "missing order url to scan"}
    _runner = os.path.join(_HERE, "pipeline_runner.py")
    cmd = [sys.executable, _runner, order["url"],
           "--payment-ref", order["payment_ref"],
           "--order-id", order.get("order_id", ""),
           "--customer-email", order.get("customer_email", ""),
           "--product-id", order.get("selected_product_id", ""),
           "--report-language", order.get("report_language", "en")]
    env = dict(os.environ)
    try:
        subprocess.Popen(cmd, cwd=_HERE, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        return {"spawned": True, "cmd": cmd}
    except Exception as e:
        return {"spawned": False, "error": f"{type(e).__name__}: {e}"}


class Handler(BaseHTTPRequestHandler):
    server_version = "SEOAudit/1.0"

    def _send_success_page(self, order_id=""):
        """付款成功頁 —— 代替 Stripe redirect 嘅 404。顯示訂單 + 報告進度。"""
        html = ("<!DOCTYPE html>" 
            "<html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Payment Successful — seoscanaudit</title>"
            "<style>body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#fafafa;color:#111;margin:0;display:flex;align-items:center;justify-content:center;min-height:100vh}"
            ".card{background:#fff;border:1px solid #e5e7eb;border-radius:16px;max-width:480px;width:90%;padding:40px 32px;box-shadow:0 10px 30px rgba(0,0,0,.06);text-align:center}"
            ".check{width:64px;height:64px;border-radius:50%;background:#e8f5e9;color:#2e7d32;display:flex;align-items:center;justify-content:center;margin:0 auto 20px;font-size:30px}"
            "h1{font-size:24px;margin:0 0 8px}.sub{color:#5f6368;font-size:15px;line-height:1.5;margin:0 0 12px}"
            ".oid{font-family:monospace;background:#f1f3f4;padding:8px 14px;border-radius:8px;font-size:14px;display:inline-block;margin:8px 0}"
            ".btn{display:inline-block;margin-top:18px;background:#111;color:#fff;padding:12px 22px;border-radius:10px;text-decoration:none;font-size:15px}"
            ".img{width:24px;height:24px;vertical-align:middle;margin-right:6px}"
            "</style></head><body><div class='card'>"
            "<div class='check'>&#10003;</div>"
            "<h1>Payment received!</h1>"
            "<p class='sub'>Your payment went through. Your full audit report is being generated and will be emailed to you shortly (usually within ~10 minutes).</p>"
            "<div>Order ID: <span class='oid'>" + (order_id or "—") + "</span></div>"
            "<a class='btn' href='/'>Back to home</a>"
            "</div></body></html>")
        self._send(200, html.encode("utf-8"), ctype="text/html")

    def _send(self, code, body, ctype="application/json", extra_headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            return {}

    # --- routes ---------------------------------------------------------
    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/") or "/"
        # Round11：多語言 landing 子路徑（/en /zh-Hant /zh-Hans /ja /es）
        if path in LANDING_LANGS:
            candidate = os.path.join(_HERE, LANDING_LANGS[path])
            if os.path.isfile(candidate):
                try:
                    with open(candidate, "rb") as fh:
                        self._send(200, fh.read(), ctype="text/html")
                    return
                except OSError as e:
                    self._send(500, {"error": f"landing not found: {e}"})
                    return
        if path == "/success":
            # 付款後 redirect 成功頁（Stripe Checkout success_url）—— 以往 404 造成「俾咗錢見 error」
            # 注意：唔可以喺函數內局部 import parse_qs（會令成個 do_GET 視佢為 local → UnboundLocalError）
            q = parse_qs(urlparse(self.path).query)
            return self._send_success_page(q.get("order", [""])[0])

        if path in ("/", "/landing"):
            try:
                with open(LANDING_PATH, "rb") as fh:
                    self._send(200, fh.read(), ctype="text/html")
            except OSError as e:
                self._send(500, {"error": f"landing not found: {e}"})
        elif path == "/health":
            self._send(200, {"ok": True, "server": "real-backend-v1",
                             "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        elif path == "/sample-report":
            # Sample report page — a real (sanitised, labelled) excerpt of a
            # production-grade report structure, so buyers can judge quality before
            # paying. Uses the approved Golden Reference B structure; explicitly
            # labelled as a sample; zero fabricated claims.
            html = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>Sample Report — SEO Scan Audit</title>
<style>body{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#172b4d;background:#faf8f2;margin:28px auto;max-width:860px;line-height:1.55;padding:0 16px}
h1{font-size:22px}h2{font-size:16px;border-bottom:1px solid #d9d2c0;padding-bottom:4px;margin-top:28px}
.card{background:#fff;border:1px solid #e0dccd;border-radius:8px;padding:14px 18px;margin:12px 0}
.lbl{color:#6b7280;font-size:12px;text-transform:uppercase;letter-spacing:.4px}
.disc{color:#6b7280;font-size:12px;margin-top:24px}
.cta{display:inline-block;background:#111;color:#fff;padding:11px 20px;border-radius:8px;text-decoration:none;margin-top:14px}</style></head><body>
<h1>What a real SEO Scan Audit report looks like</h1>
<p>This is an <strong>excerpt from a real production report</strong> (business details anonymised). Every recommendation in a paid report is tied to one exact page on your own website, with direct observation, the buyer question it answers, who executes it, and how to verify it worked.</p>
<div class="card"><p class="lbl">Report type</p><p><strong>SEO Opportunity Diagnostic</strong> — evidence-led decision report for a professional-service firm (goal: more enquiries). Delivered as a PDF, in your chosen language, within 24 hours of payment.</p></div>
<h2>Finding 1 (excerpt) — proof is what converts</h2>
<div class="card">
<p class="lbl">Customer page</p><p>[the firm's own criminal-defense service page]</p>
<p class="lbl">Direct observation</p><p>The page lists practice coverage and fee flexibility, but shows <strong>no case results, no outcomes, no client proof</strong>, and never tells an anxious visitor what to do first after an arrest — the single question a person in that moment actually has.</p>
<p class="lbl">Buyer question it fails to answer</p><p>"Will a lawyer take my case, what will it cost, and what do I do first?"</p>
<p class="lbl">Specific gap</p><p>No visible proof, no immediate next-steps guide, no clear route to the free consultation from this page.</p>
<p class="lbl">Business mechanism</p><p>A person needing a criminal-defense lawyer acts under urgency and anxiety; a page that stops at coverage does not convert hesitancy into a call — enquiries leak silently at the exact moment intent is highest.</p>
<p class="lbl">Recommended change</p><p>Add an "Immediate next steps after an arrest" block plus a prominent free-case-evaluation CTA — content the owner approves before publication.</p>
<p class="lbl">Investment status</p><p>VALIDATE FIRST (attorney-approved wording required before publishing legal guidance)</p>
<p class="lbl">Definition of done</p><p>The module renders on mobile and desktop, links work, the approver signs off, and page-to-contact clicks are measured against a recorded 14-day baseline.</p>
</div>
<h2>What else the full report contains</h2>
<div class="card"><p>Five findings of this depth · Investment decision matrix (DO NOW / VALIDATE FIRST / DEFER) · Customer journey map · 90-day execution roadmap with owners · First measurable signal and scale rule per action · Commercial opportunity model · Sources and honest limitations</p></div>
<h2>What we will honestly not do</h2>
<div class="card"><p>We do not invent rankings, traffic or revenue claims. If public evidence is not sufficient for an honest 90+ quality report, we tell you and stop — you are never sent a filler document.</p></div>
<p><a class="cta" href="/#choose">Choose your report — US$497 / delivered in 24h</a></p>
<p class="disc">Sample excerpt shown with business identity anonymised; structure and quality identical to the delivered report. Every paid report passes an independent 90+ semantic quality gate with a three-way verified PDF artifact.</p>
</body></html>""".encode("utf-8")
            self._send(200, html, ctype="text/html")
        elif path == "/robots.txt":
            # Static robots: allow normal crawling of public pages; block API/order
            # endpoints from index. Safe, standard SEO surface.
            body = (
                "User-agent: *\n"
                "Allow: /\n"
                "Disallow: /api/\n"
                "Disallow: /webhook/\n"
                "Disallow: /success\n\n"
                "Sitemap: https://seoscanaudit.com/sitemap.xml\n"
            ).encode("utf-8")
            self._send(200, body, ctype="text/plain")
        elif path == "/sitemap.xml":
            # Minimal sitemap for the public pages (single-language canonical set;
            # language variants are served from / with user-selectable routing).
            pages = ["/", "/en", "/es", "/ja", "/zh-Hans", "/zh-Hant",
                     "/legal/privacy", "/legal/refund", "/legal/terms"]
            today = time.strftime("%Y-%m-%d", time.gmtime())
            urls = "".join(
                f"<url><loc>https://seoscanaudit.com{p}</loc><lastmod>{today}</lastmod></url>"
                for p in pages)
            xml = ('<?xml version="1.0" encoding="UTF-8"?>'
                   '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                   + urls + "</urlset>").encode("utf-8")
            self._send(200, xml, ctype="application/xml")
        elif path.startswith("/legal/"):
            # Round8b：多語言 legal 路由。支援幾種形式（name 係語意名如 privacy/terms，
            # 亦兼容直接數 .md 檔名）：
            #   /legal/<name>            繁中 default（可按 Accept-Language fallback 英文）
            #   /legal/<name>/<lang>     指定語言（非繁中→英文）
            #   /legal/<lang>/<name>     同上
            #   /legal/<name>?lang=<L>   query 覆寫語言
            # basename 化防止 path traversal；唔刪原有繁中檔。
            qlang = (parse_qs(urlparse(self.path).query).get("lang") or [""])[0].strip().lower()
            segs = [s for s in urlparse(self.path).path[len("/legal/"):].strip("/").split("/") if s]
            if not segs:
                self._send(404, {"error": "legal doc not found", "name": path})
                return
            name, lang = None, ""
            if len(segs) == 2 and segs[0].lower() in LEGAL_LANG_DIR:
                lang, name = segs[0].lower(), segs[1]
            elif len(segs) == 2 and segs[1].lower() in LEGAL_LANG_DIR:
                name, lang = segs[0], segs[1].lower()
            else:
                name = segs[0]
            if not lang:
                lang = qlang
            if not lang:
                # Accept-Language 偵測：網頁瀏覽器偏好多於一個非繁中語言 → 英文。
                ac = (self.headers.get("Accept-Language") or "").lower()
                if ac:
                    toks = [t.split(";")[0].strip().lower() for t in ac.split(",") if t.strip()]
                    if toks and not any(t in ("zh", "zh-hant", "zh-hk", "zh-tw") for t in toks):
                        lang = "en"
            # 無語言 → 繁中 root；有語言 → 查表，未知語言 fallback 英文。
            legal_dir = LEGAL_LANG_DIR.get(lang, LEGAL_DIR_EN) if lang else LEGAL_DIR
            fname = (LEGAL_ROUTES_EN.get(name) if legal_dir == LEGAL_DIR_EN
                     else LEGAL_ROUTES.get(name, name))
            fname = os.path.basename(fname or name)
            if not fname.endswith(".md"):
                self._send(404, {"error": "legal doc not found", "name": name})
                return
            legal_file = os.path.join(legal_dir, fname)
            if not os.path.isfile(legal_file) and legal_dir != LEGAL_DIR:
                # 英文超差 → fallback 到繁中 root 對應檔。
                legal_file = os.path.join(LEGAL_DIR, LEGAL_ROUTES.get(name, name))
            if not os.path.isfile(legal_file):
                self._send(404, {"error": "legal doc not found", "name": name})
                return
            try:
                with open(legal_file, "r", encoding="utf-8") as fh:
                    self._send(200, fh.read(), ctype="text/markdown")
            except OSError as e:
                self._send(500, {"error": f"legal read failed: {e}"})
        elif path == "/api/status":
            # Task2：讀訂單狀態 —— order_<id>.json（pipeline 寫嘅檔）。
            qs = parse_qs(urlparse(self.path).query)
            order_id = (qs.get("order_id") or [None])[0]
            if not order_id:
                self._send(400, {"error": "missing order_id"})
                return
            status_file = os.path.join(OUTPUT_DIR, f"order_{order_id}.json")
            if not os.path.exists(status_file):
                self._send(404, {"error": "order not found", "order_id": order_id})
                return
            try:
                with open(status_file, "r", encoding="utf-8") as fh:
                    st = json.load(fh)
            except Exception as e:
                self._send(500, {"error": f"corrupt status: {e}"})
                return
            # Round8：路徑泄露修復 —— report_pdf/report_html 只出 basename，
            # 唔向客戶端暴露絕對路徑。
            def _base_only(p):
                return os.path.basename(p) if p else None

            self._send(200, {
                "order_id": st.get("order_id", order_id),
                "url": st.get("url"),
                "status": st.get("status"),
                "steps": st.get("steps", {}),
                "score": st.get("score"),
                "fix_count": st.get("fix_count"),
                "report_pdf": _base_only(st.get("report_pdf")),
                "report_html": _base_only(st.get("report_html")),
                "delivery_marker": _base_only(st.get("delivery_marker")),
                "fallback_used": st.get("fallback_used"),
                "ai_error": st.get("ai_error"),
                "created_at": st.get("created_at"),
                "finished_at": st.get("finished_at"),
            })
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/") or "/"

        if path == "/api/scan":
            # Round5：per-IP rate limit（約 10/min）
            client_ip = _client_ip(self)
            allowed, retry = rate_limited(client_ip)
            if not allowed:
                resp = {"error": f"rate limited —— 每分鐘最多 {RATE_LIMIT} 次 scan，請稍後再試"}
                self._send(429, resp, extra_headers={"Retry-After": str(retry)})
                return

            body = self._read_json()
            url_raw = (body.get("url") or "").strip()
            # Round5：SSRF 防護 —— 喺真正 crawl 之前驗證 url 只准 http/https 且必須係公開 IP。
            # Round7：validate 同時返回 pinned IP，fetch 用嗰個 IP（Host header 保留域名）封 TOCTOU。
            url, pinned_ip, verify_err = validate_scan_url(url_raw)
            if url is None:
                self._send(400, {"error": verify_err or "invalid url"})
                return
            result = run_scan(url, pinned_ip=pinned_ip)
            # Round9：回傳收窄 payload —— 唔再帶 full fix_list（免費 scan 防洩漏付費報告）。
            out = shape_scan_response(result)
            self._send(200, out)

        elif path == "/api/order":
            # Round8：全面限流 —— /api/order 都套用 per-IP rate limit
            # （除咗 /api/scan 之外，落單/checkout/webhook 都限，防濫用）。
            client_ip = _client_ip(self)
            allowed, retry = rate_limited(client_ip)
            if not allowed:
                self._send(429, {"error": "rate limited —— 請稍後再試"},
                           extra_headers={"Retry-After": str(retry)})
                return
            # Task1（自助落單）：收 url + customer_email + 報告所需欄位（HERMES A2/A3/A4），
            # 驗證格式（Task6 前置 400），生成 order_id，寫低 order_<id>.json 初始狀態。
            body = self._read_json()
            url_raw = (body.get("url") or "").strip()
            email = (body.get("customer_email") or "").strip()
            report_language = (body.get("report_language") or "").strip()
            product_id = (body.get("selected_product_id") or body.get("product_id") or "").strip()
            company_name = (body.get("company_name") or "").strip()
            biz_goal = (body.get("primary_business_goal") or "").strip()
            market_area = (body.get("primary_market_or_service_area") or "").strip()
            main_offers = (body.get("main_products_or_services") or "").strip()
            ideal_customer = (body.get("ideal_customer_or_target_audience") or "").strip()
            customer_action = (body.get("primary_customer_action") or "").strip()
            competitors = (body.get("known_competitors") or "") or []
            notes = (body.get("notes_or_constraints") or "").strip()

            # A2/A3：product 必須存在（map 到 ENTRY/PREMIUM）；report_language 必須係 5 個之一。
            # 唔淨係前端驗，後端硬 gate——缺任何一個就 400 拒收，唔好讓壞單入。
            import product_catalog as _pc
            if not product_id or not _pc.product_exists(product_id):
                code = "PRODUCT_MAPPING_ERROR" if product_id else "MISSING_PRODUCT"
                self._send(400, {"error": code,
                                 "message": "selected_product_id 必須對應內部產品目錄"})
                return
            if not _pc.valid_language(report_language):
                self._send(400, {"error": "INVALID_LANGUAGE",
                                 "message": f"report_language 必須係 {_pc.REPORT_LANGUAGES} 之一"})
                return
            if not company_name:
                self._send(400, {"error": "MISSING_COMPANY",
                                 "message": "company_name 必須提供"})
                return
            allowed_goals = ("leads", "sales-revenue", "qualified-traffic",
                             "local-enquiries", "subscriptions", "other")
            if not biz_goal or biz_goal not in allowed_goals:
                self._send(400, {"error": "INVALID_BUSINESS_GOAL",
                                 "message": f"primary_business_goal 必須係 {allowed_goals} 之一"})
                return

            # Task6：email 前置驗證 —— 無效即 400，唔好讓壞 email 入單。
            if not is_valid_email(email):
                self._send(400, {"error": "customer_email 格式無效，請提供有效 email"})
                return

            url, pinned_ip, verify_err = validate_scan_url(url_raw)
            if url is None:
                self._send(400, {"error": verify_err or "invalid url"})
                return

            order_id = "ORD-" + uuid.uuid4().hex[:12].upper()
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            import product_catalog as _pc
            _tier = _pc.get_tier(product_id)
            _prod = _pc.get_product(product_id)
            status_file = os.path.join(OUTPUT_DIR, f"order_{order_id}.json")
            initial = {
                "order_id": order_id,
                "url": url,
                "customer_email": email,
                # HERMES 報告所需欄位 / 產品路由
                "report_language": report_language,
                "selected_product_id": product_id,
                "report_tier": _tier,
                "report_skill": (_prod or {}).get("skill") if _prod else None,
                "company_name": company_name,
                "primary_business_goal": biz_goal,
                "primary_market_or_service_area": market_area,
                "main_products_or_services": main_offers,
                "ideal_customer_or_target_audience": ideal_customer,
                "primary_customer_action": customer_action,
                "known_competitors": competitors if isinstance(competitors, list) else [competitors],
                "notes_or_constraints": notes,
                "status_file": status_file,
                "status": "running",
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "steps": {"order_received": {"state": "created", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}},
            }
            with open(status_file, "w", encoding="utf-8") as fh:
                json.dump(initial, fh, ensure_ascii=False, indent=2)

            self._send(200, {
                "order_id": order_id,
                "url": url,
                "report_language": report_language,
                "report_tier": _tier,
                "status_url": f"/api/status?order_id={order_id}",
                "pinned_ip": pinned_ip,
            })

        elif path == "/api/create-checkout":
            # Round8：全面限流
            client_ip = _client_ip(self)
            allowed, retry = rate_limited(client_ip)
            if not allowed:
                self._send(429, {"error": "rate limited —— 請稍後再試"},
                           extra_headers={"Retry-After": str(retry)})
                return
            # 接真 Stripe Checkout Session，由選定產品路由到對應 price（HERMES A2，唔猜價）。
            # /api/order 已建好 order_id + selected_product_id，付款後 webhook 用 client_reference_id 接返。
            body = self._read_json()
            url = (body.get("url") or "").strip() or "demo"
            order_id = (body.get("order_id") or "").strip() or ("o-" + uuid.uuid4().hex[:10])
            customer_email = (body.get("customer_email") or "").strip()
            product_id = (body.get("selected_product_id") or body.get("product_id") or "").strip()
            # 由 order file 讀返真正 product（前端可能無帶，order 記錄先係 truth）
            import product_catalog as _pc
            _of = os.path.join(OUTPUT_DIR, f"order_{order_id}.json")
            if os.path.exists(_of):
                try:
                    with open(_of, "r", encoding="utf-8") as _fh:
                        _od = json.load(_fh)
                    product_id = product_id or (_od.get("selected_product_id") or "")
                    customer_email = customer_email or (_od.get("customer_email") or "")
                except Exception:
                    pass
            _tier = _pc.get_tier(product_id)
            if not _tier:
                self._send(400, {"error": "PRODUCT_MAPPING_ERROR",
                                 "message": "選定產品無法 map 去 ENTRY/PREMIUM"})
                return
            _price, _env_key = _pc.price_point_for(product_id)
            from stripe_lib import StripeError, create_checkout_session, load_env, get_price_id
            load_env()
            site = os.environ.get("PUBLIC_URL", "").rstrip("/") or "https://seoscan.ai"
            try:
                # 用產品對應緊嘅 price id（test-mode CHECKOUT_TEST_PRICE 仍可短暫 override）
                cs = create_checkout_session(
                    order_id=order_id,
                    success_url=f"{site}/success?order={order_id}",
                    cancel_url=f"{site}/",
                    customer_email=customer_email or None,
                    url_to_scan=url,
                    product_id=product_id,
                )
                self._send(200, {
                    "checkout_session_id": cs["id"],
                    "redirect_url": cs["url"],
                    "order_id": order_id,
                    "price_usd": _price,
                    "report_tier": _tier,
                })
            except StripeError as e:
                self._send(502, {"error": f"checkout 建立失敗: {e.code}: {e.message}"})

        elif path == "/webhook/stripe":
            # Round8：全面限流
            client_ip = _client_ip(self)
            allowed, retry = rate_limited(client_ip)
            if not allowed:
                self._send(429, {"error": "rate limited —— 請稍後再試"},
                           extra_headers={"Retry-After": str(retry)})
                return
            # 真 Stripe webhook：驗證簽名 → paid 後 spawn pipeline_runner 自動交報告。
            from stripe_lib import load_env, handle_webhook
            load_env()
            try:
                body_len = int(self.headers.get("Content-Length") or 0)
                payload = self.rfile.read(body_len).decode("utf-8", "replace")
            except Exception:
                payload = ""
            sig = self.headers.get("Stripe-Signature") or ""
            code, result = handle_webhook(payload, sig)
            if result.get("paid") and result.get("delivery") == "spawn":
                # 攞返 order_id (client_reference_id) + url_to_scan metadata → spawn 交付
                meta = result.get("metadata") or {}
                order_id = result.get("client_reference_id") or meta.get("order_id") or ""
                customer_email = (result.get("customer_email") or "").strip()
                # 若 Stripe session 冇帶 email，由 /api/order 建立時存嘅 order file 攞返
                # （landing 填咗 email 落 order，session 層未必帶到）
                if not customer_email and order_id:
                    _of = os.path.join(OUTPUT_DIR, f"order_{order_id}.json")
                    try:
                        import json as _json
                        with open(_of, "r", encoding="utf-8") as _fh:
                            _od = _json.load(_fh)
                        customer_email = (_od.get("customer_email") or "").strip()
                    except Exception:
                        pass
                # 由 order file 攞返完整訂單資料（product/report_language/tier/business 欄位），
                # 交付 pipeline 就知去 ENTRY/PREMIUM + report_language。
                _od = {}
                _of = os.path.join(OUTPUT_DIR, f"order_{order_id}.json")
                if os.path.exists(_of):
                    try:
                        with open(_of, "r", encoding="utf-8") as _fh:
                            _od = json.load(_fh)
                    except Exception:
                        _od = {}
                order = {
                    "url": meta.get("url_to_scan") or (_od.get("url") or "demo"),
                    "order_id": order_id,
                    "payment_ref": result.get("session_id"),
                    "customer_email": customer_email,
                    # HERMES：產品路由 + 語言 + 商業欄位由 order file 帶落 pipeline
                    "selected_product_id": meta.get("selected_product_id") or (_od.get("selected_product_id") or ""),
                    "report_language": _od.get("report_language") or "en",
                    "report_tier": _od.get("report_tier"),
                    "company_name": _od.get("company_name") or "",
                    "primary_business_goal": _od.get("primary_business_goal") or "",
                    "primary_market_or_service_area": _od.get("primary_market_or_service_area") or "",
                    "main_products_or_services": _od.get("main_products_or_services") or "",
                    "known_competitors": _od.get("known_competitors") or [],
                    "notes_or_constraints": _od.get("notes_or_constraints") or "",
                }
                delivery = spawn_delivery_pipeline(order)
                result["delivery_result"] = delivery
            self._send(code, result)

        else:
            self._send(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args))


def main():
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "0.0.0.0")
    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"[server] real SEO backend listening on http://{host}:{port} "
          f"(landing at /, api at /api/scan)", file=sys.stderr)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()