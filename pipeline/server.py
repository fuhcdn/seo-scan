#!/usr/bin/env python3
"""
A8 :: SEO Audit — real HTTP server (stdlib only).

Round 3 fix: gives the landing page a REAL backend instead of the demo stub.

Routes:
  GET  /                     -> serves landing_page.html (live site entry)
  GET  /landing              -> alias for landing_page.html
  POST /api/scan             -> {url} -> runs seo_crawler.run(url),
                                   returns REAL score + top-5 issues + fix_count.
  POST /api/create-checkout  -> RESERVED checkout path. Real Stripe Checkout Session is
                                   created here by @Yan. Until then returns
                                   {"checkout_placeholder": true, "redirect_url": null}.
  POST /webhook/stripe       -> placeholder for Yan to wire real Stripe Checkout.
  GET  /health               -> {"ok":true}

Stripe wiring (@Yan):
  - /api/create-checkout  : after STRIPE_SECRET_KEY is set, create a Checkout Session here
                            (price US$79 / config.DEFAULT_PRICE_USD) and return its
                            `url` as redirect_url. The landing page auto-redirects.
  - /webhook/stripe        : verify the Checkout Session paid, then auto-spawn
                            `pipeline_runner.run_pipeline(order)` to deliver the report.
                            Until Stripe is wired, the server simply returns placeholders
                            so the page + pipeline stay runnable in dev/demo.

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
        result = seo_crawler.run(url, pinned_ip=pinned_ip)
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
    """Round9：收費單價唯一來源 —— 夾死 config.DEFAULT_PRICE_USD（唔理 client 傳咩）。"""
    try:
        import config as _cfg
        return int(_cfg.DEFAULT_PRICE_USD)
    except Exception:
        return 79


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
           "--customer-email", order.get("customer_email", "")]
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
        if path in ("/", "/landing"):
            try:
                with open(LANDING_PATH, "rb") as fh:
                    self._send(200, fh.read(), ctype="text/html")
            except OSError as e:
                self._send(500, {"error": f"landing not found: {e}"})
        elif path == "/health":
            self._send(200, {"ok": True, "server": "real-backend-v1",
                             "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        elif path.startswith("/legal/"):
            # Round8：serve pipeline/legal/*.md（例如 /legal/privacy、/legal/terms、
            # /legal/disclaimer，或直接用檔名）。basename 化防止 path traversal。
            name = path[len("/legal/"):].strip("/")
            fname = LEGAL_ROUTES.get(name, name)
            fname = os.path.basename(fname)
            if not name or not fname.endswith(".md"):
                self._send(404, {"error": "legal doc not found", "name": name})
                return
            legal_file = os.path.join(LEGAL_DIR, fname)
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
            # Task1（自助落單）：收 url + customer_email，驗證 email 格式（Task6 前置 400），
            # 生成 order_id，寫低 order_<id>.json 初始狀態，等 checkout 付款後 pipeline 接手。
            body = self._read_json()
            url_raw = (body.get("url") or "").strip()
            email = (body.get("customer_email") or "").strip()

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
            status_file = os.path.join(OUTPUT_DIR, f"order_{order_id}.json")
            initial = {
                "order_id": order_id,
                "url": url,
                "customer_email": email,
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
            # 接真 Stripe Checkout Session (price = config.DEFAULT_PRICE_USD)。
            # /api/order 已建好 order_id，付款後 webhook 用 client_reference_id 接返張單。
            body = self._read_json()
            url = (body.get("url") or "").strip() or "demo"
            order_id = (body.get("order_id") or "").strip() or ("o-" + uuid.uuid4().hex[:10])
            customer_email = (body.get("customer_email") or "").strip()
            _price = checkout_price()
            from stripe_lib import StripeError, create_checkout_session, load_env
            load_env()
            site = os.environ.get("PUBLIC_URL", "").rstrip("/") or "https://seoscan.ai"
            try:
                cs = create_checkout_session(
                    order_id=order_id,
                    success_url=f"{site}/success?order={order_id}",
                    cancel_url=f"{site}/",
                    customer_email=customer_email or None,
                    url_to_scan=url,
                )
                self._send(200, {
                    "checkout_session_id": cs["id"],
                    "redirect_url": cs["url"],
                    "order_id": order_id,
                    "price_usd": _price,
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
                order = {
                    "url": meta.get("url_to_scan") or "demo",
                    "order_id": result.get("client_reference_id") or meta.get("order_id"),
                    "payment_ref": result.get("session_id"),
                    "customer_email": result.get("customer_email") or "",
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