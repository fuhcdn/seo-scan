#!/usr/bin/env python3
"""resend_send — real Resend API sender (evidence_v1 delivery only).

Reached only via verified_pdf_delivery after every quality gate has passed.
Config comes from env: RESEND_API_KEY, EMAIL_FROM (verified Resend domain sender).
"""
import os


def resend_send(pdf_path, to_addr, subject, from_addr):
    """Send one PDF attachment email via the Resend REST API."""
    import base64
    import json
    import urllib.request

    key = (os.environ.get("RESEND_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("resend_misconfigured: RESEND_API_KEY empty")
    from_addr = (from_addr or os.environ.get("EMAIL_FROM") or "").strip()
    if from_addr.endswith(("gmail.com", "yahoo.com", "outlook.com", "hotmail.com")):
        from_addr = "onboarding@resend.dev"

    if not (pdf_path and os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0):
        raise RuntimeError("delivery_has_no_pdf_attachment: no PDF attachment")

    with open(pdf_path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode()

    payload = {
        "from": from_addr,
        "to": [to_addr],
        "subject": subject or "Your SEO report",
        "text": "Your AI SEO report is ready. The full PDF report is attached. — seoscanaudit.com",
        "attachments": [{"filename": os.path.basename(pdf_path), "content": b64}],
    }
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        body = resp.read().decode()[:200]
        return body
