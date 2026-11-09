"""
Course & Job Hunter — Full Streamlit Cloud Deployment
======================================================
Single-file Streamlit app that replaces both admin.py + FastAPI portal.
Runs entirely on Streamlit Cloud (no FastAPI / uvicorn needed).

Pages:
  🎯 Member Portal    — Craftwork bento UI with vault, quiz, AI pitch
  🚀 Digest Engine    — Run harvester, preview email
  👥 Subscribers      — Manage members & source preferences
  📡 Source Health    — Live feed checker
  📊 Market Insights  — Weekly trends
  ☁️ DB Explorer      — Supabase / local seen.json
"""

# ── Standard library ──────────────────────────────────────────────────────────
import contextlib
import datetime
import hashlib
import io
import json
import os
import sys
import urllib.parse
from typing import Any, Dict, List, Optional

# ── Third-party ───────────────────────────────────────────────────────────────
import requests
import streamlit as st
import streamlit.components.v1 as components

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG  (must be first Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Hunter Hub",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Sync Streamlit secrets → env vars ─────────────────────────────────────────
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

# ── Project imports ───────────────────────────────────────────────────────────
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
# GLOBAL CRAFTWORK CSS  (injected once)
# ─────────────────────────────────────────────────────────────────────────────
CRAFTWORK_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ── Force dark base everywhere ── */
html, body { background-color: #07080d !important; color: #f1f5f9 !important; }
[class*="css"], [data-testid], .stApp, .main, .main > div,
.element-container, .stMarkdown, .stForm,
div[data-testid="stAppViewContainer"],
div[data-testid="stAppViewBlockContainer"],
div[data-testid="block-container"],
div[data-testid="stVerticalBlock"],
section[data-testid="stSidebar"] ~ div {
    background-color: #07080d !important;
    color: #f1f5f9 !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* App container */
.stApp { background: #07080d !important; }
.main .block-container { background: #07080d !important; }

/* Hide default Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 1.5rem 2rem !important; max-width: 1100px; }

/* Scrollbar */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 99px; }

/* Sidebar — force dark */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div,
[data-testid="stSidebar"] .css-1lcbmhc,
[data-testid="stSidebar"] .css-17eq0hr {
    background: linear-gradient(180deg, #09111d 0%, #07080d 100%) !important;
    border-right: 1px solid rgba(255,255,255,0.07) !important;
}
[data-testid="stSidebar"] * { color: #94a3b8 !important; }
[data-testid="stSidebar"] .stRadio > label { color: #f1f5f9 !important; }
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span { color: #94a3b8 !important; }

/* Top header bar — hide white bar */
[data-testid="stHeader"] { background: #07080d !important; border-bottom: 1px solid rgba(255,255,255,0.05) !important; }
[data-testid="stToolbar"] { background: #07080d !important; }

/* All white backgrounds → dark */
div[class*="stBlock"], div[class*="st-"], section { background-color: transparent !important; }
div[data-testid="stHorizontalBlock"] { background: transparent !important; }
div[data-testid="column"] { background: transparent !important; }

/* Metric cards */
[data-testid="stMetricValue"] { color: #f1f5f9 !important; font-weight: 800 !important; }
[data-testid="stMetricLabel"] { color: #64748b !important; font-size: 11px !important; }
[data-testid="metric-container"] {
    background: linear-gradient(145deg, rgba(15,20,32,0.9), rgba(9,12,20,0.95)) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 16px !important;
    padding: 1rem !important;
    box-shadow: 0 1px 0 rgba(255,255,255,0.05) inset, 0 8px 24px -8px rgba(0,0,0,0.5) !important;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #4f46e5, #3b82f6) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    padding: 8px 20px !important;
    box-shadow: 0 4px 14px rgba(79,70,229,0.3) !important;
    transition: all 0.15s ease !important;
}
.stButton > button:hover { filter: brightness(1.1) !important; transform: translateY(-1px) !important; }

/* Secondary buttons */
.stButton > button[kind="secondary"] {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    box-shadow: none !important;
}

/* Text inputs */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div,
.stNumberInput > div > div > input {
    background: rgba(6,8,16,0.9) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 10px !important;
    color: #f1f5f9 !important;
    font-size: 13px !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: rgba(99,102,241,0.5) !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.1) !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(10,13,22,0.9) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 999px !important;
    padding: 4px !important;
    gap: 2px !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 999px !important;
    padding: 6px 18px !important;
    font-weight: 600 !important;
    font-size: 12px !important;
    color: #64748b !important;
    border: none !important;
    background: transparent !important;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #4f46e5, #3b82f6) !important;
    color: white !important;
    box-shadow: 0 4px 14px rgba(99,102,241,0.4) !important;
}
.stTabs [data-baseweb="tab-highlight"] { display: none !important; }

/* Expanders */
.stExpander > details {
    background: linear-gradient(145deg, rgba(15,20,32,0.85), rgba(9,12,20,0.95)) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 16px !important;
}
.stExpander > details > summary { color: #f1f5f9 !important; font-weight: 600 !important; }

/* Divider */
hr { border-color: rgba(255,255,255,0.07) !important; }

/* Success / info / error / warning */
.stSuccess { background: rgba(16,185,129,0.1) !important; border: 1px solid rgba(16,185,129,0.25) !important; border-radius: 12px !important; color: #6ee7b7 !important; }
.stInfo    { background: rgba(99,102,241,0.1) !important; border: 1px solid rgba(99,102,241,0.25) !important; border-radius: 12px !important; color: #a5b4fc !important; }
.stError   { background: rgba(244,63,94,0.1) !important; border: 1px solid rgba(244,63,94,0.25) !important; border-radius: 12px !important; color: #fda4af !important; }
.stWarning { background: rgba(245,158,11,0.1) !important; border: 1px solid rgba(245,158,11,0.25) !important; border-radius: 12px !important; color: #fcd34d !important; }

/* Spinner */
[data-testid="stSpinner"] > div { border-top-color: #6366f1 !important; }

/* Forms */
.stForm { background: transparent !important; border: none !important; }

/* Checkbox */
.stCheckbox > label > div:first-child {
    border-color: rgba(99,102,241,0.5) !important;
    border-radius: 4px !important;
}

/* Radio */
.stRadio > div { gap: 6px !important; }
.stRadio > div > label {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 10px !important;
    padding: 8px 12px !important;
    color: #94a3b8 !important;
    font-size: 12px !important;
}

/* Code blocks */
.stCode, code { 
    background: rgba(99,102,241,0.1) !important; 
    color: #a5b4fc !important; 
    border-radius: 6px !important;
    font-family: 'JetBrains Mono', monospace !important;
}

/* Multiselect */
[data-baseweb="tag"] {
    background: rgba(99,102,241,0.2) !important;
    border: 1px solid rgba(99,102,241,0.3) !important;
    border-radius: 999px !important;
    color: #a5b4fc !important;
}
</style>
"""

st.markdown(CRAFTWORK_CSS, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
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
        return pw == "hunter123"
    if stored.startswith("sha256:"):
        return stored == _hash_pw(pw)
    return stored == pw


def classify_item(url: str, meta: Optional[Dict] = None) -> str:
    if meta and meta.get("type"):
        return str(meta["type"])
    course_domains = ["answersq","tutorialbar","discudemy","freecodecamp","udemy",
                      "coursetegg","learnviral","swayam","nptel","geeksforgeeks","coursera"]
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


def pill(text: str, color: str = "indigo") -> str:
    palettes = {
        "indigo": ("rgba(99,102,241,0.12)", "#a5b4fc", "rgba(99,102,241,0.3)"),
        "green":  ("rgba(16,185,129,0.1)",  "#6ee7b7", "rgba(16,185,129,0.3)"),
        "blue":   ("rgba(59,130,246,0.1)",  "#93c5fd", "rgba(59,130,246,0.3)"),
        "amber":  ("rgba(245,158,11,0.1)",  "#fcd34d", "rgba(245,158,11,0.3)"),
        "rose":   ("rgba(244,63,94,0.1)",   "#fda4af", "rgba(244,63,94,0.3)"),
        "violet": ("rgba(139,92,246,0.12)", "#c4b5fd", "rgba(139,92,246,0.3)"),
    }
    bg, fg, border = palettes.get(color, palettes["indigo"])
    return (f'<span style="display:inline-flex;align-items:center;gap:4px;'
            f'padding:2px 9px;border-radius:999px;font-size:10px;font-weight:700;'
            f'letter-spacing:0.04em;text-transform:uppercase;'
            f'background:{bg};color:{fg};border:1px solid {border};">{text}</span>')


def craft_card_start(height: str = "auto") -> str:
    return f"""<div style="
        background:linear-gradient(145deg,rgba(15,20,32,0.92),rgba(9,12,20,0.97));
        border:1px solid rgba(255,255,255,0.07);
        border-radius:20px;
        padding:20px 22px;
        box-shadow:0 1px 0 rgba(255,255,255,0.05) inset,0 8px 32px -8px rgba(0,0,0,0.6);
        margin-bottom:12px;
        position:relative;overflow:hidden;
        {'min-height:'+height if height!='auto' else ''};
    ">"""


def craft_card_end() -> str:
    return "</div>"


def item_row_html(item: Dict, show_pitch: bool = False) -> str:
    is_course = item["type"] == "course"
    dom = item.get("domain", "")
    title = item.get("title", "Untitled")
    url = item.get("url", "#")
    date = item.get("date", "")
    location = item.get("location") or ""
    salary = item.get("salary") or ""

    if is_course:
        is_udemy = any(x in dom.lower() for x in ["udemy","tutorialbar","discudemy","coursetegg","learnviral"])
        badge = pill("100% OFF Coupon", "rose") if is_udemy else pill("Free Certificate", "green")
        action_btn = f'<a href="{url}" target="_blank" style="display:inline-flex;align-items:center;gap:6px;padding:7px 14px;border-radius:10px;background:linear-gradient(135deg,#059669,#10b981);color:white;font-size:11px;font-weight:700;text-decoration:none;box-shadow:0 4px 12px rgba(16,185,129,0.3);white-space:nowrap;">Claim Free ↗</a>'
    else:
        badge = pill(dom or "Job Board", "blue")
        action_btn = f'<a href="{url}" target="_blank" style="display:inline-flex;align-items:center;gap:6px;padding:7px 14px;border-radius:10px;background:linear-gradient(135deg,#2563eb,#3b82f6);color:white;font-size:11px;font-weight:700;text-decoration:none;box-shadow:0 4px 12px rgba(59,130,246,0.3);white-space:nowrap;">Apply ↗</a>'

    meta_parts = []
    if not is_course:
        meta_parts.append(f'<span style="color:#64748b;">via {dom}</span>')
    else:
        meta_parts.append(f'<span style="color:#64748b;">via {dom}</span>')
    if location:
        meta_parts.append(f'<span style="color:#64748b;">📍 {location}</span>')
    if salary:
        meta_parts.append(f'<span style="color:#10b981;font-weight:700;font-family:JetBrains Mono,monospace;">💰 {salary}</span>')
    if date:
        meta_parts.append(f'<span style="color:#334155;font-family:JetBrains Mono,monospace;">{date}</span>')

    meta_html = " · ".join(meta_parts) if meta_parts else ""

    return f"""
    <div style="
        background:linear-gradient(135deg,rgba(13,16,24,0.85),rgba(8,10,18,0.95));
        border:1px solid rgba(255,255,255,0.06);
        border-radius:16px;padding:14px 18px;margin-bottom:10px;
        box-shadow:0 4px 16px -4px rgba(0,0,0,0.5);
        display:flex;align-items:center;justify-content:space-between;gap:16px;
        transition:border-color 0.2s;
    ">
        <div style="min-width:0;flex:1;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap;">
                {badge}
                <span style="font-size:9px;color:#334155;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;">{'REMOTE / INDIA' if not is_course else '100% FREE'}</span>
            </div>
            <div style="font-size:13px;font-weight:600;color:#e2e8f0;line-height:1.4;margin-bottom:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{title}</div>
            <div style="font-size:11px;display:flex;gap:8px;flex-wrap:wrap;">{meta_html}</div>
        </div>
        <div style="flex-shrink:0;">{action_btn}</div>
    </div>"""


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE DEFAULTS
# ─────────────────────────────────────────────────────────────────────────────
if "portal_logged_in" not in st.session_state:
    st.session_state.portal_logged_in = False
if "portal_email" not in st.session_state:
    st.session_state.portal_email = ""
if "portal_name" not in st.session_state:
    st.session_state.portal_name = ""
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False
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


# ─────────────────────────────────────────────────────────────────────────────
# DAILY QUIZ BANK  (rotates daily by day-of-year)
# ─────────────────────────────────────────────────────────────────────────────
QUIZ_BANK = [
    {
        "category": "Python & Backend",
        "question": "What is the key difference between `deepcopy` and shallow `copy` in Python?",
        "options": [
            "Shallow copy copies nested objects recursively; deepcopy does not",
            "Deepcopy creates new compound object & recursively copies all child objects",
            "Shallow copy is thread-safe; deepcopy causes GIL deadlocks",
            "There is no difference — deepcopy is a performance alias",
        ],
        "answer": 1,
        "explanation": "`copy.deepcopy()` constructs a brand-new object and recursively copies all nested objects, preventing shared-reference mutation bugs."
    },
    {
        "category": "System Design",
        "question": "Which algorithm is most commonly used in distributed rate limiters (Cloudflare, Redis)?",
        "options": [
            "Token Bucket / Sliding Window Counter",
            "Dijkstra's Shortest Path",
            "Consistent Hashing Ring",
            "Raft Consensus Protocol",
        ],
        "answer": 0,
        "explanation": "Token Bucket and Sliding Window allow burst handling while enforcing strict request rates across distributed Redis nodes."
    },
    {
        "category": "Cloud & DevOps",
        "question": "What happens when a Kubernetes Pod exceeds its configured memory **limit**?",
        "options": [
            "The Pod is throttled by CPU cgroups without termination",
            "The Pod is killed with OOMKilled (Exit Code 137)",
            "The node automatically swaps pod memory to disk",
            "Kubernetes provisions an additional replica automatically",
        ],
        "answer": 1,
        "explanation": "When memory exceeds the limit, the Linux kernel OOM Killer immediately terminates the container with Exit Code 137."
    },
    {
        "category": "SQL & Databases",
        "question": "Why is indexing every column in a high-traffic PostgreSQL table bad practice?",
        "options": [
            "PostgreSQL enforces a hard limit of 5 indexes per table",
            "Indexes degrade write/insert/update performance and consume RAM/disk",
            "B-tree indexes lock the table permanently during SELECT queries",
            "Queries with WHERE clauses fail if more than two indexes exist",
        ],
        "answer": 1,
        "explanation": "Every INSERT/UPDATE must write to all indexes. Selective indexing only on predicate columns keeps writes fast."
    },
    {
        "category": "Security",
        "question": "What vulnerability is primarily prevented by `HttpOnly` + `SameSite=Lax` cookies?",
        "options": [
            "SQL Injection and buffer overflows",
            "XSS cookie theft and Cross-Site Request Forgery (CSRF)",
            "DDoS attacks and TCP SYN flooding",
            "DNS Spoofing and man-in-the-middle attacks",
        ],
        "answer": 1,
        "explanation": "`HttpOnly` blocks JS `document.cookie` access (stops XSS theft). `SameSite=Lax` prevents cross-site POST forgery."
    },
    {
        "category": "React & Frontend",
        "question": "What is the primary purpose of React's `useCallback` hook?",
        "options": [
            "To memoize a component's rendered output and skip re-renders",
            "To memoize a function reference so it's stable across renders",
            "To run side effects after every render, like `useEffect`",
            "To create a ref object that persists across renders",
        ],
        "answer": 1,
        "explanation": "`useCallback` returns a memoized function that only changes if one of its dependencies changes — preventing unnecessary child re-renders."
    },
    {
        "category": "Data Structures",
        "question": "What is the time complexity of inserting into a balanced BST (AVL / Red-Black Tree)?",
        "options": ["O(1)", "O(log n)", "O(n)", "O(n log n)"],
        "answer": 1,
        "explanation": "Balanced BSTs maintain O(log n) height, so insert, delete, and search all take O(log n) in the worst case."
    },
]


def get_todays_quiz():
    day_of_year = datetime.date.today().timetuple().tm_yday
    return QUIZ_BANK[day_of_year % len(QUIZ_BANK)]


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR NAVIGATION
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
        <div style="width:36px;height:36px;border-radius:12px;background:linear-gradient(135deg,#4f46e5,#3b82f6);display:flex;align-items:center;justify-content:center;font-size:18px;box-shadow:0 4px 12px rgba(79,70,229,0.3);">🎯</div>
        <div>
            <div style="font-size:14px;font-weight:800;color:#f1f5f9;">Hunter Hub</div>
            <div style="font-size:10px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;">Career Radar</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<hr style='margin:12px 0;border-color:rgba(255,255,255,0.07);'>", unsafe_allow_html=True)

    nav_page = st.radio(
        "Navigation",
        [
            "🎯 Member Portal",
            "🚀 Digest Engine",
            "👥 Subscribers",
            "📡 Source Health",
            "📊 Market Insights",
            "☁️ DB Explorer",
        ],
        index=0,
        label_visibility="collapsed",
    )

    st.markdown("<hr style='margin:12px 0;border-color:rgba(255,255,255,0.07);'>", unsafe_allow_html=True)

    supabase_active = db.is_supabase_enabled()
    if supabase_active:
        st.markdown('<div style="font-size:11px;color:#10b981;font-weight:600;">☁️ Supabase: Connected</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="font-size:11px;color:#64748b;font-weight:600;">📁 Storage: Local JSON</div>', unsafe_allow_html=True)

    st.markdown('<div style="font-size:10px;color:#334155;margin-top:8px;">Course &amp; Job Hunter · v2.0</div>', unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 1 — MEMBER PORTAL  (Craftwork Bento UI)
# ═════════════════════════════════════════════════════════════════════════════
if nav_page == "🎯 Member Portal":

    # ── LOGIN GATE ───────────────────────────────────────────────────────────
    if not st.session_state.portal_logged_in:
        cols = st.columns([1, 1.2, 1])
        with cols[1]:
            st.markdown("""
            <div style="text-align:center;margin-bottom:24px;">
                <div style="font-size:40px;margin-bottom:10px;">🎯</div>
                <div style="font-size:22px;font-weight:800;color:#f1f5f9;margin-bottom:4px;">Hunter Hub</div>
                <div style="font-size:13px;color:#64748b;">Your curated career radar & daily opportunity vault</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown(craft_card_start(), unsafe_allow_html=True)
            login_email = st.text_input("Email Address", placeholder="you@example.com", key="login_email_inp")
            login_pw    = st.text_input("Password", type="password", placeholder="••••••••", key="login_pw_inp")
            st.markdown('<div style="font-size:11px;color:#475569;margin:-8px 0 8px;">Default password: <code style="color:#818cf8;">hunter123</code></div>', unsafe_allow_html=True)

            if st.button("Sign In to Vault →", use_container_width=True):
                subs = load_subscribers()
                found = next((s for s in subs if s.get("email","").strip().lower() == login_email.strip().lower()), None)
                if not found:
                    st.error("No account found for that email.")
                elif not _verify_pw(found, login_pw):
                    st.error("Incorrect password.")
                else:
                    st.session_state.portal_logged_in = True
                    st.session_state.portal_email = found["email"].strip().lower()
                    st.session_state.portal_name = found.get("name") or login_email.split("@")[0].title()
                    st.rerun()

            st.markdown(craft_card_end(), unsafe_allow_html=True)
        st.stop()

    # ── AUTHENTICATED PORTAL ─────────────────────────────────────────────────
    email = st.session_state.portal_email
    name  = st.session_state.portal_name

    subs = load_subscribers()
    sub = next((s for s in subs if s.get("email","").strip().lower() == email), None)
    if not sub:
        st.session_state.portal_logged_in = False
        st.rerun()

    # Build vault items
    seen_dict = main.load_seen_dict()
    raw = seen_dict.get(email, {}) if isinstance(seen_dict, dict) else {}
    vault_items = []
    for url, meta in raw.items():
        if not url or str(url).startswith("__"):
            continue
        m = meta if isinstance(meta, dict) else {}
        item_type = m.get("type") or classify_item(url, m)
        vault_items.append({
            "url": url,
            "title": derive_title(url, m),
            "type": item_type,
            "date": m.get("date", ""),
            "domain": urllib.parse.urlparse(url).netloc.replace("www.", ""),
            "location": m.get("location"),
            "salary": m.get("salary"),
        })
    vault_items.sort(key=lambda x: str(x.get("date", "")), reverse=True)
    courses = [i for i in vault_items if i["type"] == "course"]
    jobs    = [i for i in vault_items if i["type"] == "job"]

    today_str = datetime.date.today().isoformat()
    hour      = datetime.datetime.now().hour
    greeting  = "Good morning" if hour < 12 else ("Good afternoon" if hour < 17 else "Good evening")
    is_active = sub.get("active", True)
    est_saved = max(len(courses) * 85, 290)

    # ── TOPBAR ───────────────────────────────────────────────────────────────
    hcol1, hcol2 = st.columns([6, 1])
    with hcol1:
        active_badge = pill("● Active Radar", "green") if is_active else pill("● Paused", "amber")
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:4px;">
            <div style="width:38px;height:38px;border-radius:12px;background:linear-gradient(135deg,#4f46e5,#3b82f6);display:flex;align-items:center;justify-content:center;font-size:18px;">🎯</div>
            <div>
                <div style="font-size:18px;font-weight:800;color:#f1f5f9;">{greeting}, {name} 👋</div>
                <div style="font-size:11px;color:#64748b;">Member Hub · {active_badge}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with hcol2:
        if st.button("Sign Out", key="portal_logout"):
            st.session_state.portal_logged_in = False
            st.rerun()

    st.markdown("<hr style='margin:8px 0 16px;border-color:rgba(255,255,255,0.07);'>", unsafe_allow_html=True)

    # ── BENTO HERO GRID ───────────────────────────────────────────────────────
    bc1, bc2, bc3 = st.columns(3)

    with bc1:
        # Streak Card
        today_checked = st.session_state.last_checkin == today_str
        week_dots_html = "".join([
            f'<div style="width:9px;height:9px;border-radius:50%;background:{"#f59e0b" if i < st.session_state.streak_days else "#1e293b"};box-shadow:{"0 0 8px rgba(245,158,11,0.5)" if i < st.session_state.streak_days else "none"};"></div>'
            for i in range(7)
        ])
        xp = st.session_state.xp
        level = "🌱 Career Seedling" if xp < 150 else ("⚡ Career Sprinter" if xp < 300 else ("🎯 Career Sniper" if xp < 500 else "🚀 Career Rocketeer"))

        st.markdown(f"""
        {craft_card_start()}
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
            <div style="font-size:11px;font-weight:700;color:#f59e0b;text-transform:uppercase;letter-spacing:0.08em;">🔥 Daily Streak</div>
            {pill(f"Day {st.session_state.streak_days}", "amber")}
        </div>
        <div style="display:flex;align-items:baseline;gap:6px;margin-bottom:4px;">
            <span style="font-size:28px;font-weight:900;color:#f1f5f9;line-height:1;">{xp}</span>
            <span style="font-size:12px;font-weight:700;color:#f59e0b;">XP</span>
        </div>
        <div style="font-size:11px;color:#94a3b8;margin-bottom:14px;">{level}</div>
        <div style="border-top:1px solid rgba(255,255,255,0.07);padding-top:12px;display:flex;align-items:center;justify-content:space-between;">
            <div style="display:flex;align-items:center;gap:5px;">{week_dots_html}</div>
            <div style="font-size:10px;color:{"#10b981" if today_checked else "#64748b"};font-weight:600;">
                {"✓ Checked-in today" if today_checked else "Check-in available"}
            </div>
        </div>
        {craft_card_end()}
        """, unsafe_allow_html=True)

        if not today_checked:
            if st.button("⚡ Claim +25 XP Today", key="checkin_btn", use_container_width=True):
                st.session_state.streak_days += 1
                st.session_state.xp += 25
                st.session_state.last_checkin = today_str
                st.rerun()

    with bc2:
        # Flash Freebies Countdown
        now = datetime.datetime.now()
        eod = now.replace(hour=23, minute=59, second=59)
        diff = eod - now
        h_left = diff.seconds // 3600
        m_left = (diff.seconds % 3600) // 60
        s_left = diff.seconds % 60

        st.markdown(f"""
        {craft_card_start()}
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
            <div style="display:flex;align-items:center;gap:6px;">
                <div style="width:8px;height:8px;border-radius:50%;background:#f43f5e;animation:pulse 2s infinite;"></div>
                <span style="font-size:11px;font-weight:700;color:#f43f5e;text-transform:uppercase;letter-spacing:0.08em;">Flash Freebies</span>
            </div>
            {pill("100% OFF", "rose")}
        </div>
        <div style="font-size:14px;font-weight:700;color:#f1f5f9;margin-bottom:4px;">Coupons Expiring Tonight</div>
        <div style="font-size:11px;color:#94a3b8;margin-bottom:14px;">Udemy &amp; certification coupons vanish at midnight. Claim them now!</div>
        <div style="border-top:1px solid rgba(255,255,255,0.07);padding-top:12px;display:flex;align-items:center;justify-content:space-between;">
            <div style="display:flex;align-items:center;gap:4px;font-family:'JetBrains Mono',monospace;">
                <div style="text-align:center;">
                    <div style="font-size:22px;font-weight:800;color:#f1f5f9;line-height:1;">{h_left:02d}</div>
                    <div style="font-size:9px;color:#64748b;font-weight:600;letter-spacing:0.08em;">HRS</div>
                </div>
                <span style="font-size:18px;color:#f43f5e;font-weight:800;padding-bottom:14px;">:</span>
                <div style="text-align:center;">
                    <div style="font-size:22px;font-weight:800;color:#f1f5f9;line-height:1;">{m_left:02d}</div>
                    <div style="font-size:9px;color:#64748b;font-weight:600;letter-spacing:0.08em;">MIN</div>
                </div>
                <span style="font-size:18px;color:#f43f5e;font-weight:800;padding-bottom:14px;">:</span>
                <div style="text-align:center;">
                    <div style="font-size:22px;font-weight:800;color:#f1f5f9;line-height:1;">{s_left:02d}</div>
                    <div style="font-size:9px;color:#64748b;font-weight:600;letter-spacing:0.08em;">SEC</div>
                </div>
            </div>
            <div style="font-size:12px;color:#fb7185;font-weight:700;">{len(courses)} free →</div>
        </div>
        {craft_card_end()}
        """, unsafe_allow_html=True)

    with bc3:
        # Value Metrics
        st.markdown(f"""
        {craft_card_start()}
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
            <div style="font-size:11px;font-weight:700;color:#10b981;text-transform:uppercase;letter-spacing:0.08em;">💰 Value Delivered</div>
            {pill("Today", "green")}
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px;">
            <div style="background:rgba(255,255,255,0.025);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:10px 12px;">
                <div style="font-size:9px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px;">Free Courses</div>
                <div style="display:flex;align-items:baseline;gap:4px;">
                    <span style="font-size:24px;font-weight:900;color:#f1f5f9;">{len(courses)}</span>
                    <span style="font-size:10px;color:#10b981;font-weight:700;">100% free</span>
                </div>
            </div>
            <div style="background:rgba(255,255,255,0.025);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:10px 12px;">
                <div style="font-size:9px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px;">Live Jobs</div>
                <div style="display:flex;align-items:baseline;gap:4px;">
                    <span style="font-size:24px;font-weight:900;color:#f1f5f9;">{len(jobs)}</span>
                    <span style="font-size:10px;color:#3b82f6;font-weight:700;">remote</span>
                </div>
            </div>
        </div>
        <div style="border-top:1px solid rgba(255,255,255,0.07);padding-top:10px;display:flex;align-items:center;justify-content:space-between;">
            <span style="font-size:11px;color:#94a3b8;font-weight:500;">Est. Tuition Saved</span>
            <span style="font-size:14px;font-weight:900;color:#10b981;font-family:'JetBrains Mono',monospace;">${est_saved}+ USD</span>
        </div>
        {craft_card_end()}
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    # ── MAIN TABS ─────────────────────────────────────────────────────────────
    tab_vault_c, tab_vault_j, tab_quiz, tab_pitch, tab_settings = st.tabs([
        f"📚 Courses ({len(courses)})",
        f"💼 Jobs ({len(jobs)})",
        "🧠 Daily Byte",
        "🤖 AI Pitch",
        "⚙️ Settings",
    ])

    # ── TAB: COURSES ──────────────────────────────────────────────────────────
    with tab_vault_c:
        sc1, sc2 = st.columns([4, 1])
        with sc1:
            course_q = st.text_input("", placeholder="🔍  Search free courses…", label_visibility="collapsed", key="cq")
        with sc2:
            csort = st.selectbox("", ["Newest", "A → Z", "By Platform"], label_visibility="collapsed", key="csort")

        filtered_courses = courses
        if course_q:
            q = course_q.strip().lower()
            filtered_courses = [c for c in courses if q in c["title"].lower() or q in c["domain"].lower()]
        if csort == "A → Z":
            filtered_courses = sorted(filtered_courses, key=lambda x: x["title"])
        elif csort == "By Platform":
            filtered_courses = sorted(filtered_courses, key=lambda x: x["domain"])

        st.markdown(f'<div style="font-size:12px;color:#64748b;font-weight:600;margin-bottom:8px;">Showing {len(filtered_courses)} free certified courses</div>', unsafe_allow_html=True)

        if not filtered_courses:
            st.markdown("""
            <div style="text-align:center;padding:60px 20px;color:#334155;">
                <div style="font-size:48px;margin-bottom:12px;">📚</div>
                <div style="font-size:14px;font-weight:600;color:#475569;">No courses yet</div>
                <div style="font-size:12px;margin-top:4px;">Run the digest engine to harvest today's free courses.</div>
            </div>""", unsafe_allow_html=True)
        else:
            html_rows = "".join(item_row_html(c) for c in filtered_courses)
            st.markdown(html_rows, unsafe_allow_html=True)

    # ── TAB: JOBS ─────────────────────────────────────────────────────────────
    with tab_vault_j:
        jc1, jc2 = st.columns([4, 1])
        with jc1:
            job_q = st.text_input("", placeholder="🔍  Search roles, companies, locations…", label_visibility="collapsed", key="jq")
        with jc2:
            jsort = st.selectbox("", ["Newest", "A → Z", "By Source"], label_visibility="collapsed", key="jsort")

        # Source filter chips (using selectbox)
        all_domains = sorted(set(j["domain"] for j in jobs if j["domain"]))
        if all_domains:
            src_filter = st.selectbox("Filter by source", ["All Sources"] + all_domains, label_visibility="collapsed", key="src_filter")
        else:
            src_filter = "All Sources"

        filtered_jobs = jobs
        if src_filter != "All Sources":
            filtered_jobs = [j for j in jobs if j["domain"] == src_filter]
        if job_q:
            q = job_q.strip().lower()
            filtered_jobs = [j for j in filtered_jobs if q in j["title"].lower() or q in j["domain"].lower() or q in (j.get("location") or "").lower()]
        if jsort == "A → Z":
            filtered_jobs = sorted(filtered_jobs, key=lambda x: x["title"])
        elif jsort == "By Source":
            filtered_jobs = sorted(filtered_jobs, key=lambda x: x["domain"])

        st.markdown(f'<div style="font-size:12px;color:#64748b;font-weight:600;margin-bottom:8px;">Showing {len(filtered_jobs)} active opportunities</div>', unsafe_allow_html=True)

        if not filtered_jobs:
            st.markdown("""
            <div style="text-align:center;padding:60px 20px;color:#334155;">
                <div style="font-size:48px;margin-bottom:12px;">💼</div>
                <div style="font-size:14px;font-weight:600;color:#475569;">No jobs yet</div>
                <div style="font-size:12px;margin-top:4px;">Jobs from LinkedIn, Naukri, Remotive appear after digest runs.</div>
            </div>""", unsafe_allow_html=True)
        else:
            # Render with AI Pitch button — use Streamlit columns for each job
            for j in filtered_jobs:
                jrow1, jrow2, jrow3 = st.columns([6, 1, 1])
                with jrow1:
                    st.markdown(item_row_html(j), unsafe_allow_html=True)
                with jrow2:
                    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                    if st.button("🤖 Pitch", key=f"pitch_{j['url'][:30]}"):
                        st.session_state.pitch_job = j
                        st.session_state.active_tab_hint = "pitch"
                        st.rerun()
                with jrow3:
                    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)

    # ── TAB: DAILY INTERVIEW BYTE ─────────────────────────────────────────────
    with tab_quiz:
        quiz = get_todays_quiz()
        quiz_key = f"quiz_{today_str}"
        already_answered = st.session_state.quiz_answered.get(quiz_key)

        st.markdown(f"""
        {craft_card_start()}
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
            {pill(quiz['category'], 'violet')}
            {pill('⚡ +50 XP Reward', 'amber')}
        </div>
        <div style="font-size:11px;color:#64748b;margin-bottom:8px;font-weight:600;">Challenge for {today_str}</div>
        <div style="font-size:16px;font-weight:700;color:#f1f5f9;line-height:1.5;margin-bottom:20px;">{quiz['question']}</div>
        {craft_card_end()}
        """, unsafe_allow_html=True)

        LETTERS = ["A", "B", "C", "D"]
        for idx, opt in enumerate(quiz["options"]):
            if already_answered is not None:
                is_correct_opt = idx == quiz["answer"]
                is_selected    = idx == already_answered
                if is_correct_opt:
                    bg = "rgba(16,185,129,0.1)"; border = "rgba(16,185,129,0.4)"; fg = "#6ee7b7"; suffix = " ✓"
                elif is_selected and not is_correct_opt:
                    bg = "rgba(244,63,94,0.1)"; border = "rgba(244,63,94,0.4)"; fg = "#fda4af"; suffix = " ✗"
                else:
                    bg = "rgba(8,10,18,0.5)"; border = "rgba(255,255,255,0.04)"; fg = "#334155"; suffix = ""

                st.markdown(f"""
                <div style="padding:12px 16px;border-radius:12px;border:1px solid {border};background:{bg};
                    font-size:12px;font-weight:500;color:{fg};margin-bottom:8px;">
                    <strong style="color:#475569;margin-right:8px;">{LETTERS[idx]}.</strong>{opt}{suffix}
                </div>""", unsafe_allow_html=True)
            else:
                if st.button(f"{LETTERS[idx]}.  {opt}", key=f"quiz_opt_{idx}", use_container_width=True):
                    st.session_state.quiz_answered[quiz_key] = idx
                    if idx == quiz["answer"]:
                        st.session_state.xp += 50
                    st.rerun()

        if already_answered is not None:
            is_right = already_answered == quiz["answer"]
            if is_right:
                st.markdown(f"""
                <div style="margin-top:16px;padding:16px;border-radius:12px;border:1px solid rgba(16,185,129,0.25);
                    background:rgba(16,185,129,0.07);color:#6ee7b7;font-size:12px;line-height:1.6;">
                    <strong style="display:block;margin-bottom:4px;">🎉 Correct! +50 XP earned!</strong>
                    {quiz['explanation']}
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="margin-top:16px;padding:16px;border-radius:12px;border:1px solid rgba(245,158,11,0.25);
                    background:rgba(245,158,11,0.07);color:#fcd34d;font-size:12px;line-height:1.6;">
                    <strong style="display:block;margin-bottom:4px;">💡 Key Takeaway:</strong>
                    {quiz['explanation']}
                </div>""", unsafe_allow_html=True)

    # ── TAB: AI PITCH GENERATOR ───────────────────────────────────────────────
    with tab_pitch:
        st.markdown(f"""
        {craft_card_start()}
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;padding-bottom:14px;border-bottom:1px solid rgba(255,255,255,0.07);">
            <div style="width:40px;height:40px;border-radius:12px;background:rgba(99,102,241,0.15);border:1px solid rgba(99,102,241,0.3);display:flex;align-items:center;justify-content:center;font-size:20px;">🤖</div>
            <div>
                <div style="font-size:14px;font-weight:700;color:#f1f5f9;">1-Click AI Outreach Pitch Generator</div>
                <div style="font-size:11px;color:#64748b;">Generate a tailored LinkedIn note + cold email for any job in seconds</div>
            </div>
        </div>
        {craft_card_end()}
        """, unsafe_allow_html=True)

        pre_title   = st.session_state.pitch_job["title"]   if st.session_state.pitch_job else ""
        pre_company = st.session_state.pitch_job["domain"]  if st.session_state.pitch_job else ""

        pc1, pc2 = st.columns(2)
        with pc1:
            pitch_title   = st.text_input("Job Title / Role", value=pre_title, placeholder="e.g. Senior Python Developer")
        with pc2:
            pitch_company = st.text_input("Company Name", value=pre_company, placeholder="e.g. Infosys")

        pitch_name = st.text_input("Your Name", value=name, placeholder="Your full name")

        if st.button("🤖 Generate AI Pitch Now", use_container_width=True):
            if not pitch_title:
                st.error("Please enter the job title.")
            else:
                li_note = (
                    f"Hi {pitch_company or 'Team'}, I noticed your opening for {pitch_title} and was immediately drawn to your team's mission. "
                    f"With hands-on experience building scalable systems and a passion for creating impact, I'd love to connect and share how my background fits your needs. "
                    f"Best, {pitch_name}"
                )
                cold_email = (
                    f"Subject: Application & Quick Introduction – {pitch_title} | {pitch_name}\n\n"
                    f"Hi {pitch_company or 'Hiring Team'},\n\n"
                    f"I came across the {pitch_title} opening and was genuinely excited by the work your team is doing.\n\n"
                    f"I bring deep hands-on expertise in full-stack architecture, automation, and cloud-native solutions, "
                    f"with a proven track record of shipping reliable, high-performance features that move the needle.\n\n"
                    f"I'd welcome a 15-minute call to discuss how I can accelerate your team's current goals.\n\n"
                    f"Portfolio & Resume: [Insert Link]\n"
                    f"LinkedIn: [Insert Profile URL]\n\n"
                    f"Best regards,\n{pitch_name}"
                )

                st.markdown("""
                <div style="font-size:11px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px;margin-top:16px;">
                    LinkedIn Connection Note (300 chars)
                </div>""", unsafe_allow_html=True)
                st.code(li_note, language=None)

                st.markdown("""
                <div style="font-size:11px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px;margin-top:12px;">
                    Full Cold Application Email
                </div>""", unsafe_allow_html=True)
                st.code(cold_email, language=None)

                st.success("✓ Pitches generated! Click the copy icon (top-right of each block) to copy.")
                st.session_state.pitch_job = None

    # ── TAB: SETTINGS ─────────────────────────────────────────────────────────
    with tab_settings:
        st.markdown(f"""
        {craft_card_start()}
        <div style="font-size:14px;font-weight:700;color:#f1f5f9;margin-bottom:4px;">⚙️ Radar Preferences</div>
        <div style="font-size:11px;color:#64748b;">Customize your daily digest, sources, and targets.</div>
        {craft_card_end()}
        """, unsafe_allow_html=True)

        with st.form("portal_settings_form"):
            s_active = st.checkbox(
                "Morning Email Digest Active (~8 AM IST)",
                value=bool(sub.get("active", True))
            )
            st.caption("Uncheck to pause without losing your streak.")

            existing_kws = ", ".join(list({*sub.get("keywords", []), *sub.get("job_searches", [])}))
            s_keywords = st.text_area(
                "Target Keywords & Roles (comma-separated)",
                value=existing_kws,
                placeholder="python, machine learning, remote, devops…"
            )

            all_job_opts    = list(getattr(config, "AVAILABLE_JOB_SOURCES", {}).keys())
            all_course_opts = list(getattr(config, "AVAILABLE_COURSE_PLATFORMS", {}).keys())
            cur_job_srcs    = [s for s in (sub.get("job_sources") or all_job_opts) if s in all_job_opts]
            cur_course_srcs = [s for s in (sub.get("course_sources") or all_course_opts) if s in all_course_opts]

            s_job_sources = st.multiselect(
                "Active Job Boards",
                options=all_job_opts,
                default=cur_job_srcs,
                format_func=lambda k: getattr(config, "AVAILABLE_JOB_SOURCES", {}).get(k, k),
            )
            s_course_srcs = st.multiselect(
                "Course Platforms",
                options=all_course_opts,
                default=cur_course_srcs,
                format_func=lambda k: getattr(config, "AVAILABLE_COURSE_PLATFORMS", {}).get(k, k),
            )

            save_prefs = st.form_submit_button("💾 Save Preferences", use_container_width=True)

        if save_prefs:
            kw_list = [k.strip() for k in s_keywords.split(",") if k.strip()]
            idx = next((i for i, s in enumerate(subs) if s.get("email","").strip().lower() == email), None)
            if idx is not None:
                subs[idx]["active"]         = bool(s_active)
                subs[idx]["keywords"]       = kw_list
                subs[idx]["job_searches"]   = kw_list
                subs[idx]["job_sources"]    = s_job_sources
                subs[idx]["course_sources"] = s_course_srcs
                save_subscribers(subs)
                st.success("✓ Preferences saved successfully!")

        st.markdown("<hr style='border-color:rgba(255,255,255,0.07);margin:16px 0;'>", unsafe_allow_html=True)
        st.markdown('<div style="font-size:12px;font-weight:700;color:#f1f5f9;margin-bottom:10px;">🔐 Change Password</div>', unsafe_allow_html=True)
        with st.form("change_pw_form"):
            old_pw = st.text_input("Current Password", type="password")
            new_pw = st.text_input("New Password (min 6 chars)", type="password")
            change_pw = st.form_submit_button("Update Password")

        if change_pw:
            if not _verify_pw(sub, old_pw):
                st.error("Current password is incorrect.")
            elif len(new_pw) < 6:
                st.error("New password must be at least 6 characters.")
            else:
                idx = next((i for i, s in enumerate(subs) if s.get("email","").strip().lower() == email), None)
                if idx is not None:
                    subs[idx]["portal_password"] = _hash_pw(new_pw)
                    save_subscribers(subs)
                    st.success("✓ Password updated!")


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 2 — DIGEST ENGINE
# ═════════════════════════════════════════════════════════════════════════════
elif nav_page == "🚀 Digest Engine":
    st.markdown(f"""
    {craft_card_start()}
    <div style="font-size:22px;font-weight:800;color:#f1f5f9;margin-bottom:4px;">🚀 Digest Engine</div>
    <div style="font-size:13px;color:#64748b;">Trigger the harvester to scan RSS feeds &amp; job boards and send personalized digests.</div>
    {craft_card_end()}
    """, unsafe_allow_html=True)

    subscribers = load_subscribers()
    recipient_options = ["ALL Subscribers"] + [s.get("email") for s in subscribers if s.get("email")]

    col_a, col_b = st.columns(2)
    with col_a:
        run_mode = st.radio(
            "Execution Mode",
            ["🔵 Dry Run (Safe Simulation — No Emails)", "🔴 Live Run (Send Real Emails)"],
        )
        is_dry = "Dry Run" in run_mode
    with col_b:
        target_sel = st.selectbox("Target Recipient", recipient_options)
        weekly_flag = st.checkbox("Include Weekly Insights Report")

    if not is_dry:
        st.markdown(f"""
        <div style="background:rgba(244,63,94,0.08);border:1px solid rgba(244,63,94,0.2);border-radius:12px;padding:10px 14px;margin-bottom:12px;font-size:12px;color:#fda4af;">
            ⚠️  <strong>Live mode</strong> will send real emails to recipients. Enter admin password to confirm.
        </div>""", unsafe_allow_html=True)
        admin_pw_input = st.text_input("Admin Password", type="password")
    else:
        admin_pw_input = ""

    if st.button("🚀 Execute Digest Engine", use_container_width=True):
        if not is_dry and admin_pw_input != ADMIN_PASSWORD:
            st.error("Invalid admin password. Live sending blocked.")
        else:
            target_recipients = None
            if target_sel != "ALL Subscribers":
                target_recipients = [s for s in subscribers if s.get("email") == target_sel]

            log_buf = io.StringIO()
            with st.spinner("🔄 Harvesting courses and jobs…"):
                with contextlib.redirect_stdout(log_buf):
                    try:
                        main.run(dry_run=is_dry, weekly=weekly_flag, target_recipients=target_recipients)
                    except Exception as e:
                        print(f"[Error] {e}")

            st.success("✅ Engine execution completed!")
            st.markdown('<div style="font-size:12px;font-weight:700;color:#94a3b8;margin:12px 0 6px;">Console Output</div>', unsafe_allow_html=True)
            st.code(log_buf.getvalue() or "(No output)", language="text")


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 3 — SUBSCRIBERS
# ═════════════════════════════════════════════════════════════════════════════
elif nav_page == "👥 Subscribers":
    st.markdown(f"""
    {craft_card_start()}
    <div style="font-size:22px;font-weight:800;color:#f1f5f9;margin-bottom:4px;">👥 Subscribers &amp; Preferences</div>
    <div style="font-size:13px;color:#64748b;">Manage group members, source APIs, keyword filters, and delivery settings.</div>
    {craft_card_end()}
    """, unsafe_allow_html=True)

    subscribers = load_subscribers()

    with st.expander("➕ Add New Subscriber"):
        with st.form("add_sub_form", clear_on_submit=True):
            fc1, fc2 = st.columns(2)
            with fc1:
                f_name  = st.text_input("Full Name", placeholder="e.g. Ojasvi")
                f_email = st.text_input("Email", placeholder="e.g. ojasvi@example.com")
            with fc2:
                f_max  = st.number_input("Max Items Daily", 1, 50, 15)
                f_active = st.checkbox("Active from Day 1", value=True)
            f_kws  = st.text_area("Course Keywords (comma-separated)", "python, ai, project management")
            f_jobs = st.text_area("Job Searches (comma-separated)", "remote python, product manager, devops")
            if st.form_submit_button("Add Subscriber →", use_container_width=True):
                if not f_email.strip() or not f_name.strip():
                    st.error("Name and Email are required.")
                elif any(s.get("email","").lower() == f_email.strip().lower() for s in subscribers):
                    st.error(f"Email '{f_email}' already exists.")
                else:
                    subscribers.append({
                        "name": f_name.strip(), "email": f_email.strip().lower(),
                        "active": f_active, "max_items": int(f_max),
                        "keywords": [k.strip() for k in f_kws.split(",") if k.strip()],
                        "job_searches": [j.strip() for j in f_jobs.split(",") if j.strip()],
                        "course_feeds": [], "welcome_sent": False,
                    })
                    save_subscribers(subscribers)
                    st.success(f"✓ Added {f_name}!")
                    st.rerun()

    st.markdown(f'<div style="font-size:12px;font-weight:700;color:#94a3b8;margin:16px 0 10px;">Current Members ({len(subscribers)})</div>', unsafe_allow_html=True)

    all_job_opts    = list(getattr(config, "AVAILABLE_JOB_SOURCES", {}).keys())
    all_course_opts = list(getattr(config, "AVAILABLE_COURSE_PLATFORMS", {}).keys())

    for idx, sub in enumerate(subscribers):
        icon = "🟢" if sub.get("active", True) else "⏸️"
        with st.expander(f"{icon} {sub.get('name','?')}  ·  {sub.get('email','')}"):
            with st.form(f"edit_sub_{idx}"):
                e1, e2 = st.columns(2)
                with e1:
                    s_name   = st.text_input("Name", value=sub.get("name",""), key=f"n{idx}")
                    s_active = st.checkbox("Active", value=sub.get("active", True), key=f"a{idx}")
                    s_max    = st.number_input("Max Items", 1, 50, sub.get("max_items", 15), key=f"m{idx}")
                with e2:
                    s_kw = st.text_area("Keywords", value=", ".join(sub.get("keywords", [])), key=f"k{idx}")
                    s_js = st.text_area("Job Searches", value=", ".join(sub.get("job_searches", [])), key=f"j{idx}")

                cur_js = [s for s in (sub.get("job_sources") or all_job_opts) if s in all_job_opts]
                cur_cs = [c for c in (sub.get("course_sources") or all_course_opts) if c in all_course_opts]
                s_jsrc = st.multiselect("Job Boards", all_job_opts, default=cur_js,
                                        format_func=lambda k: getattr(config,"AVAILABLE_JOB_SOURCES",{}).get(k,k), key=f"js{idx}")
                s_csrc = st.multiselect("Course Platforms", all_course_opts, default=cur_cs,
                                        format_func=lambda k: getattr(config,"AVAILABLE_COURSE_PLATFORMS",{}).get(k,k), key=f"cs{idx}")

                if st.form_submit_button("Save Changes"):
                    subscribers[idx].update({
                        "name": s_name.strip(), "active": bool(s_active), "max_items": int(s_max),
                        "keywords": [k.strip() for k in s_kw.split(",") if k.strip()],
                        "job_searches": [j.strip() for j in s_js.split(",") if j.strip()],
                        "job_sources": s_jsrc, "course_sources": s_csrc,
                    })
                    save_subscribers(subscribers)
                    st.success("✓ Saved!")
                    st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 4 — SOURCE HEALTH INSPECTOR
# ═════════════════════════════════════════════════════════════════════════════
elif nav_page == "📡 Source Health":
    st.markdown(f"""
    {craft_card_start()}
    <div style="font-size:22px;font-weight:800;color:#f1f5f9;margin-bottom:4px;">📡 Source Health Inspector</div>
    <div style="font-size:13px;color:#64748b;">Test live connectivity to all configured course RSS feeds and job board APIs.</div>
    {craft_card_end()}
    """, unsafe_allow_html=True)

    if st.button("🔄 Test All Sources Now", use_container_width=True):
        feeds = getattr(config, "COURSE_FEEDS", [])
        st.markdown(f'<div style="font-size:13px;font-weight:700;color:#f1f5f9;margin:16px 0 8px;">📚 Course Feeds ({len(feeds)})</div>', unsafe_allow_html=True)
        for url in feeds:
            try:
                res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
                if res.status_code == 200:
                    st.success(f"🟢 {url}")
                else:
                    st.warning(f"🟡 {url}  (HTTP {res.status_code})")
            except Exception as e:
                st.error(f"🔴 {url}  ({e})")

        st.markdown('<div style="font-size:13px;font-weight:700;color:#f1f5f9;margin:16px 0 8px;">💼 Job Board APIs</div>', unsafe_allow_html=True)
        job_tests = [
            ("LinkedIn Jobs", "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=python&location=India&f_WT=2&start=0"),
            ("Naukri.com", "https://www.naukri.com/python-jobs"),
            ("Remotive API", "https://remotive.com/api/remote-jobs?limit=2"),
            ("Jobicy API",   "https://jobicy.com/api/v2/remote-jobs?count=2"),
            ("Arbeitnow API","https://www.arbeitnow.com/api/job-board-api"),
            ("Adzuna India", "https://www.adzuna.in/search.rss?q=python&country=in"),
        ]
        for name_t, url in job_tests:
            try:
                res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
                if res.status_code in (200, 201):
                    st.success(f"🟢 **{name_t}** — Operational")
                else:
                    st.warning(f"🟡 **{name_t}** — HTTP {res.status_code}")
            except Exception as e:
                st.error(f"🔴 **{name_t}** — Failed ({e})")
    else:
        st.info("Click the button above to run a live health check on all platforms.")


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 5 — MARKET INSIGHTS
# ═════════════════════════════════════════════════════════════════════════════
elif nav_page == "📊 Market Insights":
    st.markdown(f"""
    {craft_card_start()}
    <div style="font-size:22px;font-weight:800;color:#f1f5f9;margin-bottom:4px;">📊 Weekly Market Insights</div>
    <div style="font-size:13px;color:#64748b;">Analyzes 7-day opportunity data to surface skill demand and hiring trends.</div>
    {craft_card_end()}
    """, unsafe_allow_html=True)

    seen_dict = main.load_seen_dict()
    report = main.generate_weekly_insights(seen_dict, days=7)
    st.markdown(report)


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 6 — DB EXPLORER
# ═════════════════════════════════════════════════════════════════════════════
elif nav_page == "☁️ DB Explorer":
    st.markdown(f"""
    {craft_card_start()}
    <div style="font-size:22px;font-weight:800;color:#f1f5f9;margin-bottom:4px;">☁️ Cloud DB Explorer</div>
    <div style="font-size:13px;color:#64748b;">Inspect seen links stored in Supabase Cloud DB (or local fallback seen.json).</div>
    {craft_card_end()}
    """, unsafe_allow_html=True)

    seen_dict = main.load_seen_dict()
    total = sum(len(v) for v in seen_dict.values() if isinstance(v, dict))

    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("Total Tracked Links", f"{total:,}")
    mc2.metric("Subscribers in DB", len(seen_dict))
    mc3.metric("Storage Mode", "Supabase ☁️" if db.is_supabase_enabled() else "Local JSON 📁")

    st.markdown("<hr style='border-color:rgba(255,255,255,0.07);margin:16px 0;'>", unsafe_allow_html=True)

    for em, items in seen_dict.items():
        if isinstance(items, dict):
            with st.expander(f"📁 {em}  ({len(items)} links tracked)"):
                st.json(items)
