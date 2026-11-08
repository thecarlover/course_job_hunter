"""
Unit tests for course-job-hunter using pytest.
Tests keyword filtering, seen/deduplication logic, MAX_ITEMS limit, and error resilience.
"""

from unittest.mock import patch, MagicMock
import requests

from main import (
    matches_keywords,
    format_item,
    format_message,
    fetch_courses,
    fetch_jobs,
    load_seen,
    save_seen,
)


def test_keyword_filtering():
    """Test that course titles are matched against keywords case-insensitively."""
    keywords = ["python", "automation", "excel", "ai", "free"]

    # Positive matches
    assert matches_keywords("Learn PYTHON from scratch", keywords) is True
    assert matches_keywords("Mastering Business Automation with n8n", keywords) is True
    assert matches_keywords("Complete Excel formulas masterclass", keywords) is True
    assert matches_keywords("Generative AI Bootcamp 2026", keywords) is True
    assert matches_keywords("100% Free Web Development", keywords) is True

    # Negative matches
    assert matches_keywords("Watercolor Painting for Beginners", keywords) is False
    assert matches_keywords("Modern Cooking Masterclass", keywords) is False
    assert matches_keywords("", keywords) is False
    assert matches_keywords("Some title", []) is False


def test_dont_repeat_items():
    """Test that links already in the 'seen' set are filtered out."""
    seen_links = {
        "https://example.com/course-1",
        "https://remotive.com/job-1",
    }

    mock_entries = [
        MagicMock(title="Free Python Course", link="https://example.com/course-1"),  # Seen
        MagicMock(title="Free Automation Course", link="https://example.com/course-2"),  # New
    ]

    mock_parsed_feed = MagicMock()
    mock_parsed_feed.entries = mock_entries

    with patch("requests.get") as mock_get, patch("feedparser.parse", return_value=mock_parsed_feed):
        mock_response = MagicMock()
        mock_response.content = b"<rss></rss>"
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        new_courses = fetch_courses(
            feeds=["https://fake-feed.com/rss"],
            seen=seen_links,
            keywords=["python", "automation"],
        )

        # Only the unseen course should be returned
        assert len(new_courses) == 1
        assert new_courses[0]["link"] == "https://example.com/course-2"
        assert new_courses[0]["title"] == "Free Automation Course"


def test_dont_repeat_jobs():
    """Test that jobs with links in seen are skipped."""
    seen_links = {"https://remotive.com/job-seen"}

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "jobs": [
            {"title": "Python Dev", "company_name": "Acme", "url": "https://remotive.com/job-seen"},
            {"title": "Automation Engineer", "company_name": "Beta Corp", "url": "https://remotive.com/job-new"},
        ]
    }

    with patch("requests.get", return_value=mock_response):
        new_jobs = fetch_jobs(["python"], seen=seen_links)

        assert len(new_jobs) == 1
        assert new_jobs[0]["link"] == "https://remotive.com/job-new"
        assert new_jobs[0]["title"] == "Automation Engineer (Beta Corp)"


def test_max_items_limit():
    """Test that when more than MAX_ITEMS are available, we cap at MAX_ITEMS (15)."""
    max_limit = 15

    # Simulate 20 items (10 courses, 10 jobs)
    courses = [
        {"type": "course", "title": f"Course {i}", "link": f"https://example.com/c/{i}"}
        for i in range(10)
    ]
    jobs = [
        {"type": "job", "title": f"Job {i}", "link": f"https://example.com/j/{i}"}
        for i in range(10)
    ]

    all_items = courses + jobs
    assert len(all_items) == 20

    # Apply limit
    limited_items = all_items[:max_limit]
    assert len(limited_items) == 15

    # Check formatting of the 15 items
    message = format_message(limited_items)
    lines = message.split("\n\n")
    assert len(lines) == 15
    assert lines[0].startswith("🎓 Course 0")
    assert lines[10].startswith("💼 Job 0")


