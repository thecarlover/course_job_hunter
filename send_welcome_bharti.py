"""
send_welcome_bharti.py
======================
Send an editorial-grade, personalized welcome email to Bharti (vbharti2020@gmail.com).
Includes:
- Configuration overview (Project Management, Agile, Scrum, PMP, JIRA)
- One-click magic link into personal Hunter Hub dashboard
- 5 dashboard themes highlight
- Daily 8:00 AM IST digest details
- Prominent 'Share with Friends' referral section
"""

import hashlib
import hmac
import os
import urllib.parse
import notifier

notifier.load_dotenv()

PORTAL_SECRET_KEY = (os.environ.get("PORTAL_SECRET_KEY") or "hunter_portal_secret_2026").strip()
DASHBOARD_URL = "https://coursejobhunter.streamlit.app"
BHARTI_EMAIL = "vbharti2020@gmail.com"
BHARTI_NAME = "Bharti"

# Generate magic token for one-click authentication
magic_sig = hmac.new(
    PORTAL_SECRET_KEY.encode(),
    f"magic:{BHARTI_EMAIL.strip().lower()}".encode(),
    hashlib.sha256,
).hexdigest()[:24]

magic_dashboard_url = f"{DASHBOARD_URL}?email={urllib.parse.quote(BHARTI_EMAIL)}&magic={magic_sig}"
share_signup_url = f"{DASHBOARD_URL}?mode=signup"

kw_list = [
    "Project Management", "Agile & Scrum", "PMP & Certifications",
    "Jira & Workflow", "Product Management", "Operations Management", "100% Free Certs"
]

kw_pills = "".join(
    f'<span style="display:inline-block;background:#1e2235;border:1px solid rgba(99,102,241,0.3);'
    f'color:#a5b4fc;border-radius:99px;font-size:11px;font-weight:600;padding:4px 12px;margin:3px 3px 0 0;">'
    f'{k}</span>'
    for k in kw_list
)

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Welcome to Hunter Hub, {BHARTI_NAME}!</title>
</head>
<body style="margin:0;padding:0;background:#04050a;font-family:'Segoe UI',-apple-system,BlinkMacSystemFont,Arial,sans-serif;color:#e2e8f0;">

<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">
  Welcome to Hunter Hub! Your Project Management career radar & opportunity vault is active. Open your dashboard ↗
  &zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;
</div>

