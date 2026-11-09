"""
Course & Job Hunter — Personal Career Radar
============================================
A dedicated, single-user opportunity vault and career radar.
Tailored exclusively for the subscriber's personal job hunt and certification tracking.
"""

import contextlib
import datetime
import hashlib
import io
import json
import os
import sys
import urllib.parse
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Hunter Radar — Personal Opportunity Vault",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Sync Streamlit Secrets ───────────────────────────────────────────────────
_SECRET_KEYS = [
    "EMAIL", "APP_PASSWORD", "SUPABASE_URL", "SUPABASE_KEY",
    "ADMIN_PASSWORD", "NOTIFIER", "NTFY_TOPIC", "WEBHOOK_URL", "PORTAL_SECRET_KEY",
]
try:
    for _k in _SECRET_KEYS:
        if _k in st.secrets and _k not in os.environ:
            os.environ[_k] = str(st.secrets[_k])
except Exception:
    pass

import config
import db
import main
import notifier

notifier.load_dotenv()

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
RECIPIENTS_FILE = os.path.join(BASE_DIR, "recipients.json")

# ─────────────────────────────────────────────────────────────────────────────
# CRAFTWORK BESPOKE DESIGN (Editorial, minimal, production-grade)
# ─────────────────────────────────────────────────────────────────────────────
CRAFTWORK_DESIGN = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* Base canvas */
html, body, [class*="css"], [data-testid="stAppViewContainer"], .stApp {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
    background-color: #08090d !important;
    color: #e2e8f0 !important;
    letter-spacing: -0.01em;
}

#MainMenu, footer, header { visibility: hidden !important; }
.block-container {
    padding: 1.8rem 2.5rem 4rem !important;
    max-width: 1140px !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #08090d; }
::-webkit-scrollbar-thumb { background: #1c202e; border-radius: 99px; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: #0f121d !important;
    border: 1px solid rgba(255, 255, 255, 0.06) !important;
    border-radius: 12px !important;
    padding: 4px !important;
    gap: 4px !important;
    margin-bottom: 16px !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    padding: 8px 20px !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    color: #8b949e !important;
    border: none !important;
    background: transparent !important;
    transition: all 0.15s ease !important;
}
.stTabs [aria-selected="true"] {
    background: #1e2235 !important;
    color: #ffffff !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4) !important;
}
.stTabs [data-baseweb="tab-highlight"] { display: none !important; }

/* Buttons */
.stButton > button {
    background: #4f46e5 !important;
    color: #ffffff !important;
    border: 1px solid rgba(255, 255, 255, 0.12) !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 12px !important;
    padding: 8px 18px !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.2) !important;
    transition: all 0.15s ease !important;
}
.stButton > button:hover {
    background: #4338ca !important;
    transform: translateY(-1px) !important;
}

/* Inputs */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div {
    background: #0f121d !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 10px !important;
    color: #f1f5f9 !important;
    font-size: 12px !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15) !important;
}

