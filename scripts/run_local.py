#!/usr/bin/env python3
"""
Local runner for testing with real data before deploying to Lambda.

Reads credentials from .env (see .env.example), calls each module in sequence,
and prints the raw data from each step followed by the final briefing.

Usage:
    pip install -r requirements-dev.txt
    python scripts/run_local.py
    python scripts/run_local.py --date 2026-05-21   # test a specific date
    python scripts/run_local.py --skip-calendar      # skip Google Calendar
    python scripts/run_local.py --skip-claude        # print raw data only
"""

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

# Allow importing from src/ without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

load_dotenv(Path(__file__).parent.parent / ".env")


def section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Date to query (YYYY-MM-DD), defaults to today")
    parser.add_argument("--skip-calendar", action="store_true")
    parser.add_argument("--skip-claude", action="store_true")
    args = parser.parse_args()

    target_date = (
        datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else date.today()
    )
    pupil_names = [n.strip() for n in os.environ.get("PUPIL_NAMES", "").split(",") if n.strip()]

    print(f"\nSchool Assistant — local run for {target_date.strftime('%A %d %B %Y')}")
    print(f"Pupils: {', '.join(pupil_names)}")

    combined: dict = {}

    # ── ClassCharts ───────────────────────────────────────────────────────────
    section("ClassCharts")
    from classcharts import ClassChartsClient

    email = os.environ["CLASSCHARTS_EMAIL"]
    password = os.environ["CLASSCHARTS_PASSWORD"]

    cc = ClassChartsClient(email, password)
    school_data = cc.fetch_all(pupil_names, target_date)
    combined.update(school_data)

    print(f"\nHomework due ({len(school_data['homework'])} items):")
    for hw in school_data["homework"]:
        print(f"  [{hw['pupil']}] {hw['subject']} — {hw['title']}")

    print(f"\nTimetable ({len(school_data['timetable'])} lessons):")
    for lesson in school_data["timetable"]:
        print(f"  [{lesson['pupil']}] {lesson['start']} {lesson['subject']} ({lesson['room']})")

    print(f"\nAnnouncements ({len(school_data['announcements'])} items):")
    for ann in school_data["announcements"]:
        print(f"  [{ann['pupil']}] {ann['title']}")

    # ── Google Calendar ───────────────────────────────────────────────────────
    if not args.skip_calendar:
        section("Google Calendar")
        import requests as _req
        from google_calendar import GoogleCalendarClient

        token_resp = _req.post("https://oauth2.googleapis.com/token", data={
            "grant_type": "refresh_token",
            "refresh_token": os.environ["GOOGLE_REFRESH_TOKEN"],
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
        }, timeout=10)
        token_resp.raise_for_status()

        cal = GoogleCalendarClient.__new__(GoogleCalendarClient)
        cal._access_token = token_resp.json()["access_token"]

        events = cal.get_today_events(target_date)
        combined["calendar_events"] = [
            {"summary": e.summary, "start": e.start, "end": e.end,
             "description": e.description, "all_day": e.all_day}
            for e in events
        ]

        print(f"\nEvents ({len(events)} items):")
        for e in events:
            tag = "[all-day]" if e.all_day else f"[{e.start}]"
            print(f"  {tag} {e.summary}")
    else:
        combined["calendar_events"] = []
        print("\n(skipped)")

    # ── Raw data dump ─────────────────────────────────────────────────────────
    section("Combined data sent to Claude")
    print(json.dumps(combined, indent=2, default=str))

    # ── Claude synthesis ──────────────────────────────────────────────────────
    if not args.skip_claude:
        section("Claude briefing")
        from claude_client import ClaudeClient

        claude = ClaudeClient(api_key=os.environ["ANTHROPIC_API_KEY"])
        briefing = claude.synthesise_briefing(combined, target_date)
        print(f"\n{briefing}\n")
    else:
        print("\n(skipped — run without --skip-claude to see Claude output)")


if __name__ == "__main__":
    main()
