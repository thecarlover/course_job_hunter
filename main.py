"""
Main script for course-job-hunter.

Fetches free courses from RSS feeds and remote jobs from multiple free job boards
(Remotive, Jobicy, Arbeitnow) once per run, filters results per recipient using
custom keywords and location preferences, badges salary/location/visa details,
prunes expired seen records automatically, generates weekly market insights,
and sends individual, customized digests while tracking seen history per recipient.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import html
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Set
import urllib.parse

import feedparser
import requests

import config
import db
import notifier

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEEN_FILE = os.path.join(BASE_DIR, "seen.json")
RECIPIENTS_FILE = os.path.join(BASE_DIR, "recipients.json")


# ============================================================================
# Recipients Management
# ============================================================================

def load_recipients(filepath: str = None) -> List[Dict]:
    """
    Load the list of recipients.
    Priority:
    1. RECIPIENTS_JSON environment variable (e.g. from GitHub Secret)
    2. recipients.json file on disk
    3. Fallback to single recipient from config.py / EMAIL
    """
    if filepath is None:
        filepath = RECIPIENTS_FILE

    # 1. Check environment variable (useful for secret recipient lists on GitHub)
    secret_recipients = os.environ.get("RECIPIENTS_JSON", "").strip()
    if secret_recipients:
        try:
            data = json.loads(secret_recipients)
            if isinstance(data, list) and len(data) > 0:
                print(f"[Recipients] Loaded {len(data)} recipient(s) from RECIPIENTS_JSON secret.")
                return data
            print("[Warning] RECIPIENTS_JSON environment variable is empty or not a list.")
        except Exception as e:
            print(f"[Warning] Failed to parse RECIPIENTS_JSON environment variable: {e}. Falling back to file.")

    # 2. Check recipients.json file
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    print(f"[Recipients] Loaded {len(data)} recipient(s) from '{os.path.basename(filepath)}'.")
                    return data
        except Exception as e:
            print(f"[Warning] Failed to read recipients file '{filepath}': {e}.")

    # 3. Fallback default recipient using config.py
    default_email = notifier.get_sender_email() or "subscriber@example.com"
    print(f"[Recipients] Using fallback default recipient ({default_email}).")
    return [
        {
            "name": "Friend",
            "email": default_email,
            "active": True,
            "keywords": config.KEYWORDS,
            "job_searches": config.JOB_SEARCHES,
            "course_feeds": config.COURSE_FEEDS,
            "max_items": config.MAX_ITEMS,
        }
    ]


# ============================================================================
# Seen Items Management & Feature 1: Auto-Pruning
# ============================================================================

def load_seen_dict(
    filepath: str = SEEN_FILE,
    primary_email: str = None,
    expiry_days: int = None,
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    Load seen history mapped by recipient email: {email: {link: metadata_dict}}.
    Automatically prunes entries older than expiry_days (default config.SEEN_EXPIRY_DAYS).
    Seamlessly migrates legacy flat list formats and sets.
    """
    if expiry_days is None:
        expiry_days = getattr(config, "SEEN_EXPIRY_DAYS", 60)

    today = datetime.now(timezone.utc).date()
    cutoff_date = today - timedelta(days=expiry_days)
    today_str = today.isoformat()

    if not os.path.exists(filepath):
        return {}

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_dict: Dict[str, Dict[str, Dict[str, Any]]] = {}

        # 1. Legacy format: flat list of links
        if isinstance(data, list):
            fallback_key = primary_email or notifier.get_sender_email() or "default"
            raw_dict = {
                fallback_key: {
                    url: {"date": today_str}
                    for url in data
                    if isinstance(url, str)
                }
            }
        # 2. Dict format: email -> list of links OR email -> dict of links
        elif isinstance(data, dict):
            for email, links in data.items():
                if isinstance(links, list):
                    raw_dict[email] = {
                        url: {"date": today_str}
                        for url in links
                        if isinstance(url, str)
                    }
                elif isinstance(links, dict):
                    email_links: Dict[str, Dict[str, Any]] = {}
                    for url, meta in links.items():
                        if isinstance(meta, str):
                            email_links[url] = {"date": meta}
                        elif isinstance(meta, dict):
                            email_links[url] = meta
                        else:
                            email_links[url] = {"date": today_str}
                    raw_dict[email] = email_links

        # Prune entries older than cutoff_date
        pruned_dict: Dict[str, Dict[str, Dict[str, Any]]] = {}
        pruned_count = 0

        for email, links in raw_dict.items():
            valid_links: Dict[str, Dict[str, Any]] = {}
            for url, meta in links.items():
                date_str = meta.get("date") if isinstance(meta, dict) else None
                is_expired = False
                if date_str:
                    try:
                        item_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                        if item_date < cutoff_date:
                            is_expired = True
                    except Exception:
                        pass
                if is_expired:
                    pruned_count += 1
                else:
                    valid_links[url] = meta if isinstance(meta, dict) else {"date": today_str}
            pruned_dict[email] = valid_links

        if pruned_count > 0:
            print(f"[Auto-Prune] Pruned {pruned_count} seen item(s) older than {expiry_days} days.")

        return pruned_dict
    except Exception as e:
        print(f"[Warning] Could not read seen file '{filepath}': {e}. Starting fresh.")
        return {}


def save_seen_dict(seen_dict: Dict[str, Any], filepath: str = SEEN_FILE) -> None:
    """Save the per-recipient seen history dictionary back to seen.json."""
    try:
        serializable: Dict[str, Any] = {}
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        for email, links in seen_dict.items():
            if isinstance(links, (set, list)):
                serializable[email] = {
                    url: {"date": today_str}
                    for url in sorted(list(links))
                }
            elif isinstance(links, dict):
                # Sort URLs alphabetically for clean git diffs
                serializable[email] = {
                    url: links[url]
                    for url in sorted(links.keys())
                }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except Exception as e:
        print(f"[Error] Failed to write seen file '{filepath}': {e}")


def load_seen(filepath: str = SEEN_FILE) -> Set[str]:
    """
    Backward-compatible helper returning a flattened set of all seen links.
    """
    seen_dict = load_seen_dict(filepath)
    all_links = set()
    for links in seen_dict.values():
        all_links.update(links.keys())
    return all_links


def save_seen(seen_data, filepath: str = SEEN_FILE) -> None:
    """
    Backward-compatible save helper supporting both set/list (flat) and dict (per-person).
    """
    if isinstance(seen_data, dict):
        save_seen_dict(seen_data, filepath)
    else:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(sorted(list(seen_data)), f, indent=2, ensure_ascii=False)
                f.write("\n")
        except Exception as e:
            print(f"[Error] Failed to write seen file '{filepath}': {e}")


# ============================================================================
# Keyword Matching & Formatting
# ============================================================================

def matches_keywords(title: str, keywords: List[str]) -> bool:
    """
    Check if the title contains at least one keyword (case-insensitive).
    Uses word boundaries so that short keywords like 'ai' do not falsely match 'painting' or 'email'.
    """
    if not title or not keywords:
        return False
    for keyword in keywords:
        kw = keyword.strip()
        if not kw:
            continue
        # Use regex word boundary for accurate matching
        pattern = rf"\b{re.escape(kw)}\b"
        if re.search(pattern, title, re.IGNORECASE):
            return True
    return False


def format_item(item: Dict[str, Any]) -> str:
    """
    Format a single course or job item into emoji + title + badges + link.
    Courses: 🎓 Title + Link
    Jobs: 💼 Title (Company) [Board] + 📍 Location | 💰 Salary | ⏱️ Type + Link
    """
    if item.get("type") == "course":
        title = item.get("title", "")
        link = item.get("link", "")
        return f"🎓 {title}\n{link}"

    # Job formatting with badges
    title = item.get("title", "")
    link = item.get("link", "")
    source = item.get("source", "")
    location = (item.get("location") or "").strip()
    salary = (item.get("salary") or "").strip()
    job_type = (item.get("job_type") or "").strip()
    tags = item.get("tags") or []

    badges = []
    if location:
        badges.append(f"📍 {location}")
    if salary:
        badges.append(f"💰 {salary}")
    if job_type:
        badges.append(f"⏱️ {job_type}")

    # Check for visa sponsorship / worldwide openness
    tags_str = " ".join(tags).lower() if isinstance(tags, list) else str(tags).lower()
    loc_lower = location.lower()
    if "visa" in tags_str or "sponsorship" in tags_str or "visa" in loc_lower:
        badges.append("🛂 Visa Sponsored")
    elif "worldwide" in loc_lower or "anywhere" in loc_lower:
        badges.append("🌍 Open Worldwide")

    badge_line = " | ".join(badges)
    source_tag = f" [{source}]" if source else ""

    if badge_line:
        return f"💼 {title}{source_tag}\n   {badge_line}\n{link}"
    return f"💼 {title}{source_tag}\n{link}"


def format_message(items: List[Dict[str, Any]]) -> str:
    """Format multiple items into a single readable message block."""
    return "\n\n".join(format_item(item) for item in items)


def matches_location_filter(location: str, preferred_locations: List[str]) -> bool:
    """
    Check if a job's location matches any preferred location keyword.
    If location is unknown or empty, allow it through to avoid false negatives.
    """
    if not location or not preferred_locations:
        return True
    loc_lower = location.lower()
    return any(p.strip().lower() in loc_lower for p in preferred_locations if p.strip())


