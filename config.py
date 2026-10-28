"""
Configuration settings for course-job-hunter.

Customize your sources, keywords, limits, and notification channel here.
"""

# RSS feeds for free courses and certifications
# Includes Reddit plus dedicated free course platforms and learning hubs
COURSE_FEEDS = [
    # Reddit Udemy Freebies
    "https://www.reddit.com/r/udemyfreebies/.rss",
    # TutorialBar (Daily 100% OFF coupons for Udemy, tech, business & management)
    "https://tutorialbar.com/feed/",
    # Discudemy (Curated 100% free courses across programming, AI, IT, Excel, etc.)
    "https://www.discudemy.com/feed",
    # freeCodeCamp (Top-tier free programming, Python, AI, security & DevOps tutorials)
    "https://www.freecodecamp.org/news/rss/",
    # AnswersQ (Free certificates, Coursera/Google courses & tech roadmaps)
    "https://answersq.com/feed/",
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
