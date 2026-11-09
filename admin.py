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
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import socket
import sys
import urllib.parse
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

# Portal (member) auth — separate from admin auth
PORTAL_SECRET_KEY = (os.environ.get("PORTAL_SECRET_KEY") or "hunter_portal_secret_2026").strip()
_PORTAL_SESSIONS: Dict[str, str] = {}  # token → email

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


# ── Portal auth helpers ──────────────────────────────────────────────────────

def _hash_password(password: str, salt: str = "") -> str:
    """Return sha256:{hex} hash for a portal password."""
    raw = (salt + password).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _get_subscriber_password(sub: Dict[str, Any]) -> str:
    """Return the stored hashed password, or the default hash."""
    stored = sub.get("portal_password", "")
    if stored and stored.startswith("sha256:"):
        return stored
    name = (sub.get("name") or sub.get("email", "user")).lower().split("@")[0]
    # Default: hunter123
    return _hash_password("hunter123")


def _verify_password(sub: Dict[str, Any], raw_password: str) -> bool:
    """Verify a plain-text password against the subscriber's stored hash."""
    expected = _get_subscriber_password(sub)
    candidate = _hash_password(raw_password)
    return hmac.compare_digest(expected, candidate)


def _create_portal_token(email: str) -> str:
    """Generate a secure session token and store the email mapping."""
    token = secrets.token_hex(32)
    _PORTAL_SESSIONS[token] = email.strip().lower()
    return token


def _get_portal_email(request: fastapi.Request) -> Optional[str]:
    """Extract the authenticated portal member's email from the cookie, or None."""
    token = request.cookies.get("portal_token", "")
    return _PORTAL_SESSIONS.get(token)


# ── Admin auth middleware ─────────────────────────────────────────────────────