<table cellpadding="0" cellspacing="0" width="100%" style="background:#04050a;padding:36px 16px;">
  <tr>
    <td align="center">
      <table cellpadding="0" cellspacing="0" width="580" style="max-width:580px;">

        <!-- TOP BADGE -->
        <tr>
          <td align="center" style="padding-bottom:20px;">
            <span style="display:inline-block;background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.3);
              color:#6ee7b7;border-radius:99px;font-size:11px;font-weight:700;padding:6px 18px;
              letter-spacing:0.06em;text-transform:uppercase;">
              🎯 &nbsp;Welcome to Hunter Hub · Invited by Ojasvi
            </span>
          </td>
        </tr>

        <!-- HERO CARD -->
        <tr>
          <td style="background:#0d101c;border:1px solid rgba(255,255,255,0.08);border-radius:22px;
            padding:38px 36px 30px 36px;text-align:center;box-shadow:0 12px 36px rgba(0,0,0,0.5);">

            <div style="width:64px;height:64px;line-height:64px;border-radius:18px;
              background:rgba(99,102,241,0.14);border:1px solid rgba(99,102,241,0.35);
              margin:0 auto 20px auto;font-size:30px;">🎯</div>

            <h1 style="margin:0 0 10px 0;font-size:27px;font-weight:800;color:#ffffff;
              letter-spacing:-0.02em;line-height:1.2;">
              Welcome aboard, {BHARTI_NAME}!
            </h1>
            <p style="margin:0 0 22px 0;font-size:14px;color:#94a3b8;line-height:1.65;">
              Your dedicated <strong style="color:#ffffff;">Project Management Career Radar</strong> is now live.
              Starting <strong style="color:#10b981;">every morning at 8:00 AM IST</strong>, you'll receive a curated,
              verified digest of the freshest Project Management openings and 100% FREE certification courses.
            </p>

            <!-- PRE-CONFIGURED SETTINGS -->
            <div style="background:#08090d;border:1px solid rgba(255,255,255,0.06);border-radius:14px;
              padding:18px 20px;text-align:left;margin-bottom:26px;">
              <div style="font-size:10px;font-weight:700;color:#6366f1;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:10px;">
                ⚡ Pre-Configured For Your Targets:
              </div>
              <div style="margin-bottom:12px;">
                {kw_pills}
              </div>
              <div style="font-size:11px;color:#64748b;line-height:1.5;">
                📡 <strong>Monitored Sources:</strong> LinkedIn Jobs, Naukri, Remotive, Indeed India, Udemy 100% OFF Coupons, Swayam/NPTEL.
              </div>
            </div>

            <!-- CTA BUTTON -->
            <a href="{magic_dashboard_url}"
              style="display:inline-block;background:#4f46e5;color:#ffffff;text-decoration:none;
              font-size:15px;font-weight:700;padding:15px 36px;border-radius:12px;
              box-shadow:0 4px 24px rgba(79,70,229,0.45);letter-spacing:-0.01em;">
              Open My Dashboard &nbsp;↗
            </a>
            <p style="margin:14px 0 0 0;font-size:11px;color:#475569;">
              One-click instant login — no password required from this email
            </p>
          </td>
        </tr>

        <!-- SPACER -->
        <tr><td style="height:20px;"></td></tr>

        <!-- WHAT YOU GET INSIDE DASHBOARD -->
        <tr>
          <td style="background:#0d101c;border:1px solid rgba(255,255,255,0.08);border-radius:20px;padding:28px 32px;">
            <div style="font-size:11px;font-weight:700;color:#f59e0b;letter-spacing:0.08em;
              text-transform:uppercase;margin-bottom:16px;">🔥 &nbsp;What's Waiting In Your Dashboard</div>
            
            <table cellpadding="0" cellspacing="0" width="100%">
              <tr>
                <td style="padding-bottom:14px;">
                  <table cellpadding="0" cellspacing="0"><tr>
                    <td width="36" valign="top"><span style="font-size:20px;">💼</span></td>
                    <td>
                      <div style="font-size:13px;font-weight:700;color:#ffffff;">Curated PM Job Vault</div>
                      <div style="font-size:12px;color:#8b949e;line-height:1.5;margin-top:2px;">
                        Handpicked Project & Product Management opportunities with verified salary & location tags.
                      </div>
                    </td>
                  </tr></table>
                </td>
              </tr>
              <tr>
                <td style="padding-bottom:14px;">
                  <table cellpadding="0" cellspacing="0"><tr>
                    <td width="36" valign="top"><span style="font-size:20px;">🎓</span></td>
                    <td>
                      <div style="font-size:13px;font-weight:700;color:#ffffff;">100% Free Certifications</div>
                      <div style="font-size:12px;color:#8b949e;line-height:1.5;margin-top:2px;">
                        Udemy free discount coupons, Scrum/Agile guides, and Govt Swayam/NPTEL certifications.
                      </div>
                    </td>
                  </tr></table>
                </td>
              </tr>
              <tr>
                <td style="padding-bottom:14px;">
                  <table cellpadding="0" cellspacing="0"><tr>
                    <td width="36" valign="top"><span style="font-size:20px;">🎨</span></td>
                    <td>
                      <div style="font-size:13px;font-weight:700;color:#ffffff;">5 Bento Color Themes</div>
                      <div style="font-size:12px;color:#8b949e;line-height:1.5;margin-top:2px;">
                        Personalize your dashboard with Obsidian, Midnight Rose, Forest Hacker, Cyber Amber, or Arctic Blue.
                      </div>
                    </td>
                  </tr></table>
                </td>
              </tr>
              <tr>
                <td>
                  <table cellpadding="0" cellspacing="0"><tr>
                    <td width="36" valign="top"><span style="font-size:20px;">⚙️</span></td>
                    <td>
                      <div style="font-size:13px;font-weight:700;color:#ffffff;">Full Custom Control</div>
                      <div style="font-size:12px;color:#8b949e;line-height:1.5;margin-top:2px;">
                        Adjust your keywords, job boards, or pause digests anytime right from your Preferences tab.
                      </div>
                    </td>
                  </tr></table>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- SPACER -->
        <tr><td style="height:20px;"></td></tr>

        <!-- SHARE WITH FRIENDS CARD -->
        <tr>
          <td style="background:#0d101c;border:1px solid rgba(16,185,129,0.25);border-radius:20px;
            padding:28px 32px;text-align:center;">
            <div style="font-size:24px;margin-bottom:8px;">👥</div>
            <div style="font-size:16px;font-weight:800;color:#ffffff;margin-bottom:6px;">
              Share Hunter Hub with Your Friends!
            </div>
            <div style="font-size:13px;color:#94a3b8;line-height:1.6;margin-bottom:20px;">
              Know classmates, colleagues, or friends searching for jobs or wanting free tech certifications?
              Forward this email or share your invite link — it's completely free for them to set up their own radar!
            </div>

            <a href="{share_signup_url}"
              style="display:inline-block;background:rgba(16,185,129,0.14);color:#6ee7b7;
              text-decoration:none;font-size:13px;font-weight:700;padding:12px 28px;
              border-radius:10px;border:1px solid rgba(16,185,129,0.35);">
              🚀 &nbsp;Share Hunter Hub With Friends
            </a>

            <div style="margin-top:14px;font-size:11px;color:#64748b;">
              Direct Sign Up Link: <span style="color:#a5b4fc;font-family:monospace;">https://coursejobhunter.streamlit.app?mode=signup</span>
            </div>
          </td>
        </tr>

        <!-- SPACER -->
        <tr><td style="height:28px;"></td></tr>

        <!-- FOOTER -->
        <tr>
          <td align="center" style="padding-bottom:32px;">
            <div style="font-size:11px;color:#475569;line-height:1.8;">
              You're receiving this because you were added to <strong style="color:#94a3b8;">Hunter Hub</strong> by Ojasvi.<br>
              Daily digests land at ~8:00 AM IST · Need help? Reply directly to this email or reach out to Ojasvi.<br>
              <a href="{magic_dashboard_url}" style="color:#6366f1;text-decoration:none;">Open Dashboard</a>
              &nbsp;·&nbsp;
              <a href="https://github.com/thecarlover/course_job_hunter" style="color:#64748b;text-decoration:none;">GitHub</a>
            </div>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>
