#!/usr/bin/env python3
"""
Insufficient-evidence / clarification state machine — owner decision A→C.

Owner-approved default order:
  A: request customer clarification/additional information first
  C: if clarification received but evidence still insufficient for an honest
     90+ report -> stop normal delivery -> manual_support_required

Rules (owner-approved):
- NO generic/filler report, NO knowingly weak paid report, NO fabricated
  evidence, NO threshold lowering.
- NO auto-refund, NO auto-credit, NO auto-partial-report.
- NO refund/legal policy change.
- NO live customer clarification email until live email identity/sender-domain
  is separately approved — mock/safe recipient only for now.
- Response window: 3 business days.
- In manual_support_required: preserve audit record, never delete order data,
  create concise owner-support decision record, wait for owner-approved remedy.

States added to the job state machine:
  clarification_required
  awaiting_customer_clarification
  (manual_support_required already exists in job_watchdog TERMINAL_STATES)
"""
import json
import os
import time
from datetime import datetime, timedelta, timezone

CLARIFICATION_WINDOW_BUSINESS_DAYS = 3
SUPPORT_EMAIL_PLACEHOLDER = "hello@seoscanaudit.com"  # wording only; live send NOT enabled

# ---------------- state helpers ----------------

def is_terminal(state: str) -> bool:
    return state in {"email_sent", "delivery_failed", "insufficient_public_evidence",
                     "manual_support_required", "cancelled"}


def enter_clarification_required(status: dict, missing: list) -> dict:
    """Owner rule 1: intake/evidence insufficient -> clarification_required.
    Persists the minimum-missing-info list (used to build the request)."""
    status["status"] = "clarification_required"
    status["clarification"] = {
        "missing": missing,
        "state_entered_at": now_iso(),
        "window_business_days": CLARIFICATION_WINDOW_BUSINESS_DAYS,
    }
    return save(status)


def build_clarification_request(status: dict, report_language: str = "en") -> dict:
    """Owner rule 2-3: build the clarification request asking ONLY for the minimum
    missing information. MOCK/STAGING ONLY — never sends; returns the draft."""
    missing = (status.get("clarification", {}) or {}).get("missing", [])
    items = {
        "website": "correct customer-owned website/domain (e.g. https://yourdomain.com)",
        "service_pages": "the specific service/product pages on your own site that matter most",
        "market": "your intended market / service area",
        "goal": "your primary business goal for the website",
        "action": "the primary action you want visitors to take (buy/quote/book/call/enquire)",
        "offer": "confirmation of which current offer/products the site is selling",
        "blocked": "which public pages are blocked, thin or outdated (if known)",
    }
    lines = [items[m] for m in missing if m in items] or ["the information listed in your order"]
    lang = report_language if report_language in ("en", "zh-Hant", "zh-Hans", "ja", "es") else "en"
    if lang == "en":
        subject = "Quick clarification needed for your SEO report"
        body = ("Hello,\n\nTo prepare your report, we need a little more information:\n\n"
                + "\n".join(f"- {l}" for l in lines)
                + "\n\nPlease reply to this email with the above. Thank you!\n")
    elif lang == "zh-Hant":
        subject = "你嘅 SEO 報告需要少少補充資料"
        body = ("你好,\n\n要完成你嘅報告,我哋需要以下資料:\n\n"
                + "\n".join(f"- {l}" for l in lines)
                + "\n\n請直接回覆呢個電郵。謝謝!\n")
    elif lang == "zh-Hans":
        subject = "您的 SEO 报告需要一点补充资料"
        body = ("您好,\n\n要完成您的报告,我们需要以下资料:\n\n"
                + "\n".join(f"- {l}" for l in lines)
                + "\n\n请直接回复本邮件。谢谢!\n")
    elif lang == "ja":
        subject = "SEOレポートにあたり追加のご確認のお願い"
        body = ("お世話になっております。\n\nレポート作成のため、以下の情報をご確認ください:\n\n"
                + "\n".join(f"- {l}" for l in lines)
                + "\n\n本メールへの返信でお願いいたします。\n")
    else:  # es
        subject = "Aclaración rápida necesaria para tu informe SEO"
        body = ("Hola:\n\nPara preparar tu informe necesitamos un poco más de información:\n\n"
                + "\n".join(f"- {l}" for l in lines)
                + "\n\nResponde a este correo con los datos. ¡Gracias!\n")
    return {"language": lang, "subject": subject, "body": body,
            "mock_only": True, "live_send_enabled": False,
            "note": "MOCK/STAGING ONLY — live send requires separate owner approval of email identity/sender domain"}


def awaiting_customer_clarification(status: dict) -> dict:
    """Owner rule 4: while awaiting reply."""
    status["status"] = "awaiting_customer_clarification"
    if status.get("clarification"):
        status["clarification"]["awaiting_since"] = now_iso()
    return save(status)


def reply_received(status: dict, reply_sufficient: bool) -> dict:
    """Owner rules 6-8: customer replied -> re-validate; enough -> resume pipeline;
    still insufficient -> manual_support_required."""
    if reply_sufficient:
        status["status"] = "running"
        status["clarification"]["resolved_at"] = now_iso()
        status["clarification"]["outcome"] = "evidence_sufficient_resumed"
    else:
        status["status"] = "manual_support_required"
        status["clarification"]["resolved_at"] = now_iso()
        status["clarification"]["outcome"] = "still_insufficient_manual_support"
    return save(status)


def window_expired(status: dict) -> dict:
    """Owner rule 9: no reply after 3 business days -> manual_support_required.
    Preserves audit record; no auto report/refund/credit; no data deletion."""
    status["status"] = "manual_support_required"
    if status.get("clarification"):
        status["clarification"]["outcome"] = "no_reply_window_expired"
    status["owner_support_record"] = {
        "created_at": now_iso(),
        "job_id": status.get("order_id", ""),
        "reason": "clarification window expired (3 business days) or evidence still insufficient",
        "audit_preserved": True,
        "next": "owner-approved remedy decision pending",
    }
    return save(status)


def check_window_expired(status: dict) -> bool:
    """True if awaiting_customer_clarification has passed 3 business days."""
    cl = status.get("clarification") or {}
    since = cl.get("awaiting_since") or cl.get("state_entered_at")
    if not since:
        return False
    try:
        dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
    except Exception:
        return False
    return business_days_between(dt, datetime.now(timezone.utc)) >= CLARIFICATION_WINDOW_BUSINESS_DAYS


# ---------------- utils ----------------

def business_days_between(start: datetime, end: datetime) -> int:
    days = 0
    d = start.date()
    while d < end.date():
        if d.weekday() < 5:
            days += 1
        d += timedelta(days=1)
    return days


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def save(status: dict):
    path = status.get("status_file")
    if not path:
        return status
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(status, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return status
