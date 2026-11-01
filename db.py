"""
Database management module for course-job-hunter.

Supports dual modes:
1. Supabase Cloud Database (PostgreSQL via REST API) - Scalable to 1000s of users, zero git bloat.
2. Local seen.json Fallback - Used when SUPABASE_URL / SUPABASE_KEY are not configured or offline.
"""

from datetime import datetime, timezone, timedelta
import json
import os
from typing import Any, Dict, List, Optional, Set
import requests

import config

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEEN_FILE = os.path.join(BASE_DIR, "seen.json")


def get_supabase_credentials():
    """Retrieve Supabase URL and Key from environment or config."""
    url = (
        os.environ.get("SUPABASE_URL")
        or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
        or getattr(config, "SUPABASE_URL", "")
    ).strip().rstrip("/")

    key = (
        os.environ.get("SUPABASE_KEY")
        or os.environ.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
        or getattr(config, "SUPABASE_KEY", "")
    ).strip()

    return url, key


def is_supabase_enabled() -> bool:
    """Check if valid Supabase credentials are configured."""
    url, key = get_supabase_credentials()
    return bool(url and key and url.startswith("https://"))


def _get_headers(key: str) -> Dict[str, str]:
    """Standard HTTP headers for Supabase REST API (PostgREST)."""
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal,resolution=ignore-duplicates",
    }


# ============================================================================
# Supabase Operations
# ============================================================================

def load_seen_for_user(user_email: str, expiry_days: int = 60) -> Set[str]:
    """
    Fetch all seen links for a given user email.
    Queries Supabase if enabled; falls back to local seen.json.
    """
    if is_supabase_enabled():
        url, key = get_supabase_credentials()
        endpoint = f"{url}/rest/v1/seen_items"
        cutoff_date = (datetime.now(timezone.utc).date() - timedelta(days=expiry_days)).isoformat()

        params = {
            "user_email": f"eq.{user_email.strip()}",
            "seen_at": f"gte.{cutoff_date}",
            "select": "link",
        }

        try:
            resp = requests.get(endpoint, headers=_get_headers(key), params=params, timeout=12)
            if resp.status_code == 200:
                rows = resp.json()
                links = {r["link"] for r in rows if isinstance(r, dict) and "link" in r}
                return links
            else:
                print(f"[Supabase Warning] Failed to load seen for {user_email} (HTTP {resp.status_code}): {resp.text}")
        except Exception as e:
            print(f"[Supabase Warning] Network error contacting database: {e}")

    # Fallback to local seen.json
    return _fallback_load_user_seen(user_email, expiry_days)


def record_seen_batch(email_to_items: Dict[str, List[Dict[str, Any]]]) -> bool:
    """
    Save new delivered opportunities in bulk.
    Inserts into Supabase if enabled, and updates local seen.json as fallback backup.
    """
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows_to_insert = []

    for email, items in email_to_items.items():
        clean_email = email.strip()
        for item in items:
            link = (item.get("link") or "").strip()
            if not link:
                continue
            rows_to_insert.append({
                "user_email": clean_email,
                "link": link,
                "title": (item.get("title") or "")[:250],
                "item_type": item.get("type", "job"),
                "company": (item.get("company") or "")[:100],
                "salary": (item.get("salary") or "")[:80],
                "location": (item.get("location") or "")[:100],
                "seen_at": today_str,
            })

    if not rows_to_insert:
        return True

    success = False
    if is_supabase_enabled():
        url, key = get_supabase_credentials()
        endpoint = f"{url}/rest/v1/seen_items"
        headers = _get_headers(key)
        headers["Prefer"] = "return=minimal,resolution=ignore-duplicates"

        try:
            resp = requests.post(endpoint, headers=headers, json=rows_to_insert, timeout=15)
            if resp.status_code in (200, 201, 204):
                print(f"[Supabase] Successfully saved {len(rows_to_insert)} records to cloud database.")
                success = True
            else:
                print(f"[Supabase Error] HTTP {resp.status_code} saving records: {resp.text}")
        except Exception as e:
            print(f"[Supabase Error] Failed to write to cloud database: {e}")

    # Also maintain local seen.json as secondary safety backup
    _fallback_save_items(email_to_items)
    return success


