"""
send_early_bird_announcement.py
================================
Broadcast email to ALL active subscribers announcing the brand new
'First 10 Applicants' Urgent Radar feature, with personalized 1-click magic
login links and a prominent referral/share prompt.
"""

import hashlib
import hmac
import json
import os
import urllib.parse
import notifier

notifier.load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RECIPIENTS_FILE = os.path.join(BASE_DIR, "recipients.json")
PORTAL_SECRET_KEY = (os.environ.get("PORTAL_SECRET_KEY") or "hunter_portal_secret_2026").strip()
DASHBOARD_URL = "https://coursejobhunter.streamlit.app"
SHARE_SIGNUP_URL = f"{DASHBOARD_URL}?mode=signup"


def make_magic_link(email: str) -> str:
    sig = hmac.new(
        PORTAL_SECRET_KEY.encode(),
        f"magic:{email.strip().lower()}".encode(),
        hashlib.sha256,
    ).hexdigest()[:24]
    return f"{DASHBOARD_URL}?email={urllib.parse.quote(email)}&magic={sig}"


def build_announcement_html(name: str, email: str, keywords: list) -> str:
    magic_link = make_magic_link(email)
    kw_pills = "".join(
        f'<span style="display:inline-block;background:#1e2235;border:1px solid rgba(245,158,11,0.3);'
        f'color:#fcd34d;border-radius:99px;font-size:11px;font-weight:600;padding:3px 10px;margin:3px 3px 0 0;">'
        f'{k}</span>'
        for k in (keywords or [])[:6]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>⚡ New Feature: "First 10 Applicants" Urgent Radar</title>
</head>
<body style="margin:0;padding:0;background:#04050a;font-family:'Segoe UI',-apple-system,BlinkMacSystemFont,Arial,sans-serif;color:#e2e8f0;">

<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">
  New on Hunter Hub: "First 10 Applicants" Urgent Radar is live! Apply in the 2-hour window for 3x callbacks. Open your dashboard ↗
  &zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;
</div>

<table cellpadding="0" cellspacing="0" width="100%" style="background:#04050a;padding:36px 16px;">
  <tr>
    <td align="center">
      <table cellpadding="0" cellspacing="0" width="580" style="max-width:580px;">

        <!-- TOP PILL -->
        <tr>
          <td align="center" style="padding-bottom:20px;">
            <span style="display:inline-block;background:rgba(245,158,11,0.14);border:1px solid rgba(245,158,11,0.35);
              color:#fcd34d;border-radius:99px;font-size:11px;font-weight:700;padding:6px 18px;
              letter-spacing:0.06em;text-transform:uppercase;">
              ⚡ &nbsp;Major Feature Drop · Hunter Hub
            </span>
          </td>
        </tr>

        <!-- HERO CARD -->
        <tr>
          <td style="background:#0d101c;border:1px solid rgba(245,158,11,0.28);border-radius:22px;
            padding:38px 36px 30px 36px;text-align:center;box-shadow:0 12px 36px rgba(0,0,0,0.5);">

            <div style="width:64px;height:64px;line-height:64px;border-radius:18px;
              background:rgba(245,158,11,0.12);border:1px solid rgba(245,158,11,0.35);
              margin:0 auto 20px auto;font-size:30px;">⚡</div>

            <h1 style="margin:0 0 10px 0;font-size:26px;font-weight:800;color:#ffffff;
              letter-spacing:-0.02em;line-height:1.25;">
              "First 10 Applicants"<br><span style="color:#fcd34d;">Urgent Radar</span> is Live!
            </h1>
            <p style="margin:0 0 22px 0;font-size:14px;color:#94a3b8;line-height:1.65;">
              Hey <strong style="color:#ffffff;">{name}</strong> 👋 — ever applied to a job on LinkedIn that already had 300+ applicants and never heard back? We just solved that.
            </p>

            <!-- STAT CALLOUT BOX -->
            <div style="background:#08090d;border:1px solid rgba(245,158,11,0.25);border-radius:14px;
              padding:18px 20px;text-align:left;margin-bottom:24px;">
              <div style="font-size:11px;font-weight:700;color:#fcd34d;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:6px;">
                💡 Why This Gives You an Unfair Advantage:
              </div>
              <div style="font-size:13px;color:#e2e8f0;line-height:1.6;">
                Hiring managers &amp; recruiters review candidates in batches. Over <strong style="color:#10b981;">80% of interview calls</strong> go to applicants who submit within the <strong>first 2 to 4 hours</strong> of posting — before the ATS gets flooded.
              </div>
              {f'<div style="margin-top:14px;padding-top:10px;border-top:1px solid rgba(255,255,255,0.06);font-size:11px;color:#64748b;">🎯 <strong>Your Active Targets:</strong><br>{kw_pills}</div>' if kw_pills else ''}
            </div>

            <!-- CTA BUTTON -->
            <a href="{magic_link}"
              style="display:inline-block;background:#f59e0b;color:#000000;text-decoration:none;
              font-size:15px;font-weight:800;padding:15px 36px;border-radius:12px;
              box-shadow:0 4px 24px rgba(245,158,11,0.45);letter-spacing:-0.01em;">
              Check Urgent Openings Now &nbsp;↗
            </a>
            <p style="margin:14px 0 0 0;font-size:11px;color:#475569;">
              1-click instant login — opens directly to your personalized vault
            </p>
          </td>
        </tr>

        <!-- SPACER -->
        <tr><td style="height:20px;"></td></tr>

        <!-- HOW TO USE THE NEW RADAR -->
        <tr>
          <td style="background:#0d101c;border:1px solid rgba(255,255,255,0.08);border-radius:20px;padding:28px 32px;">
            <div style="font-size:11px;font-weight:700;color:#6366f1;letter-spacing:0.08em;
              text-transform:uppercase;margin-bottom:16px;">🔥 &nbsp;How the Urgent Radar Works in Your Dashboard</div>
            
            <table cellpadding="0" cellspacing="0" width="100%">
              <tr>
                <td style="padding-bottom:14px;">
                  <table cellpadding="0" cellspacing="0"><tr>
                    <td width="36" valign="top"><span style="font-size:20px;">🏷️</span></td>
                    <td>
                      <div style="font-size:13px;font-weight:700;color:#ffffff;">Live "Early Bird" Badges</div>
                      <div style="font-size:12px;color:#8b949e;line-height:1.5;margin-top:2px;">
                        Openings with under 15 applicants are highlighted with glowing gold badges so you can spot them instantly.
                      </div>
                    </td>
                  </tr></table>
                </td>
              </tr>
              <tr>
                <td style="padding-bottom:14px;">
                  <table cellpadding="0" cellspacing="0"><tr>
                    <td width="36" valign="top"><span style="font-size:20px;">⚡</span></td>
                    <td>
                      <div style="font-size:13px;font-weight:700;color:#ffffff;">1-Click "Early Bird Only" Filter</div>
                      <div style="font-size:12px;color:#8b949e;line-height:1.5;margin-top:2px;">
                        Check the new <strong>"🔥 Early Bird Only"</strong> box to hide crowded listings and focus strictly on fresh roles.
                      </div>
                    </td>
                  </tr></table>
                </td>
              </tr>
              <tr>
                <td>
                  <table cellpadding="0" cellspacing="0"><tr>
                    <td width="36" valign="top"><span style="font-size:20px;">⏰</span></td>
                    <td>
                      <div style="font-size:13px;font-weight:700;color:#ffffff;">Daily 8:00 AM IST Sync</div>
                      <div style="font-size:12px;color:#8b949e;line-height:1.5;margin-top:2px;">
                        Your morning email will now feature Early Bird opportunities right at the top so you can apply before your first meeting.
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

        <!-- SHARE WITH FRIENDS CARD (PROMINENT) -->
        <tr>
          <td style="background:#0d101c;border:1px solid rgba(16,185,129,0.3);border-radius:20px;
            padding:32px 32px;text-align:center;box-shadow:0 8px 24px rgba(16,185,129,0.1);">
            <div style="font-size:26px;margin-bottom:8px;">👥</div>
            <div style="font-size:17px;font-weight:800;color:#ffffff;margin-bottom:6px;">
              Know Friends Looking for Jobs or Free Courses?
            </div>
            <div style="font-size:13px;color:#94a3b8;line-height:1.6;margin-bottom:20px;">
              Don't let them apply cold to 300-applicant listings! Share Hunter Hub with them. It takes <strong>30 seconds</strong> to set up their own personalized career radar — completely free.
            </div>

            <a href="{SHARE_SIGNUP_URL}"
              style="display:inline-block;background:#10b981;color:#000000;
              text-decoration:none;font-size:14px;font-weight:800;padding:13px 32px;
              border-radius:10px;box-shadow:0 4px 18px rgba(16,185,129,0.4);">
              🚀 &nbsp;Share Hunter Hub With Friends
            </a>

            <div style="margin-top:16px;background:#08090d;border:1px solid rgba(255,255,255,0.06);border-radius:8px;padding:8px 12px;display:inline-block;">
              <span style="font-size:11px;color:#64748b;">Copy &amp; share this link:</span>
              <span style="font-size:11px;color:#a5b4fc;font-family:monospace;margin-left:6px;">https://coursejobhunter.streamlit.app?mode=signup</span>
            </div>
          </td>
        </tr>

        <!-- SPACER -->
        <tr><td style="height:28px;"></td></tr>

        <!-- FOOTER -->
        <tr>
          <td align="center" style="padding-bottom:32px;">
            <div style="font-size:11px;color:#475569;line-height:1.8;">
              You're receiving this because you're a subscriber of <strong style="color:#94a3b8;">Hunter Hub</strong>.<br>
              Daily digests arrive at ~8:00 AM IST · Update preferences inside your dashboard.<br>
              <a href="{magic_link}" style="color:#6366f1;text-decoration:none;">Open Dashboard</a>
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


def build_announcement_plain(name: str, magic_link: str) -> str:
    return f"""Hey {name}! ⚡

Big feature drop on Hunter Hub: The "First 10 Applicants" Urgent Radar is officially live!

━━━ WHY THIS MATTERS ━━━
Applying to a job that already has 200+ applicants often lands your resume in an ATS black hole.
Data shows that over 80% of interview callbacks go to candidates who apply in the FIRST 2 TO 4 HOURS of posting.

Hunter Hub now automatically detects and tags these fresh openings with:
🔥 EARLY BIRD · <15 APPLICANTS (3X CALLBACK WINDOW)

━━━ OPEN YOUR DASHBOARD (1-CLICK LOGIN) ━━━
{magic_link}
(No password required from this link!)

Inside:
• See your urgent openings with glowing Early Bird badges
• Use the new "Early Bird Only" filter to skip crowded listings
• Apply directly to uncrowded openings first thing in the morning

━━━ SHARE WITH YOUR FRIENDS 👥 ━━━
Know friends, classmates, or colleagues who are grinding through job applications?
Share Hunter Hub with them so they can get their own radar:
{SHARE_SIGNUP_URL}

Happy hunting,
Ojasvi & The Hunter Hub Team 🎯
"""


def main():
    if not os.path.exists(RECIPIENTS_FILE):
        print(f"[Error] {RECIPIENTS_FILE} not found.")
        return

    with open(RECIPIENTS_FILE, "r", encoding="utf-8") as f:
        subscribers = json.load(f)

    active_subs = [s for s in subscribers if s.get("active", True)]
    print(f"\n[Broadcast] Sending Urgent Radar Announcement to {len(active_subs)} subscriber(s)...\n")

    success_count = 0
    fail_count = 0

    for sub in active_subs:
        name = sub.get("name") or sub.get("email", "").split("@")[0].title()
        email = (sub.get("email") or "").strip()
        kws = list({*sub.get("keywords", []), *sub.get("job_searches", [])})

        if not email:
            continue

        subject = f"⚡ New on Hunter Hub: \"First 10 Applicants\" Urgent Radar is Live, {name}!"
        magic_link = make_magic_link(email)
        html_msg = build_announcement_html(name, email, kws)
        plain_msg = build_announcement_plain(name, magic_link)

        try:
            notifier.send(
                text=plain_msg,
                to_email=email,
                subject=subject,
                html=html_msg,
            )
            print(f"  ✅ Sent to {name} <{email}>")
            success_count += 1
        except Exception as exc:
            print(f"  ❌ Failed for {name} <{email}>: {exc}")
            fail_count += 1

    print(f"\n[Broadcast Complete] {success_count} sent successfully, {fail_count} failed.\n")


if __name__ == "__main__":
    main()
