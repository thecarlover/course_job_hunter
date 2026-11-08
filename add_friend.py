#!/usr/bin/env python3
"""
Helper script to add a new recipient to recipients.json.
Prompts for name, email, and keywords interactively.
"""

import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RECIPIENTS_FILE = os.path.join(BASE_DIR, "recipients.json")


def load_recipients(filepath: str = RECIPIENTS_FILE) -> list:
    """Load existing recipients or return an empty list."""
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except Exception as e:
        print(f"[Warning] Could not read '{filepath}': {e}. Initializing fresh list.")
        return []


def save_recipients(recipients: list, filepath: str = RECIPIENTS_FILE) -> None:
    """Save recipients list back to recipients.json."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(recipients, f, indent=2, ensure_ascii=False)
        f.write("\n")


def add_friend_interactive():
    print("=" * 55)
    print(" 🎓💼 Course & Job Hunter - Add a Friend")
    print("=" * 55)

    name = input("Enter friend's name: ").strip()
    if not name:
        print("[Error] Name cannot be empty.")
        sys.exit(1)

    email = input("Enter friend's email: ").strip()
    if not email or "@" not in email:
        print("[Error] Please enter a valid email address.")
        sys.exit(1)

    keywords_input = input(
        "Enter keywords to match (comma-separated, e.g. python, ai, excel): "
    ).strip()
    keywords = [k.strip().lower() for k in keywords_input.split(",") if k.strip()]
    if not keywords:
        keywords = ["python", "automation", "ai", "free"]
        print(f"No keywords entered. Using default keywords: {keywords}")

    job_searches_input = input(
        "Enter job search terms (comma-separated, press Enter to use keywords): "
    ).strip()
    if job_searches_input:
        job_searches = [j.strip().lower() for j in job_searches_input.split(",") if j.strip()]
    else:
        job_searches = keywords[:4]  # Use top keywords as default job searches
        print(f"Using search terms: {job_searches}")

    max_items_input = input("Enter max items per digest [default 15]: ").strip()
    try:
        max_items = int(max_items_input) if max_items_input else 15
    except ValueError:
        max_items = 15

    recipients = load_recipients(RECIPIENTS_FILE)

    # Check if friend with this email already exists
    existing = next((r for r in recipients if r.get("email", "").lower() == email.lower()), None)
    if existing:
        print(f"\n[Notice] A recipient with email '{email}' already exists ({existing.get('name')}).")
        overwrite = input("Do you want to update their settings? (y/N): ").strip().lower()
        if overwrite == "y":
            existing["name"] = name
            existing["active"] = True
            existing["keywords"] = keywords
            existing["job_searches"] = job_searches
            existing["max_items"] = max_items
            save_recipients(recipients, RECIPIENTS_FILE)
            print(f"\n✅ Updated settings for '{name}' ({email}) in recipients.json!")
            return
        else:
            print("Aborted. No changes were made.")
            return

    new_person = {
        "name": name,
        "email": email,
        "active": True,
        "keywords": keywords,
        "job_searches": job_searches,
        "course_feeds": [],
        "max_items": max_items,
        "welcome_sent": False,
    }

    recipients.append(new_person)
    save_recipients(recipients, RECIPIENTS_FILE)

    print("\n" + "=" * 55)
    print(f"✅ Successfully added '{name}' ({email}) to recipients.json!")
    print(f"   Keywords: {keywords}")
    print(f"   Job searches: {job_searches}")
    print(f"   Max items: {max_items}")
    print(f"   Status: Active")
    print("=" * 55)

    send_now = input("\nWould you like to send their Welcome Email right now? (Y/n): ").strip().lower()
    if send_now != "n":
        try:
            import notifier
            from main import compose_welcome_message, build_html_welcome, mark_welcome_sent, load_seen_dict
            welcome_msg = compose_welcome_message(name, email, keywords, job_searches, max_items)
            welcome_html = build_html_welcome(name, email, keywords, job_searches, max_items)
            print(f"Sending welcome email to {email}...")
            notifier.send(
                welcome_msg,
                to_email=email,
                subject=f"👋 Welcome to Course & Job Hunter, {name}!",
                html=welcome_html,
            )
            seen_dict = load_seen_dict()
            mark_welcome_sent(new_person, seen_dict, RECIPIENTS_FILE)
            print(f"✅ Welcome email successfully sent to {name} <{email}>!")
        except Exception as e:
            print(f"[Notice] Could not send welcome email immediately ({e}).")
            print("It will be sent automatically on the next daily run.")
    else:
        print("Welcome email will be sent automatically on the next daily run.")


if __name__ == "__main__":
    add_friend_interactive()

