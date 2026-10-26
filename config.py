"""
Configuration settings for course-job-hunter.

Customize your sources, keywords, limits, and notification channel here.
"""

# RSS feeds for free courses (add any standard RSS/Atom URL)
COURSE_FEEDS = [
    "https://www.reddit.com/r/udemyfreebies/.rss",
]

# Remote job search terms for Remotive API (https://remotive.com/api/remote-jobs)
JOB_SEARCHES = [
    "python",
    "automation",
]

# Keywords to match in course titles (case-insensitive)
KEYWORDS = [
    "python",
    "automation",
    "excel",
    "ai",
    "linkedin",
    "free",
]

# Maximum total items (courses + jobs) to send in a single daily digest
MAX_ITEMS = 15

# Notification service to use.
# Options: "email", "ntfy", "discord"
NOTIFIER = "email"
