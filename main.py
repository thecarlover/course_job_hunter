"""
Main script for course-job-hunter.

Fetches free courses from RSS feeds and remote jobs from Remotive API once per run,
filters results per recipient using their custom keywords and search preferences,
and sends individual, customized digests while tracking seen history per recipient.
"""

import argparse
import json
import os
import re
import sys
from typing import Dict, List, Set

import feedparser
import requests

import config
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
# Seen Items Management (Per-Person History)
# ============================================================================

def load_seen_dict(filepath: str = SEEN_FILE, primary_email: str = None) -> Dict[str, Set[str]]:
    """
    Load seen history mapped by recipient email: {email: set([link1, link2, ...])}.
    Migrates legacy list formats seamlessly.
    """
    if not os.path.exists(filepath):
        return {}

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Legacy format: simple list of links -> migrate to dict
        if isinstance(data, list):
            fallback_key = primary_email or notifier.get_sender_email() or "default"
            print(f"[Notice] Migrated legacy seen.json list format to per-person tracking under '{fallback_key}'.")
            return {fallback_key: set(data)}

        # Modern format: dict mapping email -> list of links
        if isinstance(data, dict):
            return {email: set(links) for email, links in data.items() if isinstance(links, list)}

        return {}
    except Exception as e:
        print(f"[Warning] Could not read seen file '{filepath}': {e}. Starting fresh.")
        return {}


def save_seen_dict(seen_dict: Dict[str, Set[str]], filepath: str = SEEN_FILE) -> None:
    """Save the per-recipient seen history dictionary back to seen.json."""
    try:
        serializable = {email: sorted(list(links)) for email, links in seen_dict.items()}
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except Exception as e:
        print(f"[Error] Failed to write seen file '{filepath}': {e}")


def load_seen(filepath: str = SEEN_FILE) -> Set[str]:
    """
    Backward-compatible helper returning a flattened set of all seen links,
    or empty set if file does not exist.
    """
    if not os.path.exists(filepath):
        return set()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return set(data)
            if isinstance(data, dict):
                all_links = set()
                for links in data.values():
                    if isinstance(links, list):
                        all_links.update(links)
                return all_links
            return set()
    except Exception:
        return set()


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


def format_item(item: Dict[str, str]) -> str:
    """Format a single course or job item into emoji + title + link."""
    emoji = "🎓" if item.get("type") == "course" else "💼"
    title = item.get("title", "")
    link = item.get("link", "")
    return f"{emoji} {title}\n{link}"


def format_message(items: List[Dict[str, str]]) -> str:
    """Format multiple items into a single readable message block."""
    return "\n\n".join(format_item(item) for item in items)


# ============================================================================
# Single-Pass Source Fetching
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


def fetch_raw_jobs(search_terms: List[str]) -> List[Dict[str, str]]:
    """
    Fetch all jobs from Remotive API for the given search terms once without filtering.
    Tagged with origin search_term.
    """
    raw_jobs = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 "
            "CourseJobHunter/2.0"
        )
    }

    for term in search_terms:
        clean_term = term.strip()
        if not clean_term:
            continue
        print(f"  [Job API] Querying Remotive for search term: '{clean_term}'")
        try:
            url = f"https://remotive.com/api/remote-jobs?search={clean_term}&limit=10"
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            jobs = data.get("jobs", [])

            job_count = 0
            for job in jobs:
                link = (job.get("url") or "").strip()
                if not link:
                    continue
                title = (job.get("title") or "").strip()
                company = (job.get("company_name") or "").strip()
                display_title = f"{title} ({company})" if company else title

                raw_jobs.append({
                    "type": "job",
                    "title": display_title,
                    "link": link,
                    "search_term": clean_term.lower(),
                })
                job_count += 1
            print(f"  [Job API] Found {job_count} job(s) for search: '{clean_term}'")
        except Exception as e:
            print(f"  [Warning] Skipping job search for '{clean_term}' due to error: {e}")

    return raw_jobs


# Backward-compatible wrapper functions for direct callers and unit tests
def fetch_courses(
    feeds: List[str], seen: Set[str], keywords: List[str]
) -> List[Dict[str, str]]:
    """Fetch courses and filter by seen set and keywords (backward-compatible)."""
    raw = fetch_raw_courses(feeds)
    filtered = []
    seen_in_batch = set(seen)
    for c in raw:
        if c["link"] not in seen_in_batch and matches_keywords(c["title"], keywords):
            seen_in_batch.add(c["link"])
            filtered.append(c)
    return filtered


def fetch_jobs(search_terms: List[str], seen: Set[str]) -> List[Dict[str, str]]:
    """Fetch jobs and filter by seen set (backward-compatible)."""
    raw = fetch_raw_jobs(search_terms)
    filtered = []
    seen_in_batch = set(seen)
    for j in raw:
        if j["link"] not in seen_in_batch:
            seen_in_batch.add(j["link"])
            filtered.append(j)
    return filtered


# ============================================================================
# Main Execution Workflow
# ============================================================================

def run(dry_run: bool = False) -> None:
    """
    Main workflow:
    1. Validates required credentials upfront (exits cleanly with error if missing).
    2. Loads recipients and active subscriptions.
    3. Fetches unique sources ONCE.
    4. Filters per recipient (keywords, search terms, seen links).
    5. Sends individual, personalized emails with recipient-specific footer.
    6. Persists updated seen.json per recipient.
    """
    print("\n" + "=" * 65)
    print(" 🎓💼 Course & Job Hunter - Daily Digest Run")
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

    # 3. Load per-person seen history
    primary_email = active_recipients[0].get("email")
    seen_dict = load_seen_dict(SEEN_FILE, primary_email=primary_email)
    print(f"[History] Loaded seen history for {len(seen_dict)} recipient(s).")

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

        recipient_seen = seen_dict.setdefault(email, set())
        print(f"\nEvaluating for {name} <{email}> (already seen {len(recipient_seen)} items):")

        # Filter courses: must belong to recipient's subscribed feeds, match keywords, and not be seen
        matched_courses = []
        for c in raw_courses:
            if c["feed_url"] in user_feeds and c["link"] not in recipient_seen:
                if matches_keywords(c["title"], keywords):
                    matched_courses.append(c)

        # Filter jobs: must match recipient's job searches or keywords, and not be seen
        matched_jobs = []
        for j in raw_jobs:
            if j["link"] not in recipient_seen:
                # Match if job originated from recipient's search terms or matches their keywords
                if j.get("search_term") in job_searches or matches_keywords(j["title"], keywords):
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

        # Rule: If a person has nothing new, skip them silently
        if not selected_items:
            print(f"  -> No new items for {name}. Skipping silently.")
            continue

        recipients_with_new_items += 1

        # Compose personalized message
        header = f"Hi {name},\n\nHere is your daily digest of free courses and remote jobs:\n\n"
        body = format_message(selected_items)
        footer = f"\n\nWant changes to your keywords or want to stop these emails? Reply to {sender_email}."
        message = header + body + footer

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

                # Update recipient's seen links only upon successful delivery
                for item in selected_items:
                    recipient_seen.add(item["link"])

            except Exception as e:
                # Rule: If sending to one person fails, log the error and continue with the others.
                print(f"  -> [Error] Failed to send email to {name} <{email}>: {e}")
                errors_count += 1

    # 6. Save updated seen history
    if not dry_run and emails_sent > 0:
        save_seen_dict(seen_dict, SEEN_FILE)
        print(f"\n[Storage] Updated '{os.path.basename(SEEN_FILE)}' with new seen entries.")

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
    args = parser.parse_args()
    run(dry_run=args.dry_run)
