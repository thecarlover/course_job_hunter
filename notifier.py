"""
Notification module for course-job-hunter.

Supports sending alerts via:
- Gmail SMTP (email)
- ntfy (push notifications to web/phone)
- Discord (webhook)

All credentials are read from environment variables to keep secrets secure.
"""

import os
import smtplib
from email.message import EmailMessage
import requests
import config

# Directory of this project
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_dotenv(filepath: str = None) -> None:
    """
    Load key-value pairs from a .env file into os.environ.
    Only sets keys if they are not already set in the environment.
    """
    if filepath is None:
        filepath = os.path.join(BASE_DIR, ".env")
    if not os.path.isfile(filepath):
        return

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = val
    except Exception as e:
        print(f"[Warning] Failed to load .env file '{filepath}': {e}")


# Load on module import
load_dotenv()


def _send_email(text: str) -> None:
    """Send digest email to self via Gmail SMTP over SSL."""
    load_dotenv()
    email_addr = (os.environ.get("EMAIL") or getattr(config, "EMAIL", "") or "").strip()
    app_password = (os.environ.get("APP_PASSWORD") or getattr(config, "APP_PASSWORD", "") or "").strip()

    if not email_addr or not app_password:
        raise ValueError(
            "Missing EMAIL or APP_PASSWORD in environment variables, .env file, or config.py."
        )

    # Google App Passwords are 16 letters, often copied with spaces (e.g. 'xxxx xxxx xxxx xxxx')
    clean_password = app_password.replace(" ", "")

    msg = EmailMessage()
    msg["Subject"] = "Daily Digest: Free Courses & Remote Jobs"
    msg["From"] = email_addr
    msg["To"] = email_addr
    msg.set_content(text)

    # Gmail SMTP over SSL on port 465
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
        server.login(email_addr, clean_password)
        server.send_message(msg)


def _send_ntfy(text: str) -> None:
    """Publish digest to an ntfy topic."""
    load_dotenv()
    topic = (os.environ.get("NTFY_TOPIC") or getattr(config, "NTFY_TOPIC", "") or "").strip()
    if not topic:
        raise ValueError(
            "Missing NTFY_TOPIC in environment variables, .env file, or config.py."
        )

    url = f"https://ntfy.sh/{topic}"
    response = requests.post(
        url,
        data=text.encode("utf-8"),
        headers={
            "Title": "Daily Digest: Free Courses & Remote Jobs",
            "Priority": "default",
        },
        timeout=15,
    )
    response.raise_for_status()


def _send_discord(text: str) -> None:
    """Post digest to a Discord channel via webhook."""
    load_dotenv()
    webhook_url = (os.environ.get("WEBHOOK_URL") or getattr(config, "WEBHOOK_URL", "") or "").strip()
    if not webhook_url:
        raise ValueError(
            "Missing WEBHOOK_URL in environment variables, .env file, or config.py."
        )

    # Discord has a 2000-character message limit; trim to 1900 for safety
    payload = {"content": text[:1900]}
    response = requests.post(webhook_url, json=payload, timeout=15)
    response.raise_for_status()


def send(text: str) -> None:
    """
    Route the notification to the provider configured in config.NOTIFIER.
    """
    method = (config.NOTIFIER or "").strip().lower()

    if method == "email":
        _send_email(text)
    elif method == "ntfy":
        _send_ntfy(text)
    elif method == "discord":
        _send_discord(text)
    else:
        raise ValueError(
            f"Unsupported NOTIFIER '{config.NOTIFIER}'. "
            "Supported options: 'email', 'ntfy', 'discord'"
        )
