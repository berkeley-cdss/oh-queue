"""Sending email over SMTP, as seating does."""

from email.message import EmailMessage
from email.utils import formataddr
from smtplib import SMTP

from flask import current_app


def send_email(*, target: str, subject: str, body: str, attachments: dict = None):
    """Email ``target`` from EMAIL_SENDER, or log it without EMAIL_SERVER.

    :param attachments: file name to contents, as bytes
    """
    config = current_app.config
    if not config.get("EMAIL_SERVER"):
        current_app.logger.info(
            "EMAIL_SERVER isn't set, so not sending to %s: %s\n%s", target, subject, body
        )
        return

    msg = EmailMessage()
    msg["From"] = formataddr(("OH Queue", config["EMAIL_SENDER"]))
    msg["To"] = target
    msg["Subject"] = subject
    msg.set_content(body)
    for filename, content in (attachments or {}).items():
        maintype, subtype = (
            ("text", "calendar") if filename.endswith(".ics") else ("application", "octet-stream")
        )
        msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)

    # The appointment change that triggered the email is already saved, so a
    # failed send is logged rather than failing the request.
    try:
        with SMTP(config["EMAIL_SERVER"], config["EMAIL_PORT"], timeout=30) as smtp:
            smtp.starttls()
            if config.get("EMAIL_USERNAME"):
                smtp.login(config["EMAIL_USERNAME"], config["EMAIL_PASSWORD"])
            smtp.send_message(msg)
    except Exception:
        current_app.logger.exception("Couldn't send %r to %s", subject, target)