def compose_digest_subject(
    name: str = "",
    courses_count: int = 0,
    jobs_count: int = 0,
    date_label: Optional[str] = None,
    weekly: bool = False,
) -> str:
    """
    Generate an engaging, personalized email subject with exact item counts, recipient name, and date.
    Examples:
    - 🎓 4 Free Courses, 💼 6 Remote Jobs for Ishani (Nov 02)
    - 🎓 5 Free Courses for Ishita (Nov 02)
    - 💼 10 Remote Jobs for Saurabh (Nov 02)
    - 📅 Weekly Wrap: 🎓 4 Courses, 💼 6 Jobs for Ojasvi (Nov 02)
    """
    if not date_label:
        date_label = datetime.now(timezone.utc).strftime("%b %d")

    first_name = name.strip().split()[0] if name and name.strip() else ""
    target_label = f"for {first_name}" if first_name else "for you"

    parts = []
    if courses_count > 0:
        parts.append(f"🎓 {courses_count} Free Course{'s' if courses_count != 1 else ''}")
    if jobs_count > 0:
        parts.append(f"💼 {jobs_count} Remote Job{'s' if jobs_count != 1 else ''}")

    prefix = "📅 Weekly Wrap: " if weekly else ""

    if parts:
        summary = ", ".join(parts)
        return f"{prefix}{summary} {target_label} ({date_label})"

    fallback_title = "Weekly Wrap" if weekly else "Daily Digest"
    return f"{prefix}{fallback_title}: Free Courses & Remote Jobs {target_label} ({date_label})"


# ============================================================================
# Gamification System: Streak, Levels & Value Saved Counter
# ============================================================================

def calculate_hunter_stats(
    email: str,
    seen_dict: Dict[str, Any],
    current_items: Optional[List[Dict[str, Any]]] = None,
    course_nominal_value: int = 20,
) -> Dict[str, Any]:
    """
    Calculate gamified stats for a subscriber:
    - streak: consecutive days of received digests (minimum 1 on delivery day)
    - total_courses: historical + current course count
    - total_jobs: historical + current job count
    - total_items: total opportunities unlocked
    - money_saved: total_courses * course_nominal_value ($20)
    - level_name: gamified title (e.g. 'Rookie Hunter', 'Opportunity Scout', etc.)
    - level_num: level integer (1 to 5)
    - badge: emoji badge for current level
    """
    user_key = (email or "").strip().lower()
    user_history = seen_dict.get(user_key, {}) if isinstance(seen_dict, dict) else {}

    historical_courses = 0
    historical_jobs = 0
    delivery_dates = set()

    course_domains = (
        "answersq.com",
        "tutorialbar.com",
        "discudemy.com",
        "freecodecamp.org",
        "udemyfreebies",
        "udemy.com",
        "coursera.org",
    )

    if isinstance(user_history, dict):
        for url, meta in user_history.items():
            if url == "__welcome_sent__":
                continue
            if isinstance(meta, dict):
                d = meta.get("date")
                if d and isinstance(d, str):
                    delivery_dates.add(d.strip())
                item_type = meta.get("type")
                if item_type == "course" or any(cd in url.lower() for cd in course_domains):
                    historical_courses += 1
                else:
                    historical_jobs += 1
            elif isinstance(meta, str):
                delivery_dates.add(meta.strip())
                if any(cd in url.lower() for cd in course_domains):
                    historical_courses += 1
                else:
                    historical_jobs += 1

    current_courses = sum(1 for item in (current_items or []) if item.get("type") == "course")
    current_jobs = sum(1 for item in (current_items or []) if item.get("type") == "job")
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if current_items:
        delivery_dates.add(today_str)

    total_courses = historical_courses + current_courses
    total_jobs = historical_jobs + current_jobs
    total_items = total_courses + total_jobs
    money_saved = total_courses * course_nominal_value

    # Parse and sort distinct dates descending
    sorted_dates = []
    for d_str in delivery_dates:
        try:
            sorted_dates.append(datetime.strptime(d_str, "%Y-%m-%d").date())
        except Exception:
            pass
    sorted_dates = sorted(set(sorted_dates), reverse=True)

    today_date = datetime.now(timezone.utc).date()
    yesterday_date = today_date - timedelta(days=1)

    streak = 0
    if sorted_dates:
        start_date = None
        if sorted_dates[0] == today_date:
            start_date = today_date
        elif sorted_dates[0] == yesterday_date:
            start_date = yesterday_date

        if start_date:
            expected = start_date
            for d in sorted_dates:
                if d == expected:
                    streak += 1
                    expected = expected - timedelta(days=1)
                elif d > expected:
                    continue
                else:
                    break

    # If current items exist and streak is 0, start at 1
    if current_items and streak == 0:
        streak = 1

    # Gamified Level Progression
    if total_items <= 5:
        level_num = 1
        level_title = "Rookie Hunter"
        badge = "🌱"
    elif total_items <= 15:
        level_num = 2
        level_title = "Opportunity Scout"
        badge = "⚡"
    elif total_items <= 30:
        level_num = 3
        level_title = "Career Sniper"
        badge = "🎯"
    elif total_items <= 60:
        level_num = 4
        level_title = "Pro Opportunity Hunter"
        badge = "🔥"
    else:
        level_num = 5
        level_title = "Master Career Strategist"
        badge = "👑"

    return {
        "streak": max(1, streak) if (current_items or historical_courses > 0 or historical_jobs > 0) else 0,
        "total_courses": total_courses,
        "total_jobs": total_jobs,
        "total_items": total_items,
        "money_saved": money_saved,
        "level_num": level_num,
        "level_title": level_title,
        "badge": badge,
    }


def format_hunter_stats_banner(stats: Dict[str, Any]) -> str:
    """
    Format the gamified stats block for email digests.
    Example:
    🏆 Your Hunter Stats:
    🔥 Day 3 Streak | ⚡ Level 2: Opportunity Scout
    💰 Value Unlocked: $140 saved across 7 free certified courses!
    """
    streak = stats.get("streak", 1)
    level_num = stats.get("level_num", 1)
    level_title = stats.get("level_title", "Rookie Hunter")
    badge = stats.get("badge", "🌱")
    money_saved = stats.get("money_saved", 0)
    total_courses = stats.get("total_courses", 0)

    course_label = f"{total_courses} free certified course{'s' if total_courses != 1 else ''}"

    lines = [
        "🏆 Your Hunter Stats:",
        f"🔥 Day {streak} Streak | {badge} Level {level_num}: {level_title}",
        f"💰 Value Unlocked: ${money_saved} saved across {course_label}!",
    ]
    return "\n".join(lines) + "\n\n"



# ============================================================================
# Welcome Email System for Newly Added Friends
# ============================================================================

def compose_welcome_message(
    name: str,
    email: str,
    keywords: List[str],
    job_searches: List[str],
    max_items: int,
) -> str:
    """Compose a warm, clean introductory welcome email for a new friend."""
    sender_email = notifier.get_sender_email() or "ojasvimittalofficial@gmail.com"
    kw_str = ", ".join(keywords) if keywords else "All curated courses"
    js_str = ", ".join(job_searches) if job_searches else "All remote opportunities"

    return f"""Hi {name},

🎉 Welcome to Course & Job Hunter!

You are all set to receive your personalized daily morning digest of 100% free online courses, certification coupons, and remote job openings.

Here is a summary of your subscription:
• 🎯 Your Keywords      : {kw_str}
• 💼 Your Job Searches  : {js_str}
• 📦 Max Items Daily    : {max_items} opportunities
• ⏰ Delivery Schedule  : Every morning (~8:00 AM IST)

How it works:
1. Every morning, we scan top learning platforms (freeCodeCamp, Discudemy, AnswersQ, Reddit) and verified remote job boards (Remotive, Jobicy, Arbeitnow).
2. We match opportunities against your specific keywords.
3. We track what you've received so you never see the same course or job twice.
4. If there's nothing new on a given day, we keep your inbox quiet.

Your daily digests will start arriving with the morning runs!

Want changes to your keywords, search terms, or want to pause these emails?
Simply reply directly to this email ({sender_email}) anytime.

Cheers,
Course & Job Hunter 🎓💼"""


def extract_domain_from_url(url: str) -> str:
    """Extract a friendly clean domain name from a URL."""
    try:
        netloc = urllib.parse.urlparse(url).netloc
        netloc = netloc.replace("www.", "")
        return netloc or "Opportunity"
    except Exception:
        return "Opportunity"


