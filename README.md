# Course & Job Hunter 🎓💼

A lightweight Python automation tool that checks the internet daily for free online courses and remote jobs, sending curated, personalized daily digests.

It supports **multiple recipients**—each person gets their own private email with their own keywords and search terms. It runs **100% free on GitHub Actions** in the cloud on a schedule, so your computer does not need to stay on!

---

## What It Does

1. **Multi-Person Support**: Send personalized digests to you and your friends. Each person gets their own email starting with `"Hi <name>,"`. No shared To/CC headers!
2. **Efficient Fetching**: Checks each RSS feed and job API **only once** per run, then filters results individually for each person using their chosen keywords.
3. **Independent History**: Tracks seen links per person in `seen.json` so one person's digest never affects another's.
4. **Quiet When Empty**: If a person has no new items for the day, the bot skips them silently without sending empty emails.
5. **Resilient**: If an RSS feed fails or sending to one person encounters an issue, the bot logs the error and continues with the others without crashing.

---

## 1. How to Add a Friend

### Method A: Use the interactive script (Easiest)
Run the built-in helper script in your terminal:
```bash
python add_friend.py
```
It will ask you for:
- Friend's name
- Friend's email
- Keywords (e.g. `python, ai, excel, cybersecurity`)
- Job search terms (or press Enter to use their keywords)
- Max items per email (default is 15)

The script automatically formats and saves them into `recipients.json`.

---

### Method B: Edit `recipients.json` directly
Open `recipients.json` in your editor and add a new entry to the list:
```json
[
  {
    "name": "Alex",
    "email": "alex@example.com",
    "active": true,
    "keywords": ["python", "machine learning", "data science"],
    "job_searches": ["python", "data scientist"],
    "course_feeds": [],
    "max_items": 15
  }
]
```
- `course_feeds`: Optional. Leave as `[]` to use the default feeds from `config.py`.
- `active`: Set to `true` to receive digests.

---

### Method C: Keep friends' emails secret using GitHub Secrets
If you want to keep your friends' emails completely out of your GitHub repository:
1. Go to your GitHub repository -> **Settings** -> **Secrets and variables** -> **Actions**.
2. Click **New repository secret**.
3. Name: `RECIPIENTS_JSON`.
4. Value: Paste the full JSON array from `recipients.json`.
5. Whenever `RECIPIENTS_JSON` is set as a GitHub Secret, the bot uses it automatically!

---

## 2. How to Pause or Remove a Friend

- **To Pause a friend** (without deleting their settings):
  In `recipients.json`, change their `active` setting to `false`:
  ```json
  "active": false
  ```
  The bot will skip them during daily runs while keeping their keywords and seen history safe.
- **To Remove a friend**:
  Simply delete their block from `recipients.json`.

After editing `recipients.json`, commit and push your changes:
```bash
git add recipients.json
git commit -m "update recipients list"
git push
```

---

## 3. How to Check If the Daily Run Worked

1. Go to your repository on GitHub.
2. Click the **Actions** tab at the top.
3. Under "All workflows", click **Daily Course & Job Hunter**.
4. Click on the latest workflow run in the list.
5. Click on the **hunt** job.
6. Click on the **Run Course & Job Hunter** step to expand its logs.
7. You will see an **Execution Summary** detailing:
   - Sources checked
   - Total items harvested
   - Active recipients evaluated
   - Emails sent
   - Any errors encountered

---

## 4. Troubleshooting Guide

### 1. Workflow Not Running on Schedule
- **GitHub Actions Delay**: GitHub's cron scheduler can be delayed by 15 to 40 minutes during peak hours. The workflow is scheduled at `01:45 UTC` (7:15 AM IST) so it arrives around 8:00 AM IST.
- **Scheduled Workflows Disabled**: On new repositories, GitHub may pause scheduled actions. Go to the **Actions** tab. If you see a yellow banner asking to enable workflows, click **Enable workflow**.
- **Manual Test**: You can trigger the workflow anytime: go to **Actions** -> **Daily Course & Job Hunter** -> click **Run workflow**.

### 2. Secrets Missing or Wrong
- If `EMAIL` or `APP_PASSWORD` is missing, `main.py` will exit with a clear error in the Actions log: `[Fatal Error] Configuration check failed: Missing required secret(s)...`.
- To fix: Go to **Settings** -> **Secrets and variables** -> **Actions** -> Add `EMAIL` and `APP_PASSWORD`.

### 3. Gmail Login Failing
- **Do not use your regular Gmail password** — Google blocks it.
- Make sure **2-Step Verification** is turned on in your Google Account.
- Generate a new 16-letter App Password at [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
- Paste the 16 letters into your `APP_PASSWORD` secret (spaces are automatically stripped by the bot).

### 4. No Emails Arriving
- **Already Seen**: If you or your friends received all available courses and jobs yesterday, and no *new* items were posted today, the bot silently skips sending to avoid spam. Check the Actions log: if it says `No new items for <name>. Skipping silently`, it is working normally.
- Check the **Execution Summary** in the Actions tab to confirm how many items were found and sent.

### 5. Emails Going to Spam
- Check your Gmail **Spam** folder.
- If found in Spam, select the email and click **Report not spam**.
- Add your sender email address to your Google Contacts to guarantee inbox delivery.

### 6. Workflow Cannot Save `seen.json` (Permission Denied)
- Go to repository **Settings** -> **Actions** -> **General**.
- Scroll to **Workflow permissions**.
- Select **Read and write permissions** and click **Save**.

---

## 5. Local Setup & Testing

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Test in dry-run mode (prints output without sending emails):
   ```bash
   python main.py --dry-run
   ```
3. Run the automated test suite:
   ```bash
   pytest
   ```
