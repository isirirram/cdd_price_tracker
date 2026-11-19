"""Price-drop notifications: email (SMTP) and Telegram.

Email env vars (worker/.env or the root .env used by docker-compose):
    SMTP_HOST        e.g. smtp.gmail.com
    SMTP_PORT        587 (STARTTLS, default) or 465 (SSL)
    SMTP_USER        the sending account, e.g. yourproject@gmail.com
    SMTP_PASSWORD    for Gmail this must be an App Password, not your login password
    ALERT_FROM_EMAIL "From" address (optional, defaults to SMTP_USER)
    ALERT_EMAIL_TO   fallback recipient when a product has no notify_email (optional)

Telegram env vars:
    TELEGRAM_BOT_TOKEN  token from @BotFather
    TELEGRAM_CHAT_ID    fallback chat when a product has no telegram_chat_id (optional)

Product names come from scraped web pages, so they are untrusted text:
they are HTML-escaped in the email body and stripped of line breaks in the
subject. Telegram messages are sent as plain text (no parse_mode), so
nothing in them is interpreted as markup.
"""

import html
import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlparse

import requests

TELEGRAM_API = "https://api.telegram.org"
MAX_NAME_LENGTH = 150


class EmailNotConfigured(RuntimeError):
    pass


class TelegramNotConfigured(RuntimeError):
    pass


# ------------------------------------------------------------ safe text
def clean_name(name) -> str:
    """One line, no control characters, sensible length."""
    text = " ".join(str(name or "").split())  # collapses \r, \n, tabs
    text = "".join(ch for ch in text if ch.isprintable())
    if len(text) > MAX_NAME_LENGTH:
        text = text[: MAX_NAME_LENGTH - 1] + "…"
    return text or "Tracked product"


def safe_link(url) -> str | None:
    """Only http(s) links may go into the email's button."""
    url = str(url or "").strip()
    if urlparse(url).scheme.lower() in ("http", "https"):
        return url
    return None


# ----------------------------------------------------------------- email
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
    name = clean_name(product_name)
    link = safe_link(product_url)
    saving = target_price - current_price

    msg = EmailMessage()
    msg["Subject"] = f"Price drop: {name} is now ₹{current_price:,.2f}"
    msg["From"] = from_email
    msg["To"] = to_email

    text = (
        f"Good news! A product you're tracking has hit your target price.\n\n"
        f"Product:       {name}\n"
        f"Current price: ₹{current_price:,.2f}\n"
        f"Your target:   ₹{target_price:,.2f}\n"
        f"Below target:  ₹{saving:,.2f}\n\n"
        + (f"Buy it here: {link}\n\n" if link else "")
        + "- Smart Price Tracker"
    )
    msg.set_content(text)

    safe_name = html.escape(name)
    button = (
        f'<p><a href="{html.escape(link, quote=True)}"\n'
        '      style="background:#2563eb;color:#fff;padding:10px 16px;\n'
        '             text-decoration:none;border-radius:6px;">View product</a></p>'
        if link
        else ""
    )
    body = f"""\
<html>
  <body style="font-family: Arial, sans-serif; color: #222;">
    <h2 style="color: #16a34a;">Price drop alert</h2>
    <p>A product you're tracking has hit your target price.</p>
    <table cellpadding="6" style="border-collapse: collapse;">
      <tr><td><b>Product</b></td><td>{safe_name}</td></tr>
      <tr><td><b>Current price</b></td><td style="color:#16a34a;"><b>₹{current_price:,.2f}</b></td></tr>
      <tr><td><b>Your target</b></td><td>₹{target_price:,.2f}</td></tr>
      <tr><td><b>Below target by</b></td><td>₹{saving:,.2f}</td></tr>
    </table>
    {button}
    <p style="color:#888;font-size:12px;">Smart Price Tracker</p>
  </body>
</html>
"""
    msg.add_alternative(body, subtype="html")
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
    """Send one price-drop email. Raises on any failure."""
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


# -------------------------------------------------------------- telegram
def resolve_telegram_chat(product: dict) -> str | None:
    """The product's own chat id wins; otherwise use TELEGRAM_CHAT_ID."""
    chat = product.get("telegram_chat_id") or os.getenv("TELEGRAM_CHAT_ID")
    return str(chat).strip() if chat else None


def build_telegram_text(
    product_name: str, product_url: str, current_price: float, target_price: float
) -> str:
    link = safe_link(product_url)
    return (
        "🔔 PRICE DROP ALERT\n\n"
        f"Product: {clean_name(product_name)}\n"
        f"Current price: ₹{current_price:,.2f}\n"
        f"Your target: ₹{target_price:,.2f}\n"
        f"Below target by: ₹{target_price - current_price:,.2f}\n"
        + (f"\nBuy it here: {link}" if link else "")
    )


def send_telegram_alert(
    chat_id: str,
    product_name: str,
    product_url: str,
    current_price: float,
    target_price: float,
) -> None:
    """Send one price-drop Telegram message. Raises on any failure."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise TelegramNotConfigured("Telegram is not configured. Set TELEGRAM_BOT_TOKEN.")

    resp = requests.post(
        f"{TELEGRAM_API}/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": build_telegram_text(product_name, product_url, current_price, target_price),
            "disable_web_page_preview": True,
        },
        timeout=20,
    )
    data = resp.json() if resp.content else {}
    if resp.status_code != 200 or not data.get("ok"):
        # Never include the token (it's in the URL) in the error message
        raise RuntimeError(f"Telegram API error: {data.get('description') or resp.status_code}")


# ------------------------------------------------------------ all channels
def send_price_alerts(
    product: dict,
    product_name: str,
    product_url: str,
    current_price: float,
    target_price: float,
) -> tuple[list[str], list[str]]:
    """Try every configured channel.

    Returns (sent, problems): what was delivered, and why anything wasn't.
    """
    sent, problems = [], []
    details = dict(
        product_name=product_name,
        product_url=product_url,
        current_price=current_price,
        target_price=target_price,
    )

    to_email = resolve_recipient(product)
    if not to_email:
        problems.append("no email address is set")
    else:
        try:
            send_email_alert(to_email=to_email, **details)
            sent.append(f"email to {to_email}")
        except EmailNotConfigured:
            problems.append("email is not configured")
        except Exception as exc:
            problems.append(f"email failed ({exc})")

    chat_id = resolve_telegram_chat(product)
    if chat_id:
        try:
            send_telegram_alert(chat_id=chat_id, **details)
            sent.append("Telegram")
        except TelegramNotConfigured:
            problems.append("Telegram is not configured")
        except Exception as exc:
            problems.append(f"Telegram failed ({exc})")

    return sent, problems
