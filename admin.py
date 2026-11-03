"""
Admin Control Center & Testing Backend for course-job-hunter.

Runs a lightweight local web dashboard at http://localhost:8000 for:
- Managing subscribers (recipients.json)
- Live test execution (Dry run & real run simulation with visual email preview)
- Supabase Cloud Database Explorer (inspect & reset seen links)
- Real-time Source Health Inspector (test RSS feeds & job board APIs)
- Weekly Insights report preview
"""

import contextlib
import io
import json
import os
import socket
import sys
from typing import Any, Dict, List, Optional

import fastapi
from fastapi.responses import HTMLResponse, JSONResponse
import requests
import uvicorn

import config
import db
import main
import notifier

# Ensure environment variables are loaded
notifier.load_dotenv()
ADMIN_PASSWORD = (os.environ.get("ADMIN_PASSWORD") or "hunter2026").strip()

app = fastapi.FastAPI(title="Course & Job Hunter Admin Portal")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
RECIPIENTS_FILE = os.path.join(BASE_DIR, "recipients.json")


def get_local_ip() -> str:
    """Retrieve the primary local LAN IP address of this machine for phone/mobile access."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"


def is_authenticated(request: fastapi.Request) -> bool:
    """Verify that the request has the correct password via header, cookie, or query param."""
    if not ADMIN_PASSWORD:
        return True

    # 1. Custom Header
    token = request.headers.get("X-Admin-Password") or ""
    if token == ADMIN_PASSWORD:
        return True

    # 2. Authorization Header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        if auth_header[7:].strip() == ADMIN_PASSWORD:
            return True

    # 3. Cookie
    if request.cookies.get("admin_token") == ADMIN_PASSWORD:
        return True

    # 4. Query param
    if request.query_params.get("token") == ADMIN_PASSWORD:
        return True

    return False


@app.middleware("http")
async def auth_middleware(request: fastapi.Request, call_next):
    """Enforce authentication for protected API endpoints."""
    path = request.url.path
    public_paths = [
        "/",
        "/favicon.ico",
        "/api/auth/login",
        "/api/auth/status",
        "/api/auth/logout",
        "/api/network-info",
    ]
    if path in public_paths:
        return await call_next(request)

    if path.startswith("/api/"):
        if not is_authenticated(request):
            return JSONResponse({"error": "Unauthorized: Admin password required", "auth_required": True}, status_code=401)

    return await call_next(request)


# ============================================================================
# Authentication & Network APIs
# ============================================================================

@app.post("/api/auth/login")
async def auth_login(payload: Dict[str, Any], response: fastapi.Response):
    """Validate admin password and issue authentication token/cookie."""
    password = (payload.get("password") or "").strip()
    if not ADMIN_PASSWORD or password == ADMIN_PASSWORD:
        response.set_cookie(
            key="admin_token",
            value=ADMIN_PASSWORD,
            httponly=False,
            samesite="lax",
            max_age=86400 * 30,  # 30 days
        )
        return JSONResponse({"success": True, "token": ADMIN_PASSWORD})
    return JSONResponse({"success": False, "error": "Incorrect password. Please try again."}, status_code=401)


@app.get("/api/auth/status")
async def auth_status(request: fastapi.Request):
    """Check current authentication status."""
    return JSONResponse({
        "authenticated": is_authenticated(request),
        "password_required": bool(ADMIN_PASSWORD),
    })


@app.post("/api/auth/logout")
async def auth_logout(response: fastapi.Response):
    """Log out and remove session cookie."""
    response.delete_cookie("admin_token")
    return JSONResponse({"success": True})


@app.get("/api/network-info")
async def get_network_info():
    """Return local LAN IP and mobile connection URL."""
    local_ip = get_local_ip()
    port = 8000
    phone_url = f"http://{local_ip}:{port}"
    return JSONResponse({
        "local_ip": local_ip,
        "port": port,
        "phone_url": phone_url,
    })



# ============================================================================
# Frontend Dashboard HTML Route
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the single-page admin dashboard."""
    html_path = os.path.join(TEMPLATES_DIR, "admin.html")
    if not os.path.exists(html_path):
        return HTMLResponse("<h3>Admin dashboard template not found.</h3>", status_code=404)
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content)


# ============================================================================
# Subscribers Management API (recipients.json)
# ============================================================================

