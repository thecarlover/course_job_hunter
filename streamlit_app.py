"""
Streamlit Cloud & Local Deployment Application for Course & Job Hunter.

Provides an interactive dashboard for:
- 🎓 Member Opportunity Vault (Browse courses & jobs per subscriber with filters)
- 🚀 Engine Test Runner (Dry run and live runs with real-time logs)
- 👥 Subscriber Preferences (Tailor keywords, search terms, and vacation mode)
- 📡 Source Health Inspector (Live check RSS feeds & India/Global job boards)
- 📊 Weekly Market Trends (Sunday report generator & skill demand explorer)
"""

import contextlib
import io
import json
import os
import sys
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

# Configure page
st.set_page_config(
    page_title="Course & Job Hunter",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sync Streamlit secrets to environment variables if deployed to Streamlit Cloud
try:
    for k in [
        "EMAIL",
        "APP_PASSWORD",
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "ADMIN_PASSWORD",
        "NOTIFIER",
        "NTFY_TOPIC",
        "WEBHOOK_URL",
        "PORTAL_SECRET_KEY",
    ]:
        if k in st.secrets and k not in os.environ:
            os.environ[k] = str(st.secrets[k])
except Exception:
    pass

import config
import db
import main
import notifier

notifier.load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RECIPIENTS_FILE = os.path.join(BASE_DIR, "recipients.json")
SEEN_FILE = os.path.join(BASE_DIR, "seen.json")
ADMIN_PASSWORD = (os.environ.get("ADMIN_PASSWORD") or "hunter2026").strip()


# ============================================================================
# Helpers
# ============================================================================

def classify_vault_item(url: str, meta: Optional[Dict[str, Any]] = None) -> str:
    if meta and meta.get("type"):
        return str(meta["type"])
    u = (url or "").lower()
    course_domains = [
        "answersq", "tutorialbar", "discudemy", "freecodecamp",
        "udemy", "coursetegg", "learnviral", "swayam", "nptel", "geeksforgeeks"
    ]
    if any(cd in u for cd in course_domains):
        return "course"
    return "job"


def derive_vault_title(url: str, meta: Optional[Dict[str, Any]] = None) -> str:
    if meta and meta.get("title"):
        return str(meta["title"])
    try:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.rstrip("/")
        slug = path.split("/")[-1] if path else parsed.netloc
        title = slug.replace("-", " ").replace("_", " ").title()
        return title or url
    except Exception:
        return url


def load_all_subscribers() -> List[Dict[str, Any]]:
    if not os.path.exists(RECIPIENTS_FILE):
        return []
    try:
        with open(RECIPIENTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_subscribers(subs: List[Dict[str, Any]]) -> None:
    with open(RECIPIENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(subs, f, indent=2, ensure_ascii=False)
        f.write("\n")


# ============================================================================
# Sidebar & Navigation
# ============================================================================

st.sidebar.markdown("## 🎯 Course & Job Hunter")
st.sidebar.caption("Automated Free Courses & Remote Opportunities")

nav_page = st.sidebar.radio(
    "Navigation",
    [
        "🎓 Opportunity Vault",
        "🚀 Run Digest Engine",
        "👥 Subscribers & Preferences",
        "📡 Source Health Inspector",
        "📊 Weekly Market Insights",
        "☁️ Cloud Database Explorer",
    ],
    index=0,
)

st.sidebar.divider()

# Cloud DB & Environment Badge
supabase_active = db.is_supabase_enabled()
if supabase_active:
    st.sidebar.success("☁️ Supabase Cloud DB: Connected")
else:
    st.sidebar.info("📁 Storage: Local seen.json")

st.sidebar.caption("Course & Job Hunter · Streamlit Cloud Edition")


# ============================================================================
# Page 1: Opportunity Vault (Member View)
# ============================================================================

if nav_page == "🎓 Opportunity Vault":
    st.title("🎓 Opportunity Vault & Member Hub")
    st.write("Browse curated courses and remote jobs delivered to group members.")

    subscribers = load_all_subscribers()
    if not subscribers:
        st.warning("No subscribers found in recipients.json.")
        st.stop()

    sub_options = {f"{s.get('name', 'Friend')} ({s.get('email')})": s for s in subscribers}
    selected_label = st.selectbox("Select Member", list(sub_options.keys()))
    selected_sub = sub_options[selected_label]
    user_email = selected_sub.get("email", "").strip().lower()

    # Load seen data & calculate stats
    seen_dict = main.load_seen_dict()
    stats = main.calculate_hunter_stats(user_email, seen_dict)

    # Gamification Stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🔥 Active Streak", f"Day {stats.get('streak', 1)}")
    with col2:
        st.metric(f"{stats.get('badge', '🌱')} Rank", f"Lvl {stats.get('level_num', 1)}: {stats.get('level_title', 'Rookie')}")
    with col3:
        st.metric("💰 Value Unlocked", f"${stats.get('money_saved', 0)}")
    with col4:
        st.metric("📦 Total Delivered", f"{stats.get('total_items', 0)} items")

    st.divider()

    # Build member vault
    raw_history = seen_dict.get(user_email, {}) if isinstance(seen_dict, dict) else {}
    vault_items = []

    for url, meta in raw_history.items():
        if not url or str(url).startswith("__"):
            continue
        item_meta = meta if isinstance(meta, dict) else {}
        item_type = item_meta.get("type") or classify_vault_item(url, item_meta)
        title = derive_vault_title(url, item_meta)
        date_str = item_meta.get("date") or "Earlier"
        domain = urllib.parse.urlparse(url).netloc.replace("www.", "")

        vault_items.append({
            "url": url,
            "title": title,
            "type": item_type,
            "date": date_str,
            "domain": domain,
            "location": item_meta.get("location"),
            "salary": item_meta.get("salary"),
        })

    # Sort descending by date
    vault_items.sort(key=lambda x: str(x.get("date", "")), reverse=True)

    courses = [it for it in vault_items if it["type"] == "course"]
    jobs = [it for it in vault_items if it["type"] == "job"]

    tab_courses, tab_jobs = st.tabs([f"📚 Courses ({len(courses)})", f"💼 Jobs ({len(jobs)})"])

    with tab_courses:
        search_course = st.text_input("🔍 Search Courses", placeholder="Filter by title or platform…", key="search_course")
        filtered_courses = courses
        if search_course:
            q = search_course.strip().lower()
            filtered_courses = [c for c in courses if q in c["title"].lower() or q in c["domain"].lower()]

        if not filtered_courses:
            st.info("No courses match your filter.")
        else:
            for c in filtered_courses:
                with st.container(border=True):
                    c_col1, c_col2 = st.columns([5, 1])
                    with c_col1:
                        st.markdown(f"**[{c['title']}]({c['url']})**")
                        st.caption(f"🎓 100% Free · 🌐 {c['domain']} · 📅 {c['date']}")
                    with c_col2:
                        st.link_button("Open ↗", c["url"], use_container_width=True)

    with tab_jobs:
        search_job = st.text_input("🔍 Search Jobs", placeholder="Filter by title, company, or location…", key="search_job")
        filtered_jobs = jobs
        if search_job:
            q = search_job.strip().lower()
            filtered_jobs = [j for j in jobs if q in j["title"].lower() or q in j["domain"].lower() or (j["location"] and q in j["location"].lower())]

        if not filtered_jobs:
            st.info("No jobs match your filter.")
        else:
            for j in filtered_jobs:
                with st.container(border=True):
                    j_col1, j_col2 = st.columns([5, 1])
                    with j_col1:
                        st.markdown(f"**[{j['title']}]({j['url']})**")
                        loc_str = f" · 📍 {j['location']}" if j.get("location") else ""
                        sal_str = f" · 💰 {j['salary']}" if j.get("salary") else ""
                        st.caption(f"💼 Remote Job · 🌐 {j['domain']}{loc_str}{sal_str} · 📅 {j['date']}")
                    with j_col2:
                        st.link_button("Apply ↗", j["url"], use_container_width=True)


# ============================================================================
# Page 2: Run Digest Engine
# ============================================================================

elif nav_page == "🚀 Run Digest Engine":
    st.title("🚀 Run Digest Engine")
    st.write("Trigger the harvester pipeline to scan RSS feeds & job boards and generate digests.")

    subscribers = load_all_subscribers()
    recipient_options = ["ALL Subscribers"] + [s.get("email") for s in subscribers if s.get("email")]

    col_a, col_b = st.columns(2)
    with col_a:
        run_mode = st.radio("Execution Mode", ["Dry Run (Safe Simulation - No Emails Sent)", "Live Run (Send Actual Emails)"])
        is_dry_run = "Dry Run" in run_mode
    with col_b:
        target_selection = st.selectbox("Target Recipient", recipient_options)
        trigger_weekly = st.checkbox("Include Weekly Insights Report", value=False)

    if not is_dry_run:
        admin_pass_input = st.text_input("Admin Password (Required for Live Email Sending)", type="password")

    if st.button("🚀 Start Engine Execution", type="primary", use_container_width=True):
        if not is_dry_run and admin_pass_input != ADMIN_PASSWORD:
            st.error("Invalid Admin Password. Live sending prevented.")
            st.stop()

        target_recipients = None
        if target_selection != "ALL Subscribers":
            target_recipients = [s for s in subscribers if s.get("email") == target_selection]

        log_buffer = io.StringIO()
        with st.spinner("Harvesting courses and jobs..."):
            with contextlib.redirect_stdout(log_buffer):
                try:
                    main.run(
                        dry_run=is_dry_run,
                        weekly=trigger_weekly,
                        target_recipients=target_recipients,
                    )
                except Exception as e:
                    print(f"[Execution Error]: {e}")

        logs = log_buffer.getvalue()
        st.success("Execution completed!")

        st.subheader("Console Output")
        st.code(logs, language="text")


# ============================================================================
# Page 3: Subscribers & Preferences
# ============================================================================

elif nav_page == "👥 Subscribers & Preferences":
    st.title("👥 Subscribers & Tailored Preferences")
    st.write("Manage group members, keyword filters, and delivery preferences.")

    subscribers = load_all_subscribers()

    # Add new friend expander
    with st.expander("➕ Add New Friend to the Radar"):
        with st.form("add_friend_form", clear_on_submit=True):
            f_name = st.text_input("Name", placeholder="e.g. Ishita")
            f_email = st.text_input("Email", placeholder="e.g. ishita@example.com")
            f_keywords = st.text_area("Course Keywords (comma separated)", "python, ai, project management, excel")
            f_searches = st.text_area("Job Searches (comma separated)", "remote, python, product manager")
            f_max = st.number_input("Max Items Daily", min_value=1, max_value=50, value=15)
            f_submitted = st.form_submit_button("Add Subscriber")

            if f_submitted:
                if not f_email.strip() or not f_name.strip():
                    st.error("Name and Email are required.")
                elif any(s.get("email", "").lower() == f_email.strip().lower() for s in subscribers):
                    st.error(f"Subscriber with email '{f_email}' already exists.")
                else:
                    new_sub = {
                        "name": f_name.strip(),
                        "email": f_email.strip().lower(),
                        "active": True,
                        "keywords": [k.strip() for k in f_keywords.split(",") if k.strip()],
                        "job_searches": [j.strip() for j in f_searches.split(",") if j.strip()],
                        "course_feeds": [],
                        "max_items": int(f_max),
                        "welcome_sent": False,
                    }
                    subscribers.append(new_sub)
                    save_subscribers(subscribers)
                    st.success(f"Added {f_name} successfully! A welcome email will be sent on their first run.")
                    st.rerun()

    st.subheader(f"Current Subscribers ({len(subscribers)})")
    for idx, sub in enumerate(subscribers):
        with st.expander(f"{'🟢' if sub.get('active', True) else '⏸️'} {sub.get('name', 'Friend')} ({sub.get('email')})", expanded=False):
            with st.form(f"edit_sub_{idx}"):
                col1, col2 = st.columns(2)
                with col1:
                    name_val = st.text_input("Name", value=sub.get("name", ""), key=f"name_{idx}")
                    active_val = st.checkbox("Active (Daily Morning Digests)", value=sub.get("active", True), key=f"active_{idx}")
                    max_val = st.number_input("Max Items Daily", min_value=1, max_value=50, value=sub.get("max_items", 15), key=f"max_{idx}")
                with col2:
                    kws = ", ".join(sub.get("keywords", []))
                    kw_val = st.text_area("Keywords (Course Match)", value=kws, key=f"kw_{idx}")
                    searches = ", ".join(sub.get("job_searches", []))
                    search_val = st.text_area("Job Searches", value=searches, key=f"search_{idx}")

                # Source APIs Customization
                all_job_opts = list(getattr(config, "AVAILABLE_JOB_SOURCES", {}).keys())
                cur_job_sources = sub.get("job_sources") if sub.get("job_sources") else all_job_opts
                # Filter to only valid options
                cur_job_sources = [s for s in cur_job_sources if s in all_job_opts]
                selected_jobs = st.multiselect(
                    "Job Board Sources",
                    all_job_opts,
                    default=cur_job_sources,
                    format_func=lambda k: getattr(config, "AVAILABLE_JOB_SOURCES", {}).get(k, k),
                    key=f"jobs_{idx}"
                )

                all_course_opts = list(getattr(config, "AVAILABLE_COURSE_PLATFORMS", {}).keys())
                cur_course_sources = sub.get("course_sources") if sub.get("course_sources") else all_course_opts
                cur_course_sources = [c for c in cur_course_sources if c in all_course_opts]
                selected_courses = st.multiselect(
                    "Course Platforms",
                    all_course_opts,
                    default=cur_course_sources,
                    format_func=lambda k: getattr(config, "AVAILABLE_COURSE_PLATFORMS", {}).get(k, k),
                    key=f"courses_{idx}"
                )

                sub_col1, sub_col2 = st.columns([1, 4])
                with sub_col1:
                    save_btn = st.form_submit_button("Save Changes")
                if save_btn:
                    subscribers[idx]["name"] = name_val.strip()
                    subscribers[idx]["active"] = bool(active_val)
                    subscribers[idx]["max_items"] = int(max_val)
                    subscribers[idx]["keywords"] = [k.strip() for k in kw_val.split(",") if k.strip()]
                    subscribers[idx]["job_searches"] = [j.strip() for j in search_val.split(",") if j.strip()]
                    subscribers[idx]["job_sources"] = selected_jobs
                    subscribers[idx]["course_sources"] = selected_courses
                    save_subscribers(subscribers)
                    st.success("Preferences updated!")
                    st.rerun()


# ============================================================================
# Page 4: Source Health Inspector
# ============================================================================

elif nav_page == "📡 Source Health Inspector":
    st.title("📡 Live Source Health Inspector")
    st.write("Test connectivity to all configured free course RSS feeds and job board APIs.")

    if st.button("🔄 Test All Sources Live", type="primary"):
        with st.spinner("Testing sources..."):
            feeds = getattr(config, "COURSE_FEEDS", [])
            st.subheader(f"📚 Course Feeds ({len(feeds)})")
            for url in feeds:
                try:
                    res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
                    if res.status_code == 200:
                        st.success(f"🟢 **{url}** (HTTP {res.status_code})")
                    else:
                        st.warning(f"🟡 **{url}** (HTTP {res.status_code})")
                except Exception as e:
                    st.error(f"🔴 **{url}** (Error: {e})")

            st.divider()
            st.subheader("💼 Remote & India Job Board APIs")
            job_tests = [
                ("LinkedIn Jobs (India & Global)", "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=python&location=India&f_WT=2&start=0"),
                ("Naukri.com (India)", "https://www.naukri.com/python-jobs"),
                ("Remotive API", "https://remotive.com/api/remote-jobs?limit=2"),
                ("Jobicy API", "https://jobicy.com/api/v2/remote-jobs?count=2"),
                ("Arbeitnow API", "https://www.arbeitnow.com/api/job-board-api"),
                ("Glassdoor India RSS", "https://www.glassdoor.co.in/Job/python-jobs-SRCH_KO0,6.htm?format=rss"),
                ("Adzuna India RSS", "https://www.adzuna.in/search.rss?q=python&country=in"),
            ]
            for name, url in job_tests:
                try:
                    res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
                    if res.status_code in (200, 201):
                        st.success(f"🟢 **{name}** — Operational (HTTP {res.status_code})")
                    else:
                        st.warning(f"🟡 **{name}** — HTTP {res.status_code}")
                except Exception as e:
                    st.error(f"🔴 **{name}** — Failed ({e})")
    else:
        st.info("Click the button above to run a live health check on all platforms.")


# ============================================================================
# Page 5: Weekly Market Insights
# ============================================================================

elif nav_page == "📊 Weekly Market Insights":
    st.title("📊 Weekly Market & Tech Insights")
    st.write("Analyzes opportunities delivered over the past 7 days to compile skills in demand and hiring trends.")

    seen_dict = main.load_seen_dict()
    if st.button("📊 Generate Fresh Weekly Insights Report", type="primary"):
        report = main.generate_weekly_insights(seen_dict, days=7)
        st.markdown(report)
    else:
        report = main.generate_weekly_insights(seen_dict, days=7)
        st.markdown(report)


# ============================================================================
# Page 6: Cloud Database Explorer
# ============================================================================

elif nav_page == "☁️ Cloud Database Explorer":
    st.title("☁️ Cloud Database & Deduplication Explorer")
    st.write("Inspect seen links stored in Supabase Cloud Database (or local fallback).")

    seen_dict = main.load_seen_dict()
    total_tracked = sum(len(items) for items in seen_dict.values() if isinstance(items, dict))

    m1, m2 = st.columns(2)
    with m1:
        st.metric("Total Tracked Opportunities", f"{total_tracked} links")
    with m2:
        st.metric("Subscribers in Seen DB", f"{len(seen_dict)} users")

    for email, items in seen_dict.items():
        if isinstance(items, dict):
            with st.expander(f"📁 {email} ({len(items)} opportunities tracked)"):
                st.json(items)
