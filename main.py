"""
Main script for course-job-hunter.

Fetches free courses from RSS feeds and remote jobs from Remotive API,
filters out already-seen items and non-matching titles, limits to MAX_ITEMS,
and sends a digest via the selected notification channel.
"""

import argparse
import json
import os
import re
import sys
from typing import List, Set, Dict

import requests
import feedparser

import config
import notifier

# Path to the persistent seen links file (relative to this script)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEEN_FILE = os.path.join(BASE_DIR, "seen.json")


def load_seen(filepath: str = SEEN_FILE) -> Set[str]:
    """Load the set of already sent links from a JSON file."""
    if not os.path.exists(filepath):
        return set()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return set(data)
            return set()
    except Exception as e:
        print(f"[Warning] Could not read seen file '{filepath}': {e}. Starting fresh.")
        return set()


def save_seen(seen: Set[str], filepath: str = SEEN_FILE) -> None:
    """Save the set of sent links back to the JSON file."""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(sorted(list(seen)), f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Error] Failed to write seen file '{filepath}': {e}")


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


def fetch_courses(
    feeds: List[str], seen: Set[str], keywords: List[str]
) -> List[Dict[str, str]]:
    """
    Fetch course RSS feeds, filter by keywords and seen list.
    Handles network or parser errors gracefully per feed.
    """
    items = []
    headers = {"User-Agent": "CourseJobHunter/1.0 (Daily digest bot)"}

    for feed_url in feeds:
        try:
            response = requests.get(feed_url, headers=headers, timeout=15)
            response.raise_for_status()
            feed = feedparser.parse(response.content)

            for entry in feed.entries:
                title = getattr(entry, "title", "").strip()
                link = getattr(entry, "link", "").strip()

                if not title or not link:
                    continue
                if link in seen:
                    continue
                if matches_keywords(title, keywords):
                    items.append({
                        "type": "course",
                        "title": title,
                        "link": link,
                    })
        except Exception as e:
            print(f"[Warning] Skipping course feed '{feed_url}' due to error: {e}")
            continue

    return items


def fetch_jobs(search_terms: List[str], seen: Set[str]) -> List[Dict[str, str]]:
    """
    Fetch remote jobs from Remotive API for each search term.
    Handles network and JSON errors gracefully per search term.
    """
    items = []
    headers = {"User-Agent": "CourseJobHunter/1.0 (Daily digest bot)"}

    for term in search_terms:
        try:
            url = f"https://remotive.com/api/remote-jobs?search={term}&limit=10"
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            jobs = data.get("jobs", [])

            for job in jobs:
                link = (job.get("url") or "").strip()
                if not link or link in seen:
                    continue

                title = (job.get("title") or "").strip()
                company = (job.get("company_name") or "").strip()
                display_title = f"{title} ({company})" if company else title

                items.append({
                    "type": "job",
                    "title": display_title,
                    "link": link,
                })
        except Exception as e:
            print(f"[Warning] Skipping job search for '{term}' due to error: {e}")
            continue

    return items


def format_item(item: Dict[str, str]) -> str:
    """Format a single course or job item into emoji + title + link."""
    emoji = "🎓" if item.get("type") == "course" else "💼"
    title = item.get("title", "")
    link = item.get("link", "")
    return f"{emoji} {title}\n{link}"


def format_message(items: List[Dict[str, str]]) -> str:
    """Format multiple items into a single readable message."""
    return "\n\n".join(format_item(item) for item in items)


def run(dry_run: bool = False) -> None:
    """Main execution workflow."""
    print("Loading previously seen links...")
    seen = load_seen(SEEN_FILE)
    print(f"Total seen items currently tracked: {len(seen)}")

    # We track items already picked in this run to avoid duplicates across feeds/searches
    seen_in_run = set(seen)

    print("Fetching free courses from RSS feeds...")
    course_items = []
    for item in fetch_courses(config.COURSE_FEEDS, seen_in_run, config.KEYWORDS):
        if item["link"] not in seen_in_run:
            seen_in_run.add(item["link"])
            course_items.append(item)
    print(f"Found {len(course_items)} new matching courses.")

    print("Fetching jobs from Remotive API...")
    job_items = []
    for item in fetch_jobs(config.JOB_SEARCHES, seen_in_run):
        if item["link"] not in seen_in_run:
            seen_in_run.add(item["link"])
            job_items.append(item)
    print(f"Found {len(job_items)} new jobs.")

    # Combine items and enforce MAX_ITEMS limit
    all_new_items = course_items + job_items
    if not all_new_items:
        print("No new items found today. Nothing to send.")
        return

    selected_items = all_new_items[: config.MAX_ITEMS]
    message = format_message(selected_items)

    print(
        f"Prepared digest with {len(selected_items)} item(s) "
        f"(max limit: {config.MAX_ITEMS})."
    )

    if dry_run:
        print("\n--- [DRY RUN MODE: Notification will NOT be sent] ---")
        print(message)
        print("--- [END OF MESSAGE] ---\n")
        print("Dry run completed. seen.json was not updated.")
    else:
        print(f"Sending notification using '{config.NOTIFIER}' notifier...")
        notifier.send(message)
        print("Notification sent successfully!")

        # Update and persist seen.json with the links that were sent
        for item in selected_items:
            seen.add(item["link"])
        save_seen(seen, SEEN_FILE)
        print(f"Updated seen.json (now tracking {len(seen)} items).")


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
