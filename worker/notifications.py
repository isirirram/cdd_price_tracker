import os
import smtplib
import ssl
import base64
import json
import urllib.request
import urllib.error

from pathlib import Path
from email.message import EmailMessage
from dotenv import load_dotenv


# Load environment variables from worker/.env
env_path = Path(__file__).with_name(".env")
load_dotenv(env_path, override=True)


# Gmail configuration
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").replace(" ", "")


# Telegram configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_email_alert(recipient_email, product_name, current_price, target_price):

    if not SMTP_EMAIL or not SMTP_PASSWORD:
        raise ValueError(
            "Gmail email or app password is missing in worker/.env"
        )

    if not recipient_email:
        raise ValueError("Recipient email address is missing")

    message = EmailMessage()

    message["Subject"] = f"Price Drop Alert: {product_name}"
    message["From"] = SMTP_EMAIL
    message["To"] = recipient_email

    message.set_content(
        f"""PRICE DROP ALERT!

Product: {product_name}
Current Price: Rs. {current_price}
Target Price: Rs. {target_price}

Your target price has been reached!

Check the product now before the price changes.
"""
    )

    context = ssl.create_default_context()

    try:
        with smtplib.SMTP_SSL(
            SMTP_HOST,
            SMTP_PORT,
            context=context,
            timeout=30
        ) as server:

            print("Connected to Gmail successfully.")

            server.ehlo()

            print("Trying Gmail LOGIN authentication...")

            code, response = server.docmd("AUTH", "LOGIN")

            if code != 334:
                raise smtplib.SMTPAuthenticationError(code, response)

            encoded_email = base64.b64encode(
                SMTP_EMAIL.encode("utf-8")
            ).decode("ascii")

            code, response = server.docmd(encoded_email)

            if code != 334:
                raise smtplib.SMTPAuthenticationError(code, response)

            encoded_password = base64.b64encode(
                SMTP_PASSWORD.encode("utf-8")
            ).decode("ascii")

            code, response = server.docmd(encoded_password)

            if code != 235:
                raise smtplib.SMTPAuthenticationError(code, response)

            print("Gmail authentication successful!")

            server.send_message(message)

            print(f"Email sent successfully to {recipient_email}!")

    except Exception as e:
        print("Email sending error:", type(e).__name__, str(e))
        raise


def send_telegram_alert(product_name, current_price, target_price):

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise ValueError(
            "Telegram bot token or chat ID is missing in worker/.env"
        )

    message = (
        "PRICE DROP ALERT!\n\n"
        f"Product: {product_name}\n"
        f"Current Price: Rs. {current_price}\n"
        f"Target Price: Rs. {target_price}\n\n"
        "Your target price has been reached!\n"
        "Check the product now before the price changes."
    )

    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }

    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:

            result = json.loads(response.read().decode("utf-8"))

            if not result.get("ok"):
                raise RuntimeError(
                    "Telegram API could not send the message"
                )

            print("Telegram message sent successfully!")

    except Exception as e:
        print("Telegram sending error:", type(e).__name__, str(e))
        raise