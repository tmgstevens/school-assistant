"""Fixed scenarios for the briefing LLM evals.

Each scenario supplies the exact `data` dict that `_build_briefing` would hand
to `ClaudeClient.synthesise_briefing` (homework/timetable/announcements from
ClassCharts + calendar_events from Google Calendar) — ClassCharts and Calendar
are never called; only the Claude side is real. Child names follow the
Alice/Bob convention already used elsewhere in this codebase (claude_client.py
fallback prompt, test fixtures).
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

FAMILY_CONTEXT = """The children are Alice and Bob.

  Calendar attendee emails:
  - Alice: alice@example.com
  - Bob: bob@example.com
  - Parent account (ignore): parent@example.com"""


@dataclass
class Scenario:
    name: str
    description: str
    briefing_date: date
    now: datetime
    data: dict
    # Each entry is a phrase, or a tuple of alternative phrasings where any one counts.
    must_mention: list = field(default_factory=list)
    must_not_mention: list[str] = field(default_factory=list)


_TUE = date(2026, 10, 13)
_WED = date(2026, 10, 14)

# First Monday on/after _TUE — computed rather than hand-picked so the rule
# ("include on Mondays as a weekly reminder") is actually exercised correctly.
_MONDAY = _TUE + timedelta(days=(7 - _TUE.weekday()) % 7 or 7)
assert _MONDAY.weekday() == 0

SCENARIOS = [
    Scenario(
        name="normal_day_pe_core_kit_and_announcement",
        description=(
            "Baseline day: PE/CORE lesson (kit required), homework due, a timely "
            "money-due announcement, and after-school clutter that should be ignored."
        ),
        briefing_date=_TUE,
        now=datetime(2026, 10, 13, 7, 30),
        data={
            "homework": [
                {"subject": "Mathematics", "title": "Algebra worksheet",
                 "description": "Complete exercises 1-10", "due_date": "2026-10-13",
                 "pupil": "Alice"},
            ],
            "timetable": [
                {"subject": "PE/CORE", "teacher": "Mr Davies", "room": "Sports Hall",
                 "start": "11:00", "pupil": "Alice"},
                {"subject": "English", "teacher": "Ms Johnson", "room": "Room 12",
                 "start": "09:00", "pupil": "Bob"},
            ],
            "announcements": [
                {"title": "School Trip to London — Science Museum",
                 "description": "Permission slip and £15 payment due by Friday 16th "
                                 "October. Please return to form tutor.",
                 "pupil": "Alice", "timestamp": "2026-10-13 08:00:00+00:00"},
            ],
            "calendar_events": [
                {"summary": "Alice football training", "start": "2026-10-13T16:00:00Z",
                 "end": "2026-10-13T17:30:00Z", "description": "At the rec ground, remember boots",
                 "all_day": False, "attendees": []},
                {"summary": "Cake rota — Bob's class", "start": "2026-10-13",
                 "end": "2026-10-14", "description": "", "all_day": True, "attendees": []},
                {"summary": "Ring plumber about leak", "start": "2026-10-13",
                 "end": "2026-10-14", "description": "", "all_day": True, "attendees": []},
            ],
        },
        must_mention=["alice", "kit", "football"],
        must_not_mention=["cake", "plumber"],
    ),
    Scenario(
        name="pe_games_does_not_need_kit",
        description=(
            "PE/GAMES is a classroom theory lesson, not practical PE — must not be "
            "flagged as needing kit, and shouldn't be mentioned at all with no homework/announcement."
        ),
        briefing_date=_WED,
        now=datetime(2026, 10, 14, 7, 30),
        data={
            "homework": [],
            "timetable": [
                {"subject": "PE/GAMES", "teacher": "Mr Davies", "room": "Classroom 4",
                 "start": "13:00", "pupil": "Bob"},
            ],
            "announcements": [],
            "calendar_events": [],
        },
        must_not_mention=["kit"],
    ),
    Scenario(
        name="stale_announcement_suppressed",
        description=(
            "An announcement about a now-irrelevant past event, posted weeks ago with "
            "no upcoming deadline, should be skipped rather than padding the briefing."
        ),
        briefing_date=_WED,
        now=datetime(2026, 10, 14, 7, 30),
        data={
            "homework": [],
            "timetable": [],
            "announcements": [
                {"title": "Autumn Fair — Change of Date",
                 "description": "The Autumn Fair originally planned for this Saturday has "
                                 "been moved to next month due to the weather forecast.",
                 "pupil": "Alice", "timestamp": "2026-09-24 09:00:00+00:00"},
            ],
            "calendar_events": [],
        },
        must_not_mention=["autumn fair", "fair"],
    ),
    Scenario(
        name="monday_resurfaces_old_announcement",
        description=(
            "The weekly-reminder rule says announcements resurface on Mondays "
            "regardless of posting date — this one is 10 days old."
        ),
        briefing_date=_MONDAY,
        now=datetime(_MONDAY.year, _MONDAY.month, _MONDAY.day, 7, 30),
        data={
            "homework": [],
            "timetable": [],
            "announcements": [
                {"title": "Spanish Trip — Final Payment",
                 "description": "Final payment of £45 for the Spain trip was due last "
                                 "Friday. If you haven't yet paid via ParentPay please do so.",
                 "pupil": "Alice",
                 "timestamp": f"{_MONDAY - timedelta(days=10)} 09:00:00+00:00"},
            ],
            "calendar_events": [],
        },
        must_mention=[("spain", "spanish")],
    ),
    Scenario(
        name="multi_kid_correct_attribution",
        description=(
            "Both kids have homework and an evening activity on the same day — each "
            "item must land on the right child, not get crossed over."
        ),
        briefing_date=_WED,
        now=datetime(2026, 10, 14, 7, 30),
        data={
            "homework": [
                {"subject": "Mathematics", "title": "Algebra worksheet",
                 "description": "Exercises 1-10", "due_date": "2026-10-14", "pupil": "Alice"},
                {"subject": "English", "title": "Essay on To Kill a Mockingbird",
                 "description": "750 words", "due_date": "2026-10-14", "pupil": "Bob"},
            ],
            "timetable": [],
            "announcements": [],
            "calendar_events": [
                {"summary": "Alice — Netball v Corsham", "start": "2026-10-14T16:00:00Z",
                 "end": "2026-10-14T17:30:00Z", "description": "Away fixture, meet at bus bays",
                 "all_day": False, "attendees": []},
                {"summary": "Bob — Chess Club", "start": "2026-10-14T15:30:00Z",
                 "end": "2026-10-14T16:30:00Z", "description": "", "all_day": False, "attendees": []},
            ],
        },
        must_mention=["alice", "algebra", "netball", "bob", "essay", "chess"],
    ),
    Scenario(
        name="ignore_personal_reminders",
        description=(
            "Adult personal-task reminders mixed into the calendar must be filtered "
            "out; the one genuine kid's activity must survive."
        ),
        briefing_date=_WED,
        now=datetime(2026, 10, 14, 7, 30),
        data={
            "homework": [],
            "timetable": [],
            "announcements": [],
            "calendar_events": [
                {"summary": "Ring dentist to rebook Alice's appointment", "start": "2026-10-14",
                 "end": "2026-10-15", "description": "", "all_day": True, "attendees": []},
                {"summary": "Pay window cleaner", "start": "2026-10-14",
                 "end": "2026-10-15", "description": "", "all_day": True, "attendees": []},
                {"summary": "Bob — Swimming lesson", "start": "2026-10-14T17:00:00Z",
                 "end": "2026-10-14T17:45:00Z", "description": "Bring goggles",
                 "all_day": False, "attendees": []},
            ],
        },
        must_mention=["swimming"],
        must_not_mention=["dentist", "window cleaner"],
    ),
    Scenario(
        name="noisy_day_recall_under_volume",
        description=(
            "A real actionable announcement and a real after-school activity are buried "
            "among a pile of stale/irrelevant announcements and personal-task calendar noise. "
            "Found via real production data that a smaller model can drop genuine items once "
            "volume goes up, even though it handles clean low-volume scenarios fine — this "
            "checks recall under volume, not just precision on a quiet day."
        ),
        briefing_date=_WED,
        now=datetime(2026, 10, 14, 7, 30),
        data={
            "homework": [],
            "timetable": [],
            "announcements": [
                {"title": "Year 9 Fitness Assessment — Kit Reminder",
                 "description": "Quick reminder that this Wednesday (14th) all Year 9 students "
                                 "need full PE kit and a change of clothes for the fitness "
                                 "assessment in period 5.",
                 "pupil": "Bob", "timestamp": f"{_WED - timedelta(days=4)} 08:00:00+00:00"},
                {"title": "PTA Autumn Newsletter",
                 "description": "Catch up on everything that's been happening around the school this term.",
                 "pupil": "Alice", "timestamp": f"{_WED - timedelta(days=14)} 09:00:00+00:00"},
                {"title": "Lost Property Collection Reminder",
                 "description": "Please collect any lost property from the office before it's donated to charity.",
                 "pupil": "Bob", "timestamp": f"{_WED - timedelta(days=10)} 09:00:00+00:00"},
                {"title": "Staff INSET Day Notice",
                 "description": "A reminder that INSET days for this academic year have been published on the website.",
                 "pupil": "Alice", "timestamp": f"{_WED - timedelta(days=21)} 09:00:00+00:00"},
                {"title": "School Photos Order Deadline — CLOSED",
                 "description": "The ordering window for individual school photos has now closed.",
                 "pupil": "Bob", "timestamp": f"{_WED - timedelta(days=20)} 09:00:00+00:00"},
                {"title": "Library Book Amnesty Week",
                 "description": "Return any overdue library books this week with no fine.",
                 "pupil": "Alice", "timestamp": f"{_WED - timedelta(days=7)} 09:00:00+00:00"},
                {"title": "Road Closure Near School Gates",
                 "description": "Be aware of temporary road works near the main gates this month.",
                 "pupil": "Bob", "timestamp": f"{_WED - timedelta(days=5)} 09:00:00+00:00"},
                {"title": "Summer Fair — Thank You",
                 "description": "Thanks to everyone who came along and supported the summer fair.",
                 "pupil": "Alice", "timestamp": f"{_WED - timedelta(days=30)} 09:00:00+00:00"},
            ],
            "calendar_events": [
                {"summary": "Bob — Sharks Swimming", "start": "2026-10-14T17:00:00Z",
                 "end": "2026-10-14T18:00:00Z", "description": "", "all_day": False, "attendees": []},
                {"summary": "Pay window cleaner", "start": "2026-10-14",
                 "end": "2026-10-15", "description": "", "all_day": True, "attendees": []},
                {"summary": "Chase plumber about boiler", "start": "2026-10-14",
                 "end": "2026-10-15", "description": "", "all_day": True, "attendees": []},
                {"summary": "England vs Portugal", "start": "2026-10-14",
                 "end": "2026-10-15", "description": "", "all_day": True, "attendees": []},
                {"summary": "Bin collection", "start": "2026-10-14",
                 "end": "2026-10-15", "description": "", "all_day": True, "attendees": []},
                {"summary": "Staff meeting — parents evening prep", "start": "2026-10-14",
                 "end": "2026-10-15", "description": "", "all_day": True, "attendees": []},
                {"summary": "Order new school shoes", "start": "2026-10-14",
                 "end": "2026-10-15", "description": "", "all_day": True, "attendees": []},
            ],
        },
        must_mention=["sharks", "fitness"],
        must_not_mention=["window cleaner", "newsletter", "lost property", "portugal", "inset"],
    ),
]
