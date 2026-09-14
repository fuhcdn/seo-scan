#!/usr/bin/env python3
"""smtp_send — the single real-SMTP PDF-attachment sender (extracted 2026-09-14
during legacy retirement; formerly pipeline_runner._smtp_send).

Only reachable via verified_pdf_delivery.default_smtp_send, which is only
invoked on the evidence_v1 route after every quality gate passes.
"""
import os


def smtp_send(pdf_path, to_addr, subject, from_addr, smtp_host, smtp_port,
              username, password, implicit_ssl=True):
    """真正用 smtplib 送一封含 PDF 附件嘅 email。有設定先會 call 到呢度。"""
    import smtplib
    from email.mime.application import MIMEApplication
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    # Customer replies route to the support inbox (env-configured; identity NOT
    # changed here — this only adds a header when the owner sets REPLY_TO_EMAIL).
    reply_to = (os.environ.get("REPLY_TO_EMAIL", "") or "").strip()
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.attach(MIMEText(
        "你的 AI SEO 審計報告已完成，完整 PDF 報告請見附件。\n\n"
        "如有任何問題，請回覆本電郵或電郵 hello@seoscanaudit.com。"
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
