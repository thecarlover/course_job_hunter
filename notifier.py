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


def get_sender_email() -> str:
    """Return the configured sender email address."""
    load_dotenv()
    return (os.environ.get("EMAIL") or getattr(config, "EMAIL", "") or "").strip()


def validate_credentials() -> tuple:
    """
    Validate that required credentials for the active notifier are present.
    Returns (is_valid: bool, error_message: str).
    """
    load_dotenv()
    method = (getattr(config, "NOTIFIER", "") or "").strip().lower()

    if method == "email":
        email_addr = (os.environ.get("EMAIL") or getattr(config, "EMAIL", "") or "").strip()
        app_password = (os.environ.get("APP_PASSWORD") or getattr(config, "APP_PASSWORD", "") or "").strip()
        if not email_addr or not app_password:
            missing = []
            if not email_addr:
                missing.append("EMAIL")
            if not app_password:
                missing.append("APP_PASSWORD")
            return (
                False,
                f"Missing required secret(s) for email notifier: {', '.join(missing)}. "
                "Please set them in GitHub Repository Secrets or in a local .env file.",
            )
        return (True, "")

    elif method == "ntfy":
        topic = (os.environ.get("NTFY_TOPIC") or getattr(config, "NTFY_TOPIC", "") or "").strip()
        if not topic:
            return (
                False,
                "Missing NTFY_TOPIC for ntfy notifier. Set it in GitHub Secrets or .env file.",
            )
        return (True, "")

    elif method == "discord":
        url = (os.environ.get("WEBHOOK_URL") or getattr(config, "WEBHOOK_URL", "") or "").strip()
        if not url:
            return (
                False,
                "Missing WEBHOOK_URL for discord notifier. Set it in GitHub Secrets or .env file.",
            )
        return (True, "")

    return (
        False,
        f"Unsupported NOTIFIER '{config.NOTIFIER}'. Supported options: 'email', 'ntfy', 'discord'.",
    )


def _send_email(text: str, to_email: str = None, subject: str = None) -> None:
    """Send digest email to a recipient via Gmail SMTP over SSL."""
    load_dotenv()
    email_addr = (os.environ.get("EMAIL") or getattr(config, "EMAIL", "") or "").strip()
    app_password = (os.environ.get("APP_PASSWORD") or getattr(config, "APP_PASSWORD", "") or "").strip()

    if not email_addr or not app_password:
        raise ValueError(
            "Missing EMAIL or APP_PASSWORD in environment variables, .env file, or config.py."
        )

    target_email = (to_email or email_addr).strip()

    # Google App Passwords are 16 letters, often copied with spaces (e.g. 'xxxx xxxx xxxx xxxx')
    clean_password = app_password.replace(" ", "")

    msg = EmailMessage()
    msg["Subject"] = subject or "Daily Digest: Free Courses & Remote Jobs"
    msg["From"] = email_addr
    msg["To"] = target_email
    msg.set_content(text)

    try:
        # Gmail SMTP over SSL on port 465
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(email_addr, clean_password)
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError as e:
        raise RuntimeError(
            f"Gmail SMTP authentication failed for '{email_addr}'. "
            "Please verify that: 1) 2-Step Verification is ON in your Google Account, "
            "and 2) APP_PASSWORD is an active 16-character App Password generated at "
            "https://myaccount.google.com/apppasswords. "
            f"Server details: {e}"
        ) from e


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


def send(text: str, to_email: str = None, subject: str = None) -> None:
    """
    Route the notification to the provider configured in config.NOTIFIER.
    For email, sends to `to_email` (defaulting to self if omitted).
    """
    method = (config.NOTIFIER or "").strip().lower()

    if method == "email":
        _send_email(text, to_email=to_email, subject=subject)
    elif method == "ntfy":
        _send_ntfy(text)
    elif method == "discord":
        _send_discord(text)
    else:
        raise ValueError(
            f"Unsupported NOTIFIER '{config.NOTIFIER}'. "
            "Supported options: 'email', 'ntfy', 'discord'"
        )