/* Multiselect tags */
[data-baseweb="tag"] {
    background: rgba(99, 102, 241, 0.18) !important;
    border: 1px solid rgba(99, 102, 241, 0.3) !important;
    border-radius: 99px !important;
    color: #a5b4fc !important;
}
</style>
"""
st.markdown(CRAFTWORK_DESIGN, unsafe_allow_html=True)

def render_html(html_str: str) -> None:
    """Safely render HTML without CommonMark 4-space code block conversion."""
    cleaned = "\n".join(line.strip() for line in html_str.strip().splitlines())
    st.markdown(cleaned, unsafe_allow_html=True)


def make_job_card_html(job_entry: Dict) -> str:
    dom = (job_entry.get("domain") or "JOB").upper()
    loc = f" · 📍 {job_entry['location']}" if job_entry.get("location") else ""
    sal = f" · 💰 {job_entry['salary']}" if job_entry.get("salary") else ""
    d_str = f" · {job_entry['date']}" if job_entry.get("date") else ""
    title = str(job_entry.get("title", "Untitled")).replace("<", "&lt;").replace(">", "&gt;")
    url = job_entry.get("url", "#")
    domain = job_entry.get("domain", "")

    return (
        f'<div style="background:#0f121d;border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:16px 20px;margin-bottom:10px;display:flex;align-items:center;justify-content:space-between;gap:16px;">'
        f'<div style="min-width:0;flex:1;">'
        f'<div style="margin-bottom:6px;">'
        f'<span style="font-size:9px;font-weight:700;letter-spacing:0.06em;padding:2px 8px;border-radius:99px;background:rgba(99,102,241,0.1);color:#a5b4fc;border:1px solid rgba(99,102,241,0.25);">{dom}</span>'
        f'<span style="font-size:9px;color:#64748b;margin-left:6px;font-weight:600;">VERIFIED OPPORTUNITY</span>'
        f'</div>'
        f'<div style="font-size:14px;font-weight:700;color:#f0f6fc;line-height:1.4;margin-bottom:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{title}</div>'
        f'<div style="font-size:11px;color:#8b949e;">via {domain}{loc}{sal}{d_str}</div>'
        f'</div>'
        f'<a href="{url}" target="_blank" style="padding:7px 14px;border-radius:8px;background:#4f46e5;color:#ffffff;font-size:11px;font-weight:700;text-decoration:none;white-space:nowrap;">Apply ↗</a>'
        f'</div>'
    )


def make_course_card_html(c: Dict) -> str:
    dom = c.get("domain", "")
    d_str = f" · {c['date']}" if c.get("date") else ""
    title = str(c.get("title", "Untitled")).replace("<", "&lt;").replace(">", "&gt;")
    url = c.get("url", "#")

    return (
        f'<div style="background:#0f121d;border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:16px 20px;margin-bottom:10px;display:flex;align-items:center;justify-content:space-between;gap:16px;">'
        f'<div style="min-width:0;flex:1;">'
        f'<div style="margin-bottom:6px;">'
        f'<span style="font-size:9px;font-weight:700;letter-spacing:0.06em;padding:2px 8px;border-radius:99px;background:rgba(16,185,129,0.1);color:#6ee7b7;border:1px solid rgba(16,185,129,0.25);">100% FREE</span>'
        f'<span style="font-size:9px;color:#64748b;margin-left:6px;font-weight:600;">COUPON APPLIED</span>'
        f'</div>'
        f'<div style="font-size:14px;font-weight:700;color:#f0f6fc;line-height:1.4;margin-bottom:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{title}</div>'
        f'<div style="font-size:11px;color:#8b949e;">via {dom}{d_str}</div>'
        f'</div>'
        f'<a href="{url}" target="_blank" style="padding:7px 14px;border-radius:8px;background:#059669;color:#ffffff;font-size:11px;font-weight:700;text-decoration:none;white-space:nowrap;">Claim Free ↗</a>'
        f'</div>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# LOAD DEDICATED SUBSCRIBER
# ─────────────────────────────────────────────────────────────────────────────

def get_subscribers() -> List[Dict[str, Any]]:
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


# Determine the single subscriber for this app instance
all_subscribers = get_subscribers()
if not all_subscribers:
    st.error("No subscribers configured in recipients.json.")
    st.stop()

# Priority: URL ?user=email -> EMAIL env var -> First subscriber
target_email = ""
try:
    target_email = st.query_params.get("user") or st.query_params.get("email") or ""
except Exception:
    pass

if not target_email:
    target_email = os.environ.get("EMAIL", "").strip().lower()

sub_idx = 0
for idx, s in enumerate(all_subscribers):
    if target_email and s.get("email", "").strip().lower() == target_email.strip().lower():
        sub_idx = idx
        break

user = all_subscribers[sub_idx]
user_email = user.get("email", "").strip().lower()
user_name = user.get("name") or user_email.split("@")[0].title()

# ─────────────────────────────────────────────────────────────────────────────
# VAULT OPPORTUNITIES DATA
# ─────────────────────────────────────────────────────────────────────────────

def classify_item(url: str, meta: Optional[Dict] = None) -> str:
    if meta and meta.get("type"):
        return str(meta["type"])
    course_domains = [
        "answersq", "tutorialbar", "discudemy", "freecodecamp", "udemy",
        "coursetegg", "learnviral", "swayam", "nptel", "geeksforgeeks", "coursera"
    ]
    return "course" if any(d in (url or "").lower() for d in course_domains) else "job"


def derive_title(url: str, meta: Optional[Dict] = None) -> str:
    if meta and meta.get("title"):
        return str(meta["title"])
    try:
        path = urllib.parse.urlparse(url).path.rstrip("/")
        slug = path.split("/")[-1] if path else urllib.parse.urlparse(url).netloc
        return slug.replace("-", " ").replace("_", " ").title() or url
    except Exception:
        return url


seen_dict = main.load_seen_dict()
user_seen = seen_dict.get(user_email, {}) if isinstance(seen_dict, dict) else {}

vault_items = []
for url, meta in user_seen.items():
    if not url or str(url).startswith("__"):
        continue
    m = meta if isinstance(meta, dict) else {}
    vault_items.append({
        "url": url,
        "title": derive_title(url, m),
        "type": m.get("type") or classify_item(url, m),
        "date": m.get("date", ""),
        "domain": urllib.parse.urlparse(url).netloc.replace("www.", ""),
        "location": m.get("location"),
        "salary": m.get("salary"),
    })

vault_items.sort(key=lambda x: str(x.get("date", "")), reverse=True)
courses = [it for it in vault_items if it["type"] == "course"]
jobs    = [it for it in vault_items if it["type"] == "job"]
est_tuition = max(len(courses) * 85, 290)

# Streak state in session
if "user_streak" not in st.session_state:
    st.session_state.user_streak = 7
if "user_xp" not in st.session_state:
    st.session_state.user_xp = 350
if "pitch_active" not in st.session_state:
    st.session_state.pitch_active = None

# ─────────────────────────────────────────────────────────────────────────────
# HEADER & BENTO STATS
# ─────────────────────────────────────────────────────────────────────────────

is_active = bool(user.get("active", True))
status_color = "#10b981" if is_active else "#f59e0b"
status_text  = "Radar Active (Daily 8:00 AM IST)" if is_active else "Radar Paused"

render_html(f"""
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;border-bottom:1px solid rgba(255,255,255,0.06);padding-bottom:16px;">
    <div>
        <div style="display:flex;align-items:center;gap:10px;">
            <div style="font-size:22px;font-weight:800;color:#ffffff;letter-spacing:-0.02em;">{user_name}'s Career Radar</div>
            <span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:99px;background:rgba(16,185,129,0.12);color:{status_color};border:1px solid rgba(16,185,129,0.25);">
                {status_text}
            </span>
        </div>
        <div style="font-size:12px;color:#64748b;margin-top:4px;">
            Targeting: {", ".join(user.get('keywords', [])[:5])} · Verified daily pipeline
        </div>
    </div>
    <div style="text-align:right;">
        <div style="font-size:11px;color:#64748b;font-family:'JetBrains Mono',monospace;">{user_email}</div>
    </div>
