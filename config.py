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
    "project management",
    "automation",
    "Cybersecurity",
    "Regulatory",
    "compliance",
]

# Keywords to match in course titles (case-insensitive)
KEYWORDS = [
    "project management",
    "automation",
    "excel",
    "ai",
    "linkedin",
    "free",
    "security",
    "Project",
    "Compliance",

]

# Maximum total items (courses + jobs) to send in a single daily digest
MAX_ITEMS = 15

# Notification service to use.
# Options: "email", "ntfy", "discord"
NOTIFIER = "email"

# Credentials for the notification services are loaded automatically from:
# 1. Environment variables, or
# 2. A local .env file in the root folder (recommended for local development):
#      EMAIL=yourname@gmail.com
#      APP_PASSWORD=xxxx xxxx xxxx xxxx
#      NTFY_TOPIC=your-custom-topic
#      WEBHOOK_URL=https://discord.com/api/webhooks/...
# 3. Or you can optionally define fallback defaults here (keep file private if using secrets):
# EMAIL = ""
# APP_PASSWORD = ""
# NTFY_TOPIC = ""
# WEBHOOK_URL = ""
