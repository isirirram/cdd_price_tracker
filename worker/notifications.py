"""Email alerts for price drops (replaces the old Telegram alerts).

Configure with these environment variables (see .env.example):

    SMTP_HOST       e.g. smtp.gmail.com
    SMTP_PORT       587 for STARTTLS (default), 465 for SSL
    SMTP_USER       the sending account, e.g. yourteam@gmail.com
    SMTP_PASSWORD   for Gmail this must be an App Password, not your login password
    SMTP_FROM       optional, defaults to SMTP_USER
    ALERT_EMAIL_TO  optional fallback recipient when a product has no alert_email

If SMTP is not configured, send_email_alert() raises EmailNotConfigured.
The caller (tasks.check_price) catches it, so a price check never crashes
just because email isn't set up.
"""

import os
import smtplib
import ssl
from email.message import EmailMessage


class EmailNotConfigured(RuntimeError):
    pass


def _smtp_settings() -> dict:
    host = os.getenv("SMTP_HOST", "").strip()
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    if not (host and user and password):
        raise EmailNotConfigured(
            "SMTP_HOST, SMTP_USER and SMTP_PASSWORD must be set to send email alerts."
        )
    return {
        "host": host,
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": user,
        "password": password,
        "sender": os.getenv("SMTP_FROM", "").strip() or user,
    }


def resolve_recipient(product_email: str | None) -> str:
    recipient = (product_email or "").strip() or os.getenv("ALERT_EMAIL_TO", "").strip()
    if not recipient:
        raise EmailNotConfigured(
            "No recipient: product has no alert_email and ALERT_EMAIL_TO is not set."
        )
    return recipient


def build_message(
    sender: str,
    recipient: str,
    product_name: str,
    current_price: float,
    target_price: float,
    product_url: str,
) -> EmailMessage:
    saved = target_price - current_price
    msg = EmailMessage()
    msg["Subject"] = f"Price drop: {product_name} is now ₹{current_price:,.2f}"
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(
        f"Good news! A product you are tracking has reached your target price.\n\n"
        f"Product:       {product_name}\n"
        f"Current price: ₹{current_price:,.2f}\n"
        f"Your target:   ₹{target_price:,.2f}\n"
        f"Below target by ₹{saved:,.2f}\n\n"
        f"Link: {product_url}\n\n"
        f"- Smart Price Tracker"
    )
    return msg


def send_email_alert(
    product_name: str,
    current_price: float,
    target_price: float,
    product_url: str,
    recipient: str | None = None,
) -> str:
    """Send the alert and return the address it was sent to."""
    settings = _smtp_settings()
    to_addr = resolve_recipient(recipient)
    msg = build_message(
        settings["sender"], to_addr, product_name, current_price, target_price, product_url
    )

    context = ssl.create_default_context()
    if settings["port"] == 465:
        with smtplib.SMTP_SSL(settings["host"], settings["port"], context=context, timeout=15) as server:
            server.login(settings["user"], settings["password"])
            server.send_message(msg)
    else:
        with smtplib.SMTP(settings["host"], settings["port"], timeout=15) as server:
            server.starttls(context=context)
            server.login(settings["user"], settings["password"])
            server.send_message(msg)
    return to_addr