</div>
""")

# Bento Grid via native Streamlit columns (no CommonMark indentation escape bugs)
b1, b2, b3 = st.columns(3)

with b1:
    st.markdown(
        f'<div style="background:#0f121d;border:1px solid rgba(255,255,255,0.06);border-radius:16px;padding:18px 20px;box-shadow:0 8px 24px rgba(0,0,0,0.4);">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">'
        f'<span style="font-size:10px;font-weight:700;color:#6366f1;letter-spacing:0.08em;text-transform:uppercase;">Active Inventory</span>'
        f'<span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:99px;background:rgba(99,102,241,0.12);color:#a5b4fc;border:1px solid rgba(99,102,241,0.25);">Live Verified</span>'
        f'</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px;">'
        f'<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:10px;padding:8px 12px;">'
        f'<div style="font-size:9px;font-weight:700;color:#64748b;text-transform:uppercase;">Curated Jobs</div>'
        f'<div style="font-size:22px;font-weight:800;color:#ffffff;margin-top:2px;">{len(jobs)}</div>'
        f'</div>'
        f'<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:10px;padding:8px 12px;">'
        f'<div style="font-size:9px;font-weight:700;color:#64748b;text-transform:uppercase;">Free Courses</div>'
        f'<div style="font-size:22px;font-weight:800;color:#ffffff;margin-top:2px;">{len(courses)}</div>'
        f'</div>'
        f'</div>'
        f'<div style="display:flex;align-items:center;justify-content:space-between;border-top:1px solid rgba(255,255,255,0.05);padding-top:10px;">'
        f'<span style="font-size:11px;color:#94a3b8;">Est. Tuition Unlocked</span>'
        f'<span style="font-size:13px;font-weight:700;color:#10b981;font-family:JetBrains Mono,monospace;">${est_tuition}+ USD</span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True
    )

with b2:
    dots_html = "".join([f'<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#f59e0b;margin-right:5px;"></span>' for _ in range(7)])
    st.markdown(
        f'<div style="background:#0f121d;border:1px solid rgba(255,255,255,0.06);border-radius:16px;padding:18px 20px;box-shadow:0 8px 24px rgba(0,0,0,0.4);">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">'
        f'<span style="font-size:10px;font-weight:700;color:#f59e0b;letter-spacing:0.08em;text-transform:uppercase;">Daily Momentum</span>'
        f'<span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:99px;background:rgba(245,158,11,0.12);color:#fcd34d;border:1px solid rgba(245,158,11,0.25);">Day {st.session_state.user_streak}</span>'
        f'</div>'
        f'<div style="display:flex;align-items:baseline;gap:6px;margin-bottom:4px;">'
        f'<span style="font-size:26px;font-weight:800;color:#ffffff;line-height:1;">{st.session_state.user_xp}</span>'
        f'<span style="font-size:12px;font-weight:700;color:#64748b;">XP · Career Sniper</span>'
        f'</div>'
        f'<div style="font-size:12px;color:#94a3b8;margin-bottom:12px;">Active habit loop maintaining daily cadence.</div>'
        f'<div style="display:flex;align-items:center;border-top:1px solid rgba(255,255,255,0.05);padding-top:10px;">'
        f'{dots_html}'
        f'<span style="font-size:11px;color:#64748b;margin-left:auto;font-weight:500;">7-Day History</span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True
    )

with b3:
    st.markdown(
        f'<div style="background:#0f121d;border:1px solid rgba(255,255,255,0.06);border-radius:16px;padding:18px 20px;box-shadow:0 8px 24px rgba(0,0,0,0.4);">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">'
        f'<span style="font-size:10px;font-weight:700;color:#10b981;letter-spacing:0.08em;text-transform:uppercase;">Automation Schedule</span>'
        f'<span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:99px;background:rgba(16,185,129,0.12);color:#6ee7b7;border:1px solid rgba(16,185,129,0.25);">Connected</span>'
        f'</div>'
        f'<div style="font-size:15px;font-weight:700;color:#ffffff;margin-bottom:4px;">Daily Digest ~8:00 AM IST</div>'
        f'<div style="font-size:12px;color:#94a3b8;line-height:1.5;margin-bottom:12px;">LinkedIn, Naukri, and Udemy feeds scanned daily.</div>'
        f'<div style="display:flex;align-items:center;gap:6px;border-top:1px solid rgba(255,255,255,0.05);padding-top:10px;">'
        f'<span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:#10b981;"></span>'
        f'<span style="font-size:11px;color:#64748b;">PostgreSQL seen-link deduplication active</span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True
    )

st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# WORKSPACE TABS (Clean, dedicated)
# ─────────────────────────────────────────────────────────────────────────────

tab_jobs, tab_courses, tab_config = st.tabs([
    f"Curated Jobs ({len(jobs)})",
    f"Free Certifications ({len(courses)})",
    "Targeting & Source Preferences",
])

# ── TAB 1: CURATED JOBS ──────────────────────────────────────────────────────
with tab_jobs:
    j_col1, j_col2 = st.columns([4, 1])
    with j_col1:
        jq = st.text_input("Filter Jobs", placeholder="Search role title, company, or tech stack…", label_visibility="collapsed", key="personal_jq")
    with j_col2:
        js = st.selectbox("Sort", ["Newest First", "Alphabetical", "Platform"], label_visibility="collapsed", key="personal_js")

    filtered_jobs = jobs
    if jq:
        q = jq.strip().lower()
        filtered_jobs = [j for j in jobs if q in j["title"].lower() or q in j["domain"].lower() or q in (j.get("location") or "").lower()]
    if js == "Alphabetical":
        filtered_jobs = sorted(filtered_jobs, key=lambda x: x["title"])
    elif js == "Platform":
        filtered_jobs = sorted(filtered_jobs, key=lambda x: x["domain"])

    if not filtered_jobs:
        render_html("""
        <div style="text-align:center;padding:50px 20px;color:#64748b;">
            <div style="font-size:14px;font-weight:600;color:#94a3b8;">No matching job openings right now.</div>
            <div style="font-size:11px;margin-top:4px;">Next automated crawler run will bring fresh matches.</div>
        </div>
        """)
    else:
        for idx, job_entry in enumerate(filtered_jobs):
            col_c, col_b = st.columns([6, 1])
            with col_c:
                st.markdown(make_job_card_html(job_entry), unsafe_allow_html=True)
            with col_b:
                st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
                url_hash = hashlib.sha256(job_entry.get("url", str(idx)).encode()).hexdigest()[:8]
                if st.button("AI Pitch", key=f"pitch_act_{idx}_{url_hash}", use_container_width=True):
                    st.session_state.pitch_active = job_entry

        # AI Pitch Generator Tray (If user clicked Pitch)
        if st.session_state.pitch_active:
            p_job = st.session_state.pitch_active
            st.markdown("<hr style='margin:20px 0;border-color:rgba(255,255,255,0.06);'>", unsafe_allow_html=True)
            render_html(f"""
            <div style="background:#141724;border:1px solid rgba(99,102,241,0.3);border-radius:12px;padding:16px 20px;margin-bottom:14px;">
                <div style="font-size:13px;font-weight:700;color:#ffffff;">1-Click Outreach Pitch for: {p_job['title']}</div>
                <div style="font-size:11px;color:#8b949e;">Copy and paste directly into your LinkedIn connection note or email outreach.</div>
            </div>
            """)

            ln_text = (
                f"Hi {p_job['domain'].title()} Hiring Team, I noticed your opening for {p_job['title']} and wanted to reach out. "
                f"With hands-on experience building reliable, scalable systems and executing against roadmap priorities, "
                f"I would love to connect and share how my background aligns with your team's goals. Best, {user_name}"
            )
            st.code(ln_text, language=None)
            if st.button("Close Pitch Generator", key="close_pitch_btn"):
                st.session_state.pitch_active = None
                st.rerun()

# ── TAB 2: FREE CERTIFICATIONS ───────────────────────────────────────────────
with tab_courses:
    c_col1, c_col2 = st.columns([4, 1])
    with c_col1:
        cq = st.text_input("Filter Courses", placeholder="Search course topic, Python, AI, AWS, Excel…", label_visibility="collapsed", key="personal_cq")
    with c_col2:
        cs = st.selectbox("Sort Courses", ["Newest First", "Alphabetical", "Platform"], label_visibility="collapsed", key="personal_cs")

    filtered_courses = courses
    if cq:
        q = cq.strip().lower()
        filtered_courses = [c for c in courses if q in c["title"].lower() or q in c["domain"].lower()]
    if cs == "Alphabetical":
        filtered_courses = sorted(filtered_courses, key=lambda x: x["title"])
    elif cs == "Platform":
        filtered_courses = sorted(filtered_courses, key=lambda x: x["domain"])

    if not filtered_courses:
        render_html("""
        <div style="text-align:center;padding:50px 20px;color:#64748b;">
            <div style="font-size:14px;font-weight:600;color:#94a3b8;">No matching free courses right now.</div>
            <div style="font-size:11px;margin-top:4px;">100% OFF coupons drop daily at ~8:00 AM IST.</div>
        </div>
        """)
    else:
        for c in filtered_courses:
            st.markdown(make_course_card_html(c), unsafe_allow_html=True)

# ── TAB 3: PERSONAL PREFERENCES ─────────────────────────────────────────────
with tab_config:
    render_html("""
    <div style="background:#0f121d;border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:18px 20px;margin-bottom:16px;">
        <div style="font-size:14px;font-weight:700;color:#ffffff;margin-bottom:2px;">Personal Career Targeting</div>
        <div style="font-size:11px;color:#8b949e;">Manage your target roles, keyword matchers, and source board subscriptions.</div>
    </div>
    """)

    with st.form("personal_pref_form"):
        u_active = st.checkbox("Daily morning email digest active (~8:00 AM IST)", value=bool(user.get("active", True)), key="pref_active_cb")
        st.caption("Toggle off for vacation mode — your streak and historical vault are preserved.")

        raw_kws = ", ".join(list({*user.get("keywords", []), *user.get("job_searches", [])}))
        u_kws = st.text_area("Target Keywords & Roles (comma-separated)", value=raw_kws, placeholder="python, product management, automation, devops…", key="pref_kws_area")

        all_jobs = list(getattr(config, "AVAILABLE_JOB_SOURCES", {}).keys())
        all_crse = list(getattr(config, "AVAILABLE_COURSE_PLATFORMS", {}).keys())

        cur_jobs = [j for j in (user.get("job_sources") or all_jobs) if j in all_jobs]
        cur_crse = [c for c in (user.get("course_sources") or all_crse) if c in all_crse]

        u_jobs = st.multiselect("Active Job Boards", all_jobs, default=cur_jobs, format_func=lambda k: getattr(config, "AVAILABLE_JOB_SOURCES", {}).get(k, k), key="pref_jobs_ms")
        u_crse = st.multiselect("Active Course Providers", all_crse, default=cur_crse, format_func=lambda k: getattr(config, "AVAILABLE_COURSE_PLATFORMS", {}).get(k, k), key="pref_crse_ms")

        save_btn = st.form_submit_button("Save Preferences", use_container_width=True)

    if save_btn:
        parsed_kws = [k.strip() for k in u_kws.split(",") if k.strip()]
        all_subscribers[sub_idx]["active"]         = bool(u_active)
        all_subscribers[sub_idx]["keywords"]       = parsed_kws
        all_subscribers[sub_idx]["job_searches"]   = parsed_kws
        all_subscribers[sub_idx]["job_sources"]    = u_jobs
        all_subscribers[sub_idx]["course_sources"] = u_crse
        save_subscribers(all_subscribers)
        st.success("✓ Personal radar preferences updated successfully!")
        st.rerun()
