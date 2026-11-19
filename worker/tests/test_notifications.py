"""Tests for worker/notifications.py. No real email is sent: SMTP is mocked."""
from unittest.mock import MagicMock, patch

import pytest

import notifications
from notifications import (
    EmailNotConfigured,
    build_alert_email,
    resolve_recipient,
    send_email_alert,
)

SMTP_ENV = {
    "SMTP_HOST": "smtp.example.com",
    "SMTP_PORT": "587",
    "SMTP_USER": "tracker@example.com",
    "SMTP_PASSWORD": "secret",
}


def test_resolve_recipient_prefers_product_email(monkeypatch):
    monkeypatch.setenv("ALERT_EMAIL_TO", "fallback@example.com")
    assert resolve_recipient({"notify_email": "user@example.com"}) == "user@example.com"


def test_resolve_recipient_uses_fallback(monkeypatch):
    monkeypatch.setenv("ALERT_EMAIL_TO", "fallback@example.com")
    assert resolve_recipient({"notify_email": None}) == "fallback@example.com"


def test_resolve_recipient_none(monkeypatch):
    monkeypatch.delenv("ALERT_EMAIL_TO", raising=False)
    assert resolve_recipient({}) is None


def test_build_alert_email_contents():
    msg = build_alert_email(
        "user@example.com", "tracker@example.com",
        "Test Phone", "https://shop.example/p/1", 45000.0, 50000.0,
    )
    assert msg["To"] == "user@example.com"
    assert "Test Phone" in msg["Subject"]
    body = msg.get_body(preferencelist=("plain",)).get_content()
    assert "45,000.00" in body and "5,000.00" in body


def test_send_fails_without_config(monkeypatch):
    for key in SMTP_ENV:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(EmailNotConfigured):
        send_email_alert("u@example.com", "P", "https://x", 1.0, 2.0)


def test_send_uses_starttls(monkeypatch):
    for key, value in SMTP_ENV.items():
        monkeypatch.setenv(key, value)
    server = MagicMock()
    with patch.object(notifications.smtplib, "SMTP") as smtp:
        smtp.return_value.__enter__.return_value = server
        send_email_alert("u@example.com", "P", "https://x", 1.0, 2.0)
    server.starttls.assert_called_once()
    server.login.assert_called_once_with("tracker@example.com", "secret")
    server.send_message.assert_called_once()


# ------------------------------------------------ untrusted product names
def test_scraped_name_is_escaped_in_html():
    evil = '<img src=x onerror=alert(1)><a href="https://phish.example">Click</a>'
    msg = build_alert_email(
        "user@example.com", "tracker@example.com", evil,
        "https://shop.example/p/1", 900.0, 1000.0,
    )
    html_body = msg.get_body(preferencelist=("html",)).get_content()
    assert "<img src=x" not in html_body
    assert "&lt;img src=x onerror=alert(1)&gt;" in html_body
    assert 'href="https://phish.example"' not in html_body


def test_newlines_in_name_do_not_break_subject():
    msg = build_alert_email(
        "user@example.com", "tracker@example.com",
        "Phone\r\nBcc: victim@example.com", "https://shop.example/p/1", 900.0, 1000.0,
    )
    assert "\n" not in msg["Subject"] and "\r" not in msg["Subject"]
    assert msg["Bcc"] is None


def test_non_http_product_link_is_dropped():
    msg = build_alert_email(
        "user@example.com", "tracker@example.com", "Phone",
        "javascript:alert(1)", 900.0, 1000.0,
    )
    html_body = msg.get_body(preferencelist=("html",)).get_content()
    assert "javascript:" not in html_body


def test_link_quotes_are_escaped():
    msg = build_alert_email(
        "user@example.com", "tracker@example.com", "Phone",
        'https://shop.example/p/1"onmouseover="alert(1)', 900.0, 1000.0,
    )
    html_body = msg.get_body(preferencelist=("html",)).get_content()
    assert '"onmouseover="' not in html_body


# --------------------------------------------------------------- telegram
def test_telegram_chat_prefers_product(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
    assert notifications.resolve_telegram_chat({"telegram_chat_id": "222"}) == "222"
    assert notifications.resolve_telegram_chat({}) == "111"
    monkeypatch.delenv("TELEGRAM_CHAT_ID")
    assert notifications.resolve_telegram_chat({}) is None


def test_telegram_needs_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(notifications.TelegramNotConfigured):
        notifications.send_telegram_alert("1", "P", "https://x", 1.0, 2.0)


def test_telegram_sends_plain_text(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    response = MagicMock(status_code=200, content=b"{}")
    response.json.return_value = {"ok": True}
    with patch.object(notifications.requests, "post", return_value=response) as post:
        notifications.send_telegram_alert("999", "<b>Phone</b>", "https://shop.example/p", 900.0, 1000.0)
    url = post.call_args.args[0]
    payload = post.call_args.kwargs["json"]
    assert url == "https://api.telegram.org/bot123:ABC/sendMessage"
    assert payload["chat_id"] == "999"
    assert "parse_mode" not in payload  # plain text: nothing is treated as markup
    assert "₹900.00" in payload["text"]


def test_telegram_error_does_not_leak_token(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:SECRET")
    response = MagicMock(status_code=400, content=b"{}")
    response.json.return_value = {"ok": False, "description": "Bad Request: chat not found"}
    with patch.object(notifications.requests, "post", return_value=response):
        with pytest.raises(RuntimeError) as err:
            notifications.send_telegram_alert("1", "P", "https://x", 1.0, 2.0)
    assert "chat not found" in str(err.value)
    assert "SECRET" not in str(err.value)
