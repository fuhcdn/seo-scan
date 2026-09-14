#!/usr/bin/env python3
"""stripe_lib.py — stdlib-only Stripe integration for the SEO Scan server.

Loads secrets from os.environ (deployed) or secrets.env (dev), and exposes:
  - load_env(secrets_path)          : merge secrets.env into os.environ (dev only)
  - stripe_headers()                : auth header from STRIPE_SECRET_KEY
  - create_checkout_session(...)    : returns redirect URL for /api/create-checkout
  - stripe_get_session(session_id)  : verify a Checkout Session is paid
  - verify_webhook_signature(...)   : HMAC the raw body against STRIPE_WEBHOOK_SECRET
No third-party deps. Always returns plain dicts / raises StripeError.
"""
import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
STRIPE_API = "https://api.stripe.com/v1"


class StripeError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def load_env(secrets_path=None):
    """Merge secrets.env key=value lines into os.environ (dev/local comfort only).

    On a deployed host (Render/Railway) the platform injects the same vars as
    env anyway, so this is a no-op if STRIPE_SECRET_KEY is already set.
    """
    if os.environ.get("STRIPE_SECRET_KEY"):
        return
    path = secrets_path or os.path.join(os.path.dirname(_HERE), "secrets.env")
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip()
            if k and k not in os.environ:
                os.environ[k] = v


def _api(path, method="GET", params=None, data=None):
    """Signed request to the Stripe API. Returns parsed JSON or raises StripeError."""
    key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not key:
        raise StripeError("config_error", "STRIPE_SECRET_KEY is not set")
    url = STRIPE_API + path
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(url, data=body, method="POST")
    elif params is not None:
        qs = urllib.parse.urlencode(params)
        req = urllib.request.Request(f"{url}?{qs}", method="GET")
    else:
        req = urllib.request.Request(url, method=method)
    auth = "Basic " + base64.b64encode((key + ":").encode()).decode()
    req.add_header("Authorization", auth)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode("utf-8")).get("error", {})
        except Exception:
            err = {}
        raise StripeError(err.get("code", f"http_{e.code}"),
                          err.get("message", f"HTTP {e.code}")) from None


def get_price_id(selected_product_id=None):
    """Best-effort: find the Stripe price id for the selected product (HERMES A2).
    - If a product is given, read its price env (PRICE_397/497/997) from product_catalog.
    - CHECKOUT_TEST_PRICE (env) overrides to a low test price when set.
    - LAUNCH_PRICE_397=1 (owner-approved Limited Launch Offer): ENTRY reports check out
      at the US$397 launch price while the flag is set; remove/unset to return to 497.
    Returns a price id or raises StripeError."""
    # Test-mode override: 驗證收款鏈用 $0.5，測完 delenv 即轉返正價
    test_price = os.environ.get("CHECKOUT_TEST_PRICE", "").strip()
    if test_price:
        return test_price
    # Owner-approved Limited Launch Offer (US$397) for ENTRY during launch period.
    # Flag-gated so rollback is a single env change. PREMIUM (997) is unaffected.
    if os.environ.get("LAUNCH_PRICE_397", "").strip() == "1" and selected_product_id:
        try:
            import product_catalog as _pc397
            if _pc397.get_tier(selected_product_id) == "ENTRY_REPORT":
                launch_pid = _pc397.price_id_for(selected_product_id, early=True)
                if launch_pid:
                    return launch_pid
        except Exception:
            pass
    # 產品路由優先：由 selected_product_id 讀對應 env
    if selected_product_id:
        try:
            import product_catalog as _pc
            pid = _pc.price_id_for(selected_product_id)
            if pid:
                return pid
        except Exception:
            pass
    try:
        import config as _cfg
        want_usd = int(_cfg.EARLY_PRICE_USD)
    except Exception:
        want_usd = 397
    # 早鳥 price ID (env override) —— 對應 $397 price
    price_id = os.environ.get("PRICE_397", "").strip() or os.environ.get("STRIPE_PRICE_ID", "").strip()
    if price_id:
        return price_id
    products = _api("/products", params={"active": "true", "limit": "10"})
    for p in products.get("data", []):
        if p.get("default_price"):
            return p["default_price"]
    prices = _api("/prices", params={"limit": "20"})
    for price in prices.get("data", []):
        if (int(price.get("unit_amount") or 0) == want_usd * 100
                and price.get("currency") == "usd"):
            return price["id"]
    raise StripeError("no_price", f"no active US${want_usd} price found")