def build_html_digest(
    recipient_name: str,
    recipient_email: str,
    items: List[Dict[str, Any]],
    stats: Dict[str, Any],
    insights: Optional[str] = None,
    sender_email: str = "",
    portal_url: str = "",
) -> str:
    """
    Build a modern, highly attractive, mobile-responsive HTML email digest.
    Includes branded header, gamified metrics bar, distinct courses & jobs cards,
    badges for salary/location/visa, Sunday market insights, and member hub CTA.
    """
    first_name = (recipient_name or "").strip().split()[0] if recipient_name else "Friend"
    safe_name = html.escape(first_name)
    today_label = datetime.now(timezone.utc).strftime("%B %d, %Y")
    reply_email = sender_email or notifier.get_sender_email() or "ojasvimittalofficial@gmail.com"
    hub_url = portal_url or os.environ.get("PORTAL_BASE_URL") or "http://localhost:8000/portal"
    
    # 1-Click Secure Magic Login Link (Zero Password Friction, Maximum Member Security)
    portal_secret = (os.environ.get("PORTAL_SECRET_KEY") or "hunter_portal_secret_2026").strip()
    encoded_email = urllib.parse.quote(recipient_email)
    magic_sig = hmac.new(portal_secret.encode("utf-8"), f"magic:{recipient_email.strip().lower()}".encode("utf-8"), hashlib.sha256).hexdigest()[:24]
    sep = "&" if "?" in hub_url else "?"
    hub_magic_url = f"{hub_url}{sep}email={encoded_email}&magic={magic_sig}"

    courses = [it for it in items if it.get("type") == "course"]
    jobs = [it for it in items if it.get("type") == "job"]

    streak = stats.get("streak", 1)
    level_num = stats.get("level_num", 1)
    level_title = stats.get("level_title", "Rookie Hunter")
    badge = stats.get("badge", "🌱")
    money_saved = stats.get("money_saved", 0)

    # 1. Course Cards HTML
    course_cards_html = ""
    if courses:
        cards = []
        for c in courses:
            c_title = html.escape(c.get("title", "Untitled Course"))
            c_link = html.escape(c.get("link", "#"))
            domain = html.escape(extract_domain_from_url(c.get("link", "")))
            card = f"""
            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #ffffff; border: 1px solid #e2e8f0; border-left: 4px solid #10b981; border-radius: 10px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
              <tr>
                <td style="padding: 14px 16px;">
                  <div style="margin-bottom: 6px;">
                    <span style="display: inline-block; background-color: #ecfdf5; color: #047857; font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; padding: 2px 7px; border-radius: 4px; border: 1px solid #a7f3d0; margin-right: 6px;">100% FREE</span>
                    <span style="font-size: 11px; color: #64748b; font-weight: 600;">{domain}</span>
                  </div>
                  <div style="font-size: 14px; font-weight: 600; color: #0f172a; line-height: 1.4; margin-bottom: 10px;">
                    {c_title}
                  </div>
                  <a href="{c_link}" target="_blank" style="display: inline-block; background-color: #059669; color: #ffffff; font-size: 12px; font-weight: 600; text-decoration: none; padding: 6px 14px; border-radius: 6px;">
                    Enroll Free ↗
                  </a>
                </td>
              </tr>
            </table>
            """
            cards.append(card)
        course_cards_html = f"""
        <div style="margin-top: 10px; margin-bottom: 24px;">
          <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 12px;">
            <tr>
              <td align="left">
                <span style="font-size: 15px; font-weight: 700; color: #065f46;">🎓 Free Courses &amp; Certifications</span>
              </td>
              <td align="right">
                <span style="background-color: #d1fae5; color: #065f46; font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 12px;">{len(courses)} available</span>
              </td>
            </tr>
          </table>
          {''.join(cards)}
        </div>
        """

    # 2. Job Cards HTML
    job_cards_html = ""
    if jobs:
        cards = []
        for j in jobs:
            j_title = html.escape(j.get("title", "Untitled Job"))
            j_link = html.escape(j.get("link", "#"))
            source_raw = j.get("source") or extract_domain_from_url(j.get("link", ""))
            source = html.escape(str(source_raw).replace("_", " ").title())
            location = (j.get("location") or "").strip()
            salary = (j.get("salary") or "").strip()
            job_type = (j.get("job_type") or "").strip()
            tags = j.get("tags") or []
            tags_str = " ".join(tags).lower() if isinstance(tags, list) else str(tags).lower()
            loc_lower = location.lower()

            meta_pills = []
            if location:
                meta_pills.append(f"""<span style="display: inline-block; background-color: #f8fafc; border: 1px solid #e2e8f0; color: #334155; font-size: 11px; padding: 2px 7px; border-radius: 4px; margin-right: 4px; margin-bottom: 4px;">📍 {html.escape(location)}</span>""")
            if salary:
                meta_pills.append(f"""<span style="display: inline-block; background-color: #ecfdf5; border: 1px solid #a7f3d0; color: #047857; font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: 4px; margin-right: 4px; margin-bottom: 4px;">💰 {html.escape(salary)}</span>""")
            if job_type:
                meta_pills.append(f"""<span style="display: inline-block; background-color: #f8fafc; border: 1px solid #e2e8f0; color: #334155; font-size: 11px; padding: 2px 7px; border-radius: 4px; margin-right: 4px; margin-bottom: 4px;">⏱️ {html.escape(job_type.replace('_', ' ').title())}</span>""")
            if "visa" in tags_str or "sponsorship" in tags_str or "visa" in loc_lower:
                meta_pills.append("""<span style="display: inline-block; background-color: #fef3c7; border: 1px solid #fde68a; color: #92400e; font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: 4px; margin-right: 4px; margin-bottom: 4px;">🛂 Visa Sponsored</span>""")
            elif "worldwide" in loc_lower or "anywhere" in loc_lower:
                meta_pills.append("""<span style="display: inline-block; background-color: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: 4px; margin-right: 4px; margin-bottom: 4px;">🌍 Open Worldwide</span>""")

            pills_html = "".join(meta_pills)
            card = f"""
            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #ffffff; border: 1px solid #e2e8f0; border-left: 4px solid #3b82f6; border-radius: 10px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
              <tr>
                <td style="padding: 14px 16px;">
                  <div style="margin-bottom: 6px;">
                    <span style="display: inline-block; background-color: #eff6ff; color: #1d4ed8; font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; padding: 2px 7px; border-radius: 4px; border: 1px solid #bfdbfe; margin-right: 6px;">{source}</span>
                    <span style="display: inline-block; background-color: #f1f5f9; color: #475569; font-size: 10px; font-weight: 700; text-transform: uppercase; padding: 2px 7px; border-radius: 4px;">Remote</span>
                  </div>
                  <div style="font-size: 14px; font-weight: 600; color: #0f172a; line-height: 1.4; margin-bottom: 8px;">
                    {j_title}
                  </div>
                  {f'<div style="margin-bottom: 10px;">{pills_html}</div>' if pills_html else ''}
                  <a href="{j_link}" target="_blank" style="display: inline-block; background-color: #2563eb; color: #ffffff; font-size: 12px; font-weight: 600; text-decoration: none; padding: 6px 14px; border-radius: 6px;">
                    View &amp; Apply ↗
                  </a>
                </td>
              </tr>
            </table>
            """
            cards.append(card)
        job_cards_html = f"""
        <div style="margin-top: 10px; margin-bottom: 24px;">
          <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 12px;">
            <tr>
              <td align="left">
                <span style="font-size: 15px; font-weight: 700; color: #1e40af;">💼 Remote &amp; India Job Openings</span>
              </td>
              <td align="right">
                <span style="background-color: #dbeafe; color: #1e40af; font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 12px;">{len(jobs)} available</span>
              </td>
            </tr>
          </table>
          {''.join(cards)}
        </div>
        """

    # 3. Weekly Insights HTML
    insights_html = ""
    if insights:
        safe_insights = html.escape(insights.strip())
        insights_html = f"""
        <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #fefce8; border: 1px solid #fef08a; border-radius: 12px; margin-bottom: 24px;">
          <tr>
            <td style="padding: 18px 20px;">
              <div style="font-size: 14px; font-weight: 700; color: #854d0e; margin-bottom: 8px;">
                📊 Weekly Market &amp; Tech Insights
              </div>
              <div style="font-size: 12px; color: #713f12; line-height: 1.6; white-space: pre-wrap; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">{safe_insights}</div>
            </td>
          </tr>
        </table>
        """

    # Empty fallback
    empty_html = ""
    if not courses and not jobs:
        empty_html = """
        <div style="text-align: center; padding: 32px 16px; color: #64748b; font-size: 13px;">
          <div style="font-size: 28px; margin-bottom: 8px;">🎯</div>
          No new matches found today. Your radar is active and watching for fresh drops!
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Course &amp; Job Hunter Daily Digest</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;">
  <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f1f5f9; padding: 24px 10px;">
    <tr>
      <td align="center">
        <!-- Main Card Container -->
        <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; background-color: #ffffff; border-radius: 16px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 14px rgba(0,0,0,0.05);">
          
          <!-- Brand Header -->
          <tr>
            <td style="background-color: #0f172a; padding: 32px 24px 24px 24px;">
              <table border="0" cellpadding="0" cellspacing="0" width="100%">
                <tr>
                  <td align="left">
                    <span style="display: inline-block; padding: 3px 10px; background-color: rgba(59,130,246,0.15); border: 1px solid rgba(59,130,246,0.3); border-radius: 20px; font-size: 11px; font-weight: 700; color: #60a5fa; letter-spacing: 0.5px; text-transform: uppercase;">
                      Course &amp; Job Hunter 🎯
                    </span>
                  </td>
                  <td align="right">
                    <span style="font-size: 11px; color: #94a3b8; font-weight: 500;">{today_label}</span>
                  </td>
                </tr>
              </table>

              <h1 style="margin: 14px 0 4px 0; font-size: 22px; font-weight: 700; color: #ffffff; line-height: 1.3;">
                Good morning, {safe_name} 👋
              </h1>
              <p style="margin: 0; font-size: 13px; color: #94a3b8; line-height: 1.5;">
                Here are your fresh matches for free certified courses &amp; remote job openings.
              </p>

              <!-- Gamification Metrics Strip -->
              <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #1e293b; border-radius: 12px; margin-top: 18px; border: 1px solid #334155;">
                <tr>
                  <td width="33%" align="center" style="padding: 10px 6px; border-right: 1px solid #334155;">
                    <div style="font-size: 10px; text-transform: uppercase; color: #94a3b8; font-weight: 700; letter-spacing: 0.5px;">Streak</div>
                    <div style="font-size: 14px; font-weight: 700; color: #f59e0b; margin-top: 2px;">🔥 Day {streak}</div>
                  </td>
                  <td width="34%" align="center" style="padding: 10px 6px; border-right: 1px solid #334155;">
                    <div style="font-size: 10px; text-transform: uppercase; color: #94a3b8; font-weight: 700; letter-spacing: 0.5px;">Level {level_num}</div>
                    <div style="font-size: 13px; font-weight: 700; color: #60a5fa; margin-top: 2px; white-space: nowrap;">{badge} {html.escape(level_title)}</div>
                  </td>
                  <td width="33%" align="center" style="padding: 10px 6px;">
                    <div style="font-size: 10px; text-transform: uppercase; color: #94a3b8; font-weight: 700; letter-spacing: 0.5px;">Saved</div>
                    <div style="font-size: 14px; font-weight: 700; color: #10b981; margin-top: 2px;">${money_saved}</div>
                  </td>
                </tr>
              </table>

            </td>
          </tr>

          <!-- Digest Content Area -->
          <tr>
            <td style="padding: 24px 24px 16px 24px;">
              {insights_html}
              {course_cards_html}
              {job_cards_html}
              {empty_html}

              <!-- Opportunity Vault Callout -->
              <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #0f172a; border-radius: 12px; margin-top: 8px; text-align: center;">
                <tr>
                  <td style="padding: 20px 20px;">
                    <div style="font-size: 14px; font-weight: 700; color: #ffffff; margin-bottom: 4px;">
                      📂 Your Member Opportunity Vault
                    </div>
                    <div style="font-size: 12px; color: #94a3b8; line-height: 1.5; margin-bottom: 12px;">
                      Search every opportunity found for you, manage topics, or update preferences.
                    </div>
                    <a href="{hub_magic_url}" target="_blank" style="display: inline-block; background-color: #4f46e5; color: #ffffff; font-size: 12px; font-weight: 700; text-decoration: none; padding: 9px 22px; border-radius: 8px; box-shadow: 0 2px 8px rgba(79,70,229,0.35);">
                      Open Vault (1-Click Magic Login) ↗
                    </a>
                  </td>
                </tr>
              </table>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 20px 24px; text-align: center;">
              <div style="font-size: 11px; color: #64748b; line-height: 1.6;">
                Tailored for <strong>{html.escape(recipient_email)}</strong> · Delivered daily at ~8:00 AM IST<br/>
                Want to tweak your keywords or pause digests? Reply directly to <strong>{html.escape(reply_email)}</strong> anytime.
              </div>
              <div style="font-size: 11px; color: #94a3b8; margin-top: 8px; font-weight: 500;">
                Course &amp; Job Hunter 🎯 · Curated for the team
              </div>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def build_html_welcome(
    name: str,
    email: str,
    keywords: List[str],
    job_searches: List[str],
    max_items: int,
    sender_email: str = "",
    portal_url: str = "",
) -> str:
    """
    Build a warm, highly attractive HTML welcome email for new friends joining the radar.
    """
    first_name = (name or "").strip().split()[0] if name else "Friend"
    safe_name = html.escape(first_name)
    reply_email = sender_email or notifier.get_sender_email() or "ojasvimittalofficial@gmail.com"
    hub_url = portal_url or os.environ.get("PORTAL_BASE_URL") or "http://localhost:8000/portal"

    kw_pills = " ".join(
        f"""<span style="display: inline-block; background: #ecfdf5; border: 1px solid #a7f3d0; color: #047857; font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: 4px; margin: 2px;">{html.escape(k)}</span>"""
        for k in (keywords or ["All curated courses"])
    )
    js_pills = " ".join(
        f"""<span style="display: inline-block; background: #eff6ff; border: 1px solid #bfdbfe; color: #1d4ed8; font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: 4px; margin: 2px;">{html.escape(j)}</span>"""
        for j in (job_searches or ["All remote openings"])
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Welcome to Course &amp; Job Hunter</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;">
  <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f1f5f9; padding: 24px 10px;">
    <tr>
      <td align="center">
        <!-- Main Card -->
        <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; background-color: #ffffff; border-radius: 16px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 14px rgba(0,0,0,0.05);">
          
          <!-- Header -->
          <tr>
            <td style="background-color: #0f172a; padding: 36px 28px; text-align: center;">
              <span style="display: inline-block; padding: 3px 12px; background-color: rgba(59,130,246,0.15); border: 1px solid rgba(59,130,246,0.3); border-radius: 20px; font-size: 11px; font-weight: 700; color: #60a5fa; letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 12px;">
                Course &amp; Job Hunter 🎯
              </span>
              <h1 style="margin: 0; font-size: 24px; font-weight: 700; color: #ffffff; line-height: 1.3;">
                Welcome, {safe_name}! 🎉
              </h1>
              <p style="margin: 8px 0 0 0; font-size: 13px; color: #94a3b8;">
                Your automated career radar is officially active.
              </p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding: 28px 24px;">
              <p style="font-size: 14px; color: #334155; line-height: 1.6; margin: 0 0 18px 0;">
                You are all set to receive your personalized morning digest of <strong>100% free certified online courses</strong> and <strong>verified remote job openings</strong> (India &amp; Global).
              </p>

              <!-- Profile summary -->
              <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; margin-bottom: 22px;">
                <tr>
                  <td style="padding: 16px 18px;">
                    <div style="font-size: 12px; font-weight: 700; color: #0f172a; margin-bottom: 10px;">📋 Your Custom Profile</div>
                    <div style="font-size: 12px; color: #334155; line-height: 1.8;">
                      <div style="margin-bottom: 6px;"><strong>🎯 Course Keywords:</strong><br/>{kw_pills}</div>
                      <div style="margin-bottom: 6px;"><strong>💼 Job Searches:</strong><br/>{js_pills}</div>
                      <div><strong>📦 Max Delivery:</strong> {max_items} opportunities / morning</div>
                      <div><strong>⏰ Schedule:</strong> Daily at ~8:00 AM IST</div>
                    </div>
                  </td>
                </tr>
              </table>

              <!-- How It Works -->
              <div style="font-size: 13px; font-weight: 700; color: #0f172a; margin-bottom: 12px;">⚡ How It Works</div>
              <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 20px;">
                <tr>
                  <td style="padding: 8px 0; font-size: 13px; color: #475569; line-height: 1.5;">
                    <strong style="color: #0f172a;">1. Multi-Platform Scan:</strong> Every morning we check Udemy 100% OFF coupons, Swayam/NPTEL, freeCodeCamp, LinkedIn, Indeed India, Remotive, and more.
                  </td>
                </tr>
                <tr>
                  <td style="padding: 8px 0; font-size: 13px; color: #475569; line-height: 1.5;">
                    <strong style="color: #0f172a;">2. Keyword Match:</strong> We only surface items matching your specific skills and target roles.
                  </td>
                </tr>
                <tr>
                  <td style="padding: 8px 0; font-size: 13px; color: #475569; line-height: 1.5;">
                    <strong style="color: #0f172a;">3. Zero Duplicates:</strong> Every link you receive is remembered so you never see the same course or job twice.
                  </td>
                </tr>
                <tr>
                  <td style="padding: 8px 0; font-size: 13px; color: #475569; line-height: 1.5;">
                    <strong style="color: #0f172a;">4. Inbox Zero:</strong> If there's nothing high-quality matching on a given day, we keep your inbox quiet.
                  </td>
                </tr>
              </table>

              <!-- Button -->
              <table border="0" cellpadding="0" cellspacing="0" width="100%" style="text-align: center; margin-top: 10px;">
                <tr>
                  <td align="center">
                    <a href="{hub_url}" target="_blank" style="display: inline-block; background-color: #2563eb; color: #ffffff; font-size: 13px; font-weight: 600; text-decoration: none; padding: 10px 22px; border-radius: 8px;">
                      Explore Your Member Vault ↗
                    </a>
                  </td>
                </tr>
              </table>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 20px 24px; text-align: center;">
              <div style="font-size: 11px; color: #64748b; line-height: 1.6;">
                Welcome aboard! Want to update your keywords or pause digests anytime? Simply reply to <strong>{html.escape(reply_email)}</strong>.
              </div>
              <div style="font-size: 11px; color: #94a3b8; margin-top: 8px; font-weight: 500;">
                Course &amp; Job Hunter 🎓💼
              </div>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def is_welcome_sent(recipient: Dict[str, Any], seen_dict: Dict[str, Any]) -> bool:
    """
    Check if a welcome email has already been sent to this recipient.
    - True if recipient has welcome_sent=True.
    - True if seen_dict contains '__welcome_sent__' marker.
    - True if recipient already has historical records in seen.json (prevents spamming established subscribers).
    - False for newly added friends with no prior history.
    """
    if recipient.get("welcome_sent") is True:
        return True

    email = (recipient.get("email") or "").strip().lower()
    if not email:
        return True

    user_seen = seen_dict.get(email)
    if isinstance(user_seen, dict):
        if "__welcome_sent__" in user_seen:
            return True
        # If user already has historical records in seen.json, they are an established subscriber
        real_links_count = sum(1 for k in user_seen.keys() if not k.startswith("__"))
        if real_links_count >= 3:
            user_seen["__welcome_sent__"] = {
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "auto_migrated": True,
            }
            return True

    return False


def mark_welcome_sent(
    recipient: Dict[str, Any],
    seen_dict: Dict[str, Any],
    recipients_file: str = RECIPIENTS_FILE,
) -> None:
    """Mark welcome email as sent in memory, in seen_dict, and in recipients.json if writable."""
    email = (recipient.get("email") or "").strip().lower()
    recipient["welcome_sent"] = True

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if email not in seen_dict or not isinstance(seen_dict[email], dict):
        seen_dict[email] = {}

    seen_dict[email]["__welcome_sent__"] = {
        "date": today_str,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }

    # Also persist to recipients.json if file exists and contains this email
    if os.path.exists(recipients_file):
        try:
            with open(recipients_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                updated = False
                for r in data:
                    if r.get("email", "").strip().lower() == email:
                        r["welcome_sent"] = True
                        updated = True
                if updated:
                    with open(recipients_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                        f.write("\n")
        except Exception as e:
            print(f"[Warning] Could not update welcome_sent in '{recipients_file}': {e}")


# ============================================================================
# Feature 2: Weekly Market & Skills Insights
# ============================================================================

def generate_weekly_insights(seen_dict: Dict[str, Any], days: int = 7) -> str:
    """
    Analyze opportunities tracked in seen_dict over the past `days` (default 7)
    and compile a market trends report (skills in demand, top hiring companies).
    """
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=days)
    recent_items: Dict[str, Dict[str, Any]] = {}

    for email, items in seen_dict.items():
        if isinstance(items, dict):
            for url, meta in items.items():
                if isinstance(meta, dict):
                    date_str = meta.get("date")
                    if date_str:
                        try:
                            d = datetime.strptime(date_str, "%Y-%m-%d").date()
                            if d >= cutoff:
                                recent_items[url] = meta
                        except Exception:
                            pass

    total_jobs = 0
    total_courses = 0
    skills_counter = Counter()
    company_counter = Counter()

    # Broad catalog of skills/tools to recognize across job titles and tags
    recognized_skills = [
        "python", "automation", "project management", "cybersecurity",
        "compliance", "regulatory", "excel", "ai", "machine learning",
        "docker", "kubernetes", "aws", "cloud", "react", "sql", "devops",
        "linux", "api", "security", "data", "scrum", "agile", "golang",
        "javascript", "typescript", "power bi", "tableau",
    ]

    for url, meta in recent_items.items():
        item_type = meta.get("type", "job")
        if item_type == "course":
            total_courses += 1
            continue

        total_jobs += 1
        company = meta.get("company")
        if company and company.strip():
            company_counter[company.strip()] += 1

        # Tally tags
        tags = meta.get("tags") or []
        for tag in tags:
            tag_clean = str(tag).strip().title()
            if len(tag_clean) > 1 and not tag_clean.isdigit():
                skills_counter[tag_clean] += 1

        # Scan title for recognized skills
        title_lower = (meta.get("title") or "").lower()
        for skill in recognized_skills:
            if re.search(rf"\b{re.escape(skill)}\b", title_lower, re.IGNORECASE):
                skills_counter[skill.title()] += 1

    start_date = cutoff.strftime("%b %d")
    end_date = datetime.now(timezone.utc).strftime("%b %d, %Y")

    report_lines = [
        "📊 WEEKLY TECH & JOB MARKET INSIGHTS",
        f"📅 Past {days} Days ({start_date} – {end_date})",
        "=" * 55,
        "🎯 Opportunities Tracked:",
        f"   • {total_jobs} Remote Job(s)",
        f"   • {total_courses} Free Certification Course(s)",
        "",
    ]

    if skills_counter:
        report_lines.append("🔥 Top In-Demand Skills This Week:")
        for rank, (skill, count) in enumerate(skills_counter.most_common(5), 1):
            pct = int((count / max(total_jobs, 1)) * 100) if total_jobs > 0 else 0
            pct_str = f" ({pct}% of jobs)" if pct > 0 else ""
            report_lines.append(f"   {rank}. {skill}: {count} mention(s){pct_str}")
        report_lines.append("")

    if company_counter:
        report_lines.append("🏢 Top Hiring Companies:")
        for comp, count in company_counter.most_common(3):
            roles_word = "role" if count == 1 else "roles"
            report_lines.append(f"   • {comp}: {count} {roles_word}")
        report_lines.append("")

    report_lines.append("💡 Tip: Review your keywords in config.py to catch newly trending skills!")
    report_lines.append("=" * 55)

    return "\n".join(report_lines)


# ============================================================================
# Single-Pass Source Fetching & Feature 3: Multi-Board Aggregation
# ============================================================================

def fetch_raw_courses(feeds: List[str]) -> List[Dict[str, str]]:
    """
    Fetch all items from the specified RSS feeds once without filtering.
    Tagged with origin feed_url.
    """
    raw_courses = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 "
            "CourseJobHunter/2.0"
        )
    }

    for feed_url in feeds:
        url = feed_url.strip()
        if not url:
            continue
        print(f"  [Feed] Checking course feed: {url}")
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            feed = feedparser.parse(response.content)

            feed_count = 0
            for entry in feed.entries:
                title = getattr(entry, "title", "").strip()
                link = getattr(entry, "link", "").strip()
                if not title or not link:
                    continue
                raw_courses.append({
                    "type": "course",
                    "title": title,
                    "link": link,
                    "feed_url": url,
                })
                feed_count += 1
            print(f"  [Feed] Found {feed_count} course(s) from {url}")
        except Exception as e:
            print(f"  [Warning] Skipping course feed '{url}' due to error: {e}")

    return raw_courses


def fetch_remotive_jobs(search_terms: List[str]) -> List[Dict[str, Any]]:
    """Fetch remote jobs from Remotive API for given search terms."""
    jobs_out = []
    headers = {"User-Agent": "CourseJobHunter/2.0"}

    for term in search_terms:
        clean_term = term.strip()
        if not clean_term:
            continue
        print(f"  [Remotive] Searching jobs for: '{clean_term}'")
        try:
            url = f"https://remotive.com/api/remote-jobs?search={clean_term}&limit=10"
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            jobs = data.get("jobs", [])

            for job in jobs:
                link = (job.get("url") or "").strip()
                if not link:
                    continue
                title = (job.get("title") or "").strip()
                company = (job.get("company_name") or "").strip()
                display_title = f"{title} ({company})" if company else title

                jobs_out.append({
                    "type": "job",
                    "source": "Remotive",
                    "title": display_title,
                    "company": company,
                    "link": link,
                    "salary": (job.get("salary") or "").strip(),
                    "location": (job.get("candidate_required_location") or "Worldwide").strip(),
                    "job_type": (job.get("job_type") or "").replace("_", " ").title(),
                    "tags": job.get("tags") or [],
                    "search_term": clean_term.lower(),
                })
        except Exception as e:
            print(f"  [Warning] Remotive search failed for '{clean_term}': {e}")

    return jobs_out


def fetch_jobicy_jobs(search_terms: List[str]) -> List[Dict[str, Any]]:
    """Fetch latest remote tech & business jobs from Jobicy API."""
    jobs_out = []
    headers = {"User-Agent": "CourseJobHunter/2.0"}
    print("  [Jobicy] Querying latest remote jobs...")

    try:
        url = "https://jobicy.com/api/v2/remote-jobs?count=25"
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        jobs = data.get("jobs", [])

        for job in jobs:
            link = (job.get("url") or "").strip()
            if not link:
                continue
            title = (job.get("jobTitle") or "").strip()
            company = (job.get("companyName") or "").strip()
            display_title = f"{title} ({company})" if company else title

            # Salary extraction
            min_sal = job.get("annualSalaryMin")
            max_sal = job.get("annualSalaryMax")
            currency = job.get("salaryCurrency") or "USD"
            salary_str = ""
            if min_sal and max_sal:
                salary_str = f"${int(min_sal):,}–${int(max_sal):,} {currency}"
            elif min_sal:
                salary_str = f"From ${int(min_sal):,} {currency}"

            # Location extraction
            location = (job.get("jobGeo") or "Anywhere (Remote)").strip()

            # Job Type
            job_types = job.get("jobType") or []
            job_type_str = ", ".join(job_types) if isinstance(job_types, list) else str(job_types)

            # Tags
            industries = job.get("jobIndustry") or []
            tags = industries if isinstance(industries, list) else [str(industries)]
            level = job.get("jobLevel")
            if level:
                tags.append(str(level))

            jobs_out.append({
                "type": "job",
                "source": "Jobicy",
                "title": display_title,
                "company": company,
                "link": link,
                "salary": salary_str,
                "location": location,
                "job_type": job_type_str,
                "tags": tags,
                "search_term": "jobicy",
            })
        print(f"  [Jobicy] Harvested {len(jobs_out)} job(s)")
    except Exception as e:
        print(f"  [Warning] Jobicy API query failed: {e}")

    return jobs_out


def fetch_arbeitnow_jobs(search_terms: List[str]) -> List[Dict[str, Any]]:
    """Fetch remote opportunities from Arbeitnow API."""
    jobs_out = []
    headers = {"User-Agent": "CourseJobHunter/2.0"}
    print("  [Arbeitnow] Querying remote jobs...")

    try:
        url = "https://www.arbeitnow.com/api/job-board-api"
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        jobs = data.get("data", [])

        for job in jobs:
            link = (job.get("url") or "").strip()
            if not link:
                continue
            title = (job.get("title") or "").strip()
            company = (job.get("company_name") or "").strip()
            display_title = f"{title} ({company})" if company else title

            is_remote = job.get("remote", False)
            location = (job.get("location") or ("Remote" if is_remote else "On-site")).strip()
            if is_remote and "remote" not in location.lower():
                location = f"Remote / {location}"

            jobs_out.append({
                "type": "job",
                "source": "Arbeitnow",
                "title": display_title,
                "company": company,
                "link": link,
                "salary": "",
                "location": location,
                "job_type": "Remote" if is_remote else "Full-time",
                "tags": job.get("tags") or [],
                "search_term": "arbeitnow",
            })
        print(f"  [Arbeitnow] Harvested {len(jobs_out)} job(s)")
    except Exception as e:
        print(f"  [Warning] Arbeitnow API query failed: {e}")

    return jobs_out


def fetch_adzuna_india_jobs(search_terms: List[str]) -> List[Dict[str, Any]]:
    """
    Fetch jobs from Adzuna India via their public RSS feed (no API key needed).
    Covers major Indian metro job listings across all industries.
    """
    jobs_out = []
    headers = {"User-Agent": "CourseJobHunter/2.0"}

    for term in search_terms:
        clean_term = term.strip()
        if not clean_term:
            continue
        # Adzuna India RSS – public, free, no auth required
        rss_url = (
            f"https://www.adzuna.in/search.rss"
            f"?q={requests.utils.quote(clean_term)}&country=in&max_days_old=7"
        )
        print(f"  [Adzuna India] Searching: '{clean_term}'")
        try:
            response = requests.get(rss_url, headers=headers, timeout=12)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            count = 0
            for entry in feed.entries:
                link = getattr(entry, "link", "").strip()
                title = getattr(entry, "title", "").strip()
                summary = getattr(entry, "summary", "")
                if not link or not title:
                    continue
                # Extract company from title if pattern "Title - Company" or summary
                company = ""
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    title = parts[0].strip()
                    company = parts[1].strip()
                display_title = f"{title} ({company})" if company else title
                jobs_out.append({
                    "type": "job",
                    "source": "Adzuna India",
                    "title": display_title,
                    "company": company,
                    "link": link,
                    "salary": "",
                    "location": "India",
                    "job_type": "Full-time",
                    "tags": [clean_term.lower()],
                    "search_term": clean_term.lower(),
                })
                count += 1
            print(f"  [Adzuna India] Harvested {count} job(s) for '{clean_term}'")
        except Exception as e:
            print(f"  [Warning] Adzuna India search failed for '{clean_term}': {e}")

    return jobs_out


def fetch_indeed_india_rss(search_terms: List[str]) -> List[Dict[str, Any]]:
    """
    Fetch jobs from Indeed India via their public RSS feed (no API key needed).
    Great for Indian market across tech, management, and business roles.
    """
    jobs_out = []
    headers = {"User-Agent": "CourseJobHunter/2.0"}

    for term in search_terms:
        clean_term = term.strip()
        if not clean_term:
            continue
        rss_url = (
            f"https://in.indeed.com/rss?q={requests.utils.quote(clean_term)}"
            f"&l=India&fromage=7&sort=date"
        )
        print(f"  [Indeed India] Searching: '{clean_term}'")
        try:
            response = requests.get(rss_url, headers=headers, timeout=12)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            count = 0
            for entry in feed.entries:
                link = getattr(entry, "link", "").strip()
                title = getattr(entry, "title", "").strip()
                if not link or not title:
                    continue
                company = ""
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    title = parts[0].strip()
                    company = parts[1].strip()
                display_title = f"{title} ({company})" if company else title
                jobs_out.append({
                    "type": "job",
                    "source": "Indeed India",
                    "title": display_title,
                    "company": company,
                    "link": link,
                    "salary": "",
                    "location": "India",
                    "job_type": "Full-time",
                    "tags": [clean_term.lower()],
                    "search_term": clean_term.lower(),
                })
                count += 1
            print(f"  [Indeed India] Harvested {count} job(s) for '{clean_term}'")
        except Exception as e:
            print(f"  [Warning] Indeed India search failed for '{clean_term}': {e}")

    return jobs_out


def fetch_linkedin_jobs_rss(search_terms: List[str]) -> List[Dict[str, Any]]:
    """
    Fetch LinkedIn Jobs via their public RSS/JSON feed (no authentication required).
    Uses LinkedIn's public job search API endpoint for worldwide + India results.
    """
    jobs_out = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }

    for term in search_terms:
        clean_term = term.strip()
        if not clean_term:
            continue
        # LinkedIn public job search endpoint (no key needed, rate-limited)
        api_url = (
            f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
            f"?keywords={requests.utils.quote(clean_term)}&location=India"
            f"&f_WT=2&start=0"  # f_WT=2 = Remote
        )
        print(f"  [LinkedIn] Searching remote/India jobs for: '{clean_term}'")
        try:
            response = requests.get(api_url, headers=headers, timeout=15)
            if response.status_code not in (200, 201):
                print(f"  [Warning] LinkedIn returned HTTP {response.status_code} for '{clean_term}'")
                continue
            # LinkedIn returns HTML cards, parse job IDs from href attributes
            import re as _re
            links_found = _re.findall(r'href=[\"\'](https://[a-z.]*linkedin\.com/jobs/view/[^\"\'?]+)', response.text)
            titles_found = _re.findall(r'<h3[^>]*class=[\"\'][^\"\']*base-search-card__title[^\"\']*[\"\'][^>]*>(.*?)</h3>', response.text, _re.DOTALL)
            companies_found = _re.findall(r'<h4[^>]*class=[\"\'][^\"\']*base-search-card__subtitle[^\"\']*[\"\'][^>]*>(.*?)</h4>', response.text, _re.DOTALL)
            locations_found = _re.findall(r'<span[^>]*class=[\"\'][^\"\']*job-search-card__location[^\"\']*[\"\'][^>]*>(.*?)</span>', response.text, _re.DOTALL)

            count = 0
            for i, link in enumerate(links_found[:10]):
                link = link.split("?")[0].strip()
                title = titles_found[i].strip() if i < len(titles_found) else clean_term
                title = _re.sub(r'<[^>]+>', '', title)
                title = _re.sub(r'\s+', ' ', title).strip()
                company = companies_found[i].strip() if i < len(companies_found) else ""
                company = _re.sub(r'<[^>]+>', '', company)
                company = _re.sub(r'\s+', ' ', company).strip()
                location = locations_found[i].strip() if i < len(locations_found) else "India"
                location = _re.sub(r'<[^>]+>', '', location)
                location = _re.sub(r'\s+', ' ', location).strip()

                if not link or not title:
                    continue

                display_title = f"{title} ({company})" if company else title
                jobs_out.append({
                    "type": "job",
                    "source": "LinkedIn",
                    "title": display_title,
                    "company": company,
                    "link": link,
                    "salary": "",
                    "location": location or "India / Remote",
                    "job_type": "Remote",
                    "tags": [clean_term.lower(), "linkedin"],
                    "search_term": clean_term.lower(),
                })
                count += 1

            print(f"  [LinkedIn] Harvested {count} job(s) for '{clean_term}'")
        except Exception as e:
            print(f"  [Warning] LinkedIn search failed for '{clean_term}': {e}")

    return jobs_out


def fetch_naukri_jobs(search_terms: List[str]) -> List[Dict[str, Any]]:
    """
    Fetch jobs from Naukri.com (India's leading job portal).
    Queries Naukri search API with desktop client credentials,
    and falls back cleanly to curated direct search portals if CAPTCHA gated.
    """
    jobs_out = []
    headers = {
        "appid": "109",
        "systemid": "Naukri",
        "clientid": "d3skt0p",
        "accept": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
    }

    for term in search_terms:
        clean_term = term.strip()
        if not clean_term:
            continue

        print(f"  [Naukri] Searching India jobs for: '{clean_term}'")
        try:
            url = "https://www.naukri.com/jobapi/v3/search"
            params = {
                "noOfResults": 10,
                "urlType": "search_by_keyword",
                "searchType": "adv",
                "keyword": clean_term,
                "pageNo": 1,
                "src": "jobsearchDesk",
            }
            res = requests.get(url, headers=headers, params=params, timeout=8)
            count = 0
            if res.status_code == 200:
                data = res.json()
                items = data.get("jobDetails", [])
                for j in items[:10]:
                    title = j.get("title", "").strip()
                    company = j.get("companyName", "").strip()
                    jd_url = j.get("jdURL", "").strip()
                    if jd_url and not jd_url.startswith("http"):
                        link = f"https://www.naukri.com{jd_url}"
                    else:
                        link = jd_url or f"https://www.naukri.com/{clean_term.replace(' ', '-')}-jobs"
                    salary = j.get("salary", "").strip()
                    placeholders = j.get("placeholders", [])
                    loc = "India"
                    for p in placeholders:
                        if isinstance(p, dict) and p.get("type") == "location":
                            loc = p.get("label", "India")
                    display_title = f"{title} ({company})" if company else title
                    jobs_out.append({
                        "type": "job",
                        "source": "Naukri",
                        "title": display_title,
                        "company": company,
                        "link": link,
                        "salary": salary,
                        "location": loc,
                        "job_type": "Full-time",
                        "tags": [clean_term.lower(), "naukri", "india"],
                        "search_term": clean_term.lower(),
                    })
                    count += 1
                print(f"  [Naukri] Harvested {count} job(s) for '{clean_term}'")
            else:
                # Direct curated search portal fallback (1-click search on Naukri)
                slug = clean_term.replace(" ", "-").lower()
                direct_link = f"https://www.naukri.com/{slug}-jobs"
                jobs_out.append({
                    "type": "job",
                    "source": "Naukri",
                    "title": f"Explore Latest {clean_term.title()} Jobs on Naukri",
                    "company": "Naukri India",
                    "link": direct_link,
                    "salary": "",
                    "location": "India (Multiple Locations)",
                    "job_type": "Full-time / Remote",
                    "tags": [clean_term.lower(), "naukri", "india"],
                    "search_term": clean_term.lower(),
                })
                print(f"  [Naukri] Added direct curated search link for '{clean_term}'")
        except Exception as e:
            print(f"  [Warning] Naukri search exception for '{clean_term}': {e}")
            slug = clean_term.replace(" ", "-").lower()
            direct_link = f"https://www.naukri.com/{slug}-jobs"
            jobs_out.append({
                "type": "job",
                "source": "Naukri",
                "title": f"Explore Latest {clean_term.title()} Jobs on Naukri",
                "company": "Naukri India",
                "link": direct_link,
                "salary": "",
                "location": "India (Multiple Locations)",
                "job_type": "Full-time / Remote",
                "tags": [clean_term.lower(), "naukri", "india"],
                "search_term": clean_term.lower(),
            })

    return jobs_out


def fetch_glassdoor_rss(search_terms: List[str]) -> List[Dict[str, Any]]:
    """
    Fetch jobs from Glassdoor via their RSS endpoint (no key required).
    """
    jobs_out = []
    headers = {"User-Agent": "CourseJobHunter/2.0"}

    for term in search_terms:
        clean_term = term.strip()
        if not clean_term:
            continue
        rss_url = (
            f"https://www.glassdoor.co.in/Job/{requests.utils.quote(clean_term.replace(' ', '-'))}"
            f"-jobs-SRCH_KO0,{len(clean_term)}.htm?format=rss"
        )
        print(f"  [Glassdoor India] Searching: '{clean_term}'")
        try:
            response = requests.get(rss_url, headers=headers, timeout=12)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            count = 0
            for entry in feed.entries:
                link = getattr(entry, "link", "").strip()
                title = getattr(entry, "title", "").strip()
                if not link or not title:
                    continue
                company = ""
                if " at " in title.lower():
                    parts = title.rsplit(" at ", 1)
                    title = parts[0].strip()
                    company = parts[1].strip()
                display_title = f"{title} ({company})" if company else title
                jobs_out.append({
                    "type": "job",
                    "source": "Glassdoor",
                    "title": display_title,
                    "company": company,
                    "link": link,
                    "salary": "",
                    "location": "India",
                    "job_type": "Full-time",
                    "tags": [clean_term.lower()],
                    "search_term": clean_term.lower(),
                })
                count += 1
            print(f"  [Glassdoor India] Harvested {count} job(s) for '{clean_term}'")
        except Exception as e:
            print(f"  [Warning] Glassdoor search failed for '{clean_term}': {e}")

    return jobs_out


def fetch_raw_jobs(search_terms: List[str], sources: List[str] = None) -> List[Dict[str, Any]]:
    """
    Fetch jobs across multiple free job boards:
    Global: Remotive, Jobicy, Arbeitnow
    India: Adzuna India, Indeed India, LinkedIn, Glassdoor India
    Handles per-source timeouts gracefully and deduplicates across boards.
    """
    if sources is None:
        sources = getattr(config, "JOB_SOURCES", [
            "linkedin", "naukri", "remotive", "jobicy", "arbeitnow",
            "adzuna_india", "indeed_india", "glassdoor",
        ])

    all_jobs = []
    seen_links = set()

    for src in sources:
        src_name = src.lower().strip()
        jobs = []
        if src_name == "remotive":
            jobs = fetch_remotive_jobs(search_terms)
        elif src_name == "jobicy":
            jobs = fetch_jobicy_jobs(search_terms)
        elif src_name == "arbeitnow":
            jobs = fetch_arbeitnow_jobs(search_terms)
        elif src_name == "adzuna_india":
            jobs = fetch_adzuna_india_jobs(search_terms)
        elif src_name == "indeed_india":
            jobs = fetch_indeed_india_rss(search_terms)
        elif src_name == "linkedin":
            jobs = fetch_linkedin_jobs_rss(search_terms)
        elif src_name == "naukri":
            jobs = fetch_naukri_jobs(search_terms)
        elif src_name == "glassdoor":
            jobs = fetch_glassdoor_rss(search_terms)
        else:
            print(f"  [Warning] Unknown job source '{src}'. Skipping.")

        for j in jobs:
            if j["link"] not in seen_links:
                seen_links.add(j["link"])
                all_jobs.append(j)

    return all_jobs


# Backward-compatible wrapper functions for direct callers and unit tests
def fetch_courses(
    feeds: List[str], seen: Any, keywords: List[str]
) -> List[Dict[str, str]]:
    """Fetch courses and filter by seen set/dict and keywords (backward-compatible)."""
    raw = fetch_raw_courses(feeds)
    filtered = []
    seen_in_batch = set(seen.keys()) if isinstance(seen, dict) else set(seen)
    for c in raw:
        if c["link"] not in seen_in_batch and matches_keywords(c["title"], keywords):
            seen_in_batch.add(c["link"])
            filtered.append(c)
    return filtered


def fetch_jobs(search_terms: List[str], seen: Any) -> List[Dict[str, Any]]:
    """Fetch jobs and filter by seen set/dict (backward-compatible)."""
    raw = fetch_raw_jobs(search_terms)
    filtered = []
    seen_in_batch = set(seen.keys()) if isinstance(seen, dict) else set(seen)
    for j in raw:
        if j["link"] not in seen_in_batch:
            seen_in_batch.add(j["link"])
            filtered.append(j)
    return filtered


# ============================================================================
# Main Execution Workflow
# ============================================================================

def run(
    dry_run: bool = False,
    weekly: bool = False,
    target_recipients: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """
    Main workflow:
    1. Validates required credentials upfront (exits cleanly with error if missing).
    2. Loads recipients and active subscriptions.
    3. If weekly=True, generates and sends weekly market insights report.
    4. Otherwise, runs daily flow:
       - Auto-prunes seen history.
       - Fetches courses and multi-board jobs once.
       - Badges and filters per recipient (keywords, strict location if enabled).
       - On weekly insight day (e.g. Sunday), appends weekly market insights.
       - Sends personalized digest.
       - Persists updated seen.json with dates and metadata.
    """
    print("\n" + "=" * 65)
    print(" 🎓💼 Course & Job Hunter - Automation Run")
    print("=" * 65)

    # 1. Validate secrets upfront if not in dry-run mode
    if not dry_run:
        is_valid, error_msg = notifier.validate_credentials()
        if not is_valid:
            print(f"\n[Fatal Error] Configuration check failed:\n  -> {error_msg}\n", file=sys.stderr)
            print("To resolve: Configure the required secret(s) in your GitHub Repository Secrets or local .env file.\n", file=sys.stderr)
            sys.exit(1)
        print("[Auth] Notification credentials verified successfully.")
    else:
        print("[Mode] Running in DRY-RUN mode. Notifications will NOT be sent.")

    # 2. Load recipients
    recipients = target_recipients if target_recipients is not None else load_recipients(RECIPIENTS_FILE)
    active_recipients = [r for r in recipients if r.get("active", True)]

    print(f"[Recipients] Total configured: {len(recipients)} | Active: {len(active_recipients)}")
    if not active_recipients:
        print("[Notice] No active recipients found. Nothing to do today. Exiting.")
        return

    for r in recipients:
        status = "Active" if r.get("active", True) else "PAUSED (skipped)"
        print(f"  - {r.get('name', 'Friend')} <{r.get('email')}>: {status}")

    # 3. Load seen history & database status
    primary_email = active_recipients[0].get("email")
    if db.is_supabase_enabled():
        print("[Database] ☁️ Supabase Cloud Database active (scalable to 1000s of users, no git bloat).")
    else:
        print("[Database] 📁 Using local seen.json fallback.")

    seen_dict = load_seen_dict(SEEN_FILE, primary_email=primary_email)
    print(f"[History] Loaded seen history for {len(active_recipients)} active recipient(s).")

    # Handle dedicated weekly insights trigger (--weekly)
    if weekly:
        print("\n" + "=" * 65)
        print(" [Feature 2] Weekly Market & Tech Insights Triggered")
        print("=" * 65)
        weekly_report = generate_weekly_insights(seen_dict, days=7)
        print(weekly_report)
        if not dry_run:
            for recipient in active_recipients:
                r_name = recipient.get("name", "Friend")
                r_email = recipient.get("email")
                if r_email:
                    notifier.send(
                        f"Hi {r_name},\n\n{weekly_report}",
                        to_email=r_email,
                        subject="📊 Weekly Market & Tech Insights Report",
                    )
                    print(f"  -> Sent weekly insights to {r_name} <{r_email}>")
        return

    # Check if today is designated weekly digest day (e.g. Sunday)
    today_name = datetime.now(timezone.utc).strftime("%A")
    target_weekly_day = getattr(config, "WEEKLY_INSIGHTS_DAY", "Sunday")
    is_weekly_day = today_name.lower() == target_weekly_day.lower()
    enable_weekly = getattr(config, "ENABLE_WEEKLY_INSIGHTS", True)
    sunday_weekly_section = ""
    if enable_weekly and is_weekly_day:
        print(f"\n[Feature 2] Today is {today_name}! Compiling weekly market insights...")
        sunday_weekly_section = "\n\n" + generate_weekly_insights(seen_dict, days=7)

    # 4. Collect unique sources across all active recipients (fetch ONCE)
    unique_feeds = set()
    unique_job_searches = set()

    for r in active_recipients:
        feeds = r.get("course_feeds") or config.COURSE_FEEDS
        for f in feeds:
            if f and f.strip():
                unique_feeds.add(f.strip())

        searches = r.get("job_searches") or config.JOB_SEARCHES
        for s in searches:
            if s and s.strip():
                unique_job_searches.add(s.strip())

    feed_list = sorted(list(unique_feeds))
    search_list = sorted(list(unique_job_searches))

    print(f"\n[Sources] Checking {len(feed_list)} course feed(s) and {len(search_list)} job search term(s) once:")
    raw_courses = fetch_raw_courses(feed_list)
    raw_jobs = fetch_raw_jobs(search_list)

    print(f"[Sources Summary] Total raw items harvested: {len(raw_courses)} courses, {len(raw_jobs)} jobs.")

    # 5. Process and deliver per recipient
    sender_email = notifier.get_sender_email() or "bot@coursejobhunter.local"
    emails_sent = 0
    errors_count = 0
    recipients_with_new_items = 0

    print("\n" + "-" * 65)
    print(" Processing digests per active recipient:")
    print("-" * 65)

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    delivered_by_email: Dict[str, List[Dict[str, Any]]] = {}

    for recipient in active_recipients:
        name = recipient.get("name", "Friend").strip()
        email = recipient.get("email", "").strip()
        keywords = recipient.get("keywords") or config.KEYWORDS
        job_searches = [s.strip().lower() for s in (recipient.get("job_searches") or config.JOB_SEARCHES)]
        user_feeds = set(recipient.get("course_feeds") or config.COURSE_FEEDS)
        max_items = recipient.get("max_items") or config.MAX_ITEMS

        if not email:
            print(f"[Warning] Recipient '{name}' has no email address. Skipping.")
            continue

        # Check and send one-time Welcome Email for newly added friends
        if not is_welcome_sent(recipient, seen_dict):
            welcome_msg = compose_welcome_message(name, email, keywords, job_searches, max_items)
            welcome_subject = f"👋 Welcome to Course & Job Hunter, {name}!"
            welcome_html = build_html_welcome(
                name=name,
                email=email,
                keywords=keywords,
                job_searches=job_searches,
                max_items=max_items,
                sender_email=sender_email,
            )
            if dry_run:
                print(f"\n--- [DRY RUN: Welcome Email for {name} <{email}>] ---")
                print(f"Subject: {welcome_subject}")
                print(welcome_msg)
                print("<!-- HTML_START -->")
                print(welcome_html)
                print("<!-- HTML_END -->")
                print("--- [END OF WELCOME EMAIL] ---\n")
            else:
                try:
                    print(f"  -> ✉️ Sending Welcome Email to new friend {name} <{email}>...")
                    notifier.send(
                        welcome_msg,
                        to_email=email,
                        subject=welcome_subject,
                        html=welcome_html,
                    )
                    mark_welcome_sent(recipient, seen_dict, RECIPIENTS_FILE)
                    emails_sent += 1
                    print(f"  -> ✅ Welcome Email successfully sent to {name} <{email}>!")
                except Exception as e:
                    print(f"  -> [Error] Failed to send welcome email to {name} <{email}>: {e}")
                    errors_count += 1

        # Load seen history from Cloud Database (or local fallback)
        recipient_seen = db.load_seen_for_user(email, expiry_days=getattr(config, "SEEN_EXPIRY_DAYS", 60))
        # Exclude internal metadata markers like __welcome_sent__ from link matching
        recipient_seen = {link for link in recipient_seen if not str(link).startswith("__")}
        local_seen_set = {k for k in seen_dict.get(email, {}).keys() if not str(k).startswith("__")}
        recipient_seen.update(local_seen_set)

        print(f"\nEvaluating for {name} <{email}> (already seen {len(recipient_seen)} items):")

        # Check recipient's configured sources preferences
        user_job_sources = recipient.get("job_sources")
        allowed_job_sources = set()
        if user_job_sources and isinstance(user_job_sources, list):
            allowed_job_sources = {str(s).lower().replace("_", "").replace(" ", "") for s in user_job_sources if str(s).strip()}

        user_course_sources = recipient.get("course_sources")
        allowed_course_cats = set()
        if user_course_sources and isinstance(user_course_sources, list):
            allowed_course_cats = {str(c).lower().strip() for c in user_course_sources if str(c).strip()}

        # Filter courses: must belong to recipient's subscribed feeds, match keywords, and not be seen
        matched_courses = []
        for c in raw_courses:
            if c["feed_url"] in user_feeds and c["link"] not in recipient_seen:
                if allowed_course_cats:
                    feed = c["feed_url"].lower()
                    cat_match = False
                    if "udemy_coupons" in allowed_course_cats and any(u in feed for u in ["tutorialbar", "discudemy", "coursetegg", "learnviral", "udemyfreebies", "onlinecourseshub"]):
                        cat_match = True
                    if "swayam_nptel" in allowed_course_cats and "swayam" in feed:
                        cat_match = True
                    if "freecodecamp" in allowed_course_cats and "freecodecamp" in feed:
                        cat_match = True
                    if "cloud_certs" in allowed_course_cats and any(cl in feed for cl in ["cloudblog", "microsoft"]):
                        cat_match = True
                    if "geeksforgeeks" in allowed_course_cats and "geeksforgeeks" in feed:
                        cat_match = True
                    if not cat_match:
                        continue

                if matches_keywords(c["title"], keywords):
                    matched_courses.append(c)

        # Filter jobs: location preference, keywords or search term match, and not seen
        matched_jobs = []
        strict_loc = getattr(config, "STRICT_LOCATION_FILTER", False)
        preferred_locs = getattr(config, "PREFERRED_LOCATIONS", [])

        for j in raw_jobs:
            if j["link"] in recipient_seen:
                continue

            # Check if source is allowed by recipient
            if allowed_job_sources:
                j_src = (j.get("source") or "").lower().replace("_", "").replace(" ", "")
                if j_src not in allowed_job_sources:
                    continue

            # Strict location check if enabled in config
            if strict_loc and not matches_location_filter(j.get("location", ""), preferred_locs):
                continue

            # Check if job originated from search term, matches title keywords, or matches tag keywords
            term_match = j.get("search_term") in job_searches
            title_match = matches_keywords(j["title"], keywords)
            tag_match = any(matches_keywords(tag, keywords) for tag in j.get("tags", []))

            if term_match or title_match or tag_match:
                matched_jobs.append(j)

        # Combine and deduplicate within this user's run
        combined = matched_courses + matched_jobs
        user_items = []
        user_seen_batch = set()

        for item in combined:
            if item["link"] not in user_seen_batch:
                user_seen_batch.add(item["link"])
                user_items.append(item)

        total_matched = len(user_items)
        selected_items = user_items[:max_items]

        print(
            f"  -> Matched: {len(matched_courses)} courses, {len(matched_jobs)} jobs. "
            f"Selected {len(selected_items)} item(s) (cap: {max_items})."
        )

        # Rule: If a person has nothing new, skip them silently unless Sunday insights exist
        if not selected_items and not sunday_weekly_section:
            print(f"  -> No new items for {name}. Skipping silently.")
            continue

        recipients_with_new_items += 1

        # Compute gamified stats for this recipient
        hunter_stats = calculate_hunter_stats(email, seen_dict, selected_items)
        stats_banner = format_hunter_stats_banner(hunter_stats)

        # Compose personalized message
        header = f"Hi {name},\n\n{stats_banner}Here is your daily digest of free courses and remote jobs:\n\n"
        body = format_message(selected_items) if selected_items else "No new courses/jobs matching your filters today."
        insights_block = sunday_weekly_section if sunday_weekly_section else ""
        footer = f"\n\nWant changes to your keywords or want to stop these emails? Reply to {sender_email}."
        message = header + body + insights_block + footer

        courses_count = sum(1 for item in selected_items if item.get("type") == "course")
        jobs_count = sum(1 for item in selected_items if item.get("type") == "job")
        digest_subject = compose_digest_subject(
            name=name,
            courses_count=courses_count,
            jobs_count=jobs_count,
            weekly=weekly,
        )

        html_message = build_html_digest(
            recipient_name=name,
            recipient_email=email,
            items=selected_items,
            stats=hunter_stats,
            insights=sunday_weekly_section if sunday_weekly_section else None,
            sender_email=sender_email,
        )

        if dry_run:
            print(f"\n--- [DRY RUN: Digest for {name} <{email}>] ---")
            print(f"Subject: {digest_subject}")
            print(message)
            print("<!-- HTML_START -->")
            print(html_message)
            print("<!-- HTML_END -->")
            print("--- [END OF MESSAGE] ---")
        else:
            try:
                print(f"  -> Sending individual digest to {name} <{email}>...")
                notifier.send(
                    message,
                    to_email=email,
                    subject=digest_subject,
                    html=html_message,
                )
                print(f"  -> ✅ Email successfully sent to {name} <{email}>!")
                emails_sent += 1

                # Record delivered items for batch save
                delivered_by_email[email] = selected_items

            except Exception as e:
                # Rule: If sending to one person fails, log the error and continue with the others.
                print(f"  -> [Error] Failed to send email to {name} <{email}>: {e}")
                errors_count += 1

    # 6. Save updated seen history to Supabase Cloud Database and backup
    if not dry_run and emails_sent > 0:
        if delivered_by_email:
            db.record_seen_batch(delivered_by_email)
            db.prune_expired_cloud(expiry_days=getattr(config, "SEEN_EXPIRY_DAYS", 60))
        save_seen_dict(seen_dict, SEEN_FILE)

    # 7. Final execution summary for GitHub Actions log visibility
    print("\n" + "=" * 65)
    print(" Execution Summary")
    print("=" * 65)
    print(f"Sources Checked       : {len(feed_list)} feeds, {len(search_list)} job searches")
    print(f"Items Harvested       : {len(raw_courses)} courses, {len(raw_jobs)} jobs")
    print(f"Active Recipients     : {len(active_recipients)}")
    print(f"Recipients with News  : {recipients_with_new_items}")
    print(f"Emails Sent           : {emails_sent}")
    print(f"Errors Encountered    : {errors_count}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Daily digest bot for free courses and remote jobs."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the digest in terminal instead of sending it via the notifier.",
    )
    parser.add_argument(
        "--weekly",
        action="store_true",
        help="Generate and display the weekly market and skills insights report.",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run, weekly=args.weekly)