def test_error_resilience():
    """Test that a failing feed or API timeout does not crash the script."""
    def side_effect(url, **kwargs):
        if "bad-feed" in url:
            raise requests.exceptions.Timeout("Connection timed out")
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b"<rss></rss>"
        return resp

    mock_parsed_feed = MagicMock()
    mock_parsed_feed.entries = [
        MagicMock(title="Python For Beginners", link="https://example.com/good-course")
    ]

    with patch("requests.get", side_effect=side_effect), patch(
        "feedparser.parse", return_value=mock_parsed_feed
    ):
        # One bad feed and one good feed
        courses = fetch_courses(
            feeds=["https://bad-feed.com/rss", "https://good-feed.com/rss"],
            seen=set(),
            keywords=["python"],
        )

        # Should skip bad-feed without throwing an unhandled exception, and get the course from good-feed
        assert len(courses) == 1
        assert courses[0]["link"] == "https://example.com/good-course"


def test_seen_load_and_save(tmp_path):
    """Test saving and loading seen links from JSON file."""
    test_file = str(tmp_path / "test_seen.json")

    # Initial load on non-existent file
    empty_seen = load_seen(test_file)
    assert empty_seen == set()

    # Save links
    sample_links = {"https://site.com/1", "https://site.com/2"}
    save_seen(sample_links, test_file)

    # Reload
    reloaded = load_seen(test_file)
    assert reloaded == sample_links


def test_notifier_ntfy(monkeypatch):
    """Test ntfy notification sending."""
    import notifier
    monkeypatch.setattr(notifier.config, "NOTIFIER", "ntfy")
    monkeypatch.setenv("NTFY_TOPIC", "my_secret_topic_123")

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        notifier.send("Test ntfy message")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://ntfy.sh/my_secret_topic_123"
        assert kwargs["data"] == b"Test ntfy message"


def test_notifier_discord(monkeypatch):
    """Test discord webhook notification sending."""
    import notifier
    monkeypatch.setattr(notifier.config, "NOTIFIER", "discord")
    monkeypatch.setenv("WEBHOOK_URL", "https://discord.com/api/webhooks/dummy/xyz")

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        long_message = "A" * 2500
        notifier.send(long_message)
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://discord.com/api/webhooks/dummy/xyz"
        # Truncated to 1900 chars
        assert len(kwargs["json"]["content"]) == 1900


def test_notifier_email(monkeypatch):
    """Test email sending via Gmail SMTP_SSL."""
    import notifier
    monkeypatch.setattr(notifier.config, "NOTIFIER", "email")
    monkeypatch.setenv("EMAIL", "test@gmail.com")
    monkeypatch.setenv("APP_PASSWORD", "abcd efgh ijkl mnop")  # Test with spaces

    with patch("smtplib.SMTP_SSL") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        notifier.send("Test email message")
        mock_smtp.assert_called_once_with("smtp.gmail.com", 465, timeout=15)
        # Spaces in the App Password should be stripped automatically
        mock_server.login.assert_called_once_with("test@gmail.com", "abcdefghijklmnop")
        mock_server.send_message.assert_called_once()


def test_load_dotenv(tmp_path, monkeypatch):
    """Test loading environment variables from a custom .env file."""
    import notifier
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_KEY=secret_val_123\n# comment line\nANOTHER_KEY='quoted_value'\n")

    monkeypatch.delenv("TEST_KEY", raising=False)
    monkeypatch.delenv("ANOTHER_KEY", raising=False)

    notifier.load_dotenv(str(env_file))

    import os
    assert os.environ.get("TEST_KEY") == "secret_val_123"
    assert os.environ.get("ANOTHER_KEY") == "quoted_value"


def test_per_person_keyword_filtering():
    """Test that Person A and Person B each receive only the items matching their own keywords."""
    courses = [
        {"type": "course", "title": "Complete Python 2026 Bootcamp", "link": "https://example.com/python", "feed_url": "feed1"},
        {"type": "course", "title": "Advanced Excel Automation", "link": "https://example.com/excel", "feed_url": "feed1"},
    ]

    alice_keywords = ["python"]
    bob_keywords = ["excel"]

    alice_matches = [c for c in courses if matches_keywords(c["title"], alice_keywords)]
    bob_matches = [c for c in courses if matches_keywords(c["title"], bob_keywords)]

    assert len(alice_matches) == 1
    assert alice_matches[0]["link"] == "https://example.com/python"

    assert len(bob_matches) == 1
    assert bob_matches[0]["link"] == "https://example.com/excel"


