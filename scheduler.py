"""
scheduler.py
============
Long-running loop for deployment as a Render Background Worker.

Render Cron Jobs can't attach a persistent Disk, so instead this process
stays alive and fires run_automation() itself on the same schedule as
.github/workflows/myntra_cron.yml (Mon/Wed/Fri 06:30 UTC = 12:00 PM IST),
tracking the last-run date on disk so a restart mid-day doesn't re-fire.
"""
import os
import time
import datetime
from pathlib import Path

from myntra_weekly_order import run_automation, BASE_DIR

STATE_FILE = Path(os.getenv("SCHEDULER_STATE_PATH", str(BASE_DIR / "scheduler_state.json")))
SCHEDULE_WEEKDAYS = {0, 2, 4}  # Mon, Wed, Fri
SCHEDULE_HOUR_UTC = 6
SCHEDULE_MINUTE_UTC = 30
POLL_SECONDS = 60


def load_last_run_date():
    if STATE_FILE.exists():
        return STATE_FILE.read_text().strip()
    return None


def save_last_run_date(date_str):
    STATE_FILE.write_text(date_str)


def main():
    print(
        f"Scheduler started. Watching for weekdays {sorted(SCHEDULE_WEEKDAYS)} "
        f"at {SCHEDULE_HOUR_UTC:02d}:{SCHEDULE_MINUTE_UTC:02d} UTC. "
        f"State file: {STATE_FILE}"
    )
    last_run = load_last_run_date()
    while True:
        now = datetime.datetime.now(datetime.timezone.utc)
        today_str = now.date().isoformat()
        if (
            now.weekday() in SCHEDULE_WEEKDAYS
            and now.hour == SCHEDULE_HOUR_UTC
            and now.minute == SCHEDULE_MINUTE_UTC
            and last_run != today_str
        ):
            print(f"[{now.isoformat()}] Triggering scheduled run.")
            try:
                run_automation()
            except Exception as e:
                print(f"[ERROR] run_automation() raised: {e}")
            last_run = today_str
            save_last_run_date(last_run)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
