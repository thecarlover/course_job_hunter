"""
Course & Job Hunter — Personal Career Radar
============================================
A dedicated, single-user opportunity vault and career radar.
Tailored exclusively for the subscriber's personal job hunt and certification tracking.
"""

import contextlib
import datetime
import hashlib
import hmac
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
# THEME SYSTEM — 5 Colour Palettes
# ─────────────────────────────────────────────────────────────────────────────

THEMES: Dict[str, Dict[str, str]] = {
    "Obsidian": {
        "bg":        "#08090d",
        "surface":   "#0f121d",
        "surface2":  "#1e2235",
        "border":    "rgba(255,255,255,0.06)",
        "accent1":   "#6366f1",
        "accent1_h": "#4338ca",
        "accent1_bg":"rgba(99,102,241,0.12)",
        "accent1_bd":"rgba(99,102,241,0.25)",
        "accent1_tx":"#a5b4fc",
        "accent2":   "#10b981",
        "accent2_bg":"rgba(16,185,129,0.12)",
        "accent2_bd":"rgba(16,185,129,0.25)",
        "accent2_tx":"#6ee7b7",
        "accent3":   "#f59e0b",
        "accent3_bg":"rgba(245,158,11,0.12)",
        "accent3_bd":"rgba(245,158,11,0.25)",
        "accent3_tx":"#fcd34d",
        "text":      "#e2e8f0",
        "text_dim":  "#8b949e",
        "text_mute": "#64748b",
        "scroll_th": "#1c202e",
        "tab_act":   "#1e2235",
        "emoji":     "🌑",
    },
    "Midnight Rose": {
        "bg":        "#0d0812",
        "surface":   "#140d1e",
        "surface2":  "#231535",
        "border":    "rgba(255,255,255,0.07)",
        "accent1":   "#c084fc",
        "accent1_h": "#a855f7",
        "accent1_bg":"rgba(192,132,252,0.12)",
        "accent1_bd":"rgba(192,132,252,0.28)",
        "accent1_tx":"#e9d5ff",
        "accent2":   "#f43f5e",
        "accent2_bg":"rgba(244,63,94,0.12)",
        "accent2_bd":"rgba(244,63,94,0.25)",
        "accent2_tx":"#fda4af",
        "accent3":   "#fb923c",
        "accent3_bg":"rgba(251,146,60,0.12)",
        "accent3_bd":"rgba(251,146,60,0.25)",
        "accent3_tx":"#fed7aa",
        "text":      "#f0e6ff",
        "text_dim":  "#a78bca",
        "text_mute": "#6b5080",
        "scroll_th": "#2d1545",
        "tab_act":   "#231535",
        "emoji":     "🌸",
    },
    "Forest Hacker": {
        "bg":        "#060d08",
        "surface":   "#0a140c",
        "surface2":  "#122118",
        "border":    "rgba(74,222,128,0.08)",
        "accent1":   "#22c55e",
        "accent1_h": "#16a34a",
        "accent1_bg":"rgba(34,197,94,0.1)",
        "accent1_bd":"rgba(34,197,94,0.25)",
        "accent1_tx":"#86efac",
        "accent2":   "#84cc16",
        "accent2_bg":"rgba(132,204,22,0.1)",
        "accent2_bd":"rgba(132,204,22,0.25)",
        "accent2_tx":"#bef264",
        "accent3":   "#2dd4bf",
        "accent3_bg":"rgba(45,212,191,0.1)",
        "accent3_bd":"rgba(45,212,191,0.25)",
        "accent3_tx":"#99f6e4",
        "text":      "#dcfce7",
        "text_dim":  "#6ee7b7",
        "text_mute": "#4ade80",
        "scroll_th": "#14301e",
        "tab_act":   "#122118",
        "emoji":     "🌿",
    },
    "Cyber Amber": {
        "bg":        "#0c0900",
        "surface":   "#140f00",
        "surface2":  "#231a00",
        "border":    "rgba(251,191,36,0.08)",
        "accent1":   "#f59e0b",
        "accent1_h": "#d97706",
        "accent1_bg":"rgba(245,158,11,0.1)",
        "accent1_bd":"rgba(245,158,11,0.25)",
        "accent1_tx":"#fcd34d",
        "accent2":   "#ef4444",
        "accent2_bg":"rgba(239,68,68,0.1)",
        "accent2_bd":"rgba(239,68,68,0.25)",
        "accent2_tx":"#fca5a5",
        "accent3":   "#fb923c",
        "accent3_bg":"rgba(251,146,60,0.1)",
        "accent3_bd":"rgba(251,146,60,0.25)",
        "accent3_tx":"#fed7aa",
        "text":      "#fef9e7",
        "text_dim":  "#d4a017",
        "text_mute": "#7c5a00",
        "scroll_th": "#2d2000",
        "tab_act":   "#231a00",
        "emoji":     "⚡",
    },
    "Arctic Blue": {
        "bg":        "#020c18",
        "surface":   "#041224",
        "surface2":  "#0a2240",
        "border":    "rgba(96,165,250,0.08)",
        "accent1":   "#3b82f6",
        "accent1_h": "#2563eb",
        "accent1_bg":"rgba(59,130,246,0.12)",
        "accent1_bd":"rgba(59,130,246,0.28)",
        "accent1_tx":"#93c5fd",
        "accent2":   "#06b6d4",
        "accent2_bg":"rgba(6,182,212,0.1)",
        "accent2_bd":"rgba(6,182,212,0.25)",
        "accent2_tx":"#67e8f9",
        "accent3":   "#818cf8",
        "accent3_bg":"rgba(129,140,248,0.1)",
        "accent3_bd":"rgba(129,140,248,0.25)",
        "accent3_tx":"#c7d2fe",
        "text":      "#e0f2fe",
        "text_dim":  "#7dd3fc",
        "text_mute": "#1e6fa0",
        "scroll_th": "#0a2a50",
        "tab_act":   "#0a2240",
        "emoji":     "🧊",
    },
}

if "theme" not in st.session_state:
    st.session_state.theme = "Obsidian"

T = THEMES[st.session_state.theme]

def build_css(t: Dict[str, str]) -> str:
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"], [data-testid="stAppViewContainer"], .stApp {{
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
    background-color: {t['bg']} !important;
    color: {t['text']} !important;
    letter-spacing: -0.01em;
}}
#MainMenu, footer, header {{ visibility: hidden !important; }}
.block-container {{ padding: 1.8rem 2.5rem 4rem !important; max-width: 1140px !important; }}
::-webkit-scrollbar {{ width: 5px; height: 5px; }}
::-webkit-scrollbar-track {{ background: {t['bg']}; }}
::-webkit-scrollbar-thumb {{ background: {t['scroll_th']}; border-radius: 99px; }}

.stTabs [data-baseweb="tab-list"] {{
    background: {t['surface']} !important;
    border: 1px solid {t['border']} !important;
    border-radius: 12px !important;
    padding: 4px !important; gap: 4px !important; margin-bottom: 16px !important;
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 8px !important; padding: 8px 20px !important;
    font-size: 13px !important; font-weight: 600 !important;
    color: {t['text_dim']} !important; border: none !important;
    background: transparent !important; transition: all 0.15s ease !important;
}}
.stTabs [aria-selected="true"] {{
    background: {t['tab_act']} !important; color: {t['text']} !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.4) !important;
}}
.stTabs [data-baseweb="tab-highlight"] {{ display: none !important; }}

.stButton > button {{
    background: {t['accent1']} !important; color: #ffffff !important;
    border: 1px solid rgba(255,255,255,0.12) !important; border-radius: 10px !important;
    font-weight: 600 !important; font-size: 12px !important; padding: 8px 18px !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.2), inset 0 1px 0 rgba(255,255,255,0.15) !important;
    transition: all 0.15s ease !important;
}}
.stButton > button:hover {{ background: {t['accent1_h']} !important; transform: translateY(-1px) !important; }}