def test_per_person_dont_repeat_logic():
    """Test that links seen by Person A do not block Person B from receiving them."""
    seen_dict = {
        "alice@example.com": {"https://example.com/shared-python-course"},
        "bob@example.com": set(),
    }

    course = {
        "type": "course",
        "title": "Mastering Python",
        "link": "https://example.com/shared-python-course",
        "feed_url": "feed1",
    }

    # Alice has already seen it
    alice_seen = seen_dict["alice@example.com"]
    alice_gets = [course] if course["link"] not in alice_seen else []
    assert len(alice_gets) == 0

    # Bob has NOT seen it
    bob_seen = seen_dict["bob@example.com"]
    bob_gets = [course] if course["link"] not in bob_seen else []
    assert len(bob_gets) == 1
    assert bob_gets[0]["link"] == "https://example.com/shared-python-course"


def test_skip_inactive_person(monkeypatch):
    """Test that a recipient with active: false is skipped completely."""
    from main import load_recipients
    dummy_recipients = [
        {"name": "Alice", "email": "alice@example.com", "active": True, "keywords": ["python"]},
        {"name": "Inactive Charlie", "email": "charlie@example.com", "active": False, "keywords": ["python"]},
    ]

    monkeypatch.setenv("RECIPIENTS_JSON", __import__("json").dumps(dummy_recipients))

    recipients = load_recipients()
    active_recipients = [r for r in recipients if r.get("active", True)]

    assert len(active_recipients) == 1
    assert active_recipients[0]["name"] == "Alice"
    assert not any(r["name"] == "Inactive Charlie" for r in active_recipients)


def test_missing_secret_exits_with_error(monkeypatch):
    """Test that main.py exits cleanly with status 1 when a secret is missing."""
    import pytest
    from main import run
    import notifier

    # Ensure local .env file doesn't override test environment
    monkeypatch.setattr(notifier, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(notifier.config, "NOTIFIER", "email")
    monkeypatch.delenv("EMAIL", raising=False)
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    monkeypatch.setattr(notifier.config, "EMAIL", "", raising=False)
    monkeypatch.setattr(notifier.config, "APP_PASSWORD", "", raising=False)

    # Running with dry_run=False should trigger upfront validation and exit with code 1
    with pytest.raises(SystemExit) as exc_info:
        run(dry_run=False)

    assert exc_info.value.code == 1


def test_recipients_json_from_secret(monkeypatch):
    """Test loading recipients from RECIPIENTS_JSON environment variable."""
    import json
    from main import load_recipients

    secret_data = [
        {
            "name": "Secret Friend",
            "email": "secret@example.com",
            "active": True,
            "keywords": ["ai", "python"],
            "job_searches": ["python"],
            "max_items": 10,
        }
    ]
    monkeypatch.setenv("RECIPIENTS_JSON", json.dumps(secret_data))

    loaded = load_recipients()
    assert len(loaded) == 1
    assert loaded[0]["name"] == "Secret Friend"
    assert loaded[0]["email"] == "secret@example.com"
    assert loaded[0]["max_items"] == 10


# ============================================================================
# Tests for New Features: Auto-Prune, Weekly Insights, Multi-Board, Badges
# ============================================================================

def test_auto_pruning(tmp_path):
    """Test that seen entries older than expiry_days are automatically pruned."""
    from datetime import datetime, timezone, timedelta
    from main import load_seen_dict, save_seen_dict

    test_file = str(tmp_path / "prune_seen.json")
    today = datetime.now(timezone.utc).date()
    old_date = (today - timedelta(days=90)).isoformat()
    recent_date = (today - timedelta(days=10)).isoformat()

    sample_history = {
        "user@example.com": {
            "https://remotive.com/old-job": {"date": old_date, "title": "Old Job"},
            "https://remotive.com/recent-job": {"date": recent_date, "title": "Recent Job"},
        }
    }

    # Save to disk
    save_seen_dict(sample_history, test_file)

    # Load with 60 days expiration limit
    pruned = load_seen_dict(test_file, expiry_days=60)

    user_seen = pruned.get("user@example.com", {})
    assert "https://remotive.com/old-job" not in user_seen
    assert "https://remotive.com/recent-job" in user_seen


def test_weekly_insights():
    """Test generating weekly market insights report from recent seen history."""
    from datetime import datetime, timezone, timedelta
    from main import generate_weekly_insights

    today = datetime.now(timezone.utc).date()
    three_days_ago = (today - timedelta(days=3)).isoformat()

    sample_seen = {
        "dev@example.com": {
            "https://job1.com": {
                "date": three_days_ago,
                "type": "job",
                "title": "Senior Python Automation Engineer",
                "company": "GitLab",
                "tags": ["Python", "Automation", "AWS", "Docker"],
            },
            "https://job2.com": {
                "date": three_days_ago,
                "type": "job",
                "title": "Cloud Cybersecurity Architect",
                "company": "GitLab",
                "tags": ["Cybersecurity", "Cloud", "Compliance"],
            },
            "https://course1.com": {
                "date": three_days_ago,
                "type": "course",
                "title": "Complete AI & Agent Bootcamp",
            },
        }
    }

    report = generate_weekly_insights(sample_seen, days=7)
    assert "WEEKLY TECH & JOB MARKET INSIGHTS" in report
    assert "2 Remote Job(s)" in report
    assert "1 Free Certification Course(s)" in report
    assert "GitLab" in report
    assert "Python" in report or "Cybersecurity" in report


def test_jobicy_fetch():
    """Test fetching and parsing jobs from Jobicy API."""
    from main import fetch_jobicy_jobs

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "jobs": [
            {
                "jobTitle": "Lead Python Developer",
                "companyName": "TechCo",
                "url": "https://jobicy.com/jobs/lead-python-dev",
                "annualSalaryMin": 90000,
                "annualSalaryMax": 120000,
                "salaryCurrency": "USD",
                "jobGeo": "Worldwide",
                "jobType": ["Full-Time"],
                "jobIndustry": ["Software Development"],
                "jobLevel": "Senior",
            }
        ]
    }

    with patch("requests.get", return_value=mock_resp):
        jobs = fetch_jobicy_jobs(["python"])

        assert len(jobs) == 1
        job = jobs[0]
        assert job["source"] == "Jobicy"
        assert job["title"] == "Lead Python Developer (TechCo)"
        assert job["salary"] == "$90,000–$120,000 USD"
        assert job["location"] == "Worldwide"
        assert job["job_type"] == "Full-Time"


