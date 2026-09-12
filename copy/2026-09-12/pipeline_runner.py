#!/usr/bin/env python3
"""
pipeline_runner.py — 收款 + 自動交付 狀態機（編排器）

將整條「落單 → 付款確認 → crawl → 評分 → PDF → email 交付」流程
一氣呵成地跑完，並把每一步狀態寫入 order_status.json。

流程（pay-first，付款喺前）：
    order_received -> payment_verified -> crawl -> score -> report -> deliver

用法：
    # 正式單（必須有 Stripe 付款確認 ref —— pay-first 強制）
    python pipeline_runner.py "https://example.com" --payment-ref "pi_xxx" --customer "email@x.com"

    # 開發/測試模式（未開 Stripe / 未連 email 用；會跳過付款強制檢查）
    python pipeline_runner.py "https://example.com" --dev

    # （可選）--order-id 自訂訂單號；無就自動生成
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.parse

# 統一 email 格式驗證 regex（server /api/order 同 step_deliver 共用同一規則）
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def is_valid_email(email):
    return bool(EMAIL_RE.match((email or "").strip()))

# 讓 import 搵到同目錄嘅模組
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import config
import seo_crawler
import seo_report_template

PROJECT_ROOT = os.path.dirname(_HERE)          # /opt/data/seo-audit-business
OUTPUT_DIR   = os.path.join(PROJECT_ROOT, "output")
REPORT_OUT    = os.path.join(_HERE, "out")

# Round2：由「單一 order_status.json」改做「每單獨立 order_<id>.json」，
# 避免兩個顧客同時跑 pipipeline 時互相覆蓋狀態／交付 marker。
# ORDER_STATUS_FILE 保留做無訂單號時嘅 fallback／舊檔兼容，正式流程一律 per-order。
STATUS_PATH      = os.path.join(OUTPUT_DIR, "order_status.json")
ORDER_STATUS_FILE = STATUS_PATH  # 兼容命名


def per_order_status_path(order_id):
    """每個訂單用一個獨立狀態檔：output/order_<order_id>.json。"""
    return os.path.join(OUTPUT_DIR, f"order_{order_id}.json")


def per_order_delivery_marker(order_id):
    """每個訂單用一個獨立交付 marker：output/deliveries/<order_id>_delivery.txt。"""
    return os.path.join(OUTPUT_DIR, "deliveries", f"{order_id}_delivery.txt")

# 流程步驟（順序即係依賴次序）
STEPS = ["order_received", "payment_verified", "crawl", "score", "report", "deliver"]


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def safe_domain(url):
    netloc = urllib.parse.urlparse(url).netloc or "demo"
    return re.sub(r"[^\w.-]", "_", netloc)


def safe_token(s):
    """Sanitize a string for safe use in a filename (order_id/domain)."""
    return re.sub(r"[^\w.-]", "_", str(s or "").strip()) or "unnamed"


def load_status(path=None):
    """讀訂單狀態。path 省略時 fallback 到全局 STATUS_PATH（兼容）。
    正式流程都會傳入 per-order 路徑。"""
    path = path or STATUS_PATH
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}
    return {}


def save_status(status):
    """寫入訂單狀態。用 status 內記錄嘅 per-order 路徑（status_file），
    冇就 fallback 到全局 STATUS_PATH。確保每單落返自己個檔，唔互相覆蓋。"""
    path = status.get("status_file") or STATUS_PATH
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(status, fh, ensure_ascii=False, indent=2)
    return path


def mark_step(status, step, state, **extra):
    status.setdefault("steps", {})[step] = {
        "state": state,
        "timestamp": now_iso(),
        **extra,
    }
    # 簡化紀錄：全程狀態 = 第一個未完成/失敗嘅 step
    if state == "failed":
        status["status"] = "failed"
        status["failed_step"] = step
        status["last_error"] = extra.get("error")
    elif status.get("status") in (None, "running") :
        status["status"] = "running" if state == "running" else ("done" if all(
            s.get("state") == "done" for s in status.get("steps", {}).values()
        ) else "running")
    save_status(status)


# ---------------------------------------------------------------------------
# 各步驟實作
# ---------------------------------------------------------------------------
def step_order_received(status, order):
    status["order_id"] = order["order_id"]
    status["url"] = order["url"]
    status["customer_email"] = order.get("customer_email")
    # Round2：價格單一來源 —— 讀 config.DEFAULT_PRICE_USD（環境變數可覆寫），唔再硬編 99。
    status["price_usd"] = config.DEFAULT_PRICE_USD
    status["created_at"] = now_iso()
    mark_step(status, "order_received", "done",
              url=order["url"], order_id=order["order_id"])


def _verify_stripe_payment(payment_ref):
    """pay-first 付款驗證 hook。

    @Yan：要接真 Stripe 驗證先可以正式放行付款單 ——
      有 STRIPE_SECRET_KEY 之後，用 Stripe API「Retrieve」確認收據：
         - Checkout Session:  GET /v1/checkout/sessions/{payment_ref}
              睇 `payment_status == 'paid'`
         - PaymentIntent:     GET /v1/payment_intents/{payment_ref}
              睇 `status == 'succeeded'` && `amount == charge`
     只有確認 status == paid 先可以 return verified=True；
     未 paid / 失敗 / 退款 都要 return verified=False，令 pipeline 停喺
     payment_verified=failed，唔好俾客拎到報告。

    而家：未接真 Stripe（未有 STRIPE_SECRET_KEY），淨係確認 payment_ref 有值，
    回傳 assumed_verified_placeholder，等流程仲可以跑到（開發/demo）。
    Return: {"verified": bool, "status": str, "note": str}
    """
    if not payment_ref:
        return {"verified": False, "status": "missing_ref",
                "note": "pay-first：無 payment_ref"}
    # TODO(@Yan, Stripe 接入)：喺呢度 call Stripe retrieve 確認 paid。
    #   未接之前一律當 placeholder，正式收錢前一定要改返真驗證。
    return {
        "verified": True,
        "status": "assumed_verified_placeholder",
        "note": ("未接真 Stripe retrieve —— @Yan 要接："
                 "用 PAYMENT_REF 對 Stripe 核實 payment_status=='paid' 先放行。"),
    }


def step_payment_verified(status, order):
    if order.get("dev"):
        mark_step(status, "payment_verified", "done",
                  mode="dev", note="開發模式：跳過真付款驗證")
        return
    ref = order.get("payment_ref", "").strip()
    if not ref:
        mark_step(status, "payment_verified", "failed",
                  error="pay-first：缺少付款確認 (--payment-ref)。未收到 Stripe 款項前唔會開始 crawl。")
        raise RuntimeError("no_payment_confirmation: pay-first 流程必需 payment-ref")
    # Round2：付款驗證單一 hook —— 全部透過 _verify_stripe_payment()。
    # 佢確認 paid 先放行；未接真 Stripe 時係 placeholder（見函式內 @Yan 註明）。
    verified = _verify_stripe_payment(ref)
    if not verified.get("verified"):
        mark_step(status, "payment_verified", "failed",
                  payment_ref=ref, error=verified.get("note"), **verified)
        raise RuntimeError(f"payment_not_verified: {verified.get('note')}")
    mark_step(status, "payment_verified", "done",
              payment_ref=ref,
              amount_usd=config.DEFAULT_PRICE_USD,
              note=("Stripe 收款 US$%d（單一來源 config）。%s"
                    % (config.DEFAULT_PRICE_USD, verified.get("note", ""))))


def step_crawl(status, order):
    url = order["url"]
    try:
        # Round8：crawl 前用 server.validate_scan_url 同一套 SSRF 規則驗證 url——
        # 只准 http/https 且全部分析到嘅 IP 都必須係公開 IP；成功就 resolve 出一個
        # pinned 公開 IP，連 fetch 用嗰個 IP（Host header 保留域名），封 DNS rebind。
        # 若 url 唔公開（例如指向內網/私有 IP/metadata），唔可以 scan——將呢張單
        # 當「無效審計目標」fail 返 payment_verified，stop 喺收款嗰步。
        try:
            from server import validate_scan_url
        except Exception as _imp_err:
            raise RuntimeError(f"ssrf_guard_unavailable: 無法載入 SSRF 驗證規則: {_imp_err}")

        validated_url, pinned_ip, verify_err = validate_scan_url(url)
        if validated_url is None:
            mark_step(status, "crawl", "failed",
                      error=f"SSRF blocked: {verify_err}（唔准 scan 內部/私有目標）")
            # 停喺 payment_verified —— 呢張單唔會開始 crawl。
            mark_step(status, "payment_verified", "failed",
                      error=f"SSRF blocked: {verify_err}（審計目標唔公開，交易退回等待處理）")
            raise RuntimeError(f"ssrf_blocked: {verify_err}")
        url = validated_url

        mark_step(status, "crawl", "running")
        result = seo_crawler.run(url, pinned_ip=pinned_ip)
    except Exception as e:
        mark_step(status, "crawl", "failed", error=f"{type(e).__name__}: {e}")
        raise
    # 存成審計 JSON（同時俾 report 用）
    domain = safe_domain(url)
    audit_path = os.path.join(OUTPUT_DIR, f"{domain}_{int(time.time())}.json")
    with open(audit_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    mark_step(status, "crawl", "done",
              audit_path=audit_path,
              crawl_errors=result.get("crawl_errors", []),
              http_status=result.get("server_signals", {}).get("http_status"))
    status["audit_path"] = audit_path
    save_status(status)
    return result, audit_path


def step_score(status, result, audit_path):
    score = result.get("score")
    n_fixes = len(result.get("fix_list") or [])
    mark_step(status, "score", "done",
              score=score, fix_count=n_fixes,
              ai_error=result.get("ai_error"),
              audit_path=audit_path)
    status["score"] = score
    status["fix_count"] = n_fixes
    save_status(status)


def step_report(status, audit_path):
    try:
        mark_step(status, "report", "running")
        data = seo_report_template.load_audit(audit_path)
        domain = data.get("domain") or safe_domain(data.get("url", status.get("url", "demo")))
        # Round5：報告檔名加 order_id，避免兩個單 scan 同一個 domain 時互相覆蓋。
        order_tag = safe_token(status.get("order_id")) if status.get("order_id") else safe_token(domain)
        os.makedirs(REPORT_OUT, exist_ok=True)
        html_path = os.path.join(REPORT_OUT, f"{domain}_{order_tag}_seo_audit_report.html")
        pdf_path  = os.path.join(REPORT_OUT, f"{domain}_{order_tag}_seo_audit_report.pdf")
        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(seo_report_template.build_html(data))
        pdf_ok = seo_report_template.html_to_pdf(html_path, pdf_path)
        mark_step(status, "report", "done" if pdf_ok else "done_pdf_missing",
                  html_path=html_path,
                  pdf_path=pdf_path if pdf_ok else None,
                  note=None if pdf_ok else "Chromium 未搵到，PDF 未生成（只有 HTML）")
        status["report_html"] = html_path
        status["report_pdf"] = pdf_path if pdf_ok else None
        save_status(status)
        return pdf_path if pdf_ok else None
    except Exception as e:
        mark_step(status, "report", "failed", error=f"{type(e).__name__}: {e}")
        raise


DELIVERY_MAX_ATTEMPTS = 3
DELIVERY_RETRY_DELAY = 2.0   # seconds between attempts


def _smtp_send(pdf_path, to_addr, subject, from_addr, smtp_host, smtp_port, username, password, implicit_ssl=True):
    """真正用 smtplib 送一封含 PDF 附件嘅 email。有設定先會 call 到呢度。"""
    import smtplib
    from email.mime.application import MIMEApplication
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(
        "你的 AI SEO 審計報告已完成，完整 PDF 報告請見附件。\n\n"
        "謝謝選用我們的服務。", "plain", "utf-8"))
    if pdf_path and os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
        with open(pdf_path, "rb") as fh:
            part = MIMEApplication(fh.read(), _subtype="pdf")
            part.add_header("Content-Disposition", "attachment",
                            filename=os.path.basename(pdf_path))
            msg.attach(part)
    else:
        # 冇 PDF 都要告知（例如 Chromium 唔喺度淨出 HTML），但唔可以扮成功
        raise RuntimeError("delivery_has_no_pdf_attachment: 冇 PDF 附件可以送出")

    if implicit_ssl:
        server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
    else:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
        server.starttls()
    try:
        if username and password:
            server.login(username, password)
        server.sendmail(from_addr, [to_addr], msg.as_string())
    finally:
        try:
            server.quit()
        except Exception:
            pass


def step_deliver(status, pdf_path):
    """email 交付。

    真實行為：
      - 若環境有 EMAIL_BACKEND（smtp / smtp_ssl / smtp_tls）+ SMTP_HOST + EMAIL_FROM，
        就真連 SMTP 把 PDF 附件寄出（帶 retry）。
      - 否則明確標記 email_not_configured 為失敗，唔可以當成已交付。
    唔會內部建立任何 email server；純粹讀環境變數決定。
    """
    try:
        mark_step(status, "deliver", "running")
        email = status.get("customer_email")
        if not email:
            raise RuntimeError(
                "no_delivery_recipient: 冇 customer_email (需 --customer-email) 無法交付")
        # Round7：交付前重複驗證 email 格式 —— 無效就失敗，唔可以當成功交付。
        if not is_valid_email(email):
            mark_step(status, "deliver", "failed",
                      error=f"invalid_customer_email: '{email}' 格式無效")
            raise RuntimeError(f"invalid_customer_email: '{email}' 唔係有效 email 格式")

        marker_dir = os.path.join(OUTPUT_DIR, "deliveries")
        os.makedirs(marker_dir, exist_ok=True)
        # Round2：每單獨立交付 marker，避免兩客覆蓋。
        marker = per_order_delivery_marker(status["order_id"])

        backend = (os.environ.get("EMAIL_BACKEND", "") or "").strip().lower()

        if backend in ("smtp", "smtp_ssl", "smtp_tls"):
            smtp_host = (os.environ.get("SMTP_HOST") or os.environ.get("SMTP_SERVER", "")).strip()
            from_addr = (os.environ.get("EMAIL_FROM") or "").strip()
            if not smtp_host or not from_addr:
                mark_step(status, "deliver", "failed",
                          error="EMAIL_BACKEND=smtp 但 SMTP_HOST/EMAIL_FROM 未設定",
                          email_backend=backend)
                raise RuntimeError(
                    "smtp_misconfigured: 設定咗 EMAIL_BACKEND 但 SMTP_HOST 或 EMAIL_FROM 空白")
            smtp_port = int(os.environ.get("SMTP_PORT", "465" if backend == "smtp_ssl" else "587"))
            username = (os.environ.get("SMTP_USER") or from_addr).strip()
            password = (os.environ.get("SMTP_PASSWORD") or os.environ.get("SMTP_PASS") or "").strip()
            implicit_ssl = (backend == "smtp_ssl")
            subject = f"你的 AI SEO 審計報告 — {status.get('order_id')}"

            last_err = None
            for attempt in range(1, DELIVERY_MAX_ATTEMPTS + 1):
                try:
                    _smtp_send(pdf_path, email, subject, from_addr,
                               smtp_host, smtp_port, username, password,
                               implicit_ssl=implicit_ssl)
                    # 成功：連 retry 都唔使
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
                    if attempt < DELIVERY_MAX_ATTEMPTS:
                        time.sleep(DELIVERY_RETRY_DELAY)
            if last_err is not None:
                raise RuntimeError(f"{type(last_err).__name__}: {last_err}")

            lines = [
                f"order_id: {status['order_id']}",
                f"customer_email: {email}",
                f"pdf: {pdf_path}",
                f"html: {status.get('report_html')}",
                f"delivered_at: {now_iso()}",
                f"email_backend: {backend}",
                f"smtp_host: {smtp_host}",
            ]
            with open(marker, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
            mark_step(status, "deliver", "done",
                      delivery_marker=marker,
                      email_backend=backend,
                      smtp_host=smtp_host,
                      note=f"email 已透過 SMTP 送出（含 PDF 附件，retry 上限 {DELIVERY_MAX_ATTEMPTS}）")
            status["delivery_marker"] = marker
            save_status(status)
            return marker

        # 冇 EMAIL_BACKEND / SMTP 設定 → 明確失敗，唔好當成功
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write("\n".join([
                f"order_id: {status['order_id']}",
                f"customer_email: {email}",
                f"pdf: {pdf_path}",
                f"delivered_at: {now_iso()}",
                "email_backend: NOT_CONFIGURED",
                "status: FAILED — email_not_configured，未實際寄出",
            ]) + "\n")
        mark_step(status, "deliver", "failed",
                  delivery_marker=marker,
                  email_backend="NOT_CONFIGURED",
                  error="email_not_configured: 無 EMAIL_BACKEND/SMTP 設定，無法真實交付")
        raise RuntimeError(
            "email_not_configured: 未設定 EMAIL_BACKEND/SMTP_HOST/EMAIL_FROM，email 未寄出。"
            "要真交付，請設定環境變數後重跑。")
    except RuntimeError:
        raise
    except Exception as e:
        mark_step(status, "deliver", "failed", error=f"{type(e).__name__}: {e}")
        raise


# ---------------------------------------------------------------------------
def _step_is(status, step, state="done"):
    """True if the given pipeline step reached the given state."""
    return ((status.get("steps", {}).get(step) or {}) or {}).get("state") == state


def run_pipeline(order):
    """執行成條 pipeline，回傳最終 order_status 內容。

    Round7（冄等化 / 可續行）：
      - 一開頭就 check 訂單檔：若 deliver 已 done 且已有 delivery_marker，代表
        呢張單已經處理完，直接回傳現有 status，唔會重複 crawl / 重複寄信。
      - 若未完成，由而家進度續行 —— 已 done 嘅 step 跳過，由未完成嗰個 step 接返落去，
        唔會重頭再跑（提升冄等性同避免重複交付）。
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    # Round2：一單一檔 —— 用 per-order 狀態檔，唔再用 shared order_status.json，
    # 兩個顧客同時跑唔會互相覆蓋。status_file 記錄喺 dict 內俾 save_status 用。
    status = load_status(per_order_status_path(order["order_id"]))
    status["order_id"] = order["order_id"]
    status["status_file"] = per_order_status_path(order["order_id"])
    # Round7：將本次 order 嘅收貨 email 隨時刷新入 status —— 即使 order_received 已 done
    # 而舊檔冇記低 email，resume 時都照樣用新 email，令 deliver 唔會錯判無收件人。
    if order.get("customer_email"):
        status["customer_email"] = order["customer_email"]
    # 每單獨立 status_file，避免覆蓋上次訂單
    if status.get("order_id") and status["order_id"] != order["order_id"]:
        status = {"order_id": order["order_id"],
                  "status_file": per_order_status_path(order["order_id"])}

    # Round7：冄等 —— 已完整交付嘅單直接回傳，乜都唔好再跑。
    if _step_is(status, "deliver", "done") and status.get("delivery_marker"):
        return status

    # --- 由現有進度續行：已 done 嘅 step 跳過，未完成嘅由嗰度接落去 ---
    if not _step_is(status, "order_received"):
        step_order_received(status, order)
    if not _step_is(status, "payment_verified"):
        step_payment_verified(status, order)

    # crawl：done 且有 audit_path 就直接載入上次結果，唔重差網站。
    audit_path = status.get("audit_path")
    if _step_is(status, "crawl", "done") and audit_path and os.path.exists(audit_path):
        try:
            with open(audit_path, "r", encoding="utf-8") as fh:
                result = json.load(fh)
        except Exception:
            result, audit_path = step_crawl(status, order)
    else:
        result, audit_path = step_crawl(status, order)

    # score：done 且有分數就跳過
    if not _step_is(status, "score", "done") or status.get("score") is None:
        step_score(status, result, audit_path)

    # report：done 且有 PDF 就重用；冇 PDF（之前 fail / Chromium 未裝）就重試
    if _step_is(status, "report", "done") and status.get("report_pdf"):
        pdf_path = status.get("report_pdf")
    else:
        pdf_path = step_report(status, audit_path)

    # deliver：done 且有 marker 先唔重寄（上面已 return），否則由 deliver 續落去。
    if not (_step_is(status, "deliver", "done") and status.get("delivery_marker")):
        step_deliver(status, pdf_path)

    status["status"] = "done"
    status["finished_at"] = now_iso()
    save_status(status)
    return status


