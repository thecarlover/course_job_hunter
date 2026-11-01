"""
Helper script to backfill existing seen.json records into Supabase cloud database.
"""

import json
import os
import requests
import db

def migrate():
    url, key = db.get_supabase_credentials()
    print(f"Connecting to Supabase at: {url}")
    print(f"Key length: {len(key)}")

    if not os.path.exists(db.SEEN_FILE):
        print("No seen.json found to migrate.")
        return

    with open(db.SEEN_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    for email, links in data.items():
        if isinstance(links, dict):
            for link, meta in links.items():
                rows.append({
                    "user_email": email,
                    "link": link,
                    "title": (meta.get("title") or "")[:250],
                    "item_type": meta.get("type", "job"),
                    "company": (meta.get("company") or "")[:100],
                    "salary": (meta.get("salary") or "")[:80],
                    "location": (meta.get("location") or "")[:100],
                    "seen_at": meta.get("date") or "2026-11-01",
                })
        elif isinstance(links, list):
            for link in links:
                rows.append({
                    "user_email": email,
                    "link": link,
                    "title": "",
                    "item_type": "job",
                    "company": "",
                    "salary": "",
                    "location": "",
                    "seen_at": "2026-11-01",
                })

    print(f"Found {len(rows)} records in seen.json to migrate.")

    endpoint = f"{url}/rest/v1/seen_items"
    headers = db._get_headers(key)
    headers["Prefer"] = "resolution=ignore-duplicates"

    # Batch in chunks of 50
    chunk_size = 50
    migrated = 0
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i + chunk_size]
        resp = requests.post(endpoint, headers=headers, json=chunk)
        if resp.status_code in (200, 201, 204):
            migrated += len(chunk)
            print(f"  -> Migrated {migrated}/{len(rows)} rows...")
        else:
            print(f"[Error] HTTP {resp.status_code}: {resp.text}")
            return False

    print(f"✅ Successfully migrated {migrated} records into Supabase!")
    return True

if __name__ == "__main__":
    migrate()
