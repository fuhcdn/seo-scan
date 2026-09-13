#!/usr/bin/env python3
"""
AP-2 — Payment confirmation email DRAFT/TEMPLATE system (staging-only).

Status: DRAFT_ONLY / OWNER_APPROVAL_REQUIRED
- NO live send enabled. Only mock/safe-test send via the canonical verified
  delivery service pattern (mock sender) or rendering to file for review.
- Does NOT change Stripe/webhook behaviour. Webhook integration is a proposal
  hook only (send at payment_received after webhook verify — not wired here).
- Customer-safe: no internal order IDs, file paths, secrets, provider names,
  infrastructure data. No ranking/traffic/revenue/lead promises.
- Delivery promise = the real 24-hour target only.
- report_language flow preserved (5 languages, exact codes).

Languages: en, zh-Hant, zh-Hans, ja, es
"""
import json
import os
import time

# ---- owner-approval gate ----------------------------------------------------
ALLOW_LIVE_SEND = False   # NEVER flipped to True here; owner approval required.

REPORT_LANGUAGES = ("en", "zh-Hant", "zh-Hans", "ja", "es")

SUPPORT_EMAIL = "hello@seoscanaudit.com"   # public support route (per brand copy)

# ---- exact drafts (return these to owner for approval) -----------------------
DRAFTS = {
    "en": {
        "subject": "Order received — your SEO report is in progress",
        "body": (
            "Hello,\n\n"
            "Thank you — we have received your order and your report is now in progress.\n\n"
            "What happens next:\n"
            "1. Your order is confirmed and your website/business context is being reviewed.\n"
            "2. Your report normally arrives by email within 24 hours.\n"
            "3. If anything is unclear in the details you provided, we may contact you by email "
            "to request a short clarification before your report is finalised.\n\n"
            "What you will receive:\n"
            "A decision-ready SEO report for your website, delivered to this email address as a PDF.\n\n"
            "If you have any questions, reply to this email or contact us at {support}.\n\n"
            "Thank you,\n"
            "The SEO Scan team\n"
        ),
    },
    "zh-Hant": {
        "subject": "已收到你的訂單 — SEO 報告正在處理中",
        "body": (
            "你好,\n\n"
            "多謝你 — 我哋已收到你嘅訂單,你嘅報告正在處理中。\n\n"
            "跟住會發生咩事:\n"
            "1. 你嘅訂單已確認,你嘅網站/業務背景正在審核中。\n"
            "2. 你嘅報告一般會喺 24 小時內以電郵送達。\n"
            "3. 如果你提供嘅資料有唔清楚嘅地方,我哋可能會以電郵聯絡你,請你簡單澄清一下,"
            "等我哋完成你嘅報告。\n\n"
            "你會收到:\n"
            "一份針對你網站、可以直接做決定嘅 SEO 報告,以 PDF 附件寄到呢個電郵地址。\n\n"
            "如有任何問題,直接回覆呢個電郵,或者電郵 {support}。\n\n"
            "SEO Scan 團隊 敬上\n"
        ),
    },
    "zh-Hans": {
        "subject": "已收到您的订单 — SEO 报告正在处理中",
        "body": (
            "您好,\n\n"
            "感谢您 — 我们已收到您的订单,您的报告正在处理中。\n\n"
            "接下来会发生什么:\n"
            "1. 您的订单已确认,您的网站/业务背景正在审核中。\n"
            "2. 您的报告一般会在 24 小时内以电子邮件送达。\n"
            "3. 如果您提供的资料有不清楚的地方,我们可能会通过电子邮件联系您,请您简单澄清一下,"
            "以便我们完成您的报告。\n\n"
            "您将收到:\n"
            "一份针对您网站、可以直接做决定的 SEO 报告,以 PDF 附件发送到该电子邮件地址。\n\n"
            "如有任何问题,请直接回复本邮件,或发送邮件至 {support}。\n\n"
            "SEO Scan 团队 敬上\n"
        ),
    },
    "ja": {
        "subject": "ご注文を受け付けました — SEOレポートを作成中です",
        "body": (
            "お世話になっております。\n\n"
            "ご注文を確認いたしました。貴社のレポートはただいま作成中です。\n\n"
            "今後の流れ:\n"
            "1. ご注文は確定済みです。貴社のウェブサイトおよびビジネスの内容を確認しております。\n"
            "2. レポートは通常、24時間以内にメールでお届けします。\n"
            "3. ご提供いただいた内容に不明な点がある場合は、レポート完成前に"
            "メールで簡単なご確認をさせていただくことがあります。\n\n"
            "お届けするもの:\n"
            "貴社のウェブサイト向けの、意思決定にそのまま使えるSEOレポート(PDF)を"
            "このメールアドレスにお送りします。\n\n"
            "ご不明な点は、このメールへの返信または {support} までご連絡ください。\n\n"
            "SEO Scan チーム\n"
        ),
    },
    "es": {
        "subject": "Pedido recibido — tu informe SEO está en proceso",
        "body": (
            "Hola:\n\n"
            "Gracias — hemos recibido tu pedido y tu informe está en proceso.\n\n"
            "Qué ocurre ahora:\n"
            "1. Tu pedido está confirmado y estamos revisando el contexto de tu sitio web y negocio.\n"
            "2. Tu informe normalmente llegará por correo electrónico en un plazo de 24 horas.\n"
            "3. Si algo de la información que proporcionaste no está claro, es posible que te contactemos "
            "por correo electrónico para pedirte una breve aclaración antes de finalizar tu informe.\n\n"
            "Lo que recibirás:\n"
            "Un informe SEO listo para tomar decisiones sobre tu sitio web, entregado como PDF a esta "
            "dirección de correo.\n\n"
            "Si tienes preguntas, responde a este correo o escríbenos a {support}.\n\n"
            "El equipo de SEO Scan\n"
        ),
    },
}

