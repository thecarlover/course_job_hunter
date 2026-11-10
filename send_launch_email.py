"""
send_launch_email.py
====================
One-shot broadcast: Hunter Hub dashboard launch announcement.
Sends a personalised HTML email to every active subscriber.
"""

import hashlib, hmac, json, os, sys

# ── env / dotenv ────────────────────────────────────────────────────────────
import notifier
notifier.load_dotenv()
import config

RECIPIENTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recipients.json")
PORTAL_SECRET_KEY = (os.environ.get("PORTAL_SECRET_KEY") or "hunter_portal_secret_2026").strip()
DASHBOARD_URL = "https://coursejobhunter.streamlit.app"


def magic_link(email: str) -> str:
    sig = hmac.new(
        PORTAL_SECRET_KEY.encode(),
        f"magic:{email.strip().lower()}".encode(),
        hashlib.sha256,
    ).hexdigest()[:24]
    return f"{DASHBOARD_URL}?email={email}&magic={sig}"


def build_html(name: str, email: str, keywords: list) -> str:
    kw_pills = "".join(
        f'<span style="display:inline-block;background:#1e2235;border:1px solid rgba(99,102,241,0.3);'
        f'color:#a5b4fc;border-radius:99px;font-size:11px;font-weight:600;padding:3px 10px;margin:3px 3px 0 0;">'
        f'{k}</span>'
        for k in (keywords or [])[:8]
    )
    dashboard_link = magic_link(email)

    features = [
        ("🎯", "Personal Career Radar", "Jobs & free courses curated daily at 8 AM IST — just for your keywords."),
        ("🎨", "5 Dashboard Themes", "Obsidian, Midnight Rose, Forest Hacker, Cyber Amber, Arctic Blue. Make it yours."),
        ("🔥", "Daily Streak & XP", "Earn points every day you open your radar. Keep the streak alive."),
        ("🔒", "AI Pitch (Coming Soon)", "One-click outreach emails to hiring managers. Pro feature dropping soon."),
        ("📂", "Opportunity Vault", "Every job and free course ever sent to you, searchable and filterable."),
        ("⚙️", "Targeting Preferences", "Change your keywords and job boards anytime — no waiting for support."),
    ]

    feature_cards = ""
    for icon, title, desc in features:
        feature_cards += f"""
        <tr>
          <td style="padding:0 0 12px 0;">
            <table cellpadding="0" cellspacing="0" width="100%">
              <tr>
                <td width="44" valign="top" style="padding-top:2px;">
                  <div style="width:36px;height:36px;line-height:36px;text-align:center;
                    border-radius:10px;background:#0f121d;border:1px solid rgba(255,255,255,0.08);
                    font-size:18px;">{icon}</div>
                </td>
                <td style="padding-left:12px;">
                  <div style="font-size:13px;font-weight:700;color:#ffffff;margin-bottom:2px;">{title}</div>
                  <div style="font-size:12px;color:#8b949e;line-height:1.5;">{desc}</div>
                </td>
              </tr>
            </table>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hunter Hub is Live — Your Career Radar Dashboard</title>
</head>
<body style="margin:0;padding:0;background:#04050a;font-family:'Segoe UI',Arial,sans-serif;">

<!-- Preheader -->
<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">
  Your personal Career Radar dashboard is live. 5 themes, daily streak, opportunity vault — open it now ↗
  &zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;
</div>

<table cellpadding="0" cellspacing="0" width="100%" style="background:#04050a;padding:32px 16px;">
  <tr>
    <td align="center">
      <table cellpadding="0" cellspacing="0" width="560" style="max-width:560px;">

        <!-- TOP BADGE -->
        <tr>
          <td align="center" style="padding-bottom:20px;">
            <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.3);
              color:#a5b4fc;border-radius:99px;font-size:11px;font-weight:700;padding:5px 16px;
              letter-spacing:0.06em;text-transform:uppercase;">
              🚀 &nbsp;Product Launch — Hunter Hub Dashboard
            </span>
          </td>
        </tr>

        <!-- HERO CARD -->
        <tr>
          <td style="background:#0d101c;border:1px solid rgba(255,255,255,0.08);border-radius:20px;
            padding:36px 36px 28px 36px;text-align:center;">

            <!-- Logo mark -->
            <div style="width:60px;height:60px;line-height:60px;border-radius:16px;
              background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.3);
              margin:0 auto 20px auto;font-size:28px;">🎯</div>

            <h1 style="margin:0 0 8px 0;font-size:28px;font-weight:800;color:#ffffff;
              letter-spacing:-0.02em;line-height:1.2;">
              Your Career Radar<br>Dashboard is Live
            </h1>
            <p style="margin:0 0 20px 0;font-size:14px;color:#8b949e;line-height:1.6;">
              Hey <strong style="color:#e2e8f0;">{name}</strong> 👋 — we just shipped the
              <strong style="color:#ffffff;">Hunter Hub personal dashboard</strong>. No more waiting in
              your inbox. Now you have a full career ops centre, designed around your targets.
            </p>

            <!-- Your keywords -->
            {f'<div style="margin-bottom:24px;text-align:left;">' +
             f'<div style="font-size:10px;font-weight:700;color:#64748b;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:8px;">YOUR ACTIVE TARGETS</div>' +
             kw_pills +
             '</div>' if kw_pills else ''}

            <!-- CTA Button -->
            <a href="{dashboard_link}"
              style="display:inline-block;background:#4f46e5;color:#ffffff;text-decoration:none;
              font-size:14px;font-weight:700;padding:14px 32px;border-radius:12px;
              box-shadow:0 4px 20px rgba(79,70,229,0.4);letter-spacing:-0.01em;">
              Open My Dashboard &nbsp;↗
            </a>
            <p style="margin:14px 0 0 0;font-size:11px;color:#475569;">
              One-click access — no password needed from this link
            </p>
          </td>
        </tr>

        <!-- SPACER -->
        <tr><td style="height:20px;"></td></tr>

        <!-- FEATURES CARD -->
        <tr>
          <td style="background:#0d101c;border:1px solid rgba(255,255,255,0.08);border-radius:20px;
            padding:28px 32px;">
            <div style="font-size:11px;font-weight:700;color:#6366f1;letter-spacing:0.08em;
              text-transform:uppercase;margin-bottom:18px;">What's Inside</div>
            <table cellpadding="0" cellspacing="0" width="100%">
              {feature_cards}
            </table>
          </td>
        </tr>

        <!-- SPACER -->
        <tr><td style="height:20px;"></td></tr>

        <!-- THEME SHOWCASE CARD -->
        <tr>
          <td style="background:#0d101c;border:1px solid rgba(255,255,255,0.08);border-radius:20px;
            padding:28px 32px;">
            <div style="font-size:11px;font-weight:700;color:#10b981;letter-spacing:0.08em;
              text-transform:uppercase;margin-bottom:14px;">🎨 &nbsp;Pick Your Vibe</div>
            <div style="font-size:13px;color:#94a3b8;line-height:1.6;margin-bottom:16px;">
              The dashboard now ships with <strong style="color:#ffffff;">5 colour themes</strong>.
              Hit any theme button on the dashboard header to switch instantly.
            </div>
            <table cellpadding="0" cellspacing="0">
              <tr>
                <td style="padding-right:8px;padding-bottom:8px;">
                  <span style="display:inline-block;background:#08090d;border:2px solid #6366f1;
                    color:#a5b4fc;border-radius:8px;font-size:11px;font-weight:700;padding:5px 12px;">
                    🌑 Obsidian
                  </span>
                </td>
                <td style="padding-right:8px;padding-bottom:8px;">
                  <span style="display:inline-block;background:#0d0812;border:2px solid #c084fc;
                    color:#e9d5ff;border-radius:8px;font-size:11px;font-weight:700;padding:5px 12px;">
                    🌸 Midnight Rose
                  </span>
                </td>
                <td style="padding-right:8px;padding-bottom:8px;">
                  <span style="display:inline-block;background:#060d08;border:2px solid #22c55e;
                    color:#86efac;border-radius:8px;font-size:11px;font-weight:700;padding:5px 12px;">
                    🌿 Forest Hacker
                  </span>
                </td>
              </tr>
              <tr>
                <td style="padding-right:8px;">
                  <span style="display:inline-block;background:#0c0900;border:2px solid #f59e0b;
                    color:#fcd34d;border-radius:8px;font-size:11px;font-weight:700;padding:5px 12px;">
                    ⚡ Cyber Amber
                  </span>
                </td>
                <td style="padding-right:8px;">
                  <span style="display:inline-block;background:#020c18;border:2px solid #3b82f6;
                    color:#93c5fd;border-radius:8px;font-size:11px;font-weight:700;padding:5px 12px;">
                    🧊 Arctic Blue
                  </span>
                </td>
                <td></td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- SPACER -->
        <tr><td style="height:20px;"></td></tr>

        <!-- HOW TO USE DAILY -->
        <tr>
          <td style="background:#0d101c;border:1px solid rgba(245,158,11,0.2);border-radius:20px;
            padding:28px 32px;">
            <div style="font-size:11px;font-weight:700;color:#f59e0b;letter-spacing:0.08em;
              text-transform:uppercase;margin-bottom:14px;">🔥 &nbsp;Your Daily Habit Loop</div>
            <table cellpadding="0" cellspacing="0" width="100%">
              <tr>
                <td style="padding-bottom:12px;">
                  <table cellpadding="0" cellspacing="0"><tr>
                    <td width="28" style="font-size:12px;font-weight:800;color:#fcd34d;vertical-align:top;padding-top:1px;">1.</td>
                    <td style="font-size:13px;color:#94a3b8;line-height:1.5;">
                      <strong style="color:#e2e8f0;">8:00 AM IST</strong> — your morning digest lands in inbox
                    </td>
                  </tr></table>
                </td>
              </tr>
              <tr>
                <td style="padding-bottom:12px;">
                  <table cellpadding="0" cellspacing="0"><tr>
                    <td width="28" style="font-size:12px;font-weight:800;color:#fcd34d;vertical-align:top;padding-top:1px;">2.</td>
                    <td style="font-size:13px;color:#94a3b8;line-height:1.5;">
                      <strong style="color:#e2e8f0;">Click "Open Dashboard"</strong> in the email → land on your personal vault
                    </td>
                  </tr></table>
                </td>
              </tr>
              <tr>
                <td style="padding-bottom:12px;">
                  <table cellpadding="0" cellspacing="0"><tr>
                    <td width="28" style="font-size:12px;font-weight:800;color:#fcd34d;vertical-align:top;padding-top:1px;">3.</td>
                    <td style="font-size:13px;color:#94a3b8;line-height:1.5;">
                      <strong style="color:#e2e8f0;">Browse, filter, claim</strong> — apply to jobs or enroll in free courses
                    </td>
                  </tr></table>
                </td>
              </tr>
              <tr>
                <td>
                  <table cellpadding="0" cellspacing="0"><tr>
                    <td width="28" style="font-size:12px;font-weight:800;color:#fcd34d;vertical-align:top;padding-top:1px;">4.</td>
                    <td style="font-size:13px;color:#94a3b8;line-height:1.5;">
                      <strong style="color:#e2e8f0;">Build your streak</strong> — come back tomorrow, earn XP, stay sharp
                    </td>
                  </tr></table>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- SPACER -->
        <tr><td style="height:20px;"></td></tr>

        <!-- SHARE CARD -->
        <tr>
          <td style="background:#0d101c;border:1px solid rgba(16,185,129,0.2);border-radius:20px;
            padding:28px 32px;text-align:center;">
            <div style="font-size:18px;margin-bottom:8px;">👥</div>
            <div style="font-size:15px;font-weight:700;color:#ffffff;margin-bottom:8px;">
              Know someone grinding through job applications?
            </div>
            <div style="font-size:13px;color:#8b949e;line-height:1.6;margin-bottom:18px;">
              Share Hunter Hub with them. It's completely free — daily curated jobs,
              100% off Udemy coupons, and a personal dashboard delivered to their inbox every morning.
            </div>
            <a href="https://github.com/thecarlover/course_job_hunter"
              style="display:inline-block;background:rgba(16,185,129,0.12);color:#6ee7b7;
              text-decoration:none;font-size:12px;font-weight:700;padding:10px 24px;
              border-radius:10px;border:1px solid rgba(16,185,129,0.3);">
              ⭐ &nbsp;Star on GitHub
            </a>
          </td>
        </tr>

        <!-- SPACER -->
        <tr><td style="height:28px;"></td></tr>

        <!-- FOOTER -->
        <tr>
          <td align="center" style="padding-bottom:32px;">
            <div style="font-size:11px;color:#334155;line-height:1.8;">
              You're receiving this because you subscribed to <strong style="color:#475569;">Hunter Hub</strong>.<br>
              Daily digests arrive at 8:00 AM IST · Manage preferences inside the dashboard.<br>
              <a href="{dashboard_link}" style="color:#6366f1;text-decoration:none;">Open Dashboard</a>
              &nbsp;·&nbsp;
              <a href="https://github.com/thecarlover/course_job_hunter" style="color:#475569;text-decoration:none;">GitHub</a>
            </div>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>
</body>
</html>"""