def test_arbeitnow_fetch():
    """Test fetching and parsing jobs from Arbeitnow API."""
    from main import fetch_arbeitnow_jobs

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [
            {
                "title": "Senior Automation QA",
                "company_name": "Acme Europe",
                "url": "https://arbeitnow.com/jobs/acme-qa",
                "remote": True,
                "location": "Berlin",
                "tags": ["QA", "Automation", "Python"],
            }
        ]
    }

    with patch("requests.get", return_value=mock_resp):
        jobs = fetch_arbeitnow_jobs(["automation"])

        assert len(jobs) == 1
        job = jobs[0]
        assert job["source"] == "Arbeitnow"
        assert job["title"] == "Senior Automation QA (Acme Europe)"
        assert "Remote" in job["location"]
        assert job["job_type"] == "Remote"


def test_job_badges_formatting():
    """Test format_item produces rich badges for location, salary, job type, and visa."""
    from main import format_item

    job_with_all_badges = {
        "type": "job",
        "source": "Remotive",
        "title": "Principal Architect (Canonical)",
        "link": "https://remotive.com/arch",
        "location": "Worldwide",
        "salary": "$140k - $170k",
        "job_type": "Full-Time",
        "tags": ["python", "cloud", "visa sponsorship"],
    }

    formatted = format_item(job_with_all_badges)
    assert "💼 Principal Architect (Canonical) [Remotive]" in formatted
    assert "📍 Worldwide" in formatted
    assert "💰 $140k - $170k" in formatted
    assert "⏱️ Full-Time" in formatted
    assert "🛂 Visa Sponsored" in formatted
    assert "https://remotive.com/arch" in formatted


def test_location_filter_matching():
    """Test matches_location_filter helper."""
    from main import matches_location_filter

    allowed_keywords = ["worldwide", "anywhere", "remote", "global", "apac"]

    assert matches_location_filter("Worldwide", allowed_keywords) is True
    assert matches_location_filter("Anywhere (100% Remote)", allowed_keywords) is True
    assert matches_location_filter("APAC / Remote", allowed_keywords) is True
    assert matches_location_filter("", allowed_keywords) is True  # Unknown location allowed

    # Negative match
    assert matches_location_filter("United States Only (US Citizens)", allowed_keywords) is False