def prune_expired_cloud(expiry_days: int = 60) -> int:
    """Prune seen records older than expiry_days directly in Supabase."""
    if not is_supabase_enabled():
        return 0

    url, key = get_supabase_credentials()
    endpoint = f"{url}/rest/v1/seen_items"
    cutoff_date = (datetime.now(timezone.utc).date() - timedelta(days=expiry_days)).isoformat()
    params = {"seen_at": f"lt.{cutoff_date}"}

    try:
        resp = requests.delete(endpoint, headers=_get_headers(key), params=params, timeout=12)
        if resp.status_code in (200, 204):
            print(f"[Supabase] Auto-pruning completed for records older than {expiry_days} days.")
            return 1
    except Exception as e:
        print(f"[Supabase Warning] Failed to prune expired records: {e}")
    return 0


def fetch_recent_opportunities(days: int = 7) -> List[Dict[str, Any]]:
    """
    Fetch opportunities seen across all subscribers in the past `days`.
    Used for Weekly Market Insights.
    """
    if is_supabase_enabled():
        url, key = get_supabase_credentials()
        endpoint = f"{url}/rest/v1/seen_items"
        cutoff_date = (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()
        params = {
            "seen_at": f"gte.{cutoff_date}",
            "select": "link,title,company,item_type,location,salary,seen_at",
            "order": "seen_at.desc",
        }

        try:
            resp = requests.get(endpoint, headers=_get_headers(key), params=params, timeout=12)
            if resp.status_code == 200:
                rows = resp.json()
                # Deduplicate by link
                unique_by_link = {}
                for r in rows:
                    link = r.get("link")
                    if link and link not in unique_by_link:
                        unique_by_link[link] = {
                            "date": r.get("seen_at"),
                            "title": r.get("title", ""),
                            "company": r.get("company", ""),
                            "type": r.get("item_type", "job"),
                            "location": r.get("location", ""),
                            "salary": r.get("salary", ""),
                        }
                return list(unique_by_link.values())
        except Exception as e:
            print(f"[Supabase Warning] Failed to fetch weekly stats from cloud: {e}")

    # Fallback from local seen.json
    return []


# ============================================================================
# Local seen.json Fallback Helpers
# ============================================================================

def _fallback_load_user_seen(user_email: str, expiry_days: int) -> Set[str]:
    """Load seen set from local seen.json for a user."""
    if not os.path.exists(SEEN_FILE):
        return set()
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        today = datetime.now(timezone.utc).date()
        cutoff_date = today - timedelta(days=expiry_days)

        links_set = set()
        user_data = None

        if isinstance(data, list):
            return set(data)
        elif isinstance(data, dict):
            user_data = data.get(user_email)
            if not user_data and len(data) == 1:
                user_data = list(data.values())[0]

        if isinstance(user_data, list):
            return set(user_data)
        elif isinstance(user_data, dict):
            for link, meta in user_data.items():
                date_str = meta.get("date") if isinstance(meta, dict) else meta if isinstance(meta, str) else None
                if date_str:
                    try:
                        d = datetime.strptime(date_str, "%Y-%m-%d").date()
                        if d < cutoff_date:
                            continue
                    except Exception:
                        pass
                links_set.add(link)

        return links_set
    except Exception:
        return set()


def _fallback_save_items(email_to_items: Dict[str, List[Dict[str, Any]]]) -> None:
    """Save items locally to seen.json."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    existing_data = {}

    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, dict):
                    existing_data = content
        except Exception:
            existing_data = {}

    for email, items in email_to_items.items():
        user_dict = existing_data.setdefault(email, {})
        if not isinstance(user_dict, dict):
            user_dict = {k: {"date": today_str} for k in user_dict}
            existing_data[email] = user_dict

        for item in items:
            link = item.get("link")
            if link:
                user_dict[link] = {
                    "date": today_str,
                    "title": item.get("title", ""),
                    "type": item.get("type", "job"),
                    "company": item.get("company", ""),
                    "location": item.get("location", ""),
                    "salary": item.get("salary", ""),
                    "source": item.get("source", ""),
                }

    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except Exception as e:
        print(f"[Warning] Failed to write local seen.json backup: {e}")