@app.get("/api/subscribers")
async def get_subscribers():
    """Return all subscribers from recipients.json with gamified hunter stats."""
    if not os.path.exists(RECIPIENTS_FILE):
        return JSONResponse([])
    try:
        with open(RECIPIENTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        subscribers = data if isinstance(data, list) else []
        seen_dict = main.load_seen_dict()
        for sub in subscribers:
            sub["stats"] = main.calculate_hunter_stats(sub.get("email", ""), seen_dict)
        return JSONResponse(subscribers)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/subscribers")
async def add_subscriber(sub: Dict[str, Any]):
    """Add a new subscriber to recipients.json."""
    subscribers = []
    if os.path.exists(RECIPIENTS_FILE):
        try:
            with open(RECIPIENTS_FILE, "r", encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, list):
                    subscribers = content
        except Exception:
            subscribers = []

    # Check for existing email
    email = (sub.get("email") or "").strip().lower()
    if not email:
        return JSONResponse({"error": "Email is required"}, status_code=400)

    # Overwrite if exists, else append
    existing_idx = next((i for i, s in enumerate(subscribers) if s.get("email", "").lower() == email), None)
    if existing_idx is not None:
        subscribers[existing_idx] = sub
    else:
        subscribers.append(sub)

    with open(RECIPIENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(subscribers, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return JSONResponse({"success": True, "count": len(subscribers)})


@app.put("/api/subscribers/{email}")
async def update_subscriber(email: str, updated_sub: Dict[str, Any]):
    """Update an existing subscriber."""
    if not os.path.exists(RECIPIENTS_FILE):
        return JSONResponse({"error": "No recipients file found"}, status_code=404)

    with open(RECIPIENTS_FILE, "r", encoding="utf-8") as f:
        subscribers = json.load(f)

    clean_email = email.strip().lower()
    found = False
    for i, s in enumerate(subscribers):
        if s.get("email", "").lower() == clean_email:
            # Preserve existing course_feeds or welcome_sent if not provided in updated_sub
            if "course_feeds" not in updated_sub:
                updated_sub["course_feeds"] = s.get("course_feeds", [])
            if "welcome_sent" in s and "welcome_sent" not in updated_sub:
                updated_sub["welcome_sent"] = s.get("welcome_sent")
            subscribers[i] = updated_sub
            found = True
            break

    if not found:
        return JSONResponse({"error": "Subscriber not found"}, status_code=404)

    with open(RECIPIENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(subscribers, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return JSONResponse({"success": True})


@app.delete("/api/subscribers/{email}")
async def delete_subscriber(email: str):
    """Delete a subscriber from recipients.json."""
    if not os.path.exists(RECIPIENTS_FILE):
        return JSONResponse({"error": "No recipients file found"}, status_code=404)

    with open(RECIPIENTS_FILE, "r", encoding="utf-8") as f:
        subscribers = json.load(f)

    clean_email = email.strip().lower()
    filtered = [s for s in subscribers if s.get("email", "").lower() != clean_email]

    with open(RECIPIENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(filtered, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return JSONResponse({"success": True, "remaining": len(filtered)})


# ============================================================================
# Live Test Runner & Simulator API
# ============================================================================

@app.post("/api/test-run")
async def run_test(payload: Dict[str, Any]):
    """
    Execute a test run in-process, capturing console stdout and formatting
    digest previews for the dashboard.
    """
    target = payload.get("target", "ALL")
    dry_run = payload.get("dry_run", True)
    weekly = payload.get("weekly", False)

    log_buffer = io.StringIO()
    logs = ""
    digests = []

    try:
        # Intercept print output
        with contextlib.redirect_stdout(log_buffer):
            try:
                # If target user specified, filter recipients
                original_recipients = main.load_recipients(RECIPIENTS_FILE)
                if target != "ALL":
                    target_recipients = [r for r in original_recipients if r.get("email") == target]
                else:
                    target_recipients = None

                # Run engine
                main.run(dry_run=dry_run, weekly=weekly, target_recipients=target_recipients)
            except Exception as e:
                print(f"[Engine Error]: {e}")

        logs = log_buffer.getvalue()

        # Extract regular digest previews from output safely
        blocks = logs.split("--- [DRY RUN: Digest for ")
        for block in blocks[1:]:
            if "--- [END OF MESSAGE] ---" in block:
                content_part, _, _ = block.partition("--- [END OF MESSAGE] ---")
                lines = content_part.splitlines()
                if lines:
                    header_line = lines[0].replace("] ---", "").replace("]", "").strip()
                    body = "\n".join(lines[1:]).strip()
                    subject_line = ""
                    if body.startswith("Subject:"):
                        subject_part, _, remaining_body = body.partition("\n")
                        subject_line = subject_part.replace("Subject:", "").strip()
                        body = remaining_body.strip()

                    items_count = body.count("🎓") + body.count("💼")
                    digests.append({
                        "recipient": header_line,
                        "subject": subject_line,
                        "content": body,
                        "items_count": items_count,
                    })

        # Extract welcome email previews if present
        welcome_blocks = logs.split("--- [DRY RUN: Welcome Email for ")
        for block in welcome_blocks[1:]:
            if "--- [END OF WELCOME EMAIL] ---" in block:
                content_part, _, _ = block.partition("--- [END OF WELCOME EMAIL] ---")
                lines = content_part.splitlines()
                if lines:
                    header_line = lines[0].replace("] ---", "").replace("]", "").strip()
                    body = "\n".join(lines[1:]).strip()
                    subject_line = ""
                    if body.startswith("Subject:"):
                        subject_part, _, remaining_body = body.partition("\n")
                        subject_line = subject_part.replace("Subject:", "").strip()
                        body = remaining_body.strip()

                    digests.append({
                        "recipient": f"👋 Welcome Email: {header_line}",
                        "subject": subject_line,
                        "content": body,
                        "items_count": 1,
                    })

        return JSONResponse({
            "success": True,
            "logs": logs,
            "digests": digests,
        })
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        return JSONResponse({
            "success": False,
            "error": str(e),
            "logs": logs + f"\n\n[Server Handler Error]:\n{err_msg}",
            "digests": digests,
        })


# ============================================================================
# Supabase Cloud Database Explorer API
# ============================================================================

@app.get("/api/supabase/items")
async def get_supabase_items():
    """Fetch recent rows directly from Supabase seen_items table."""
    url, key = db.get_supabase_credentials()
    if not db.is_supabase_enabled():
        # Fallback to local seen.json
        seen_set = db.load_seen()
        fallback_rows = [
            {"id": idx, "user_email": "local", "link": link, "item_type": "job", "title": link, "seen_at": "local"}
            for idx, link in enumerate(sorted(list(seen_set))[:100], 1)
        ]
        return JSONResponse({"items": fallback_rows, "source": "local"})

    endpoint = f"{url}/rest/v1/seen_items"
    headers = db._get_headers(key)
    params = {
        "select": "id,user_email,link,title,company,salary,location,item_type,seen_at",
        "order": "id.desc",
        "limit": 300,
    }

    try:
        resp = requests.get(endpoint, headers=headers, params=params, timeout=12)
        if resp.status_code == 200:
            return JSONResponse({"items": resp.json(), "source": "supabase"})
        return JSONResponse({"error": resp.text, "items": []}, status_code=resp.status_code)
    except Exception as e:
        return JSONResponse({"error": str(e), "items": []}, status_code=500)


@app.delete("/api/supabase/items")
async def delete_supabase_items(user_email: str):
    """Delete seen items for a specific user to easily reset for testing."""
    url, key = db.get_supabase_credentials()
    clean_email = user_email.strip()

    if not db.is_supabase_enabled():
        return JSONResponse({"message": "Supabase not configured; using local seen.json"})

    endpoint = f"{url}/rest/v1/seen_items"
    headers = db._get_headers(key)

    params = {} if clean_email == "ALL" else {"user_email": f"eq.{clean_email}"}

    try:
        resp = requests.delete(endpoint, headers=headers, params=params, timeout=12)
        if resp.status_code in (200, 204):
            return JSONResponse({"message": f"Successfully cleared seen history for {clean_email}."})
        return JSONResponse({"error": resp.text}, status_code=resp.status_code)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ============================================================================
# Sources Health & Feed Inspector API
# ============================================================================

@app.get("/api/sources/test")
async def test_sources():
    """Ping all configured RSS course feeds and job APIs."""
    sources_status = []
    headers = {"User-Agent": "CourseJobHunter/2.0 (Admin Inspector)"}

    # Test Course Feeds
    for feed_url in config.COURSE_FEEDS:
        name = feed_url.split("/")[2] if "/" in feed_url else feed_url
        try:
            r = requests.get(feed_url, headers=headers, timeout=8)
            feed = main.feedparser.parse(r.content)
            count = len(feed.entries)
            sources_status.append({
                "name": f"RSS: {name}",
                "type": "Course Feed",
                "url": feed_url,
                "status": "OK" if r.status_code == 200 else f"HTTP {r.status_code}",
                "harvested_count": count,
                "error": None if r.status_code == 200 else r.text[:100],
            })
        except Exception as e:
            sources_status.append({
                "name": f"RSS: {name}",
                "type": "Course Feed",
                "url": feed_url,
                "status": "ERROR",
                "harvested_count": 0,
                "error": str(e)[:120],
            })

    # Test Remotive API
    try:
        r = requests.get("https://remotive.com/api/remote-jobs?limit=10", headers=headers, timeout=8)
        data = r.json()
        count = len(data.get("jobs", []))
        sources_status.append({
            "name": "Remotive API",
            "type": "Remote Jobs",
            "url": "https://remotive.com/api/remote-jobs",
            "status": "OK" if r.status_code == 200 else f"HTTP {r.status_code}",
            "harvested_count": count,
            "error": None,
        })
    except Exception as e:
        sources_status.append({
            "name": "Remotive API",
            "type": "Remote Jobs",
            "url": "https://remotive.com/api/remote-jobs",
            "status": "ERROR",
            "harvested_count": 0,
            "error": str(e)[:120],
        })

    # Test Jobicy API
    try:
        r = requests.get("https://jobicy.com/api/v2/remote-jobs?count=25", headers=headers, timeout=8)
        data = r.json()
        count = len(data.get("jobs", []))
        sources_status.append({
            "name": "Jobicy API",
            "type": "Remote Jobs",
            "url": "https://jobicy.com/api/v2/remote-jobs",
            "status": "OK" if r.status_code == 200 else f"HTTP {r.status_code}",
            "harvested_count": count,
            "error": None,
        })
    except Exception as e:
        sources_status.append({
            "name": "Jobicy API",
            "type": "Remote Jobs",
            "url": "https://jobicy.com/api/v2/remote-jobs",
            "status": "ERROR",
            "harvested_count": 0,
            "error": str(e)[:120],
        })

    # Test Arbeitnow API
    try:
        r = requests.get("https://www.arbeitnow.com/api/job-board-api", headers=headers, timeout=8)
        data = r.json()
        count = len(data.get("data", []))
        sources_status.append({
            "name": "Arbeitnow API",
            "type": "Remote Jobs",
            "url": "https://www.arbeitnow.com/api/job-board-api",
            "status": "OK" if r.status_code == 200 else f"HTTP {r.status_code}",
            "harvested_count": count,
            "error": None,
        })
    except Exception as e:
        sources_status.append({
            "name": "Arbeitnow API",
            "type": "Remote Jobs",
            "url": "https://www.arbeitnow.com/api/job-board-api",
            "status": "ERROR",
            "harvested_count": 0,
            "error": str(e)[:120],
        })

    return JSONResponse({"sources": sources_status})


# ============================================================================
# Weekly Insights Preview API
# ============================================================================

@app.get("/api/weekly-insights")
async def get_weekly_insights_preview():
    """Generate and return the 7-day market insights report text."""
    seen_dict = main.load_seen_dict()
    report = main.generate_weekly_insights(seen_dict, days=7)
    return JSONResponse({"report": report})


if __name__ == "__main__":
    local_ip = get_local_ip()
    port = int(os.environ.get("PORT", 8000))
    print("\n" + "=" * 65)
    print(" 🚀 Course & Job Hunter — Admin Control Center")
    print("=" * 65)
    print(f"  💻 On this Mac   : http://localhost:{port}")
    print(f"  📱 On your Phone : http://{local_ip}:{port}")
    print(f"  🔐 Admin Password: {ADMIN_PASSWORD}")
    print("=" * 65)
    print("  Connect your phone to the same Wi-Fi network and open the phone URL.")
    print("  Press Ctrl+C to stop the server anytime.\n")
    uvicorn.run("admin:app", host="0.0.0.0", port=port, reload=True)