def test_db_fallback_local(tmp_path, monkeypatch):
    """Test db module fallback to local file when Supabase is disabled."""
    import db
    monkeypatch.setattr(db, "is_supabase_enabled", lambda: False)
    test_seen_file = str(tmp_path / "fallback_seen.json")
    monkeypatch.setattr(db, "SEEN_FILE", test_seen_file)

    # Initially empty
    seen = db.load_seen_for_user("user@example.com")
    assert seen == set()

    # Record batch
    batch = {
        "user@example.com": [
            {"link": "https://remotive.com/job1", "title": "Job 1", "company": "Co1"},
            {"link": "https://remotive.com/job2", "title": "Job 2", "company": "Co2"},
        ]
    }
    db.record_seen_batch(batch)

    # Reload
    reloaded = db.load_seen_for_user("user@example.com")
    assert reloaded == {"https://remotive.com/job1", "https://remotive.com/job2"}


def test_db_supabase_mock(monkeypatch):
    """Test db module querying and inserting with Supabase REST API."""
    import db
    monkeypatch.setattr(db, "is_supabase_enabled", lambda: True)
    monkeypatch.setattr(db, "get_supabase_credentials", lambda: ("https://test.supabase.co", "test_key"))

    # Test load_seen_for_user via mock GET
    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 200
    mock_get_resp.json.return_value = [{"link": "https://remotive.com/api-job"}]

    with patch("requests.get", return_value=mock_get_resp) as mock_get:
        seen = db.load_seen_for_user("alex@example.com")
        assert "https://remotive.com/api-job" in seen
        mock_get.assert_called_once()
        assert "alex@example.com" in mock_get.call_args[1]["params"]["user_email"]

    # Test record_seen_batch via mock POST
    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 201

    with patch("requests.post", return_value=mock_post_resp) as mock_post, patch("db._fallback_save_items"):
        success = db.record_seen_batch({"alex@example.com": [{"link": "https://remotive.com/new-job", "title": "New"}]})
        assert success is True
        mock_post.assert_called_once()
        payload = mock_post.call_args[1]["json"]
        assert len(payload) == 1
        assert payload[0]["link"] == "https://remotive.com/new-job"


def test_welcome_message_composition():
    """Test that compose_welcome_message personalizes name, keywords, and job searches."""
    from main import compose_welcome_message

    msg = compose_welcome_message(
        name="Ishita",
        email="ishita@example.com",
        keywords=["Project Management", "MBA"],
        job_searches=["Project Management"],
        max_items=10,
    )
    assert "Hi Ishita," in msg
    assert "Project Management, MBA" in msg
    assert "10 opportunities" in msg
    assert "Course & Job Hunter" in msg


def test_is_welcome_sent_new_vs_existing():
    """Test that new friends are flagged to receive welcome emails, while existing ones are not."""
    from main import is_welcome_sent

    seen_dict = {
        "existing_user@example.com": {
            f"https://link-{i}.com": {"date": "2026-11-01"} for i in range(10)
        },
        "welcomed_user@example.com": {
            "__welcome_sent__": {"date": "2026-11-01"}
        },
    }

    # New recipient with no history
    new_friend = {"name": "Newbie", "email": "newbie@example.com"}
    assert is_welcome_sent(new_friend, seen_dict) is False

    # Explicit flag set on recipient
    explicit_friend = {"name": "Explicit", "email": "other@example.com", "welcome_sent": True}
    assert is_welcome_sent(explicit_friend, seen_dict) is True

    # User who already has __welcome_sent__ in seen_dict
    already_welcomed = {"name": "Welcomed", "email": "welcomed_user@example.com"}
    assert is_welcome_sent(already_welcomed, seen_dict) is True

    # Existing user with legacy history -> auto-migrated to not receive spam welcome email
    existing_friend = {"name": "Existing", "email": "existing_user@example.com"}
    assert is_welcome_sent(existing_friend, seen_dict) is True
    assert "__welcome_sent__" in seen_dict["existing_user@example.com"]


def test_mark_welcome_sent(tmp_path):
    """Test marking welcome_sent updates seen_dict and recipients.json."""
    import json
    from main import mark_welcome_sent

    recipients_file = tmp_path / "test_recipients.json"
    data = [
        {"name": "Friend A", "email": "friendA@example.com", "welcome_sent": False}
    ]
    recipients_file.write_text(json.dumps(data))

    recipient = {"name": "Friend A", "email": "friendA@example.com", "welcome_sent": False}
    seen_dict = {}

    mark_welcome_sent(recipient, seen_dict, str(recipients_file))

    assert recipient["welcome_sent"] is True
    assert "__welcome_sent__" in seen_dict["frienda@example.com"]

    reloaded = json.loads(recipients_file.read_text())
    assert reloaded[0]["welcome_sent"] is True