def create_checkout_session(order_id, success_url, cancel_url,
                            customer_email=None, url_to_scan="demo",
                            product_id=None):
    """Create a real Checkout Session for the selected product. Returns {id, url}."""
    d = {
        "mode": "payment",
        "line_items[0][price]": get_price_id(product_id),
        "line_items[0][quantity]": "1",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": order_id,
        "metadata[order_id]": order_id,
        "metadata[url_to_scan]": url_to_scan,
        "metadata[selected_product_id]": product_id or "",
    }
    if customer_email:
        d["customer_email"] = customer_email
    cs = _api("/checkout/sessions", data=d)
    return {"id": cs.get("id"), "url": cs.get("url")}


def get_session_paid(session_id):
    """True if the Checkout Session exists and payment_status == 'paid'."""
    cs = _api(f"/checkout/sessions/{session_id}", params={"expand[]": "payment_intent"})
    return bool(cs.get("payment_status") == "paid"), cs


def verify_webhook_signature(payload, sig_header, tolerance_sec=300):
    """Verify Stripe's webhook HMAC. Returns (valid, event) — never raises on bad sig."""
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
    if not secret:
        # Dev/no-webhook mode: caller decides; mark unverified.
        return False, None
    # Stripe sends: t=<ts>,v1=<hex>
    parts = {}
    for item in (sig_header or "").split(","):
        if "=" in item:
            k, _, v = item.partition("=")
            parts[k] = v
    ts = parts.get("t", "")
    sig = parts.get("v1", "")
    if not ts or not sig:
        return False, None
    try:
        if abs(int(ts) - time.time()) > tolerance_sec:
            return False, None
    except ValueError:
        return False, None
    signed = f"{ts}.{payload}".encode()
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return False, None
    try:
        return True, json.loads(payload)
    except Exception:
        return False, None


def handle_webhook(payload, sig_header):
    """Entry point for /webhook/stripe. Returns (http_code, dict)."""
    valid, event = verify_webhook_signature(payload, sig_header)
    if not valid:
        return 400, {"received": False, "error": "invalid signature"}
    if event.get("type") == "checkout.session.completed":
        cs = event.get("data", {}).get("object", {})
        session_id = cs.get("id")
        # 真 Stripe verify：retrieve session 核 payment_status，唔可以淨靠 event type 就當 paid
        paid = False
        try:
            ses = _api("/checkout/sessions/" + session_id, method="GET")
            if isinstance(ses, dict):
                ps = ses.get("payment_status") or ""
                paid = ps == "paid"
        except Exception as e:
            # retrieve 失敗 = 保守 fail-closed，唔可以假設 paid
            return 200, {"received": True, "ok": False, "paid": False,
                         "webhook_error": f"stripe_retrieve_failed: {type(e).__name__}: {e}",
                         "type": event.get("type")}
        if not paid:
            # 未確實 paid（例如未付款/退款）→ 唔 spawn 交付
            return 200, {"received": True, "ok": True, "paid": False,
                         "type": event.get("type")}
        return 200, {
            "ok": True,
            "paid": True,
            "session_id": session_id,
            "customer_email": cs.get("customer_email"),
            "client_reference_id": cs.get("client_reference_id"),
            "metadata": cs.get("metadata") or {},
            "delivery": "spawn",
        }
    # Other events: ack (Stripe retries non-2xx, so accept everything valid)
    return 200, {"received": True, "type": event.get("type")}


if __name__ == "__main__":
    load_env()
    print("STRIPE_SECRET_KEY set:", bool(os.environ.get("STRIPE_SECRET_KEY")))
    try:
        cs = create_checkout_session("TEST-ORDER-1", "https://example.com/s", "https://example.com")
        print("checkout url:", cs)
    except StripeError as e:
        print("checkout error:", e.code, e.message)