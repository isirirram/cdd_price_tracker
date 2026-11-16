
import os
import smtplib
import ssl
import base64
from pathlib import Path
from email.message import EmailMessage

from dotenv import load_dotenv


# Load environment variables from worker/.env
env_path = Path(__file__).with_name(".env")
load_dotenv(env_path, override=True)


SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").replace(" ", "")


def send_email_alert(recipient_email, product_name, current_price, target_price):

    # Check Gmail configuration
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        raise ValueError(
            "Gmail email or app password is missing in worker/.env"
        )

    if not recipient_email:
        raise ValueError("Recipient email address is missing")

    # Create email
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

            # Gmail LOGIN authentication
            print("Trying Gmail LOGIN authentication...")

            code, response = server.docmd("AUTH", "LOGIN")

            if code != 334:
                raise smtplib.SMTPAuthenticationError(code, response)

            # Send Gmail address
            encoded_email = base64.b64encode(
                SMTP_EMAIL.encode("utf-8")
            ).decode("ascii")

            code, response = server.docmd(encoded_email)

            if code != 334:
                raise smtplib.SMTPAuthenticationError(code, response)

            # Send Gmail App Password
            encoded_password = base64.b64encode(
                SMTP_PASSWORD.encode("utf-8")
            ).decode("ascii")

            code, response = server.docmd(encoded_password)

            if code != 235:
                raise smtplib.SMTPAuthenticationError(code, response)

            print("Gmail authentication successful!")

            # Send email
            server.send_message(message)

            print(
                f"Email sent successfully to {recipient_email}!"
            )

    except smtplib.SMTPAuthenticationError as e:
        print("Gmail authentication failed:", e.smtp_code, e.smtp_error)
        raise

    except smtplib.SMTPException as e:
        print("SMTP error:", type(e).__name__, str(e))
        raise

    except Exception as e:
        print("Email sending error:", type(e).__name__, str(e))
        raise
