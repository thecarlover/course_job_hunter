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
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Set

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


def fetch_raw_jobs(search_terms: List[str], sources: List[str] = None) -> List[Dict[str, Any]]:
    """
    Fetch jobs across multiple free job boards: Remotive, Jobicy, and Arbeitnow.
    Handles per-source timeouts gracefully and deduplicates across boards.
    """
    if sources is None:
        sources = getattr(config, "JOB_SOURCES", ["remotive", "jobicy", "arbeitnow"])

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

def run(dry_run: bool = False, weekly: bool = False) -> None:
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
    recipients = load_recipients(RECIPIENTS_FILE)
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
            if dry_run:
                print(f"\n--- [DRY RUN: Welcome Email for {name} <{email}>] ---")
                print(f"Subject: {welcome_subject}")
                print(welcome_msg)
                print("--- [END OF WELCOME EMAIL] ---\n")
            else:
                try:
                    print(f"  -> ✉️ Sending Welcome Email to new friend {name} <{email}>...")
                    notifier.send(
                        welcome_msg,
                        to_email=email,
                        subject=welcome_subject,
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

        # Filter courses: must belong to recipient's subscribed feeds, match keywords, and not be seen
        matched_courses = []
        for c in raw_courses:
            if c["feed_url"] in user_feeds and c["link"] not in recipient_seen:
                if matches_keywords(c["title"], keywords):
                    matched_courses.append(c)

        # Filter jobs: location preference, keywords or search term match, and not seen
        matched_jobs = []
        strict_loc = getattr(config, "STRICT_LOCATION_FILTER", False)
        preferred_locs = getattr(config, "PREFERRED_LOCATIONS", [])

        for j in raw_jobs:
            if j["link"] in recipient_seen:
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

        # Compose personalized message
        header = f"Hi {name},\n\nHere is your daily digest of free courses and remote jobs:\n\n"
        body = format_message(selected_items) if selected_items else "No new courses/jobs matching your filters today."
        insights_block = sunday_weekly_section if sunday_weekly_section else ""
        footer = f"\n\nWant changes to your keywords or want to stop these emails? Reply to {sender_email}."
        message = header + body + insights_block + footer

        if dry_run:
            print(f"\n--- [DRY RUN: Digest for {name} <{email}>] ---")
            print(message)
            print("--- [END OF MESSAGE] ---")
        else:
            try:
                print(f"  -> Sending individual digest to {name} <{email}>...")
                notifier.send(
                    message,
                    to_email=email,
                    subject="Daily Digest: Free Courses & Remote Jobs",
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