# Customer-safe reference: a short opaque reference, NOT the internal order id.
def customer_safe_reference(order_id: str) -> str:
    """Derive a short opaque customer-facing reference (not the raw internal id,
    no infrastructure info). Same input → same reference (idempotent)."""
    import hashlib
    h = hashlib.sha256(("seo-scan-ref:" + order_id).encode("utf-8")).hexdigest()[:10].upper()
    return f"SS-{h[:5]}-{h[5:10]}"


def render(order_id: str, report_language: str = "en",
           company_name: str = "") -> dict:
    """Render the draft email for a language. NO sending. Returns subject/body."""
    lang = report_language if report_language in REPORT_LANGUAGES else "en"
    d = DRAFTS[lang]
    body = d["body"].replace("{support}", SUPPORT_EMAIL)
    greeting = f"{company_name} — " if company_name else ""
    return {"language": lang, "subject": d["subject"],
            "body": greeting + body,
            "customer_reference": customer_safe_reference(order_id),
            "status": "DRAFT_ONLY",
            "live_send_enabled": ALLOW_LIVE_SEND}


def mock_send_preview(order_id: str, report_language: str, out_dir: str = None) -> dict:
    """Staging-only preview: writes the rendered draft to a file (no email at all)."""
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = out_dir or os.path.join(os.path.dirname(here), "output", "email_drafts")
    os.makedirs(out_dir, exist_ok=True)
    msg = render(order_id, report_language)
    path = os.path.join(out_dir, f"payment_confirmation_{order_id}_{report_language}.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"TO: <safe-test-recipient>\nSUBJECT: {msg['subject']}\n"
                 f"REF: {msg['customer_reference']}\n\n{msg['body']}")
    msg["preview_path"] = path
    return msg


if __name__ == "__main__":
    # render all 5 language drafts to output/email_drafts/ for owner review
    previews = {}
    for lang in REPORT_LANGUAGES:
        m = mock_send_preview("PREVIEW-OWNER-REVIEW", lang)
        previews[lang] = {"subject": m["subject"], "ref": m["customer_reference"],
                          "path": m["preview_path"]}
    print(json.dumps({"status": "DRAFT_ONLY / OWNER_APPROVAL_REQUIRED",
                      "live_send_enabled": False, "languages": previews}, indent=1, ensure_ascii=False))