</body>
</html>"""

plain_text = f"""Welcome to Hunter Hub, {BHARTI_NAME}! 🎯

Your dedicated Project Management Career Radar is now active.
Starting every morning at 8:00 AM IST, you'll receive a curated digest of verified Project Management openings and 100% FREE certifications.

━━━ YOUR PRE-CONFIGURED TARGETS ━━━
• Keywords: Project Management, Agile & Scrum, PMP, Jira, Product Management, Operations
• Monitored Sources: LinkedIn Jobs, Naukri, Remotive, Indeed India, Udemy 100% OFF Coupons, Swayam/NPTEL

━━━ OPEN YOUR DASHBOARD (ONE-CLICK LOGIN) ━━━
{magic_dashboard_url}
(No password required from this link!)

Inside your dashboard:
• Explore your full opportunity vault
• Pick from 5 color themes (Obsidian, Midnight Rose, Forest Hacker, Cyber Amber, Arctic Blue)
• Update keywords or job boards anytime in Preferences

━━━ SHARE WITH FRIENDS ━━━
Know friends who are job hunting or want free certifications?
Share Hunter Hub with them (it's 100% free):
{share_signup_url}

Happy hunting!
Ojasvi & The Hunter Hub Team 🎯
"""

def main():
    print(f"[Welcome Email] Sending to {BHARTI_NAME} <{BHARTI_EMAIL}>...")
    subject = f"🎯 Welcome to Hunter Hub, {BHARTI_NAME}! Your Project Management Radar is Active"
    notifier.send(
        text=plain_text,
        to_email=BHARTI_EMAIL,
        subject=subject,
        html=html_content,
    )
    print(f"✅ Successfully delivered welcome email to {BHARTI_NAME} <{BHARTI_EMAIL}>!")

if __name__ == "__main__":
    main()
