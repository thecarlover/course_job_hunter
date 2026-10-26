# Course & Job Hunter 🎓💼

A lightweight Python automation tool that checks the internet once a day for free online courses and remote jobs, sending you a clean, curated daily digest.

It runs **100% free on GitHub Actions** in the cloud on a schedule, so your computer does not need to stay on!

---

## What It Does

1. **Free Courses**: Scrapes RSS feeds (starting with Reddit's `r/udemyfreebies`) and filters for titles matching your chosen keywords.
2. **Remote Jobs**: Queries the free [Remotive API](https://remotive.com/api/remote-jobs) for your favorite search terms.
3. **No Repeats**: Remembers previously sent links in a `seen.json` file and never alerts you about the same course or job twice.
4. **Clean Digest**: Sends up to 15 new items in a single message formatted as:
   - 🎓 `[Course Title]` + Link
   - 💼 `[Job Title]` + Link
   - If nothing new was found, it silently exits without spamming you.
5. **Resilient**: If an RSS feed or API times out or fails, it skips it and continues running smoothly without crashing.

---

## 1. How to Install and Run Locally

### Prerequisites
- Python 3.10+ (Python 3.12 recommended)
- Git

### Step-by-Step Setup
1. Open your terminal or command prompt.
2. Clone or navigate into the project directory:
   ```bash
   cd course-job-hunter
   ```
3. Create a virtual environment:
   ```bash
   python3 -m venv .venv
   ```
4. Activate the virtual environment:
   - **macOS / Linux**:
     ```bash
     source .venv/bin/activate
     ```
   - **Windows (Command Prompt)**:
     ```cmd
     .venv\Scripts\activate
     ```
   - **Windows (PowerShell)**:
     ```powershell
     .venv\Scripts\Activate.ps1
     ```
5. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
6. **Test with Dry Run** (fetches live courses and jobs, prints them in your terminal, and skips sending notifications):
   ```bash
   python main.py --dry-run
   ```
7. Run the test suite:
   ```bash
   pytest
   ```

---

## 2. How to Set Up Your Notifier

In `config.py`, set `NOTIFIER` to `"email"`, `"ntfy"`, or `"discord"`.

### Option A: Email (Gmail SMTP)
Sends an email from your Gmail account directly to your own inbox.
1. Enable **2-Step Verification** on your Google Account:
   - Visit [Google Account Security](https://myaccount.google.com/security).
2. Generate an **App Password**:
   - Go to [Google App Passwords](https://myaccount.google.com/apppasswords).
   - Enter an app name like `Course Job Hunter` and click **Create**.
   - Copy the 16-character password displayed (e.g., `abcd efgh ijkl mnop`).
3. Set your environment variables:
   - `EMAIL`: Your full Gmail address (e.g. `yourname@gmail.com`).
   - `APP_PASSWORD`: The 16-character app password (spaces can be removed).

### Option B: ntfy (Instant Mobile & Desktop Push Alerts)
The simplest free option — no account or password required!
1. Choose a unique, unguessable topic name (e.g., `my-courses-jobs-hunter-92847`).
2. Install the free **ntfy** app on your phone (iOS / Android) or open `https://ntfy.sh/<YOUR_TOPIC>` in your browser.
3. Subscribe to your chosen topic.
4. Set the environment variable:
   - `NTFY_TOPIC`: Your chosen topic name.

### Option C: Discord (Webhook)
Sends notifications directly into a Discord channel.
1. In Discord, open your server and choose (or create) a text channel.
2. Click the gear icon next to the channel name -> **Integrations** -> **Webhooks**.
3. Click **New Webhook**, give it a name (e.g. `Job Hunter`), and click **Copy Webhook URL**.
4. Set the environment variable:
   - `WEBHOOK_URL`: The full webhook URL you copied.

---

## 3. How to Put It on GitHub and Automate It for Free

GitHub Actions runs the script automatically every day at **02:30 UTC** (which is **8:00 AM India Standard Time**), commits the updated `seen.json` back to your repository, and shuts down.

### Step 1: Create a Private GitHub Repository
1. Go to [GitHub.com](https://github.com/new).
2. Name your repository (e.g., `course-job-hunter`).
3. Set visibility to **Private** (recommended, so your seen items and repo history remain private).
4. Click **Create repository**.

### Step 2: Push Your Code
In your project folder on your computer, initialize git and push:
```bash
git init
git branch -M main
git add .
git commit -m "Initial commit of course-job-hunter"
git remote add origin https://github.com/<YOUR_USERNAME>/course-job-hunter.git
git push -u origin main
```

### Step 3: Add Repository Secrets
Your credentials must never be in code. Add them safely in GitHub:
1. In your GitHub repository, click **Settings** -> **Secrets and variables** -> **Actions**.
2. Click **New repository secret**.
3. Add the secrets matching your chosen notifier:
   - If using **email**:
     - `EMAIL` = your Gmail address
     - `APP_PASSWORD` = your 16-character Gmail App Password
   - If using **ntfy**:
     - `NTFY_TOPIC` = your topic name
   - If using **discord**:
     - `WEBHOOK_URL` = your Discord webhook URL

### Step 4: Grant Workflow Write Permission
To let GitHub Actions commit the updated `seen.json` file back to the repo:
1. In your repository, click **Settings** -> **Actions** -> **General**.
2. Scroll to **Workflow permissions**.
3. Select **Read and write permissions**.
4. Click **Save**.

### Step 5: Test the First Run
1. Go to the **Actions** tab in your repository.
2. In the left sidebar, click **Daily Course & Job Hunter**.
3. Click **Run workflow** -> select `Branch: main` -> click the green **Run workflow** button.
4. Refresh after a few seconds, click into the running job, and inspect the logs!

---

## 4. How to Change Keywords and Add Sources

All customization is handled in [`config.py`](config.py):

```python
# 1. Add any RSS or Atom feed URL for courses or deals
COURSE_FEEDS = [
    "https://www.reddit.com/r/udemyfreebies/.rss",
    # Example: "https://www.reddit.com/r/FreeFolkSci/.rss",
]

# 2. Add job search terms to query Remotive API
JOB_SEARCHES = [
    "python",
    "automation",
    "data",
]

# 3. Add or remove filter keywords (matches case-insensitively with word boundaries)
KEYWORDS = [
    "python",
    "automation",
    "excel",
    "ai",
    "linkedin",
    "free",
]

# 4. Limit the maximum number of items in a single digest
MAX_ITEMS = 15

# 5. Choose your notification provider: "email", "ntfy", or "discord"
NOTIFIER = "email"
```

---

## 5. Troubleshooting & FAQ

### 1. Reddit is blocking or returning HTTP 429
- Reddit limits requests that do not specify a unique `User-Agent`.
- `main.py` is pre-configured with a custom `User-Agent: CourseJobHunter/1.0`. If you make high-frequency local requests, wait a couple of minutes before retrying.

### 2. No messages arriving
- Check the terminal output or the GitHub Actions run log:
  - If it says `No new items found today. Nothing to send.`, it is working properly and simply suppressing empty digests.
  - If you want to reset all tracking and re-fetch everything, empty `seen.json` back to `[]`.
- In GitHub, verify that your secrets (`EMAIL`, `APP_PASSWORD`, `NTFY_TOPIC`, or `WEBHOOK_URL`) exactly match the names expected.

### 3. Gmail login fails (`smtplib.SMTPAuthenticationError`)
- Do not use your standard Gmail password. You must use an **App Password**.
- Make sure **2-Step Verification** is turned on on your Google Account; otherwise, Google does not allow App Password generation.
- Ensure there are no leading or trailing spaces in your secret value.

### 4. GitHub Action fails to push `seen.json`
- Ensure you enabled **Read and write permissions** under **Settings -> Actions -> General -> Workflow permissions**.

---

## Project Structure

```
course-job-hunter/
├── .github/
│   └── workflows/
│       └── daily.yml        # GitHub Actions scheduled workflow
├── config.py                # All user settings, feeds, keywords, and notifier choice
├── main.py                  # Core logic: fetching, filtering, limiting, running
├── notifier.py              # Notification dispatch (Email, ntfy, Discord)
├── test_hunter.py           # Pytest unit test suite
├── requirements.txt         # Python dependencies (requests, feedparser, pytest)
├── seen.json                # Persisted list of sent links
├── .gitignore               # Ignored cache, virtualenv, and system files
└── README.md                # Beginner-friendly setup guide
```
