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

# ============================================================================
# Feature 1: Auto-Pruning
# ============================================================================
# Automatically prune links from seen.json older than this number of days
SEEN_EXPIRY_DAYS = 60

# ============================================================================
# Feature 2: Weekly Market & Skills Insights
# ============================================================================
# Generate and send weekly tech/skills in demand summary
ENABLE_WEEKLY_INSIGHTS = True
# Day of week to automatically send weekly insights (e.g. "Sunday")
WEEKLY_INSIGHTS_DAY = "Sunday"

# ============================================================================
# Feature 3: Multi-Board Job Aggregation (Free APIs)
# ============================================================================
# Enabled job board sources (all free APIs, no API keys required)
# Options: "remotive", "jobicy", "arbeitnow"
JOB_SOURCES = [
    "remotive",
    "jobicy",
    "arbeitnow",
]

# ============================================================================
# Feature 4: Salary, Location & Visa Filtering
# ============================================================================
# Preferred location keywords for remote roles (case-insensitive)
PREFERRED_LOCATIONS = [
    "worldwide",
    "anywhere",
    "remote",
    "global",
    "apac",
    "india",
]
# If True, only keep jobs whose location matches PREFERRED_LOCATIONS
# If False, keep all jobs and display location/salary/visa badges prominently
STRICT_LOCATION_FILTER = False

# ============================================================================
# Cloud Database Settings (Supabase)
# ============================================================================
# The bot automatically stores seen history in Supabase (PostgreSQL) instead of Git.
# Reads from SUPABASE_URL and SUPABASE_KEY environment variables first, or fallback here:
SUPABASE_URL = "https://totcwrqgyrdwuylgyccb.supabase.co"
SUPABASE_KEY = "sb_publishable_i8emK6yLcbCARlWWyc1X1Q_PSJRgeZ6"

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
