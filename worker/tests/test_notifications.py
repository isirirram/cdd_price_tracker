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