def main():
    ap = argparse.ArgumentParser(description="AI SEO 審計 收款+交付 狀態機")
    ap.add_argument("url", help="要審計嘅網站 URL")
    ap.add_argument("--payment-ref", default="", help="Stripe 付款確認 ref（pay-first 必需）")
    ap.add_argument("--customer-email", default="", help="客戶收貨 email")
    ap.add_argument("--order-id", default="", help="自訂訂單號（預設自動生成）")
    ap.add_argument("--dev", action="store_true", help="開發模式：跳過付款強制檢查")
    args = ap.parse_args()

    url = args.url.strip()
    if not url.startswith("http"):
        url = "https://" + url

    order = {
        "order_id": args.order_id or f"ORDER-{int(time.time())}",
        "url": url,
        "payment_ref": args.payment_ref,
        "customer_email": args.customer_email,
        "dev": args.dev,
    }

    # Round2：所有讀寫都走 per-order status 檔（order_<id>.json）。
    status_path = per_order_status_path(order["order_id"])

    try:
        status = run_pipeline(order)
    except RuntimeError as e:
        # pay-first 失敗：狀態已寫入該訂單嘅 order_<id>.json，提示等收款
        print(json.dumps(load_status(status_path), ensure_ascii=False, indent=2))
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(json.dumps(load_status(status_path), ensure_ascii=False, indent=2))
        print(f"\n[error] {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(status, ensure_ascii=False, indent=2))
    print(f"\n[ok] 狀態已寫入 {status_path}")


if __name__ == "__main__":
    main()