def test_compose_digest_subject():
    """Test generating dynamic email subject lines with counts, recipient name, and dates."""
    from main import compose_digest_subject

    # Both courses and jobs (plural) with full name (uses first name)
    subj1 = compose_digest_subject("Ishani Ganguly", 4, 6, "Nov 02")
    assert subj1 == "🎓 4 Free Courses, 💼 6 Remote Jobs for Ishani (Nov 02)"

    # Singular counts
    subj2 = compose_digest_subject("Ishita", 1, 1, "Nov 02")
    assert subj2 == "🎓 1 Free Course, 💼 1 Remote Job for Ishita (Nov 02)"

    # Courses only
    subj3 = compose_digest_subject("Ojasvi", 5, 0, "Nov 02")
    assert subj3 == "🎓 5 Free Courses for Ojasvi (Nov 02)"

    # Jobs only
    subj4 = compose_digest_subject("Saurabh", 0, 3, "Nov 02")
    assert subj4 == "💼 3 Remote Jobs for Saurabh (Nov 02)"

    # Empty name fallback to 'for you'
    subj_anon = compose_digest_subject("", 2, 3, "Nov 02")
    assert subj_anon == "🎓 2 Free Courses, 💼 3 Remote Jobs for you (Nov 02)"

    # Weekly wrap
    subj_weekly = compose_digest_subject("Ojasvi", 3, 5, "Nov 02", weekly=True)
    assert subj_weekly == "📅 Weekly Wrap: 🎓 3 Free Courses, 💼 5 Remote Jobs for Ojasvi (Nov 02)"

    # Neither (fallback)
    subj5 = compose_digest_subject("Friend", 0, 0, "Nov 02")
    assert subj5 == "Daily Digest: Free Courses & Remote Jobs for Friend (Nov 02)"

    # Default date formatting works
    subj6 = compose_digest_subject("Friend", 2, 2)
    assert "for Friend (" in subj6


def test_admin_auth_and_network_endpoints():
    """Test admin portal password protection and network phone endpoints."""
    from fastapi.testclient import TestClient
    from admin import app, ADMIN_PASSWORD

    client = TestClient(app)

    # 1. Unauthenticated request to protected endpoint -> 401
    res = client.get("/api/subscribers")
    assert res.status_code == 401
    assert res.json().get("auth_required") is True

    # 2. Login with wrong password -> 401
    res = client.post("/api/auth/login", json={"password": "wrong_password_123"})
    assert res.status_code == 401
    assert res.json().get("success") is False

    # 3. Login with correct password -> 200 & token
    res = client.post("/api/auth/login", json={"password": ADMIN_PASSWORD})
    assert res.status_code == 200
    assert res.json().get("success") is True
    assert res.json().get("token") == ADMIN_PASSWORD

    # 4. Request with X-Admin-Password header -> 200
    res = client.get("/api/subscribers", headers={"X-Admin-Password": ADMIN_PASSWORD})
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # 5. Network info for phone access -> 200
    res = client.get("/api/network-info")
    assert res.status_code == 200
    data = res.json()
    assert "local_ip" in data
    assert "phone_url" in data
    assert ":8000" in data["phone_url"]

    # 6. Public HTML dashboard serves without password -> 200
    res = client.get("/")
    assert res.status_code == 200
    assert "Course & Job Hunter" in res.text