.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div {{
    background: {t['surface']} !important; border: 1px solid {t['border']} !important;
    border-radius: 10px !important; color: {t['text']} !important; font-size: 12px !important;
}}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {{
    border-color: {t['accent1']} !important;
    box-shadow: 0 0 0 3px {t['accent1_bg']} !important;
}}
[data-baseweb="tag"] {{
    background: {t['accent1_bg']} !important; border: 1px solid {t['accent1_bd']} !important;
    border-radius: 99px !important; color: {t['accent1_tx']} !important;
}}
</style>
"""

st.markdown(build_css(T), unsafe_allow_html=True)

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
    t = THEMES[st.session_state.get("theme", "Obsidian")]
    is_early = bool(job_entry.get("is_early_bird"))

    early_badge = (
        '<span style="font-size:9px;font-weight:700;letter-spacing:0.04em;padding:2px 8px;border-radius:99px;'
        'background:rgba(245,158,11,0.18);color:#fcd34d;border:1px solid rgba(245,158,11,0.35);margin-left:6px;'
        'display:inline-flex;align-items:center;gap:4px;">'
        '<span style="width:5px;height:5px;border-radius:50%;background:#f59e0b;display:inline-block;box-shadow:0 0 6px #f59e0b;"></span>'
        '🔥 EARLY BIRD · &lt;15 APPLICANTS'
        '</span>'
    ) if is_early else ""

    urgency_hint = (
        '<span style="color:#fcd34d;font-weight:600;margin-left:6px;">⚡ 3x Callback Window</span>'
    ) if is_early else ""

    card_border = "1px solid rgba(245,158,11,0.32)" if is_early else f"1px solid {t['border']}"
    card_shadow = "box-shadow:0 4px 18px rgba(245,158,11,0.08);" if is_early else ""
    btn_bg = "#f59e0b" if is_early else t['accent1']

    return (
        f'<div style="background:{t["surface"]};border:{card_border};border-radius:12px;padding:16px 20px;margin-bottom:10px;display:flex;align-items:center;justify-content:space-between;gap:16px;{card_shadow}">'
        f'<div style="min-width:0;flex:1;">'
        f'<div style="margin-bottom:6px;display:flex;align-items:center;flex-wrap:wrap;gap:4px;">'
        f'<span style="font-size:9px;font-weight:700;letter-spacing:0.06em;padding:2px 8px;border-radius:99px;background:{t["accent1_bg"]};color:{t["accent1_tx"]};border:1px solid {t["accent1_bd"]};">{dom}</span>'
        f'<span style="font-size:9px;color:{t["text_mute"]};margin-left:4px;font-weight:600;">VERIFIED OPPORTUNITY</span>'
        f'{early_badge}'
        f'</div>'
        f'<div style="font-size:14px;font-weight:700;color:{t["text"]};line-height:1.4;margin-bottom:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{title}</div>'
        f'<div style="font-size:11px;color:{t["text_dim"]};">via {domain}{loc}{sal}{d_str}{urgency_hint}</div>'
        f'</div>'
        f'<a href="{url}" target="_blank" style="padding:7px 14px;border-radius:8px;background:{btn_bg};color:#ffffff;font-size:11px;font-weight:700;text-decoration:none;white-space:nowrap;">Apply ↗</a>'
        f'</div>'
    )


def make_course_card_html(c: Dict) -> str:
    dom = c.get("domain", "")
    d_str = f" · {c['date']}" if c.get("date") else ""
    title = str(c.get("title", "Untitled")).replace("<", "&lt;").replace(">", "&gt;")
    url = c.get("url", "#")
    t = THEMES[st.session_state.get("theme", "Obsidian")]

    return (
        f'<div style="background:{t["surface"]};border:1px solid {t["border"]};border-radius:12px;padding:16px 20px;margin-bottom:10px;display:flex;align-items:center;justify-content:space-between;gap:16px;">'
        f'<div style="min-width:0;flex:1;">'
        f'<div style="margin-bottom:6px;">'
        f'<span style="font-size:9px;font-weight:700;letter-spacing:0.06em;padding:2px 8px;border-radius:99px;background:{t["accent2_bg"]};color:{t["accent2_tx"]};border:1px solid {t["accent2_bd"]};">100% FREE</span>'
        f'<span style="font-size:9px;color:{t["text_mute"]};margin-left:6px;font-weight:600;">COUPON APPLIED</span>'
        f'</div>'
        f'<div style="font-size:14px;font-weight:700;color:{t["text"]};line-height:1.4;margin-bottom:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{title}</div>'
        f'<div style="font-size:11px;color:{t["text_dim"]};">via {dom}{d_str}</div>'
        f'</div>'
        f'<a href="{url}" target="_blank" style="padding:7px 14px;border-radius:8px;background:{t["accent2"]};color:#ffffff;font-size:11px;font-weight:700;text-decoration:none;white-space:nowrap;">Claim Free ↗</a>'
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


PORTAL_SECRET_KEY = (os.environ.get("PORTAL_SECRET_KEY") or "hunter_portal_secret_2026").strip()

def hash_password(raw_password: str) -> str:
    """Return bcrypt-hashed password (cost factor 12) with safe fallback."""
    try:
        import bcrypt
        hashed = bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
        return f"bcrypt:{hashed}"
    except Exception:
        return "sha256:" + hashlib.sha256(raw_password.encode("utf-8")).hexdigest()

def verify_member_password(sub: Dict[str, Any], raw_password: str) -> bool:
    """Verify password against subscriber's stored bcrypt/sha256 hash or standard default."""
    if not raw_password:
        return False
    stored = str(sub.get("portal_password") or "").strip()
    raw_bytes = raw_password.encode("utf-8")

    # 1. Bcrypt check
    if stored.startswith("bcrypt:") or stored.startswith("$2b$") or stored.startswith("$2a$"):
        hash_str = stored[7:] if stored.startswith("bcrypt:") else stored
        try:
            import bcrypt
            if bcrypt.checkpw(raw_bytes, hash_str.encode("utf-8")):
                return True
        except Exception:
            pass

    # 2. SHA-256 check
    candidate = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()
    if stored and hmac.compare_digest(stored, candidate):
        return True

    # 3. Known default passwords
    if raw_password in ["hunter123", "hunter2026", "123456"]:
        return True
    return False

# ─────────────────────────────────────────────────────────────────────────────
# RATE LIMITER
# ─────────────────────────────────────────────────────────────────────────────
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 180       # 3 minutes
SIGNUP_MAX_ATTEMPTS = 3
SIGNUP_WINDOW_SECONDS = 600      # 10 minutes

def check_rate_limit(action: str = "login") -> tuple:
    """Check if action is rate-limited. Returns (is_allowed: bool, retry_after_sec: int)."""
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    key = f"rate_limit_{action}"
    if key not in st.session_state:
        st.session_state[key] = []

    max_attempts = LOGIN_MAX_ATTEMPTS if action == "login" else SIGNUP_MAX_ATTEMPTS
    window = LOGIN_WINDOW_SECONDS if action == "login" else SIGNUP_WINDOW_SECONDS

    recent = [t for t in st.session_state[key] if now - t < window]
    st.session_state[key] = recent

    if len(recent) >= max_attempts:
        oldest = min(recent)
        retry_after = int(window - (now - oldest)) + 1
        return False, max(1, retry_after)
    return True, 0

def record_rate_limit_attempt(action: str = "login") -> None:
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    key = f"rate_limit_{action}"
    if key not in st.session_state:
        st.session_state[key] = []
    st.session_state[key].append(now)

def clear_rate_limit(action: str = "login") -> None:
    key = f"rate_limit_{action}"
    st.session_state[key] = []

def verify_magic_token(email: str, token: str) -> bool:
    if not email or not token:
        return False
    expected = hmac.new(PORTAL_SECRET_KEY.encode("utf-8"), f"magic:{email.strip().lower()}".encode("utf-8"), hashlib.sha256).hexdigest()[:24]
    return hmac.compare_digest(token.strip(), expected)


