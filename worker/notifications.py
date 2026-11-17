"""Email notifications for price-drop alerts.

Uses Python's built-in smtplib, so no extra packages are needed.

Required env vars (worker/.env or the root .env used by docker-compose):
    SMTP_HOST        e.g. smtp.gmail.com
    SMTP_PORT        587 (STARTTLS, default) or 465 (SSL)
    SMTP_USER        the sending account, e.g. yourproject@gmail.com
    SMTP_PASSWORD    for Gmail this must be an App Password, not your login password

Optional:
    ALERT_FROM_EMAIL  "From" address (defaults to SMTP_USER)
    ALERT_EMAIL_TO    fallback recipient when a product has no notify_email
"""

import os
import smtplib
import ssl
from email.message import EmailMessage


class EmailNotConfigured(RuntimeError):
    pass


def get_smtp_settings() -> dict:
    host = os.getenv("SMTP_HOST")
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")

    if not host or not user or not password:
        raise EmailNotConfigured(
            "Email is not configured. Set SMTP_HOST, SMTP_USER and SMTP_PASSWORD."
        )

    return {
        "host": host,
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": user,
        "password": password,
        "from_email": os.getenv("ALERT_FROM_EMAIL") or user,
    }


def resolve_recipient(product: dict) -> str | None:
    """The product's own email wins; otherwise use the ALERT_EMAIL_TO fallback."""
    return product.get("notify_email") or os.getenv("ALERT_EMAIL_TO") or None


def build_alert_email(
    to_email: str,
    from_email: str,
    product_name: str,
    product_url: str,
    current_price: float,
    target_price: float,
) -> EmailMessage:
    saving = target_price - current_price

    msg = EmailMessage()
    msg["Subject"] = f"Price drop: {product_name} is now ₹{current_price:,.2f}"
    msg["From"] = from_email
    msg["To"] = to_email

    text = (
        f"Good news! A product you're tracking has hit your target price.\n\n"
        f"Product:       {product_name}\n"
        f"Current price: ₹{current_price:,.2f}\n"
        f"Your target:   ₹{target_price:,.2f}\n"
        f"Below target:  ₹{saving:,.2f}\n\n"
        f"Buy it here: {product_url}\n\n"
        f"- Smart Price Tracker"
    )
    msg.set_content(text)

    html = f"""\
<html>
  <body style="font-family: Arial, sans-serif; color: #222;">
    <h2 style="color: #16a34a;">Price drop alert</h2>
    <p>A product you're tracking has hit your target price.</p>
    <table cellpadding="6" style="border-collapse: collapse;">
      <tr><td><b>Product</b></td><td>{product_name}</td></tr>
      <tr><td><b>Current price</b></td><td style="color:#16a34a;"><b>₹{current_price:,.2f}</b></td></tr>
      <tr><td><b>Your target</b></td><td>₹{target_price:,.2f}</td></tr>
      <tr><td><b>Below target by</b></td><td>₹{saving:,.2f}</td></tr>
    </table>
    <p><a href="{product_url}"
          style="background:#2563eb;color:#fff;padding:10px 16px;
                 text-decoration:none;border-radius:6px;">View product</a></p>
    <p style="color:#888;font-size:12px;">Smart Price Tracker</p>
  </body>
</html>
"""
    msg.add_alternative(html, subtype="html")
    return msg


def send_email(msg: EmailMessage, settings: dict) -> None:
    context = ssl.create_default_context()

    if settings["port"] == 465:
        with smtplib.SMTP_SSL(
            settings["host"], settings["port"], context=context, timeout=20
        ) as server:
            server.login(settings["user"], settings["password"])
            server.send_message(msg)
    else:
        with smtplib.SMTP(settings["host"], settings["port"], timeout=20) as server:
            server.starttls(context=context)
            server.login(settings["user"], settings["password"])
            server.send_message(msg)


def send_email_alert(
    to_email: str,
    product_name: str,
    product_url: str,
    current_price: float,
    target_price: float,
) -> None:
    """Send one price-drop email. Raises on any failure so the caller can retry later."""
    settings = get_smtp_settings()
    msg = build_alert_email(
        to_email=to_email,
        from_email=settings["from_email"],
        product_name=product_name,
        product_url=product_url,
        current_price=current_price,
        target_price=target_price,
    )
    send_email(msg, settings)
