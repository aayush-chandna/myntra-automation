# Myntra Weekly T-Shirt Bot

Automates: pick 3 distinct men's T-shirt styles (LLM-generated) → search
Myntra → filter to size L, ≤ ₹1500 → add to bag → checkout → select COD →
**pause for you** to clear CAPTCHA/OTP manually.

⚠️ **Read the docstring at the top of `myntra_weekly_order.py` first.**
Myntra's DOM changes often; selectors will need periodic fixes. This never
auto-solves CAPTCHA/OTP, and never touches card/UPI payment — only COD.

---

## 1. Install dependencies

```bash
cd myntra_bot
bash install_dependencies.sh
```

This creates a `venv/`, installs `playwright`, `anthropic`, and
`google-generativeai`, and downloads the Chromium browser Playwright
controls.

On Windows (PowerShell), do the equivalent manually:

```powershell
python -m venv venv
venv\Scripts\activate
pip install --upgrade pip
pip install playwright anthropic google-generativeai
playwright install chromium
```

## 2. Set your LLM API key

```bash
# macOS/Linux
export ANTHROPIC_API_KEY="sk-ant-..."
# or, to use Gemini instead:
export LLM_BACKEND=gemini
export GEMINI_API_KEY="..."
```

```powershell
# Windows PowerShell
setx ANTHROPIC_API_KEY "sk-ant-..."
```

If no key is set or the API call fails, the script falls back to a static
list of rotating styles so it never hard-crashes on an LLM outage.

## 3. One-time manual login

```bash
python myntra_weekly_order.py --login-setup
```

A visible browser opens. Log into Myntra (mobile OTP) and save a default
delivery address, then press ENTER in the terminal. This session is saved
to `./myntra_user_data` and reused by all future automated runs — you
should not need to log in again unless the session expires.

## 4. Test a run manually

```bash
python myntra_weekly_order.py
```

Watch the browser. When it reaches the final payment screen it will print:

```
🚨 WEEKLY ORDER READY: Complete CAPTCHA/OTP on screen to place your 3 T-shirt order.
```

and wait up to 120 seconds for you to finish manually. It never submits
payment for you.

### What to check/fix if something breaks
Open the failing Myntra page in a normal browser tab, right-click the
relevant element → Inspect, and compare against the `SEL = {...}`
dictionary near the top of `myntra_weekly_order.py`. Update the matching
selector string. Common breakage points: search bar, filter chips, the
"ADD TO BAG" button, and the cart/checkout buttons.

---

## 5. Scheduling weekly runs

The script must run with a visible browser (`headless=False`) since it
needs you present for CAPTCHA/OTP — schedule it for a time you're likely
to be near your computer (e.g. Sunday 10 AM).

### macOS / Linux — cron

```bash
crontab -e
```

Add (adjust paths — use absolute paths, cron has a minimal environment):

```cron
# Run every Sunday at 10:00 AM
0 10 * * 0 cd /absolute/path/to/myntra_bot && /absolute/path/to/myntra_bot/venv/bin/python myntra_weekly_order.py >> /absolute/path/to/myntra_bot/run.log 2>&1
```

Note: cron jobs normally run without a graphical session attached. On
Linux, if the job errors with a display/X11 error, either run cron from a
logged-in desktop session, or use `launchd` (macOS) / a manually-run
scheduled reminder instead, since Playwright needs a real display for
`headless=False`.

### macOS — launchd (more reliable than cron for GUI apps)

Create `~/Library/LaunchAgents/com.myntrabot.weekly.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.myntrabot.weekly</string>
    <key>ProgramArguments</key>
    <array>
        <string>/absolute/path/to/myntra_bot/venv/bin/python</string>
        <string>/absolute/path/to/myntra_bot/myntra_weekly_order.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key><integer>0</integer>  <!-- Sunday -->
        <key>Hour</key><integer>10</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key><string>/absolute/path/to/myntra_bot/run.log</string>
    <key>StandardErrorPath</key><string>/absolute/path/to/myntra_bot/run.log</string>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.myntrabot.weekly.plist
```

### Windows — Task Scheduler

1. Open **Task Scheduler** → **Create Task**.
2. **General** tab: name it "Myntra Weekly Order"; check "Run only when
   user is logged on" (required, since a visible browser needs your
   desktop session).
3. **Triggers** tab → New → Weekly → Sunday → 10:00 AM.
4. **Actions** tab → New → Start a program:
   - Program/script: `C:\path\to\myntra_bot\venv\Scripts\python.exe`
   - Add arguments: `myntra_weekly_order.py`
   - Start in: `C:\path\to\myntra_bot`
5. Save. Test it once with **Run** in the Task Scheduler UI to confirm the
   browser opens and reaches the payment pause correctly.

---

## Files in this project

| File | Purpose |
|---|---|
| `myntra_weekly_order.py` | Main script (setup, AI stylist, search/cart, checkout, human pause) |
| `install_dependencies.sh` | One-time environment setup |
| `requirements.txt` | Python package list |
| `purchased_history.json` | Auto-generated log of past weekly search terms (avoids repeats) |
| `myntra_user_data/` | Auto-generated persistent browser profile (your saved login) |
| `screenshots/` | Auto-saved screenshots of add-to-bag and final review screens |
# myntra-bot
