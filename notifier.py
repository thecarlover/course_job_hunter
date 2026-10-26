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


def _send_email(text: str) -> None:
    """Send digest email to self via Gmail SMTP over SSL."""
    email_addr = os.environ.get("EMAIL")
    app_password = os.environ.get("APP_PASSWORD")

    if not email_addr or not app_password:
        raise ValueError(
            "Missing EMAIL or APP_PASSWORD environment variables for email notification."
        )

    msg = EmailMessage()
    msg["Subject"] = "Daily Digest: Free Courses & Remote Jobs"
    msg["From"] = email_addr
    msg["To"] = email_addr
    msg.set_content(text)

    # Gmail SMTP over SSL on port 465
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
        server.login(email_addr, app_password)
        server.send_message(msg)


def _send_ntfy(text: str) -> None:
    """Publish digest to an ntfy topic."""
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        raise ValueError("Missing NTFY_TOPIC environment variable for ntfy notification.")

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
    webhook_url = os.environ.get("WEBHOOK_URL")
    if not webhook_url:
        raise ValueError("Missing WEBHOOK_URL environment variable for discord notification.")

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