def build_plain(name: str, dashboard_link: str) -> str:
    return f"""Hey {name}!

Your Hunter Hub personal career dashboard is now LIVE 🚀

Open it here (one-click, no password needed):
{dashboard_link}

━━━ WHAT'S INSIDE ━━━

🎯  Personal Career Radar — jobs & free courses curated daily at 8 AM IST
🎨  5 Colour Themes — Obsidian, Rose, Forest, Amber, Arctic. Pick your vibe.
🔥  Daily Streak & XP — earn points every day you open your radar
📂  Opportunity Vault — every job/course ever sent to you, searchable
⚙️  Targeting Prefs — update keywords & job boards without emailing anyone
🔒  AI Pitch (Coming Soon) — one-click outreach to hiring managers

━━━ YOUR DAILY HABIT ━━━

1. 8:00 AM IST — digest lands in your inbox
2. Click "Open Dashboard" → land on your personal vault
3. Browse, filter, claim — apply or enroll
4. Build your streak, earn XP, stay sharp

━━━ SHARE IT ━━━

Know someone grinding through job apps? Share Hunter Hub with them.
It's completely free and they can subscribe too.
⭐ Star on GitHub: https://github.com/thecarlover/course_job_hunter

Happy hunting,
Ojasvi & the Hunter Hub Bot 🎯

──────────────────────────────────
You're receiving this because you subscribed to Hunter Hub.
Daily digests arrive at 8:00 AM IST.
Manage preferences inside the dashboard above.
"""


def main():
    with open(RECIPIENTS_FILE, encoding="utf-8") as f:
        recipients = json.load(f)

    active = [r for r in recipients if r.get("active", True)]
    print(f"[Launch Email] Sending to {len(active)} subscriber(s)...\n")

    for sub in active:
        name  = sub.get("name") or sub.get("email", "").split("@")[0].title()
        email = sub.get("email", "").strip()
        kws   = list({*sub.get("keywords", []), *sub.get("job_searches", [])})

        if not email:
            print(f"  [SKIP] No email for {name}")
            continue

        link  = magic_link(email)
        html_body  = build_html(name, email, kws)
        plain_body = build_plain(name, link)

        subject = f"🎯 Hunter Hub is Live — Your Personal Career Dashboard, {name}!"

        try:
            notifier.send(
                text=plain_body,
                to_email=email,
                subject=subject,
                html=html_body,
            )
            print(f"  ✅  Sent to {name} <{email}>")
        except Exception as exc:
            print(f"  ❌  Failed for {name} <{email}>: {exc}")

    print("\n[Launch Email] Done.")


if __name__ == "__main__":
    main()
