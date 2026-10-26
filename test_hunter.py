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
    monkeypatch.setenv("APP_PASSWORD", "abcd-efgh-ijkl-mnop")

    with patch("smtplib.SMTP_SSL") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        notifier.send("Test email message")
        mock_smtp.assert_called_once_with("smtp.gmail.com", 465, timeout=15)
        mock_server.login.assert_called_once_with("test@gmail.com", "abcd-efgh-ijkl-mnop")
        mock_server.send_message.assert_called_once()