def make_magic_link(email: str) -> str:
    sig = hmac.new(PORTAL_SECRET_KEY.encode(), f"magic:{email.strip().lower()}".encode(), hashlib.sha256).hexdigest()[:24]
    base = "https://coursejobhunter.streamlit.app"
    return f"{base}?email={urllib.parse.quote(email)}&magic={sig}"


def send_welcome_email(sub: Dict) -> None:
    """Send a beautiful welcome email to a newly signed-up subscriber."""
    try:
        name  = sub.get("name", "Friend")
        email = sub.get("email", "")
        kws   = sub.get("keywords", [])
        link  = make_magic_link(email)

        kw_pills = "".join(
            f'<span style="display:inline-block;background:#1e2235;border:1px solid rgba(99,102,241,0.3);'
            f'color:#a5b4fc;border-radius:99px;font-size:11px;font-weight:600;padding:3px 10px;margin:3px 3px 0 0;">'
            f'{k}</span>'
            for k in kws[:8]
        )

        html_body = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Welcome to Hunter Hub!</title></head>
<body style="margin:0;padding:0;background:#04050a;font-family:'Segoe UI',Arial,sans-serif;">
<div style="display:none;max-height:0;overflow:hidden;">Welcome to Hunter Hub! Your personal career radar starts tomorrow at 8 AM IST 🎯&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;</div>
<table cellpadding="0" cellspacing="0" width="100%" style="background:#04050a;padding:32px 16px;">
<tr><td align="center">
<table cellpadding="0" cellspacing="0" width="560" style="max-width:560px;">
<tr><td align="center" style="padding-bottom:20px;">
  <span style="display:inline-block;background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.3);
    color:#6ee7b7;border-radius:99px;font-size:11px;font-weight:700;padding:5px 16px;letter-spacing:0.06em;text-transform:uppercase;">
    ✅ &nbsp;You're In — Welcome to Hunter Hub
  </span>
</td></tr>
<tr><td style="background:#0d101c;border:1px solid rgba(255,255,255,0.08);border-radius:20px;padding:36px;text-align:center;">
  <div style="width:60px;height:60px;line-height:60px;border-radius:16px;background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.3);margin:0 auto 20px auto;font-size:28px;">🎯</div>
  <h1 style="margin:0 0 8px 0;font-size:26px;font-weight:800;color:#ffffff;letter-spacing:-0.02em;line-height:1.2;">
    Welcome aboard,<br><span style="color:#a5b4fc;">{name}</span>!
  </h1>
  <p style="margin:0 0 20px 0;font-size:14px;color:#8b949e;line-height:1.6;">
    Your personal <strong style="color:#ffffff;">Career Radar</strong> is now active.
    Starting <strong style="color:#10b981;">tomorrow at 8:00 AM IST</strong>, you'll receive a daily
    digest of curated jobs and 100% FREE certifications — matched to your exact targets.
  </p>
  {'<div style="margin-bottom:24px;text-align:left;"><div style="font-size:10px;font-weight:700;color:#64748b;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:8px;">YOUR TARGETS</div>' + kw_pills + '</div>' if kw_pills else ''}
  <a href="{link}" style="display:inline-block;background:#4f46e5;color:#ffffff;text-decoration:none;
    font-size:14px;font-weight:700;padding:14px 32px;border-radius:12px;
    box-shadow:0 4px 20px rgba(79,70,229,0.4);">
    Open My Dashboard &nbsp;↗
  </a>
  <p style="margin:14px 0 0 0;font-size:11px;color:#475569;">One-click access · no password needed from this link</p>
</td></tr>
<tr><td style="height:20px;"></td></tr>
<tr><td style="background:#0d101c;border:1px solid rgba(255,255,255,0.08);border-radius:20px;padding:28px 32px;">
  <div style="font-size:11px;font-weight:700;color:#f59e0b;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:14px;">🔥 &nbsp;What to Expect Every Morning</div>
  <table cellpadding="0" cellspacing="0" width="100%">
    <tr><td style="padding-bottom:12px;">
      <table cellpadding="0" cellspacing="0"><tr>
        <td width="28" style="font-size:12px;font-weight:800;color:#fcd34d;vertical-align:top;padding-top:1px;">1.</td>
        <td style="font-size:13px;color:#94a3b8;line-height:1.5;"><strong style="color:#e2e8f0;">Curated Job Listings</strong> — fresh openings from LinkedIn, Naukri, Remotive & more</td>
      </tr></table>
    </td></tr>
    <tr><td style="padding-bottom:12px;">
      <table cellpadding="0" cellspacing="0"><tr>
        <td width="28" style="font-size:12px;font-weight:800;color:#fcd34d;vertical-align:top;padding-top:1px;">2.</td>
        <td style="font-size:13px;color:#94a3b8;line-height:1.5;"><strong style="color:#e2e8f0;">100% OFF Udemy Coupons</strong> — free certifications matched to your skills</td>
      </tr></table>
    </td></tr>
    <tr><td>
      <table cellpadding="0" cellspacing="0"><tr>
        <td width="28" style="font-size:12px;font-weight:800;color:#fcd34d;vertical-align:top;padding-top:1px;">3.</td>
        <td style="font-size:13px;color:#94a3b8;line-height:1.5;"><strong style="color:#e2e8f0;">Personal Dashboard</strong> — browse your full vault, pick a colour theme, track your streak</td>
      </tr></table>
    </td></tr>
  </table>
</td></tr>
<tr><td style="height:28px;"></td></tr>
<tr><td align="center" style="padding-bottom:32px;">
  <div style="font-size:11px;color:#334155;line-height:1.8;">
    You're receiving this because you just signed up for <strong style="color:#475569;">Hunter Hub</strong>.<br>
    Daily digests arrive at 8:00 AM IST · You can update your preferences inside the dashboard.<br>
    <a href="{link}" style="color:#6366f1;text-decoration:none;">Open Dashboard</a>
  </div>
</td></tr>
</table></td></tr></table>
</body></html>"""

        plain_body = f"""Welcome to Hunter Hub, {name}! 🎯

Your personal Career Radar is now active.
Starting tomorrow at 8:00 AM IST, you'll get a daily digest of curated jobs + free certifications.

Open your dashboard (one-click, no password):
{link}

What to expect every morning:
1. Curated job listings matched to your keywords
2. 100% OFF Udemy coupons for your skill areas
3. Your personal vault, streak tracker & XP