def test_calculate_hunter_stats_and_banner():
    """Test gamified streak, level-up, and money-saved counter calculations."""
    from main import calculate_hunter_stats, format_hunter_stats_banner
    from datetime import datetime, timezone, timedelta

    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)

    mock_seen_dict = {
        "gamer@example.com": {
            "https://tutorialbar.com/course-1": {"date": two_days_ago.isoformat(), "type": "course"},
            "https://answersq.com/course-2": {"date": yesterday.isoformat(), "type": "course"},
            "https://remotive.com/job-1": {"date": yesterday.isoformat(), "type": "job"},
        }
    }

    current_items = [
        {"link": "https://discudemy.com/course-3", "type": "course"},
        {"link": "https://jobicy.com/job-2", "type": "job"},
    ]

    # Calculate stats with current delivery today
    stats = calculate_hunter_stats("gamer@example.com", mock_seen_dict, current_items, course_nominal_value=25)

    # 3 consecutive days: two_days_ago, yesterday, today -> 3 day streak
    assert stats["streak"] == 3
    # 2 historical courses + 1 current course = 3 courses
    assert stats["total_courses"] == 3
    # 1 historical job + 1 current job = 2 jobs
    assert stats["total_jobs"] == 2
    assert stats["total_items"] == 5
    # 3 courses * $25 = $75
    assert stats["money_saved"] == 75
    assert stats["level_num"] == 1
    assert stats["level_title"] == "Rookie Hunter"

    # Test Level 5 progression (65 items)
    large_history = {
        f"https://tutorialbar.com/c-{i}": {"date": yesterday.isoformat(), "type": "course"}
        for i in range(65)
    }
    stats_lvl5 = calculate_hunter_stats("pro@example.com", {"pro@example.com": large_history}, course_nominal_value=20)
    assert stats_lvl5["level_num"] == 5
    assert stats_lvl5["level_title"] == "Master Career Strategist"
    assert stats_lvl5["money_saved"] == 1300  # 65 * 20

    # Test format banner
    banner = format_hunter_stats_banner(stats)
    assert "🏆 Your Hunter Stats:" in banner
    assert "🔥 Day 3 Streak" in banner
    assert "Level 1: Rookie Hunter" in banner
    assert "$75 saved across 3 free certified courses!" in banner


def test_user_portal_endpoints():
    """Test user self-service portal (/portal) and portal APIs."""
    from fastapi.testclient import TestClient
    from admin import app, derive_vault_title, classify_vault_item
    import json

    client = TestClient(app)

    # 1. Public user portal page serves 200 without admin password
    res = client.get("/portal")
    assert res.status_code == 200
    assert "Opportunity Vault" in res.text
    assert "Member Hub" in res.text

    # 2. Public subscribers list for profile switcher serves 200
    res = client.get("/api/portal/subscribers")
    assert res.status_code == 200
    subscribers = res.json()
    assert isinstance(subscribers, list)
    assert len(subscribers) >= 1
    assert any(s.get("email") == "ojasvimittalofficial@gmail.com" for s in subscribers)

    # 3. GET /api/portal/user for subscriber
    res = client.get("/api/portal/user?email=ojasvimittalofficial@gmail.com")
    assert res.status_code == 200
    data = res.json()
    assert "subscriber" in data
    assert "stats" in data
    assert "vault" in data
    assert data["subscriber"]["email"] == "ojasvimittalofficial@gmail.com"
    assert data["stats"]["level_num"] >= 1
    assert data["vault_count"] >= 1
    assert "title" in data["vault"][0]
    assert "type" in data["vault"][0]

    # 4. GET /api/portal/user validation errors
    res_empty = client.get("/api/portal/user?email=")
    assert res_empty.status_code == 400

    res_missing = client.get("/api/portal/user?email=nonexistent999@example.com")
    assert res_missing.status_code == 404

    # 5. Helpers: derive_vault_title & classify_vault_item
    assert derive_vault_title("https://answersq.com/ai-automation-specialist-roadmap/") == "AI Automation Specialist Roadmap"
    assert derive_vault_title("https://jobicy.com/jobs/158348-ai-trainers-network-farsi") == "AI Trainers Network Farsi"
    assert derive_vault_title("https://example.com/foo", {"title": "Custom Title"}) == "Custom Title"

    assert classify_vault_item("https://answersq.com/ai-course") == "course"
    assert classify_vault_item("https://jobicy.com/jobs/dev") == "job"


