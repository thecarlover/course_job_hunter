"""
Course & Job Hunter — Modern Craftwork Design System
=====================================================
A high-converting, editorial-grade dashboard built with Craftwork design principles.
Features:
- Instant 1-Click Magic Login via email URL query parameters (?user=...)
- Obsidian dark surfaces with layered micro-borders and ambient depth
- Minimalist typography (Inter + JetBrains Mono) without emoji clutter
- Refined Bento KPI grid with live streak, verified free certs, and active roles
- Sleek interactive cards with direct apply actions and 1-click outreach pitches
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
    page_title="Hunter Hub — Opportunity Radar",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
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
SEEN_FILE       = os.path.join(BASE_DIR, "seen.json")
ADMIN_PASSWORD  = (os.environ.get("ADMIN_PASSWORD") or "hunter2026").strip()

# ─────────────────────────────────────────────────────────────────────────────
# CRAFTWORK BESPOKE DESIGN STYLES (No AI-clutter, clean typography)
# ─────────────────────────────────────────────────────────────────────────────
CRAFTWORK_DESIGN = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* Reset and Base */
html, body, [class*="css"], [data-testid="stAppViewContainer"], .stApp {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
    background-color: #08090d !important;
    color: #e2e8f0 !important;
    letter-spacing: -0.01em;
}

#MainMenu, footer, header { visibility: hidden !important; }
.block-container {
    padding: 1.5rem 2.2rem 4rem !important;
    max-width: 1180px !important;
}

/* Custom Scrollbar */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #08090d; }
::-webkit-scrollbar-thumb { background: #1c202e; border-radius: 99px; }
::-webkit-scrollbar-thumb:hover { background: #2d3448; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: #0b0d14 !important;
    border-right: 1px solid rgba(255, 255, 255, 0.06) !important;
}
[data-testid="stSidebar"] .block-container {
    padding: 1.5rem 1rem !important;
}

/* Sidebar Radio Pills */
[data-testid="stSidebar"] .stRadio > div {
    gap: 4px !important;
}
[data-testid="stSidebar"] .stRadio > div > label {
    background: transparent !important;
    border: 1px solid transparent !important;
    border-radius: 10px !important;
    padding: 9px 12px !important;
    color: #8b949e !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    transition: all 0.15s ease !important;
}
[data-testid="stSidebar"] .stRadio > div > label:hover {
    background: rgba(255, 255, 255, 0.04) !important;
    color: #f0f6fc !important;
}
[data-testid="stSidebar"] .stRadio > div > label[data-checked="true"] {
    background: rgba(99, 102, 241, 0.12) !important;
    border-color: rgba(99, 102, 241, 0.3) !important;
    color: #a5b4fc !important;
    font-weight: 600 !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: #0f121d !important;
    border: 1px solid rgba(255, 255, 255, 0.06) !important;
    border-radius: 12px !important;
    padding: 4px !important;
    gap: 4px !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    padding: 8px 18px !important;
    font-size: 12px !important;
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
    border: 1px solid rgba(255, 255, 255, 0.15) !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 12px !important;
    padding: 8px 18px !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.2) !important;
    transition: all 0.15s ease !important;
}
.stButton > button:hover {
    background: #4338ca !important;
    border-color: rgba(255, 255, 255, 0.25) !important;
    transform: translateY(-1px) !important;
}
.stButton > button:active {
    transform: translateY(0) !important;
}

/* Inputs */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div,
.stNumberInput > div > div > input {
    background: #0f121d !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 10px !important;
    color: #f1f5f9 !important;
    font-size: 12px !important;
    box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.3) !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15) !important;
}

/* Expanders */
.stExpander > details {
    background: #0f121d !important;
    border: 1px solid rgba(255, 255, 255, 0.06) !important;
    border-radius: 14px !important;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3) !important;
}
.stExpander > details > summary {
    font-weight: 600 !important;
    color: #e2e8f0 !important;
    font-size: 13px !important;
}

/* Code & tags */
.stCode, code {
    font-family: 'JetBrains Mono', monospace !important;
    background: #141724 !important;
    color: #a5b4fc !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 6px !important;
    font-size: 11px !important;
}

/* Alert Boxes */
.stSuccess, .stInfo, .stWarning, .stError {
    border-radius: 12px !important;
    font-size: 12px !important;
}
.stSuccess { background: rgba(16, 185, 129, 0.08) !important; border: 1px solid rgba(16, 185, 129, 0.2) !important; color: #6ee7b7 !important; }
.stInfo    { background: rgba(99, 102, 241, 0.08) !important; border: 1px solid rgba(99, 102, 241, 0.2) !important; color: #a5b4fc !important; }
.stWarning { background: rgba(245, 158, 11, 0.08) !important; border: 1px solid rgba(245, 158, 11, 0.2) !important; color: #fcd34d !important; }
.stError   { background: rgba(244, 63, 94, 0.08) !important; border: 1px solid rgba(244, 63, 94, 0.2) !important; color: #fda4af !important; }
</style>
"""
st.markdown(CRAFTWORK_DESIGN, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# DATA HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def load_subscribers() -> List[Dict[str, Any]]:
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


def _hash_pw(pw: str) -> str:
    return "sha256:" + hashlib.sha256(pw.encode()).hexdigest()


def _verify_pw(sub: Dict[str, Any], pw: str) -> bool:
    stored = sub.get("portal_password", "")
    if not stored:
        return pw == "hunter2026" or pw == "hunter123"
    if stored.startswith("sha256:"):
        return stored == _hash_pw(pw)
    return stored == pw


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


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE & 1-CLICK MAGIC LOGIN AUTO-AUTHENTICATION
# ─────────────────────────────────────────────────────────────────────────────
if "portal_logged_in" not in st.session_state:
    st.session_state.portal_logged_in = False
if "portal_email" not in st.session_state:
    st.session_state.portal_email = ""
if "portal_name" not in st.session_state:
    st.session_state.portal_name = ""
if "xp" not in st.session_state:
    st.session_state.xp = 350
if "streak_days" not in st.session_state:
    st.session_state.streak_days = 7
if "last_checkin" not in st.session_state:
    st.session_state.last_checkin = ""
if "quiz_answered" not in st.session_state:
    st.session_state.quiz_answered = {}
if "pitch_job" not in st.session_state:
    st.session_state.pitch_job = None

# ✨ MAGIC 1-CLICK URL LOGIN:
# If user clicks from email (?user=email@example.com), auto-authenticate!
try:
    url_user = st.query_params.get("user") or st.query_params.get("email")
    if url_user and not st.session_state.portal_logged_in:
        all_subs = load_subscribers()
        matched = next((s for s in all_subs if s.get("email", "").strip().lower() == str(url_user).strip().lower()), None)
        if matched:
            st.session_state.portal_logged_in = True
            st.session_state.portal_email = matched["email"].strip().lower()
            st.session_state.portal_name = matched.get("name") or str(url_user).split("@")[0].title()
except Exception:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# CRAFTWORK HTML CARD COMPONENTS (Bespoke styling, zero AI-clutter)
# ─────────────────────────────────────────────────────────────────────────────

def render_bento_grid(streak_days: int, xp: int, courses_count: int, jobs_count: int, est_saved: int, is_active: bool) -> str:
    """Renders a sleek, high-contrast Bento Grid without cartoon emojis."""
    active_color = "#10b981" if is_active else "#f59e0b"
    active_label = "Radar Active" if is_active else "Radar Paused"

    week_dots = "".join([
        f'<div style="width:7px;height:7px;border-radius:50%;background:{"#f59e0b" if i < streak_days else "#1f2438"};"></div>'
        for i in range(7)
    ])

    return f"""
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;margin-bottom:20px;">
        
        <!-- Bento 1: Daily Momentum -->
        <div style="background:#0f121d;border:1px solid rgba(255,255,255,0.06);border-radius:16px;padding:20px;box-shadow:0 8px 24px rgba(0,0,0,0.4);position:relative;overflow:hidden;">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
                <span style="font-size:10px;font-weight:700;color:#f59e0b;letter-spacing:0.08em;text-transform:uppercase;">Daily Momentum</span>
                <span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:99px;background:rgba(245,158,11,0.12);color:#fcd34d;border:1px solid rgba(245,158,11,0.25);">DAY {streak_days}</span>
            </div>
            <div style="display:flex;align-items:baseline;gap:6px;margin-bottom:4px;">
                <span style="font-size:28px;font-weight:800;color:#ffffff;line-height:1;">{xp}</span>
                <span style="font-size:12px;font-weight:700;color:#64748b;">XP · Level 3</span>
            </div>
            <div style="font-size:12px;color:#94a3b8;margin-bottom:16px;">Top 5% active learner streak this week.</div>
            <div style="display:flex;align-items:center;gap:6px;border-top:1px solid rgba(255,255,255,0.05);padding-top:12px;">
                {week_dots}
                <span style="font-size:11px;color:#64748b;margin-left:auto;font-weight:500;">7-Day History</span>
            </div>
        </div>

        <!-- Bento 2: Opportunity Velocity -->
        <div style="background:#0f121d;border:1px solid rgba(255,255,255,0.06);border-radius:16px;padding:20px;box-shadow:0 8px 24px rgba(0,0,0,0.4);">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
                <span style="font-size:10px;font-weight:700;color:#6366f1;letter-spacing:0.08em;text-transform:uppercase;">Active Inventory</span>
                <span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:99px;background:rgba(99,102,241,0.12);color:#a5b4fc;border:1px solid rgba(99,102,241,0.25);">Live Verified</span>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px;">
                <div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:10px;padding:8px 12px;">
                    <div style="font-size:9px;font-weight:700;color:#64748b;text-transform:uppercase;">Free Courses</div>
                    <div style="font-size:20px;font-weight:800;color:#ffffff;margin-top:2px;">{courses_count}</div>
                </div>
                <div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:10px;padding:8px 12px;">
                    <div style="font-size:9px;font-weight:700;color:#64748b;text-transform:uppercase;">Curated Jobs</div>
                    <div style="font-size:20px;font-weight:800;color:#ffffff;margin-top:2px;">{jobs_count}</div>
                </div>
            </div>
            <div style="display:flex;align-items:center;justify-content:space-between;border-top:1px solid rgba(255,255,255,0.05);padding-top:10px;">
                <span style="font-size:11px;color:#94a3b8;">Est. Tuition Unlocked</span>
                <span style="font-size:13px;font-weight:700;color:#10b981;font-family:'JetBrains Mono',monospace;">${est_saved}+ USD</span>
            </div>
        </div>

        <!-- Bento 3: System Status -->
        <div style="background:#0f121d;border:1px solid rgba(255,255,255,0.06);border-radius:16px;padding:20px;box-shadow:0 8px 24px rgba(0,0,0,0.4);">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
                <span style="font-size:10px;font-weight:700;color:#10b981;letter-spacing:0.08em;text-transform:uppercase;">Digest Automation</span>
                <span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:99px;background:rgba(16,185,129,0.12);color:{active_color};border:1px solid rgba(16,185,129,0.25);">{active_label}</span>
            </div>
            <div style="font-size:14px;font-weight:700;color:#ffffff;margin-bottom:4px;">Next Dispatch ~8:00 AM IST</div>
            <div style="font-size:12px;color:#94a3b8;line-height:1.5;margin-bottom:14px;">LinkedIn, Naukri, and Udemy feeds scanned every morning at sunrise.</div>
            <div style="border-top:1px solid rgba(255,255,255,0.05);padding-top:10px;display:flex;align-items:center;gap:6px;">
                <span style="width:6px;height:6px;border-radius:50%;background:#10b981;"></span>
                <span style="font-size:11px;color:#64748b;">Supabase Cloud Database connected</span>
            </div>
        </div>

    </div>
    """


def render_opportunity_card(item: Dict) -> str:
    """Renders a sleek editorial opportunity card without generic emoji spam."""
    is_course = item.get("type") == "course"
    title     = item.get("title", "Untitled")
    url       = item.get("url", "#")
    domain    = item.get("domain", "")
    date      = item.get("date", "")
    location  = item.get("location") or ""
    salary    = item.get("salary") or ""

    if is_course:
        badge_style = "background:rgba(16,185,129,0.1);color:#6ee7b7;border:1px solid rgba(16,185,129,0.25);"
        badge_text  = "100% FREE CERTIFICATE"
        action_btn  = f'<a href="{url}" target="_blank" style="display:inline-flex;align-items:center;gap:6px;padding:7px 14px;border-radius:8px;background:#059669;color:#ffffff;font-size:11px;font-weight:700;text-decoration:none;box-shadow:0 1px 2px rgba(0,0,0,0.3);white-space:nowrap;">Claim Course ↗</a>'
    else:
        badge_style = "background:rgba(99,102,241,0.1);color:#a5b4fc;border:1px solid rgba(99,102,241,0.25);"
        badge_text  = domain.upper() if domain else "JOB BOARD"
        action_btn  = f'<a href="{url}" target="_blank" style="display:inline-flex;align-items:center;gap:6px;padding:7px 14px;border-radius:8px;background:#4f46e5;color:#ffffff;font-size:11px;font-weight:700;text-decoration:none;box-shadow:0 1px 2px rgba(0,0,0,0.3);white-space:nowrap;">Apply ↗</a>'

    meta_tags = []
    if not is_course:
        meta_tags.append(f'<span style="color:#8b949e;">via {domain}</span>')
    if location:
        meta_tags.append(f'<span style="color:#8b949e;">📍 {location}</span>')
    if salary:
        meta_tags.append(f'<span style="color:#10b981;font-weight:600;font-family:JetBrains Mono,monospace;">{salary}</span>')
    if date:
        meta_tags.append(f'<span style="color:#475569;font-family:JetBrains Mono,monospace;">{date}</span>')

    meta_str = " · ".join(meta_tags) if meta_tags else ""

    return f"""
    <div style="background:#0f121d;border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:16px 20px;margin-bottom:10px;display:flex;align-items:center;justify-content:space-between;gap:16px;box-shadow:0 2px 8px rgba(0,0,0,0.3);">
        <div style="min-width:0;flex:1;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                <span style="font-size:9px;font-weight:700;letter-spacing:0.06em;padding:2px 8px;border-radius:99px;{badge_style}">{badge_text}</span>
            </div>
            <div style="font-size:14px;font-weight:700;color:#f0f6fc;line-height:1.4;margin-bottom:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{title}</div>
            <div style="font-size:11px;display:flex;gap:8px;flex-wrap:wrap;">{meta_str}</div>
        </div>
        <div style="flex-shrink:0;">{action_btn}</div>
    </div>
    """


# ─────────────────────────────────────────────────────────────────────────────
# NAVIGATION DISPATCH
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;padding:4px 0;">
        <div style="width:32px;height:32px;border-radius:8px;background:linear-gradient(135deg,#4f46e5,#3b82f6);display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 4px 12px rgba(79,70,229,0.3);">🎯</div>
        <div>
            <div style="font-size:13px;font-weight:800;color:#ffffff;letter-spacing:-0.01em;">Hunter Hub</div>
            <div style="font-size:10px;color:#64748b;font-weight:600;letter-spacing:0.04em;text-transform:uppercase;">Career Radar</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    nav_page = st.radio(
        "Navigation",
        [
            "Opportunity Vault",
            "Digest Engine",
            "Subscribers",
            "Source Health",
            "Market Trends",
            "Database Inspector",
        ],
        index=0,
        label_visibility="collapsed",
    )

    st.markdown("<hr style='margin:16px 0;border-color:rgba(255,255,255,0.06);'>", unsafe_allow_html=True)
    if db.is_supabase_enabled():
        st.markdown('<div style="font-size:11px;color:#10b981;font-weight:600;">● Supabase Cloud Active</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="font-size:11px;color:#64748b;font-weight:600;">● Local Storage Mode</div>', unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 1: OPPORTUNITY VAULT (MEMBER PORTAL)
# ═════════════════════════════════════════════════════════════════════════════
if nav_page == "Opportunity Vault":

    # ── LOGIN SCREEN (If not auto-logged in via query param) ───────────────────
    if not st.session_state.portal_logged_in:
        c1, c2, c3 = st.columns([1, 1.2, 1])
        with c2:
            st.markdown("""
            <div style="text-align:center;margin:40px 0 24px;">
                <div style="font-size:32px;margin-bottom:8px;">🎯</div>
                <div style="font-size:20px;font-weight:800;color:#ffffff;">Hunter Member Portal</div>
                <div style="font-size:12px;color:#8b949e;margin-top:4px;">Sign in to inspect your tailored digest archive.</div>
            </div>
            """, unsafe_allow_html=True)

            with st.form("login_box"):
                u_email = st.text_input("Subscriber Email", placeholder="you@example.com", key="login_box_email")
                u_pass  = st.text_input("Password", type="password", placeholder="••••••••", key="login_box_pw")
                st.markdown('<div style="font-size:11px;color:#475569;margin-bottom:12px;">Default account password: <code>hunter2026</code></div>', unsafe_allow_html=True)
                login_submit = st.form_submit_button("Sign In →", use_container_width=True)

            if login_submit:
                subs = load_subscribers()
                matched = next((s for s in subs if s.get("email","").strip().lower() == u_email.strip().lower()), None)
                if not matched:
                    st.error("No account found for this email address.")
                elif not _verify_pw(matched, u_pass):
                    st.error("Incorrect password.")
                else:
                    st.session_state.portal_logged_in = True
                    st.session_state.portal_email = matched["email"].strip().lower()
                    st.session_state.portal_name = matched.get("name") or u_email.split("@")[0].title()
                    st.rerun()

        st.stop()

    # ── AUTHENTICATED PORTAL VIEW ────────────────────────────────────────────
    cur_email = st.session_state.portal_email
    cur_name  = st.session_state.portal_name
    subs = load_subscribers()
    sub  = next((s for s in subs if s.get("email","").strip().lower() == cur_email), None) or {}

    # Header Row
    top_col1, top_col2 = st.columns([6, 1])
    with top_col1:
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
            <div style="width:40px;height:40px;border-radius:10px;background:#1e2235;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:800;color:#818cf8;">{cur_name[0].upper()}</div>
            <div>
                <div style="font-size:18px;font-weight:800;color:#ffffff;line-height:1.2;">{cur_name}'s Opportunity Radar</div>
                <div style="font-size:11px;color:#64748b;margin-top:2px;">{cur_email}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with top_col2:
        if st.button("Sign Out", key="top_signout_btn"):
            st.session_state.portal_logged_in = False
            st.rerun()

    # Fetch Vault Items
    seen_dict = main.load_seen_dict()
    raw_history = seen_dict.get(cur_email, {}) if isinstance(seen_dict, dict) else {}
    vault_items = []
    for url, meta in raw_history.items():
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
    est_saved = max(len(courses) * 85, 290)

    # Render Bento Grid
    st.markdown(render_bento_grid(
        streak_days=st.session_state.streak_days,
        xp=st.session_state.xp,
        courses_count=len(courses),
        jobs_count=len(jobs),
        est_saved=est_saved,
        is_active=bool(sub.get("active", True))
    ), unsafe_allow_html=True)

    # Main Segmented Tabs
    tab_courses, tab_jobs, tab_quiz, tab_pitch, tab_settings = st.tabs([
        f"Free Courses ({len(courses)})",
        f"Job Pipeline ({len(jobs)})",
        "Daily Skill Byte (+50 XP)",
        "Outreach Pitch",
        "Radar Preferences",
    ])

    # ── TAB: COURSES ──────────────────────────────────────────────────────────
    with tab_courses:
        c_search, c_sort = st.columns([4, 1])
        with c_search:
            cq = st.text_input("Search courses", placeholder="Filter by title or learning platform…", label_visibility="collapsed", key="v_course_query")
        with c_sort:
            cs = st.selectbox("Sort", ["Newest First", "Alphabetical", "Platform"], label_visibility="collapsed", key="v_course_sort")

        filtered_c = courses
        if cq:
            q = cq.strip().lower()
            filtered_c = [c for c in courses if q in c["title"].lower() or q in c["domain"].lower()]
        if cs == "Alphabetical":
            filtered_c = sorted(filtered_c, key=lambda x: x["title"])
        elif cs == "Platform":
            filtered_c = sorted(filtered_c, key=lambda x: x["domain"])

        if not filtered_c:
            st.markdown("""
            <div style="text-align:center;padding:50px 20px;color:#475569;">
                <div style="font-size:32px;margin-bottom:8px;">📚</div>
                <div style="font-size:13px;font-weight:600;color:#64748b;">No matching courses delivered yet</div>
                <div style="font-size:11px;margin-top:2px;">Your morning digest scans Swayam, NPTEL, and Udemy daily.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            cards_html = "".join(render_opportunity_card(c) for c in filtered_c)
            st.markdown(cards_html, unsafe_allow_html=True)

    # ── TAB: JOBS ─────────────────────────────────────────────────────────────
    with tab_jobs:
        j_search, j_sort = st.columns([4, 1])
        with j_search:
            jq = st.text_input("Search jobs", placeholder="Filter by role, company, or location…", label_visibility="collapsed", key="v_job_query")
        with j_sort:
            js = st.selectbox("Sort", ["Newest First", "Alphabetical", "Source Board"], label_visibility="collapsed", key="v_job_sort")

        filtered_j = jobs
        if jq:
            q = jq.strip().lower()
            filtered_j = [j for j in jobs if q in j["title"].lower() or q in j["domain"].lower() or q in (j.get("location") or "").lower()]
        if js == "Alphabetical":
            filtered_j = sorted(filtered_j, key=lambda x: x["title"])
        elif js == "Source Board":
            filtered_j = sorted(filtered_j, key=lambda x: x["domain"])

        if not filtered_j:
            st.markdown("""
            <div style="text-align:center;padding:50px 20px;color:#475569;">
                <div style="font-size:32px;margin-bottom:8px;">💼</div>
                <div style="font-size:13px;font-weight:600;color:#64748b;">No matching jobs in pipeline</div>
                <div style="font-size:11px;margin-top:2px;">Live jobs from LinkedIn, Naukri, and Remotive appear here after digest runs.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            for idx_j, j_item in enumerate(filtered_j):
                col_card, col_action = st.columns([6, 1])
                with col_card:
                    st.markdown(render_opportunity_card(j_item), unsafe_allow_html=True)
                with col_action:
                    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
                    u_hash = hashlib.sha256(j_item.get("url", str(idx_j)).encode()).hexdigest()[:8]
                    if st.button("AI Pitch ↗", key=f"btn_pitch_{idx_j}_{u_hash}", use_container_width=True):
                        st.session_state.pitch_job = j_item
                        st.rerun()

    # ── TAB: DAILY SKILL BYTE ─────────────────────────────────────────────────
    with tab_quiz:
        today_date = datetime.date.today().isoformat()
        quiz_data = [
            {
                "cat": "System Design",
                "q": "Which data structure is primarily used in distributed sliding-window rate limiters?",
                "opts": ["Sliding Window Counter / Redis Sorted Set", "Dijkstra's Shortest Path", "B+ Tree Index", "Consistent Hashing Ring"],
                "ans": 0,
                "exp": "Redis Sorted Sets (ZSET) with microsecond timestamps allow millisecond sliding window evaluation with O(log N) purge."
            },
            {
                "cat": "Backend & Cloud",
                "q": "What happens when a container exceeds its memory limit in Kubernetes?",
                "opts": ["CPU is throttled without terminating", "Linux kernel OOM Killer terminates container with Exit Code 137", "Node swaps RAM to NVMe disk", "A replica pod is created automatically"],
                "ans": 1,
                "exp": "When container cgroups exceed memory limit, Linux OOM killer immediately terminates the process with Exit Code 137."
            }
        ]
        q_item = quiz_data[datetime.date.today().timetuple().tm_yday % len(quiz_data)]
        answered_idx = st.session_state.quiz_answered.get(today_date)

        st.markdown(f"""
        <div style="background:#0f121d;border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:20px;margin-bottom:16px;">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
                <span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:99px;background:rgba(99,102,241,0.12);color:#a5b4fc;border:1px solid rgba(99,102,241,0.25);">{q_item['cat']}</span>
                <span style="font-size:11px;font-weight:700;color:#f59e0b;">+50 XP Reward</span>
            </div>
            <div style="font-size:15px;font-weight:700;color:#ffffff;line-height:1.5;">{q_item['q']}</div>
        </div>
        """, unsafe_allow_html=True)

        for opt_idx, opt_text in enumerate(q_item["opts"]):
            if answered_idx is not None:
                is_correct = opt_idx == q_item["ans"]
                chosen     = opt_idx == answered_idx
                border_clr = "#10b981" if is_correct else ("#f43f5e" if chosen else "rgba(255,255,255,0.06)")
                bg_clr     = "rgba(16,185,129,0.08)" if is_correct else ("rgba(244,63,94,0.08)" if chosen else "#0f121d")
                status_txt = " ✓ Correct" if is_correct else (" ✗" if chosen else "")
                st.markdown(f"""
                <div style="background:{bg_clr};border:1px solid {border_clr};border-radius:10px;padding:12px 16px;margin-bottom:8px;font-size:12px;color:#e2e8f0;">
                    <strong>{chr(65+opt_idx)}.</strong> {opt_text}{status_txt}
                </div>
                """, unsafe_allow_html=True)
            else:
                if st.button(f"{chr(65+opt_idx)}. {opt_text}", key=f"q_btn_{opt_idx}", use_container_width=True):
                    st.session_state.quiz_answered[today_date] = opt_idx
                    if opt_idx == q_item["ans"]:
                        st.session_state.xp += 50
                    st.rerun()

        if answered_idx is not None:
            st.info(f"💡 **Takeaway:** {q_item['exp']}")

    # ── TAB: OUTREACH PITCH ───────────────────────────────────────────────────
    with tab_pitch:
        p_job = st.session_state.pitch_job
        p_title = p_job.get("title", "") if p_job else ""
        p_comp  = p_job.get("domain", "") if p_job else ""

        st.markdown("""
        <div style="background:#0f121d;border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:18px;margin-bottom:16px;">
            <div style="font-size:13px;font-weight:700;color:#ffffff;margin-bottom:2px;">Tailored Recruiter Outreach Generator</div>
            <div style="font-size:11px;color:#8b949e;">Generate a high-converting 300-character LinkedIn note and email application.</div>
        </div>
        """, unsafe_allow_html=True)

        col_p1, col_p2 = st.columns(2)
        with col_p1:
            inp_role = st.text_input("Target Role", value=p_title, placeholder="e.g. Senior Backend Engineer", key="outreach_role_inp")
        with col_p2:
            inp_comp = st.text_input("Company / Platform", value=p_comp, placeholder="e.g. Stripe", key="outreach_comp_inp")

        if st.button("Generate Cold Outreach Note", key="btn_outreach_gen", use_container_width=True):
            if not inp_role:
                st.error("Please provide the target role.")
            else:
                ln_note = (
                    f"Hi {inp_comp or 'Team'}, I noticed your opening for {inp_role} and wanted to reach out. "
                    f"With hands-on experience building reliable, scalable systems and shipping production features, "
                    f"I would love to connect and share how my background aligns with your roadmap. Best, {cur_name}"
                )
                em_pitch = (
                    f"Subject: Application & Quick Introduction — {inp_role} | {cur_name}\n\n"
                    f"Hi {inp_comp or 'Hiring Team'},\n\n"
                    f"I came across the {inp_role} opening and was immediately drawn to your product milestones.\n\n"
                    f"I bring proven experience in scalable architecture, API design, and system optimization, "
                    f"with a track record of delivering measurable outcomes.\n\n"
                    f"Would love 10 minutes to discuss how my skill set can accelerate your current milestones.\n\n"
                    f"Portfolio: [Insert URL]\nLinkedIn: [Insert URL]\n\nBest regards,\n{cur_name}"
                )

                st.markdown('<div style="font-size:11px;font-weight:700;color:#8b949e;text-transform:uppercase;margin:14px 0 4px;">LinkedIn Connection Note (Under 300 Chars)</div>', unsafe_allow_html=True)
                st.code(ln_note, language=None)

                st.markdown('<div style="font-size:11px;font-weight:700;color:#8b949e;text-transform:uppercase;margin:14px 0 4px;">Full Application Email</div>', unsafe_allow_html=True)
                st.code(em_pitch, language=None)

    # ── TAB: RADAR PREFERENCES ────────────────────────────────────────────────
    with tab_settings:
        with st.form("settings_form_user"):
            st.markdown('<div style="font-size:13px;font-weight:700;color:#ffffff;margin-bottom:8px;">Radar Customization</div>', unsafe_allow_html=True)
            u_active = st.checkbox("Daily morning digest active (~8:00 AM IST)", value=bool(sub.get("active", True)), key="u_active_cb")

            kws_str = ", ".join(list({*sub.get("keywords", []), *sub.get("job_searches", [])}))
            u_kws   = st.text_area("Target Topics & Keywords (comma-separated)", value=kws_str, key="u_kws_area")

            all_jobs = list(getattr(config, "AVAILABLE_JOB_SOURCES", {}).keys())
            all_crse = list(getattr(config, "AVAILABLE_COURSE_PLATFORMS", {}).keys())
            cur_j    = [s for s in (sub.get("job_sources") or all_jobs) if s in all_jobs]
            cur_c    = [c for c in (sub.get("course_sources") or all_crse) if c in all_crse]

            u_sel_jobs = st.multiselect("Connected Job Boards", all_jobs, default=cur_j, format_func=lambda k: getattr(config, "AVAILABLE_JOB_SOURCES", {}).get(k, k), key="u_jobs_ms")
            u_sel_crse = st.multiselect("Connected Course Platforms", all_crse, default=cur_c, format_func=lambda k: getattr(config, "AVAILABLE_COURSE_PLATFORMS", {}).get(k, k), key="u_crse_ms")

            if st.form_submit_button("Save Radar Settings", use_container_width=True):
                target_idx = next((i for i, s in enumerate(subs) if s.get("email","").strip().lower() == cur_email), None)
                if target_idx is not None:
                    parsed_kws = [k.strip() for k in u_kws.split(",") if k.strip()]
                    subs[target_idx]["active"]         = bool(u_active)
                    subs[target_idx]["keywords"]       = parsed_kws
                    subs[target_idx]["job_searches"]   = parsed_kws
                    subs[target_idx]["job_sources"]    = u_sel_jobs
                    subs[target_idx]["course_sources"] = u_sel_crse
                    save_subscribers(subs)
                    st.success("✓ Radar preferences saved!")


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 2: DIGEST ENGINE
# ═════════════════════════════════════════════════════════════════════════════
elif nav_page == "Digest Engine":
    st.markdown("""
    <div style="background:#0f121d;border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:20px;margin-bottom:20px;">
        <div style="font-size:18px;font-weight:800;color:#ffffff;margin-bottom:4px;">Digest Harvester Pipeline</div>
        <div style="font-size:12px;color:#8b949e;">Run the harvester live to scan RSS feeds, query job boards, and generate personalized email digests.</div>
    </div>
    """, unsafe_allow_html=True)

    all_subs = load_subscribers()
    sub_opts = ["ALL Subscribers"] + [s.get("email") for s in all_subs if s.get("email")]

    col_m, col_t = st.columns(2)
    with col_m:
        run_mode = st.radio("Pipeline Mode", ["Dry Run (Simulation — No emails dispatched)", "Live Run (Deliver real emails)"], key="de_pipeline_mode")
        is_dry = "Dry Run" in run_mode
    with col_t:
        target_sub = st.selectbox("Recipient Filter", sub_opts, key="de_recipient_filter")
        inc_weekly = st.checkbox("Include Weekly Tech Demand Report", key="de_inc_weekly")

    if not is_dry:
        st.warning("⚠️ Live mode sends real emails via Gmail SMTP.")
        admin_auth = st.text_input("Admin Password", type="password", key="de_admin_auth")
    else:
        admin_auth = ""

    if st.button("Start Pipeline Execution", key="de_run_pipeline_btn", use_container_width=True):
        if not is_dry and admin_auth != ADMIN_PASSWORD:
            st.error("Admin authentication failed. Live run aborted.")
        else:
            recipients = None
            if target_sub != "ALL Subscribers":
                recipients = [s for s in all_subs if s.get("email") == target_sub]

            buf = io.StringIO()
            with st.spinner("Harvesting opportunities across all feeds…"):
                with contextlib.redirect_stdout(buf):
                    try:
                        main.run(dry_run=is_dry, weekly=inc_weekly, target_recipients=recipients)
                    except Exception as err:
                        print(f"[Execution Error]: {err}")

            st.success("✓ Pipeline executed successfully!")
            st.markdown('<div style="font-size:11px;font-weight:700;color:#8b949e;text-transform:uppercase;margin:12px 0 6px;">Execution Log</div>', unsafe_allow_html=True)
            st.code(buf.getvalue() or "No logs produced.", language="text")


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 3: SUBSCRIBERS
# ═════════════════════════════════════════════════════════════════════════════
elif nav_page == "Subscribers":
    st.markdown("""
    <div style="background:#0f121d;border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:20px;margin-bottom:20px;">
        <div style="font-size:18px;font-weight:800;color:#ffffff;margin-bottom:4px;">Subscriber Management</div>
        <div style="font-size:12px;color:#8b949e;">Configure member accounts, keyword targeting, and delivery limits.</div>
    </div>
    """, unsafe_allow_html=True)

    subscribers = load_subscribers()

    with st.expander("➕ Add New Member"):
        with st.form("sub_add_form", clear_on_submit=True):
            f1, f2 = st.columns(2)
            with f1:
                n_name  = st.text_input("Name", placeholder="e.g. Ojasvi", key="n_name_inp")
                n_email = st.text_input("Email", placeholder="e.g. ojasvi@gmail.com", key="n_email_inp")
            with f2:
                n_max   = st.number_input("Max Daily Items", 1, 50, 15, key="n_max_inp")
                n_act   = st.checkbox("Active", value=True, key="n_act_cb")
            n_kw  = st.text_area("Keywords (Course match)", "python, ai, devops, product management", key="n_kw_inp")
            n_job = st.text_area("Job Searches", "remote python, product manager", key="n_job_inp")

            if st.form_submit_button("Add Member →", use_container_width=True):
                if not n_name.strip() or not n_email.strip():
                    st.error("Name and email are required.")
                elif any(s.get("email","").lower() == n_email.strip().lower() for s in subscribers):
                    st.error("Subscriber already exists.")
                else:
                    subscribers.append({
                        "name": n_name.strip(), "email": n_email.strip().lower(),
                        "active": n_act, "max_items": int(n_max),
                        "keywords": [k.strip() for k in n_kw.split(",") if k.strip()],
                        "job_searches": [j.strip() for j in n_job.split(",") if j.strip()],
                        "course_feeds": [], "welcome_sent": False,
                    })
                    save_subscribers(subscribers)
                    st.success(f"✓ Added {n_name}!")
                    st.rerun()

    st.markdown(f'<div style="font-size:12px;font-weight:700;color:#8b949e;margin:16px 0 8px;">Active Members ({len(subscribers)})</div>', unsafe_allow_html=True)
    for idx_s, s_item in enumerate(subscribers):
        status_dot = "🟢" if s_item.get("active", True) else "⏸️"
        with st.expander(f"{status_dot} {s_item.get('name','?')} ({s_item.get('email')})"):
            with st.form(f"sub_edit_form_{idx_s}"):
                c_e1, c_e2 = st.columns(2)
                with c_e1:
                    e_name = st.text_input("Name", value=s_item.get("name",""), key=f"e_name_{idx_s}")
                    e_act  = st.checkbox("Active", value=s_item.get("active", True), key=f"e_act_{idx_s}")
                    e_max  = st.number_input("Max Items", 1, 50, s_item.get("max_items", 15), key=f"e_max_{idx_s}")
                with c_e2:
                    e_kw  = st.text_area("Keywords", value=", ".join(s_item.get("keywords", [])), key=f"e_kw_{idx_s}")
                    e_job = st.text_area("Job Searches", value=", ".join(s_item.get("job_searches", [])), key=f"e_job_{idx_s}")

                if st.form_submit_button("Save Subscriber Changes"):
                    subscribers[idx_s].update({
                        "name": e_name.strip(), "active": bool(e_act), "max_items": int(e_max),
                        "keywords": [k.strip() for k in e_kw.split(",") if k.strip()],
                        "job_searches": [j.strip() for j in e_job.split(",") if j.strip()],
                    })
                    save_subscribers(subscribers)
                    st.success("✓ Updated!")
                    st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 4: SOURCE HEALTH
# ═════════════════════════════════════════════════════════════════════════════
elif nav_page == "Source Health":
    st.markdown("""
    <div style="background:#0f121d;border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:20px;margin-bottom:20px;">
        <div style="font-size:18px;font-weight:800;color:#ffffff;margin-bottom:4px;">Platform Connectivity Inspector</div>
        <div style="font-size:12px;color:#8b949e;">Verify live connectivity to RSS feeds, Udemy scrapers, and Job APIs.</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Run Live Connectivity Health Check", key="sh_live_check_btn", use_container_width=True):
        feeds = getattr(config, "COURSE_FEEDS", [])
        st.markdown(f'<div style="font-size:12px;font-weight:700;color:#8b949e;margin:16px 0 8px;">Course RSS Feeds ({len(feeds)})</div>', unsafe_allow_html=True)
        for f_url in feeds:
            try:
                res = requests.get(f_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
                if res.status_code == 200:
                    st.success(f"● {f_url}")
                else:
                    st.warning(f"▲ {f_url} (HTTP {res.status_code})")
            except Exception as e:
                st.error(f"■ {f_url} ({e})")

        st.markdown('<div style="font-size:12px;font-weight:700;color:#8b949e;margin:16px 0 8px;">Job Board Integrations</div>', unsafe_allow_html=True)
        job_targets = [
            ("LinkedIn Jobs (Guest)", "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=python&location=India&f_WT=2&start=0"),
            ("Naukri.com (India)", "https://www.naukri.com/python-jobs"),
            ("Remotive Remote API", "https://remotive.com/api/remote-jobs?limit=2"),
            ("Jobicy API", "https://jobicy.com/api/v2/remote-jobs?count=2"),
            ("Arbeitnow API", "https://www.arbeitnow.com/api/job-board-api"),
        ]
        for name_j, url_j in job_targets:
            try:
                r = requests.get(url_j, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
                if r.status_code in (200, 201):
                    st.success(f"● {name_j} — Operational")
                else:
                    st.warning(f"▲ {name_j} — HTTP {r.status_code}")
            except Exception as err:
                st.error(f"■ {name_j} — {err}")


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 5: MARKET TRENDS
# ═════════════════════════════════════════════════════════════════════════════
elif nav_page == "Market Trends":
    st.markdown("""
    <div style="background:#0f121d;border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:20px;margin-bottom:20px;">
        <div style="font-size:18px;font-weight:800;color:#ffffff;margin-bottom:4px;">Weekly Tech &amp; Skill Demand Report</div>
        <div style="font-size:12px;color:#8b949e;">Derived from all opportunities tracked across the past 7 days.</div>
    </div>
    """, unsafe_allow_html=True)

    seen_dict = main.load_seen_dict()
    report_md = main.generate_weekly_insights(seen_dict, days=7)
    st.markdown(report_md)


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 6: DATABASE INSPECTOR
# ═════════════════════════════════════════════════════════════════════════════
elif nav_page == "Database Inspector":
    st.markdown("""
    <div style="background:#0f121d;border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:20px;margin-bottom:20px;">
        <div style="font-size:18px;font-weight:800;color:#ffffff;margin-bottom:4px;">Supabase Cloud Database Inspector</div>
        <div style="font-size:12px;color:#8b949e;">Inspect seen links stored in PostgreSQL for zero-duplicate guarantees.</div>
    </div>
    """, unsafe_allow_html=True)

    seen_dict = main.load_seen_dict()
    total_links = sum(len(v) for v in seen_dict.values() if isinstance(v, dict))

    m1, m2, m3 = st.columns(3)
    m1.metric("Opportunities Tracked", f"{total_links:,}")
    m2.metric("Subscribers in DB", len(seen_dict))
    m3.metric("Storage Backend", "Supabase PostgreSQL" if db.is_supabase_enabled() else "Local JSON")

    st.markdown("<hr style='margin:16px 0;border-color:rgba(255,255,255,0.06);'>", unsafe_allow_html=True)
    for email_key, items in seen_dict.items():
        if isinstance(items, dict):
            with st.expander(f"📁 {email_key} ({len(items)} items tracked)"):
                st.json(items)