@app.middleware("http")
async def auth_middleware(request: fastapi.Request, call_next):
    """Enforce authentication for protected API endpoints."""
    path = request.url.path
    public_paths = [
        "/",
        "/portal",
        "/favicon.ico",
        "/api/auth/login",
        "/api/auth/status",
        "/api/auth/logout",
        "/api/network-info",
        "/api/portal/auth/login",
        "/api/portal/auth/me",
        "/api/portal/auth/logout",
    ]
    if path in public_paths or path.startswith("/api/portal/"):
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
                    html_content = ""
                    if "<!-- HTML_START -->" in body and "<!-- HTML_END -->" in body:
                        before_html, _, rest_html = body.partition("<!-- HTML_START -->")
                        html_content, _, after_html = rest_html.partition("<!-- HTML_END -->")
                        body = (before_html + after_html).strip()
                        html_content = html_content.strip()

                    digests.append({
                        "recipient": header_line,
                        "subject": subject_line,
                        "content": body,
                        "html": html_content,
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

                    welcome_html_content = ""
                    if "<!-- HTML_START -->" in body and "<!-- HTML_END -->" in body:
                        before_html, _, rest_html = body.partition("<!-- HTML_START -->")
                        welcome_html_content, _, after_html = rest_html.partition("<!-- HTML_END -->")
                        body = (before_html + after_html).strip()
                        welcome_html_content = welcome_html_content.strip()

                    digests.append({
                        "recipient": f"👋 Welcome Email: {header_line}",
                        "subject": subject_line,
                        "content": body,
                        "html": welcome_html_content,
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


# ============================================================================
# Self-Service Member Portal & Opportunity Vault APIs
# ============================================================================

COURSE_DOMAINS = (
    "answersq.com",
    "tutorialbar.com",
    "discudemy.com",
    "freecodecamp.org",
    "udemyfreebies",
    "udemy.com",
    "coursera.org",
    "edx.org",
)


def classify_vault_item(url: str, meta: Optional[Dict[str, Any]] = None) -> str:
    """Determine whether an opportunity is a free course or a remote job."""
    if isinstance(meta, dict) and meta.get("type") in ("course", "job"):
        return meta["type"]
    url_lower = (url or "").lower()
    if any(cd in url_lower for cd in COURSE_DOMAINS):
        return "course"
    return "job"


def derive_vault_title(url: str, meta: Optional[Dict[str, Any]] = None) -> str:
    """Return a clean, human-readable title for vault items."""
    if isinstance(meta, dict) and meta.get("title"):
        return str(meta["title"]).strip()
    try:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.strip("/")
        if not path:
            return parsed.netloc
        parts = [p for p in path.split("/") if p]
        slug = parts[-1] if parts else parsed.netloc
        slug = slug.split("?")[0].split("#")[0]
        slug = re.sub(r"^\d+[-_]?", "", slug)
        slug = re.sub(r"[-_]\d+$", "", slug)
        words = [w for w in re.split(r"[-_]+", slug) if w]
        title = " ".join(words).title()
        acronyms = {
            r"\bAi\b": "AI",
            r"\bQa\b": "QA",
            r"\bUi\b": "UI",
            r"\bUx\b": "UX",
            r"\bApi\b": "API",
            r"\bMl\b": "ML",
            r"\bEmea\b": "EMEA",
            r"\bB2b\b": "B2B",
            r"\bBis\b": "BIS",
            r"\bMba\b": "MBA",
        }
        for pat, rep in acronyms.items():
            title = re.sub(pat, rep, title)
        return title or parsed.netloc
    except Exception:
        return url


def calculate_xp_progress(total_items: int, level_num: int) -> Dict[str, Any]:
    """Calculate progress percentage and items required for next tier."""
    tiers = {
        1: (0, 10, "Level 2: Opportunity Scout"),
        2: (10, 25, "Level 3: Career Strategist"),
        3: (25, 50, "Level 4: Talent Pathfinder"),
        4: (50, 100, "Level 5: Master Career Strategist"),
    }
    if level_num in tiers:
        low, high, next_title = tiers[level_num]
        needed = max(0, high - total_items)
        percent = min(100, max(0, int(((total_items - low) / (high - low)) * 100)))
        return {
            "percent": percent,
            "next_title": next_title,
            "items_needed": needed,
            "is_max": False,
        }
    return {
        "percent": 100,
        "next_title": "MAX RANK",
        "items_needed": 0,
        "is_max": True,
    }


@app.get("/portal", response_class=HTMLResponse)
async def serve_user_portal():
    """Serve the self-service member hub and opportunity vault page."""
    html_path = os.path.join(TEMPLATES_DIR, "user_portal.html")
    if not os.path.exists(html_path):
        return HTMLResponse("<h3>Member portal template not found.</h3>", status_code=404)
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content)


@app.get("/api/portal/subscribers")
async def get_portal_subscribers():
    """Return subscriber profiles for profile switcher."""
    if not os.path.exists(RECIPIENTS_FILE):
        return JSONResponse([])
    try:
        with open(RECIPIENTS_FILE, "r", encoding="utf-8") as f:
            subscribers = json.load(f)
        result = []
        for s in subscribers:
            email = s.get("email", "")
            name = s.get("name") or email.split("@")[0].title()
            result.append({
                "name": name,
                "email": email,
                "active": s.get("active", True),
            })
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/portal/user")
async def get_portal_user(email: str = ""):
    """Return personalized subscriber profile, gamified stats, and opportunity vault."""
    email_clean = (email or "").strip().lower()
    if not email_clean:
        return JSONResponse({"error": "Email parameter is required"}, status_code=400)

    if not os.path.exists(RECIPIENTS_FILE):
        return JSONResponse({"error": "No subscribers configured"}, status_code=404)

    with open(RECIPIENTS_FILE, "r", encoding="utf-8") as f:
        subscribers = json.load(f)

    user_sub = next((s for s in subscribers if s.get("email", "").strip().lower() == email_clean), None)
    if not user_sub:
        return JSONResponse({"error": f"Subscriber with email '{email_clean}' not found"}, status_code=404)

    seen_dict = main.load_seen_dict()
    stats = main.calculate_hunter_stats(email_clean, seen_dict)
    stats["xp"] = calculate_xp_progress(stats.get("total_items", 0), stats.get("level_num", 1))

    # Build opportunity vault from seen_dict
    raw_history = seen_dict.get(email_clean, {}) if isinstance(seen_dict, dict) else {}
    vault = []

    for url, meta in raw_history.items():
        if not url or url.startswith("__"):
            continue
        item_meta = meta if isinstance(meta, dict) else {}
        item_type = item_meta.get("type") or classify_vault_item(url, item_meta)
        title = derive_vault_title(url, item_meta)
        date_str = item_meta.get("date") or "Earlier"
        domain = urllib.parse.urlparse(url).netloc.replace("www.", "")

        vault.append({
            "url": url,
            "title": title,
            "type": item_type,
            "date": date_str,
            "domain": domain,
            "location": item_meta.get("location"),
            "salary": item_meta.get("salary"),
        })

    # Sort vault descending by date
    vault.sort(key=lambda x: str(x.get("date", "")), reverse=True)

    return JSONResponse({
        "subscriber": {
            "name": user_sub.get("name") or email_clean.split("@")[0].title(),
            "email": user_sub.get("email"),
            "active": user_sub.get("active", True),
            "keywords": user_sub.get("keywords", []),
            "job_searches": user_sub.get("job_searches", []),
            "job_sources": user_sub.get("job_sources", list(getattr(config, "AVAILABLE_JOB_SOURCES", {}).keys())),
            "course_sources": user_sub.get("course_sources", list(getattr(config, "AVAILABLE_COURSE_PLATFORMS", {}).keys())),
            "preferred_locations": user_sub.get("preferred_locations", []),
            "max_items": user_sub.get("max_items", 10),
        },
        "available_job_sources": getattr(config, "AVAILABLE_JOB_SOURCES", {}),
        "available_course_platforms": getattr(config, "AVAILABLE_COURSE_PLATFORMS", {}),
        "stats": stats,
        "vault": vault,
        "vault_count": len(vault),
    })


@app.get("/api/portal/daily-question")
async def get_daily_question():
    """Return the interactive Daily Interview Question of the Day based on the current day."""
    import datetime
    day_of_year = datetime.date.today().timetuple().tm_yday

    questions = [
        {
            "id": 1,
            "category": "Python & Backend",
            "question": "In Python, what is the key difference between `deepcopy` and shallow `copy`?",
            "options": [
                "Shallow copy copies arbitrary nested objects recursively, while deepcopy does not",
                "Deep copy creates a new compound object and recursively inserts copies of child objects",
                "Shallow copy is thread-safe, whereas deepcopy causes GIL deadlocks",
                "There is no difference; deepcopy is just an alias for performance optimization"
            ],
            "answer": 1,
            "explanation": "`copy.deepcopy()` constructs a brand-new compound object and recursively copies all nested objects found inside, avoiding shared mutation."
        },
        {
            "id": 2,
            "category": "System Design",
            "question": "Which algorithm is most commonly used in distributed rate limiters (like Cloudflare or Redis)?",
            "options": [
                "Token Bucket / Sliding Window Counter",
                "Dijkstra's Shortest Path",
                "Consistent Hashing Ring",
                "Raft Consensus"
            ],
            "answer": 0,
            "explanation": "Token Bucket and Sliding Window Counter allow burst handling while enforcing strict request rates across distributed Redis nodes."
        },
        {
            "id": 3,
            "category": "Cloud & DevOps",
            "question": "What happens when a Kubernetes Pod exceeds its configured memory limit?",
            "options": [
                "The Pod is throttled by CPU cgroups without termination",
                "The Pod is killed immediately with an OOMKilled (Exit Code 137) status",
                "The node swaps pod memory to disk automatically",
                "Kubernetes provisions an additional replica automatically"
            ],
            "answer": 1,
            "explanation": "When a container consumes more memory than its limit, the Linux kernel OOM Killer immediately terminates it with Exit Code 137."
        },
        {
            "id": 4,
            "category": "Databases & SQL",
            "question": "Why is indexing every column in a high-traffic PostgreSQL table considered bad practice?",
            "options": [
                "PostgreSQL enforces a hard limit of only 5 indexes per table",
                "Indexes degrade write/insert/update performance and consume substantial RAM/disk",
                "B-tree indexes cause permanent table locks during SELECT queries",
                "Queries with WHERE clauses fail if more than two indexes exist"
            ],
            "answer": 1,
            "explanation": "Every INSERT/UPDATE must write to all indexes, slowing writes and bloating the buffer cache. Only index query predicate columns."
        },
        {
            "id": 5,
            "category": "Security & Architecture",
            "question": "What is the primary vulnerability prevented by using `HttpOnly` and `SameSite=Lax` cookies?",
            "options": [
                "SQL Injection and buffer overflows",
                "Cross-Site Scripting (XSS) cookie theft and Cross-Site Request Forgery (CSRF)",
                "DDoS attacks and TCP SYN flooding",
                "DNS Spoofing and man-in-the-middle attacks"
            ],
            "answer": 1,
            "explanation": "`HttpOnly` blocks JavaScript `document.cookie` access (stopping XSS token theft), while `SameSite=Lax/Strict` blocks cross-site request forging."
        }
    ]

    selected = questions[day_of_year % len(questions)]
    return JSONResponse({
        "success": True,
        "date": datetime.date.today().isoformat(),
        "item": selected
    })


@app.post("/api/portal/generate-pitch")
async def generate_pitch(payload: Dict[str, Any]):
    """Generate a high-converting, tailored 1-click cold outreach pitch for a job role."""
    title = (payload.get("title") or "Software Engineer").strip()
    company = (payload.get("company") or "Hiring Team").strip()
    user_name = (payload.get("user_name") or "Candidate").strip()

    linkedin_note = (
        f"Hi {company} Team, I noticed your opening for {title} and was impressed by your team's mission. "
        f"With hands-on experience in building scalable systems and automation, I'd love to connect and share "
        f"how my background aligns with your current priorities. Best, {user_name}"
    )

    cold_email = (
        f"Subject: Application & Quick Introduction – {title} ({user_name})\n\n"
        f"Hi {company} Hiring Team,\n\n"
        f"I came across the {title} role and immediately resonated with the impact your team is creating. "
        f"I bring deep hands-on expertise in full-stack architecture, API integration, and cloud-native solutions, "
        f"and have a proven track record of shipping reliable, performant features.\n\n"
        f"I would welcome 10 minutes to discuss how my skill set can accelerate your current milestones.\n\n"
        f"Portfolio & Resume: [Insert Link]\n"
        f"LinkedIn: [Insert Profile]\n\n"
        f"Best regards,\n{user_name}"
    )

    return JSONResponse({
        "success": True,
        "linkedin_note": linkedin_note,
        "cold_email": cold_email
    })


@app.put("/api/portal/user")
async def update_portal_user(payload: Dict[str, Any]):
    """Allow member to update their own keywords, search queries, locations, source APIs, and vacation mode."""
    email_clean = (payload.get("email") or "").strip().lower()
    if not email_clean:
        return JSONResponse({"error": "Email is required"}, status_code=400)

    if not os.path.exists(RECIPIENTS_FILE):
        return JSONResponse({"error": "Recipients file not found"}, status_code=404)

    with open(RECIPIENTS_FILE, "r", encoding="utf-8") as f:
        subscribers = json.load(f)

    target_idx = next((i for i, s in enumerate(subscribers) if s.get("email", "").strip().lower() == email_clean), None)
    if target_idx is None:
        return JSONResponse({"error": f"Subscriber with email '{email_clean}' not found"}, status_code=404)

    target_sub = subscribers[target_idx]

    # Update allowed self-service fields
    if "keywords" in payload and isinstance(payload["keywords"], list):
        target_sub["keywords"] = [str(k).strip() for k in payload["keywords"] if str(k).strip()]

    if "job_searches" in payload and isinstance(payload["job_searches"], list):
        target_sub["job_searches"] = [str(j).strip() for j in payload["job_searches"] if str(j).strip()]

    if "job_sources" in payload and isinstance(payload["job_sources"], list):
        target_sub["job_sources"] = [str(s).strip() for s in payload["job_sources"] if str(s).strip()]

    if "course_sources" in payload and isinstance(payload["course_sources"], list):
        target_sub["course_sources"] = [str(c).strip() for c in payload["course_sources"] if str(c).strip()]

    if "preferred_locations" in payload and isinstance(payload["preferred_locations"], list):
        target_sub["preferred_locations"] = [str(loc).strip() for loc in payload["preferred_locations"] if str(loc).strip()]

    if "max_items" in payload:
        try:
            val = int(payload["max_items"])
            target_sub["max_items"] = max(1, min(val, 50))
        except (ValueError, TypeError):
            pass

    if "active" in payload:
        target_sub["active"] = bool(payload["active"])

    subscribers[target_idx] = target_sub

    with open(RECIPIENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(subscribers, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return JSONResponse({
        "success": True,
        "message": "Preferences saved successfully!",
        "subscriber": target_sub,
    })


# ============================================================================
# Portal Authentication Endpoints
# ============================================================================

@app.post("/api/portal/auth/login")
async def portal_login(payload: Dict[str, Any], response: fastapi.Response):
    """Member login — email + password → portal_token cookie."""
    email = (payload.get("email") or "").strip().lower()
    password = (payload.get("password") or "").strip()
    if not email or not password:
        return JSONResponse({"error": "Email and password are required"}, status_code=400)

    if not os.path.exists(RECIPIENTS_FILE):
        return JSONResponse({"error": "No subscribers found"}, status_code=404)
    with open(RECIPIENTS_FILE, "r", encoding="utf-8") as f:
        subscribers = json.load(f)

    sub = next((s for s in subscribers if s.get("email", "").strip().lower() == email), None)
    if not sub:
        return JSONResponse({"error": "No account found for that email"}, status_code=401)

    if not _verify_password(sub, password):
        return JSONResponse({"error": "Incorrect password"}, status_code=401)

    token = _create_portal_token(email)
    name = sub.get("name") or email.split("@")[0].title()
    resp = JSONResponse({"success": True, "name": name, "email": email})
    resp.set_cookie("portal_token", token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30)
    return resp


@app.get("/api/portal/auth/me")
async def portal_me(request: fastapi.Request):
    """Return current authenticated portal member info."""
    email = _get_portal_email(request)
    if not email:
        return JSONResponse({"authenticated": False})
    if not os.path.exists(RECIPIENTS_FILE):
        return JSONResponse({"authenticated": False})
    with open(RECIPIENTS_FILE, "r", encoding="utf-8") as f:
        subscribers = json.load(f)
    sub = next((s for s in subscribers if s.get("email", "").strip().lower() == email), None)
    if not sub:
        return JSONResponse({"authenticated": False})
    name = sub.get("name") or email.split("@")[0].title()
    return JSONResponse({"authenticated": True, "email": email, "name": name})


@app.post("/api/portal/auth/logout")
async def portal_logout(request: fastapi.Request, response: fastapi.Response):
    """Invalidate portal session."""
    token = request.cookies.get("portal_token", "")
    _PORTAL_SESSIONS.pop(token, None)
    resp = JSONResponse({"success": True})
    resp.delete_cookie("portal_token")
    return resp


@app.post("/api/portal/auth/change-password")
async def portal_change_password(request: fastapi.Request, payload: Dict[str, Any]):
    """Allow authenticated member to change their own password."""
    email = _get_portal_email(request)
    if not email:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    old_pw = (payload.get("old_password") or "").strip()
    new_pw = (payload.get("new_password") or "").strip()
    if not old_pw or not new_pw:
        return JSONResponse({"error": "Both old and new passwords are required"}, status_code=400)
    if len(new_pw) < 6:
        return JSONResponse({"error": "New password must be at least 6 characters"}, status_code=400)

    with open(RECIPIENTS_FILE, "r", encoding="utf-8") as f:
        subscribers = json.load(f)
    idx = next((i for i, s in enumerate(subscribers) if s.get("email", "").strip().lower() == email), None)
    if idx is None:
        return JSONResponse({"error": "Account not found"}, status_code=404)

    if not _verify_password(subscribers[idx], old_pw):
        return JSONResponse({"error": "Current password is incorrect"}, status_code=401)

    subscribers[idx]["portal_password"] = _hash_password(new_pw)
    with open(RECIPIENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(subscribers, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return JSONResponse({"success": True, "message": "Password changed successfully!"})


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