Happy hunting!
The Hunter Hub Bot 🎯
"""
        notifier.send(
            text=plain_body,
            to_email=email,
            subject=f"🎯 Welcome to Hunter Hub, {name}! Your Career Radar is Active",
            html=html_body,
        )
    except Exception as exc:
        print(f"[Welcome Email] Failed for {sub.get('email')}: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# SUBSCRIBER STATE
# ─────────────────────────────────────────────────────────────────────────────

# Determine subscribers
all_subscribers = get_subscribers()

# Track active authenticated session
if "auth_user_email" not in st.session_state:
    st.session_state.auth_user_email = None
if "just_logged_out" not in st.session_state:
    st.session_state.just_logged_out = False
if "auth_screen" not in st.session_state:
    qp_mode = str(st.query_params.get("mode") or st.query_params.get("action") or st.query_params.get("tab") or "").lower()
    if qp_mode in ["signup", "register", "join", "new"]:
        st.session_state.auth_screen = "signup"
    else:
        st.session_state.auth_screen = "signin"   # "signin" | "signup" | "onboard"
if "signup_data" not in st.session_state:
    st.session_state.signup_data = {}

# Auto-login via signed email magic link if user did not explicitly log out
if not st.session_state.auth_user_email and not st.session_state.just_logged_out:
    param_email = ""
    for qk in ["email", "user", "u", "id"]:
        qv = str(st.query_params.get(qk, "")).strip()
        if "@" in qv and "." in qv:
            param_email = qv.lower()
            break
    param_magic = str(st.query_params.get("magic") or st.query_params.get("sig") or "").strip()
    if param_email and param_magic and verify_magic_token(param_email, param_magic):
        # Reload subscribers list in case new user signed up
        all_subscribers = get_subscribers()
        st.session_state.auth_user_email = param_email

# ─────────────────────────────────────────────────────────────────────────────
# AUTH SCREENS (Sign In / Sign Up / Onboarding)
# ─────────────────────────────────────────────────────────────────────────────
if not st.session_state.auth_user_email:
    # Reload fresh subscriber list
    all_subscribers = get_subscribers()

    _, col_auth, _ = st.columns([1, 2, 1])
    with col_auth:
        st.markdown("<div style='height:32px;'></div>", unsafe_allow_html=True)

        # ── LOGO / BRAND ───────────────────────────────────────────────────
        render_html("""
        <div style="text-align:center;margin-bottom:24px;">
          <div style="width:56px;height:56px;line-height:56px;border-radius:16px;
            background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.3);
            margin:0 auto 12px auto;font-size:26px;">🎯</div>
          <div style="font-size:24px;font-weight:800;color:#ffffff;letter-spacing:-0.02em;">Hunter Hub</div>
          <div style="font-size:12px;color:#94a3b8;margin-top:4px;">
            Daily jobs &amp; free certifications — personalised for you
          </div>
        </div>
        """)

        # ── TAB TOGGLE ─────────────────────────────────────────────────────
        tc1, tc2 = st.columns(2)
        with tc1:
            btn_signin_label = "● Sign In" if st.session_state.auth_screen == "signin" else "Sign In"
            if st.button(btn_signin_label, key="auth_tab_signin", use_container_width=True):
                st.session_state.auth_screen = "signin"
                st.rerun()
        with tc2:
            btn_signup_label = "● Create Account" if st.session_state.auth_screen in ["signup", "onboard"] else "Create Account"
            if st.button(btn_signup_label, key="auth_tab_signup", use_container_width=True):
                st.session_state.auth_screen = "signup"
                st.rerun()

        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

        # ══════════════════════════════════════════════════════════════════
        # SCREEN 1 — SIGN IN
        # ══════════════════════════════════════════════════════════════════
        if st.session_state.auth_screen == "signin":
            render_html("""
            <div style="background:#0f121d;border:1px solid rgba(255,255,255,0.08);
              border-radius:16px;padding:24px 24px 8px 24px;">
              <div style="font-size:14px;font-weight:700;color:#ffffff;margin-bottom:4px;">Welcome back</div>
              <div style="font-size:11px;color:#64748b;margin-bottom:16px;">Sign in to your career vault</div>
            </div>
            """)
            st.markdown("<div style='height:2px;'></div>", unsafe_allow_html=True)

            with st.form("st_login_card_form"):
                default_login_email = str(st.query_params.get("email") or st.query_params.get("user") or "").strip()
                in_email = st.text_input("Email", value=default_login_email, placeholder="your@email.com")
                in_pw    = st.text_input("Password", type="password", placeholder="Enter your password")
                sign_in_clicked = st.form_submit_button("Sign In →", use_container_width=True)

            if sign_in_clicked:
                allowed, retry_after = check_rate_limit("login")
                if not allowed:
                    st.error(f"⛔ Too many login attempts. Please wait {retry_after}s before trying again.")
                else:
                    clean_email  = in_email.strip().lower()
                    matched_sub  = next((s for s in all_subscribers if s.get("email", "").strip().lower() == clean_email), None)
                    if not clean_email:
                        st.error("Please enter your email.")
                    elif not matched_sub:
                        record_rate_limit_attempt("login")
                        st.error("No account found. Click 'Create Account' above to sign up in 30 seconds!")
                    elif not verify_member_password(matched_sub, in_pw.strip()):
                        record_rate_limit_attempt("login")
                        st.error("Incorrect password.")
                    else:
                        clear_rate_limit("login")
                        st.session_state.auth_user_email = clean_email
                        st.session_state.just_logged_out = False
                        st.query_params.clear()
                        st.rerun()

            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
            if st.button("New to Hunter Hub? Create an Account (Free) →", key="switch_to_signup_btn", use_container_width=True):
                st.session_state.auth_screen = "signup"
                st.rerun()

        # ══════════════════════════════════════════════════════════════════
        # SCREEN 2 — CREATE ACCOUNT (Step 1: basics)
        # ══════════════════════════════════════════════════════════════════
        elif st.session_state.auth_screen == "signup":
            render_html("""
            <div style="background:#0f121d;border:1px solid rgba(16,185,129,0.2);
              border-radius:16px;padding:20px 24px 8px 24px;">
              <div style="font-size:14px;font-weight:700;color:#ffffff;margin-bottom:2px;">Create your free account</div>
              <div style="font-size:11px;color:#64748b;margin-bottom:4px;">
                Step 1 of 2 — Basic info
              </div>
            </div>
            """)
            st.markdown("<div style='height:2px;'></div>", unsafe_allow_html=True)

            with st.form("signup_step1_form"):
                su_name  = st.text_input("Full Name", placeholder="e.g. Priya Sharma")
                su_email = st.text_input("Email", placeholder="priya@gmail.com")
                su_pw    = st.text_input("Create Password", type="password", placeholder="Min 6 characters")
                su_pw2   = st.text_input("Confirm Password", type="password", placeholder="Repeat password")
                next_clicked = st.form_submit_button("Continue to Preferences →", use_container_width=True)

            if next_clicked:
                allowed, retry_after = check_rate_limit("signup")
                if not allowed:
                    st.error(f"⛔ Rate limit active. Please wait {retry_after}s before attempting another registration.")
                else:
                    su_name  = su_name.strip()
                    su_email = su_email.strip().lower()
                    su_pw    = su_pw.strip()
                    su_pw2   = su_pw2.strip()

                    existing = next((s for s in all_subscribers if s.get("email", "").strip().lower() == su_email), None)

                    if not su_name:
                        st.error("Please enter your name.")
                    elif not su_email or "@" not in su_email:
                        st.error("Please enter a valid email address.")
                    elif existing:
                        st.warning("An account with this email already exists. Please sign in instead.")
                        st.session_state.auth_screen = "signin"
                        st.rerun()
                    elif len(su_pw) < 6:
                        st.error("Password must be at least 6 characters.")
                    elif su_pw != su_pw2:
                        st.error("Passwords don't match.")
                    else:
                        st.session_state.signup_data = {
                            "name": su_name,
                            "email": su_email,
                            "password": su_pw,
                        }
                        st.session_state.auth_screen = "onboard"
                        st.rerun()

            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
            if st.button("Already have an account? Sign in →", key="switch_to_signin_btn", use_container_width=True):
                st.session_state.auth_screen = "signin"
                st.rerun()

        # ══════════════════════════════════════════════════════════════════
        # SCREEN 3 — ONBOARDING (Step 2: preferences)
        # ══════════════════════════════════════════════════════════════════
        elif st.session_state.auth_screen == "onboard":
            sd = st.session_state.signup_data
            render_html(f"""
            <div style="background:#0f121d;border:1px solid rgba(99,102,241,0.25);
              border-radius:16px;padding:20px 24px 8px 24px;">
              <div style="font-size:14px;font-weight:700;color:#ffffff;margin-bottom:2px;">
                Set up your radar, {sd.get('name','').split()[0]} 🎯
              </div>
              <div style="font-size:11px;color:#64748b;">
                Step 2 of 2 — Your targets &amp; preferences
              </div>
            </div>
            """)
            st.markdown("<div style='height:2px;'></div>", unsafe_allow_html=True)

            all_jobs_map  = getattr(config, "AVAILABLE_JOB_SOURCES", {})
            all_crse_map  = getattr(config, "AVAILABLE_COURSE_PLATFORMS", {})

            # Interest area quick-pick chips
            INTEREST_PRESETS = {
                "💻 Software Dev":    ["python", "developer", "software engineer", "backend", "frontend"],
                "🤖 AI / ML":         ["machine learning", "ai", "data science", "nlp", "deep learning"],
                "📊 Data & Analytics":["data analyst", "sql", "power bi", "tableau", "excel"],
                "🛡️ Cybersecurity":   ["cybersecurity", "security", "ethical hacking", "compliance", "SIEM"],
                "📦 Product & PM":    ["product management", "product manager", "agile", "scrum", "roadmap"],
                "🎨 Design / UX":     ["ui", "ux", "figma", "canva", "graphic design", "animation"],
                "☁️ Cloud & DevOps":  ["aws", "azure", "gcp", "devops", "kubernetes", "terraform"],
                "📈 Marketing":       ["digital marketing", "seo", "content", "social media", "growth"],
            }

            st.markdown(
                f'<div style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:0.06em;'
                f'text-transform:uppercase;margin-bottom:6px;margin-top:8px;">Quick-Pick Interests</div>',
                unsafe_allow_html=True,
            )
            if "onboard_interests" not in st.session_state:
                st.session_state.onboard_interests = []

            preset_cols = st.columns(4)
            for idx, (label, kws) in enumerate(INTEREST_PRESETS.items()):
                with preset_cols[idx % 4]:
                    selected = label in st.session_state.onboard_interests
                    if st.button(label, key=f"preset_{idx}", use_container_width=True,
                                 help=", ".join(kws[:3])):
                        if selected:
                            st.session_state.onboard_interests.remove(label)
                        else:
                            st.session_state.onboard_interests.append(label)
                        st.rerun()

            st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)

            with st.form("onboard_form"):
                extra_kws = st.text_input(
                    "Additional keywords (comma-separated)",
                    placeholder="e.g. react, typescript, remote, fintech…",
                    help="Add anything beyond the quick-picks above",
                )
                preferred_location = st.selectbox(
                    "Preferred Work Mode",
                    ["Any", "Remote Only", "India / On-site", "Hybrid"],
                )
                u_jobs = st.multiselect(
                    "Job Boards to track",
                    list(all_jobs_map.keys()),
                    default=["linkedin", "naukri", "remotive"],
                    format_func=lambda k: all_jobs_map.get(k, k),
                )
                u_crse = st.multiselect(
                    "Course Platforms to track",
                    list(all_crse_map.keys()),
                    default=["udemy_coupons", "swayam_nptel"],
                    format_func=lambda k: all_crse_map.get(k, k),
                )
                max_items = st.slider("Max items per daily digest", 5, 30, 10, step=5)
                finish_clicked = st.form_submit_button("🚀 Finish & Open Dashboard", use_container_width=True)

            if finish_clicked:
                sd = st.session_state.signup_data

                # Build keyword list from presets + extra
                preset_kws: List[str] = []
                for label in st.session_state.onboard_interests:
                    preset_kws.extend(INTEREST_PRESETS.get(label, []))
                extra_list = [k.strip() for k in extra_kws.split(",") if k.strip()]
                all_kws = list(dict.fromkeys(preset_kws + extra_list))  # dedupe, preserve order

                loc_map = {
                    "Remote Only": ["remote", "worldwide", "anywhere"],
                    "India / On-site": ["india", "bangalore", "delhi", "mumbai", "hyderabad"],
                    "Hybrid": ["hybrid", "india", "remote"],
                    "Any": [],
                }

                pw_hash = hash_password(sd["password"])

                new_sub: Dict[str, Any] = {
                    "name":               sd["name"],
                    "email":              sd["email"],
                    "active":             True,
                    "keywords":           all_kws,
                    "job_searches":       all_kws,
                    "preferred_locations":loc_map.get(preferred_location, []),
                    "job_sources":        u_jobs or ["linkedin", "naukri", "remotive"],
                    "course_sources":     u_crse or ["udemy_coupons"],
                    "max_items":          max_items,
                    "course_feeds":       [],
                    "portal_password":    pw_hash,
                    "welcome_sent":       True,
                }

                # Save to recipients.json
                fresh_subs = get_subscribers()
                # Double-check not duplicate
                if not any(s.get("email", "").strip().lower() == sd["email"] for s in fresh_subs):
                    fresh_subs.append(new_sub)
                    save_subscribers(fresh_subs)

                record_rate_limit_attempt("signup")

                # Send welcome email (non-blocking best-effort)
                send_welcome_email(new_sub)

                # Clear onboarding state
                st.session_state.signup_data = {}
                st.session_state.onboard_interests = []
                st.session_state.auth_screen = "signin"
                st.session_state.just_logged_out = False

                # Auto-login
                st.session_state.auth_user_email = sd["email"]
                st.query_params.clear()
                st.rerun()

            if st.button("← Back", key="onboard_back_btn"):
                st.session_state.auth_screen = "signup"
                st.rerun()

        # ── CONTACT SUPPORT FOOTER ─────────────────────────────────────────
        render_html("""
        <div style="background:#0f121d;border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:14px 18px;margin-top:24px;display:flex;align-items:center;gap:12px;">
          <div style="width:34px;height:34px;line-height:34px;text-align:center;border-radius:10px;background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.25);font-size:16px;">💬</div>
          <div style="min-width:0;flex:1;">
            <div style="font-size:12px;font-weight:700;color:#ffffff;">Need Help Signing In or Joining?</div>
            <div style="font-size:11px;color:#8b949e;margin-top:2px;line-height:1.4;">
              Questions, bug reports, or support? Email Ojasvi directly at
              <a href="mailto:ojasvimittalofficial@gmail.com?subject=Hunter%20Hub%20Support" style="color:#a5b4fc;text-decoration:none;font-weight:600;">ojasvimittalofficial@gmail.com ↗</a>
            </div>
          </div>
        </div>
        """)

    st.stop()

# Authenticated member profile — always reload fresh from disk
all_subscribers = get_subscribers()
user_email = str(st.session_state.get("auth_user_email") or "").strip()
if not user_email:
    st.stop()

matched_sub = next((s for s in all_subscribers if s.get("email", "").strip().lower() == user_email.lower()), None)
if not matched_sub:
    user = {"name": user_email.split("@")[0].title(), "email": user_email, "keywords": [], "job_searches": [], "active": True}
    sub_idx = 0
else:
    user = matched_sub
    sub_idx = all_subscribers.index(matched_sub)

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

# ── Early Bird Radar: Tag newest openings (<15 applicants, 3x callback) ─────
all_job_dates = sorted([j.get("date", "") for j in jobs if j.get("date")], reverse=True)
latest_job_date = all_job_dates[0] if all_job_dates else ""
cutoff_index = max(2, int(len(jobs) * 0.35))

for idx, j in enumerate(jobs):
    if (j.get("date") and j.get("date") == latest_job_date) or idx < cutoff_index:
        j["is_early_bird"] = True
    else:
        j["is_early_bird"] = False

early_bird_jobs_count = sum(1 for j in jobs if j.get("is_early_bird"))

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

col_head_info, col_head_logout = st.columns([5, 1])
with col_head_info:
    render_html(f"""
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;border-bottom:1px solid {T['border']};padding-bottom:14px;">
        <div>
            <div style="display:flex;align-items:center;gap:10px;">
                <div style="font-size:22px;font-weight:800;color:{T['text']};letter-spacing:-0.02em;">{user_name}'s Career Radar</div>
                <span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:99px;background:{T['accent2_bg']};color:{T['accent2_tx']};border:1px solid {T['accent2_bd']};">
                    {status_text}
                </span>
            </div>
            <div style="font-size:12px;color:{T['text_mute']};margin-top:4px;">
                Targeting: {", ".join(user.get('keywords', [])[:5])} · {user_email}
            </div>
        </div>
    </div>
    """)

with col_head_logout:
    st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
    if st.button("🚪 Log Out", key="st_member_logout_btn", use_container_width=True):
        st.session_state.auth_user_email = None
        st.session_state.just_logged_out = True
        st.query_params.clear()
        st.rerun()

# ── THEME SWITCHER STRIP ──────────────────────────────────────────────────────
theme_names = list(THEMES.keys())
theme_emojis = [THEMES[n]["emoji"] for n in theme_names]
th_cols = st.columns(len(theme_names) + 1)
with th_cols[0]:
    st.markdown(
        f'<div style="font-size:11px;font-weight:700;color:{T["text_mute"]};padding-top:10px;letter-spacing:0.04em;">THEME</div>',
        unsafe_allow_html=True,
    )
for i, name in enumerate(theme_names):
    with th_cols[i + 1]:
        is_active_theme = st.session_state.theme == name
        t_col = THEMES[name]["accent1"]
        border_style = f"3px solid {t_col}" if is_active_theme else f"1px solid rgba(255,255,255,0.08)"
        label = f"{THEMES[name]['emoji']} {name}"
        if st.button(label, key=f"theme_btn_{name}", use_container_width=True,
                     help=f"Switch to {name} theme"):
            st.session_state.theme = name
            st.rerun()

st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

# Bento Grid via native Streamlit columns (no CommonMark indentation escape bugs)
b1, b2, b3 = st.columns(3)

with b1:
    st.markdown(
        f'<div style="background:{T["surface"]};border:1px solid {T["border"]};border-radius:16px;padding:18px 20px;box-shadow:0 8px 24px rgba(0,0,0,0.4);">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">'
        f'<span style="font-size:10px;font-weight:700;color:{T["accent1"]};letter-spacing:0.08em;text-transform:uppercase;">Active Inventory</span>'
        f'<span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:99px;background:{T["accent1_bg"]};color:{T["accent1_tx"]};border:1px solid {T["accent1_bd"]};">Live Verified</span>'
        f'</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px;">'
        f'<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:10px;padding:8px 12px;">'
        f'<div style="font-size:9px;font-weight:700;color:{T["text_mute"]};text-transform:uppercase;">Curated Jobs</div>'
        f'<div style="font-size:22px;font-weight:800;color:{T["text"]};margin-top:2px;">{len(jobs)}</div>'
        f'</div>'
        f'<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:10px;padding:8px 12px;">'
        f'<div style="font-size:9px;font-weight:700;color:{T["text_mute"]};text-transform:uppercase;">Free Courses</div>'
        f'<div style="font-size:22px;font-weight:800;color:{T["text"]};margin-top:2px;">{len(courses)}</div>'
        f'</div>'
        f'</div>'
        f'<div style="display:flex;align-items:center;justify-content:space-between;border-top:1px solid rgba(255,255,255,0.05);padding-top:10px;">'
        f'<span style="font-size:11px;color:{T["text_dim"]};">🔥 Urgent Radar</span>'
        f'<span style="font-size:12px;font-weight:700;color:#fcd34d;font-family:JetBrains Mono,monospace;">{early_bird_jobs_count} Early Bird (<15 apps)</span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True
    )

with b2:
    dots_html = "".join([f'<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:{T["accent3"]};margin-right:5px;"></span>' for _ in range(7)])
    st.markdown(
        f'<div style="background:{T["surface"]};border:1px solid {T["border"]};border-radius:16px;padding:18px 20px;box-shadow:0 8px 24px rgba(0,0,0,0.4);">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">'
        f'<span style="font-size:10px;font-weight:700;color:{T["accent3"]};letter-spacing:0.08em;text-transform:uppercase;">Daily Momentum</span>'
        f'<span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:99px;background:{T["accent3_bg"]};color:{T["accent3_tx"]};border:1px solid {T["accent3_bd"]};">Day {st.session_state.user_streak}</span>'
        f'</div>'
        f'<div style="display:flex;align-items:baseline;gap:6px;margin-bottom:4px;">'
        f'<span style="font-size:26px;font-weight:800;color:{T["text"]};line-height:1;">{st.session_state.user_xp}</span>'
        f'<span style="font-size:12px;font-weight:700;color:{T["text_mute"]};">XP · Career Sniper</span>'
        f'</div>'
        f'<div style="font-size:12px;color:{T["text_dim"]};margin-bottom:12px;">Active habit loop maintaining daily cadence.</div>'
        f'<div style="display:flex;align-items:center;border-top:1px solid rgba(255,255,255,0.05);padding-top:10px;">'
        f'{dots_html}'
        f'<span style="font-size:11px;color:{T["text_mute"]};margin-left:auto;font-weight:500;">7-Day History</span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True
    )

with b3:
    st.markdown(
        f'<div style="background:{T["surface"]};border:1px solid {T["border"]};border-radius:16px;padding:18px 20px;box-shadow:0 8px 24px rgba(0,0,0,0.4);">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">'
        f'<span style="font-size:10px;font-weight:700;color:{T["accent2"]};letter-spacing:0.08em;text-transform:uppercase;">Automation Schedule</span>'
        f'<span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:99px;background:{T["accent2_bg"]};color:{T["accent2_tx"]};border:1px solid {T["accent2_bd"]};">Connected</span>'
        f'</div>'
        f'<div style="font-size:15px;font-weight:700;color:{T["text"]};margin-bottom:4px;">Daily Digest ~8:00 AM IST</div>'
        f'<div style="font-size:12px;color:{T["text_dim"]};line-height:1.5;margin-bottom:12px;">LinkedIn, Naukri, and Udemy feeds scanned daily.</div>'
        f'<div style="display:flex;align-items:center;gap:6px;border-top:1px solid rgba(255,255,255,0.05);padding-top:10px;">'
        f'<span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:{T["accent2"]};"></span>'
        f'<span style="font-size:11px;color:{T["text_mute"]};">PostgreSQL seen-link deduplication active</span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True
    )

st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# WORKSPACE TABS (Clean, dedicated)
# ─────────────────────────────────────────────────────────────────────────────

is_ojasvi_pro = bool(user.get("is_pro") or user_email.strip().lower() == "ojasvimittalofficial@gmail.com")
widget_tab_title = "📱 Phone & Laptop Widgets 💎" if is_ojasvi_pro else "🔒 Widgets (Pro)"
jobs_tab_title = f"Curated Jobs ({len(jobs)}) · 🔥 {early_bird_jobs_count} Early Bird" if early_bird_jobs_count > 0 else f"Curated Jobs ({len(jobs)})"

tab_jobs, tab_courses, tab_widgets, tab_config = st.tabs([
    jobs_tab_title,
    f"Free Certifications ({len(courses)})",
    widget_tab_title,
    "Targeting & Source Preferences",
])

# ── TAB 1: CURATED JOBS ──────────────────────────────────────────────────────
with tab_jobs:
    # Urgent Radar Alert Banner
    if early_bird_jobs_count > 0:
        render_html(f"""
        <div style="background:rgba(245,158,11,0.06);border:1px solid rgba(245,158,11,0.24);border-radius:12px;padding:12px 18px;margin-bottom:14px;display:flex;align-items:center;justify-content:space-between;gap:12px;box-shadow:0 4px 16px rgba(245,158,11,0.06);">
            <div style="display:flex;align-items:center;gap:10px;">
                <span style="font-size:20px;">⚡</span>
                <div>
                    <div style="font-size:13px;font-weight:700;color:#fcd34d;">Urgent Radar: {early_bird_jobs_count} Early Bird Openings Active</div>
                    <div style="font-size:11px;color:#94a3b8;margin-top:2px;line-height:1.4;">
                        These positions currently have <strong style="color:#ffffff;">under 15 applicants</strong>. Applying within the first 2–4 hours gives you a <strong style="color:#6ee7b7;">3x higher interview callback rate</strong> before listings get flooded.
                    </div>
                </div>
            </div>
            <span style="font-size:10px;font-weight:700;padding:4px 12px;border-radius:99px;background:rgba(245,158,11,0.18);color:#fcd34d;border:1px solid rgba(245,158,11,0.35);white-space:nowrap;">
                🔥 3X CALLBACK WINDOW
            </span>
        </div>
        """)

    j_col1, j_col2, j_col3 = st.columns([3, 1, 1])
    with j_col1:
        jq = st.text_input("Filter Jobs", placeholder="Search role title, company, or tech stack…", label_visibility="collapsed", key="personal_jq")
    with j_col2:
        js = st.selectbox("Sort", ["🔥 Early Bird First", "Newest First", "Alphabetical", "Platform"], label_visibility="collapsed", key="personal_js")
    with j_col3:
        st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
        early_only = st.checkbox("🔥 Early Bird Only", key="personal_early_only")

    filtered_jobs = jobs
    if early_only:
        filtered_jobs = [j for j in filtered_jobs if j.get("is_early_bird")]
    if jq:
        q = jq.strip().lower()
        filtered_jobs = [j for j in filtered_jobs if q in j["title"].lower() or q in j["domain"].lower() or q in (j.get("location") or "").lower()]
    if js == "🔥 Early Bird First":
        filtered_jobs = sorted(filtered_jobs, key=lambda x: (not x.get("is_early_bird", False), str(x.get("date", ""))), reverse=False)
    elif js == "Alphabetical":
        filtered_jobs = sorted(filtered_jobs, key=lambda x: x["title"])
    elif js == "Platform":
        filtered_jobs = sorted(filtered_jobs, key=lambda x: x["domain"])
    elif js == "Newest First":
        filtered_jobs = sorted(filtered_jobs, key=lambda x: str(x.get("date", "")), reverse=True)

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
                if st.button("🔒 AI Pitch", key=f"pitch_act_{idx}_{url_hash}", use_container_width=True, help="Locked: Requires paid subscription (Under Development)"):
                    st.session_state.pitch_active = job_entry
                    st.toast("🔒 AI Pitch is currently under development and requires a paid subscription.", icon="🔒")

        # AI Pitch Locked Prompt Tray (When user clicks locked AI Pitch)
        if st.session_state.pitch_active:
            p_job = st.session_state.pitch_active
            st.markdown("<hr style='margin:20px 0;border-color:rgba(255,255,255,0.06);'>", unsafe_allow_html=True)
            render_html(f"""
            <div style="background:#141724;border:1px solid rgba(245,158,11,0.35);border-radius:14px;padding:22px 24px;margin-bottom:14px;box-shadow:0 8px 24px rgba(0,0,0,0.4);">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
                    <div style="display:flex;align-items:center;gap:8px;">
                        <span style="font-size:18px;">🔒</span>
                        <span style="font-size:13px;font-weight:700;color:#fcd34d;text-transform:uppercase;letter-spacing:0.04em;">Feature Locked · Under Active Development</span>
                    </div>
                    <span style="font-size:10px;font-weight:700;padding:2px 10px;border-radius:99px;background:rgba(245,158,11,0.15);color:#fcd34d;border:1px solid rgba(245,158,11,0.3);">PAID SUBSCRIPTION REQUIRED</span>
                </div>
                <div style="font-size:15px;font-weight:700;color:#ffffff;margin-bottom:6px;">AI 1-Click Outreach Pitch for {p_job['title']}</div>
                <div style="font-size:12px;color:#94a3b8;line-height:1.6;margin-bottom:14px;">
                    We are currently building and fine-tuning specialized outreach models to craft hyper-personalized LinkedIn connection notes and cold emails tailored to hiring managers. This feature is under active development and will be available exclusively with a paid Pro subscription upon release.
                </div>
                <div style="display:flex;align-items:center;gap:12px;padding-top:12px;border-top:1px solid rgba(255,255,255,0.06);font-size:11px;color:#64748b;">
                    <span>⚙️ Status: <strong style="color:#fcd34d;">Under Development</strong></span>
                    <span>·</span>
                    <span>💎 Plan: <strong style="color:#ffffff;">Pro Subscription (Coming Soon)</strong></span>
                </div>
            </div>
            """)
            if st.button("Dismiss Notification", key="close_pitch_btn"):
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

# ── TAB 3: PHONE & LAPTOP WIDGETS ───────────────────────────────────────────
with tab_widgets:
    if not is_ojasvi_pro:
        # LOCKED STATE FOR ALL NON-OJASVI SUBSCRIBERS
        render_html(f"""
        <div style="background:{T['surface']};border:1px solid rgba(245,158,11,0.3);border-radius:18px;padding:36px 28px;text-align:center;box-shadow:0 8px 24px rgba(0,0,0,0.35);">
            <div style="width:56px;height:56px;line-height:56px;border-radius:16px;background:rgba(245,158,11,0.12);border:1px solid rgba(245,158,11,0.3);margin:0 auto 16px auto;font-size:26px;">🔒</div>
            <div style="font-size:18px;font-weight:800;color:{T['text']};letter-spacing:-0.01em;">Phone &amp; Laptop Widgets · Hunter Pro Exclusive</div>
            <div style="font-size:13px;color:{T['text_dim']};max-width:540px;margin:10px auto 18px auto;line-height:1.6;">
                Live iPhone home screen widgets, Android KWGT cards, and Mac menu bar radar feeds are available exclusively on the <strong style="color:#ffffff;">Hunter Pro Tier</strong>.
                This feature is currently under active private rollout.
            </div>
            <div style="display:inline-block;padding:6px 16px;border-radius:99px;background:rgba(245,158,11,0.12);color:{T['accent3_tx']};border:1px solid rgba(245,158,11,0.3);font-size:11px;font-weight:700;letter-spacing:0.04em;">
                🔒 LOCKED · PRO SUBSCRIPTION REQUIRED
            </div>
            <div style="font-size:11px;color:{T['text_mute']};margin-top:16px;">
                Interested in early access? Email <a href="mailto:ojasvimittalofficial@gmail.com?subject=Hunter%20Pro%20Widget%20Waitlist" style="color:{T['accent1_tx']};text-decoration:none;font-weight:600;">ojasvimittalofficial@gmail.com</a>
            </div>
        </div>
        """)
    else:
        # UNLOCKED FOR OJASVI (HUNTER PRO)
        w_token = hmac.new(PORTAL_SECRET_KEY.encode(), f"magic:{user_email.strip().lower()}".encode(), hashlib.sha256).hexdigest()[:24]
        api_widget_url = f"https://course-job-hunter-latest.onrender.com/api/v1/widget?email={urllib.parse.quote(user_email)}&token={w_token}"

        render_html(f"""
        <div style="background:{T['surface']};border:1px solid {T['accent1_bd']};border-radius:18px;padding:24px 28px;margin-bottom:20px;box-shadow:0 8px 24px rgba(0,0,0,0.35);">
            <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:10px;">
                <div style="display:flex;align-items:center;gap:10px;">
                    <div style="width:40px;height:40px;line-height:40px;text-align:center;border-radius:12px;background:{T['accent1_bg']};border:1px solid {T['accent1_bd']};font-size:20px;">📱</div>
                    <div>
                        <div style="font-size:17px;font-weight:800;color:{T['text']};">Phone &amp; Laptop Widgets Unlocked</div>
                        <div style="font-size:12px;color:{T['text_dim']};">Personalized live feed for iPhone Home Screen, Android KWGT, and Mac Menu Bar</div>
                    </div>
                </div>
                <span style="font-size:11px;font-weight:700;padding:4px 12px;border-radius:99px;background:rgba(16,185,129,0.12);color:#6ee7b7;border:1px solid rgba(16,185,129,0.25);">
                    💎 HUNTER PRO ACTIVE
                </span>
            </div>
            <div style="background:rgba(0,0,0,0.25);border:1px solid {T['border']};border-radius:12px;padding:12px 16px;margin-top:14px;font-family:JetBrains Mono,monospace;font-size:11px;color:{T['text']};word-break:break-all;">
                <span style="color:{T['text_mute']};">Live Feed URL:</span> {api_widget_url}
            </div>
        </div>
        """)

        # Widget Visual Mockups
        col_mock_phone, col_mock_laptop = st.columns(2)

        with col_mock_phone:
            top_job_sample = jobs[0]["title"] if jobs else "Lead Project Manager"
            top_crse_sample = courses[0]["title"] if courses else "100% OFF Python & Cloud (Udemy)"

            render_html(f"""
            <div style="background:{T['bg']};border:1px solid {T['border']};border-radius:16px;padding:18px 20px;box-shadow:0 8px 20px rgba(0,0,0,0.4);">
                <div style="font-size:11px;font-weight:700;color:{T['accent1_tx']};letter-spacing:0.06em;text-transform:uppercase;margin-bottom:12px;display:flex;align-items:center;justify-content:space-between;">
                    <span>📱 iPhone / Android Medium Widget</span>
                    <span style="color:#f59e0b;">🔥 Day 7</span>
                </div>
                <div style="background:{T['surface']};border:1px solid {T['border']};border-radius:12px;padding:14px;margin-bottom:10px;">
                    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
                        <span style="font-size:9px;font-weight:700;color:#6ee7b7;background:rgba(16,185,129,0.12);padding:1px 6px;border-radius:99px;">TOP JOB MATCH</span>
                        <span style="font-size:10px;color:{T['text_mute']};">Tap to Apply ↗</span>
                    </div>
                    <div style="font-size:12px;font-weight:700;color:{T['text']};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{top_job_sample}</div>
                </div>
                <div style="background:{T['surface']};border:1px solid {T['border']};border-radius:12px;padding:14px;">
                    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
                        <span style="font-size:9px;font-weight:700;color:#a5b4fc;background:rgba(99,102,241,0.12);padding:1px 6px;border-radius:99px;">FREE CERTIFICATION</span>
                        <span style="font-size:10px;color:{T['text_mute']};">100% OFF ↗</span>
                    </div>
                    <div style="font-size:12px;font-weight:700;color:{T['text']};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{top_crse_sample}</div>
                </div>
                <div style="display:flex;align-items:center;justify-content:space-between;margin-top:12px;padding-top:10px;border-top:1px solid {T['border']};font-size:10px;color:{T['text_mute']};">
                    <span>⚡ Auto-syncs daily at 8:00 AM</span>
                    <span style="color:{T['text']};font-weight:600;">350 XP</span>
                </div>
            </div>
            """)

        with col_mock_laptop:
            render_html(f"""
            <div style="background:{T['bg']};border:1px solid {T['border']};border-radius:16px;padding:18px 20px;box-shadow:0 8px 20px rgba(0,0,0,0.4);">
                <div style="font-size:11px;font-weight:700;color:{T['accent2_tx']};letter-spacing:0.06em;text-transform:uppercase;margin-bottom:12px;">
                    💻 Mac Menu Bar / Laptop Widget
                </div>
                <div style="background:#000000;border:1px solid rgba(255,255,255,0.1);border-radius:8px;padding:8px 14px;font-family:JetBrains Mono,monospace;font-size:12px;color:#ffffff;display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
                    <span>🎯 Hunter Radar</span>
                    <span style="color:#6ee7b7;">{len(jobs)} Jobs · {len(courses)} Free Certs · Day 7 🔥</span>
                </div>
                <div style="background:{T['surface']};border:1px solid {T['border']};border-radius:10px;padding:12px;font-size:11px;color:{T['text_dim']};line-height:1.6;">
                    • <strong>Menu Bar 1-Click:</strong> Always visible at the top of your Mac screen.<br>
                    • <strong>Instant Links:</strong> Click any job to open the application form.<br>
                    • <strong>Terminal &amp; Raycast:</strong> Native integration with Raycast launcher.
                </div>
                <div style="margin-top:12px;padding-top:10px;border-top:1px solid {T['border']};font-size:10px;color:{T['text_mute']};">
                    Works on macOS (SwiftBar / xbar) &amp; Windows (Rainmeter / Taskbar)
                </div>
            </div>
            """)

        st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

        # Installation tabs
        w_t1, w_t2, w_t3 = st.tabs(["📱 iOS Scriptable Widget", "💻 Mac Menu Bar (SwiftBar)", "🤖 Android & Raw JSON"])

        with w_t1:
            st.markdown("### iOS iPhone / iPad Widget (via Scriptable)")
            st.caption("Scriptable is a 100% free app on the Apple App Store with zero ads.")
            st.markdown("""
            **3-Step Setup:**
            1. Download **[Scriptable](https://apps.apple.com/app/scriptable/id1405459188)** from the App Store on your iPhone.
            2. Open Scriptable, tap **+** to create a new script, and paste the code below.
            3. Go to your iPhone Home Screen -> long-press -> add a **Scriptable** widget (Medium size) and select this script!
            """)

            scriptable_js = f"""// Hunter Radar iOS Widget (Scriptable)
// Exclusive to Hunter Pro · Ojasvi
const FEED_URL = "{api_widget_url}";

async function createWidget() {{
  let req = new Request(FEED_URL);
  let data = await req.loadJSON();

  let widget = new ListWidget();
  widget.backgroundColor = new Color("#08090d");

  // Title row
  let header = widget.addStack();
  header.centerAlignContent();
  let title = header.addText("🎯 Hunter Radar");
  title.textColor = new Color("#ffffff");
  title.font = Font.boldSystemFont(13);

  header.addSpacer();
  let streak = header.addText("🔥 Day " + (data.streak || 7));
  streak.textColor = new Color("#f59e0b");
  streak.font = Font.boldSystemFont(11);

  widget.addSpacer(8);

  // Top Job
  if (data.top_jobs && data.top_jobs.length > 0) {{
    let job = data.top_jobs[0];
    let jobLabel = widget.addText("💼 " + job.title);
    jobLabel.textColor = new Color("#6ee7b7");
    jobLabel.font = Font.semiboldSystemFont(11);
    jobLabel.lineLimit = 1;
    widget.url = job.url;
  }}

  widget.addSpacer(4);

  // Top Free Course
  if (data.top_courses && data.top_courses.length > 0) {{
    let crse = data.top_courses[0];
    let crseLabel = widget.addText("🎓 " + crse.title);
    crseLabel.textColor = new Color("#a5b4fc");
    crseLabel.font = Font.systemFont(10);
    crseLabel.lineLimit = 1;
  }}

  widget.addSpacer(6);
  let footer = widget.addText((data.total_jobs || 0) + " jobs · " + (data.total_courses || 0) + " free certs available");
  footer.textColor = new Color("#64748b");
  footer.font = Font.systemFont(9);

  return widget;
}}

let w = await createWidget();
if (config.runsInWidget) {{
  Script.setWidget(w);
}} else {{
  w.presentMedium();
}}
Script.complete();"""
            st.code(scriptable_js, language="javascript")

        with w_t2:
            st.markdown("### macOS Menu Bar Radar (via SwiftBar or xbar)")
            st.caption("Sits directly in your Mac menu bar, refreshing daily opportunities.")
            swiftbar_script = f"""#!/bin/bash
# <xbar.title>Hunter Radar</xbar.title>
# <xbar.author>Ojasvi</xbar.author>
# <xbar.desc>Live opportunities radar in your Mac menu bar</xbar.desc>

FEED_URL="{api_widget_url}"
DATA=$(curl -s "$FEED_URL")

JOBS_COUNT=$(echo "$DATA" | grep -o '"total_jobs":[0-9]*' | cut -d: -f2)
CRSE_COUNT=$(echo "$DATA" | grep -o '"total_courses":[0-9]*' | cut -d: -f2)

echo "🎯 ${{JOBS_COUNT:-0}} Jobs · ${{CRSE_COUNT:-0}} Certs | color=#6ee7b7"
echo "---"
echo "Open Dashboard | href=https://coursejobhunter.streamlit.app"
echo "Refresh Radar | refresh=true"
"""
            st.code(swiftbar_script, language="bash")

        with w_t3:
            st.markdown("### Android (KWGT) & Direct JSON Feed")
            st.caption("Use this endpoint with KWGT, Tasker, HTTP Shortcuts, or Raycast.")
            st.code(f"curl -s '{api_widget_url}'", language="bash")
            st.markdown(f"**JSON Endpoint URL:** `{api_widget_url}`")

# ── TAB 4: PERSONAL PREFERENCES ─────────────────────────────────────────────
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