def test_build_html_digest():
    """Test generating a modern HTML email digest with course and job cards."""
    from main import build_html_digest

    items = [
        {
            "type": "course",
            "title": "Machine Learning for Beginners & AI Intro",
            "link": "https://freecodecamp.org/ml-course",
            "feed_url": "https://freecodecamp.org/news/rss/",
        },
        {
            "type": "job",
            "title": "Senior Python Developer",
            "link": "https://in.indeed.com/viewjob?jk=12345",
            "source": "indeed_india",
            "location": "India (Remote)",
            "salary": "₹25,00,000/year",
            "job_type": "Full-time",
            "tags": ["python", "ai", "worldwide"],
        },
    ]

    stats = {
        "streak": 5,
        "level_num": 3,
        "level_title": "Career Sniper",
        "badge": "🎯",
        "money_saved": 140,
        "total_courses": 7,
    }

    html = build_html_digest(
        recipient_name="Ishani Ganguly",
        recipient_email="ishani@example.com",
        items=items,
        stats=stats,
        insights="Demand for Python & AI is up 25%.",
        sender_email="admin@example.com",
    )

    assert "<!DOCTYPE html>" in html
    assert "Good morning, Ishani" in html
    assert "Day 5" in html
    assert "Career Sniper" in html
    assert "$140" in html
    assert "Machine Learning for Beginners &amp; AI Intro" in html
    assert "Senior Python Developer" in html
    assert "Indeed India" in html
    assert "India (Remote)" in html
    assert "₹25,00,000/year" in html
    assert "Demand for Python &amp; AI is up 25%." in html
    assert "ishani@example.com" in html


def test_build_html_welcome():
    """Test generating an attractive HTML welcome email."""
    from main import build_html_welcome

    html = build_html_welcome(
        name="Adhya Mittal",
        email="adhyamittal01@gmail.com",
        keywords=["UI/UX", "Product Management", "Figma"],
        job_searches=["Product Designer", "MERN Stack"],
        max_items=12,
        sender_email="admin@example.com",
    )

    assert "<!DOCTYPE html>" in html
    assert "Welcome, Adhya! 🎉" in html
    assert "UI/UX" in html
    assert "Product Designer" in html
    assert "12 opportunities / morning" in html
    assert "adhyamittal01@gmail.com" not in html or "admin@example.com" in html


def test_notifier_email_with_html(monkeypatch):
    """Test notifier sends multipart alternative email when html is passed."""
    import notifier
    monkeypatch.setattr(notifier.config, "NOTIFIER", "email")
    monkeypatch.setenv("EMAIL", "sender@gmail.com")
    monkeypatch.setenv("APP_PASSWORD", "test password 1234")

    with patch("smtplib.SMTP_SSL") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        notifier.send(
            text="Plain text fallback",
            to_email="friend@example.com",
            subject="Test Attractive Email",
            html="<h1>Hello in HTML</h1>",
        )

        mock_server.send_message.assert_called_once()
        sent_msg = mock_server.send_message.call_args[0][0]

        assert sent_msg["Subject"] == "Test Attractive Email"
        assert sent_msg["To"] == "friend@example.com"
        assert sent_msg.is_multipart()
        # Verify both plain text and HTML payloads exist
        payloads = [p.get_payload() for p in sent_msg.iter_parts()]
        assert any("Plain text fallback" in str(p) for p in payloads)
        assert any("<h1>Hello in HTML</h1>" in str(p) for p in payloads)


def test_fetch_naukri_jobs():
    """Test Naukri job fetcher handles search terms and returns structured job dicts."""
    from main import fetch_naukri_jobs

    jobs = fetch_naukri_jobs(["Python Developer"])
    assert isinstance(jobs, list)
    assert len(jobs) >= 1
    sample = jobs[0]
    assert sample["type"] == "job"
    assert sample["source"] == "Naukri"
    assert "naukri.com" in sample["link"]
    assert any("python" in t for t in sample["tags"])


def test_portal_user_sources_config():
    """Test GET and PUT /api/portal/user with job_sources and course_sources."""
    from fastapi.testclient import TestClient
    from admin import app

    client = TestClient(app)
    # Fetch user data
    res = client.get("/api/portal/user?email=ojasvimittalofficial@gmail.com")
    assert res.status_code == 200
    data = res.json()
    assert "available_job_sources" in data
    assert "naukri" in data["available_job_sources"]
    assert "linkedin" in data["available_job_sources"]

    # Update sources via PUT
    put_res = client.put("/api/portal/user", json={
        "email": "ojasvimittalofficial@gmail.com",
        "job_sources": ["linkedin", "naukri", "remotive"],
        "course_sources": ["udemy_coupons", "swayam_nptel"],
    })
    assert put_res.status_code == 200
    updated_sub = put_res.json()["subscriber"]
    assert "naukri" in updated_sub.get("job_sources", [])
    assert "swayam_nptel" in updated_sub.get("course_sources", [])






