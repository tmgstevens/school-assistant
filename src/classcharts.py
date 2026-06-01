import json
import re
import urllib.parse
from dataclasses import dataclass
from datetime import date, datetime, timezone, timedelta
from typing import Optional

import requests

SITE_URL = "https://www.classcharts.com/mobile/parent"
ANNOUNCEMENT_DAYS = 14  # ignore announcements older than this


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
LOGIN_URL = "https://www.classcharts.com/apiv2parent/login"
BASE_URL = "https://www.classcharts.com/apiv2parent"

_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}


@dataclass
class Pupil:
    id: int
    name: str


@dataclass
class Homework:
    subject: str
    title: str
    description: str
    due_date: str
    pupil_name: str


@dataclass
class Lesson:
    subject: str
    teacher: str
    room: str
    period_name: str
    start_time: str
    end_time: str
    pupil_name: str


@dataclass
class Announcement:
    title: str
    description: str
    timestamp: str
    pupil_name: str


class ClassChartsError(Exception):
    pass


class ClassChartsClient:
    def __init__(self, email: str, password: str):
        self._email = email
        self._password = password
        self._session_id: Optional[str] = None
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)

    def login(self) -> None:
        # Fetch the portal page first to pick up the cc-session PHP cookie
        self._session.get(SITE_URL, timeout=10)

        response = self._session.post(
            LOGIN_URL,
            data={
                "email": self._email,
                "password": self._password,
                "remember_me": 1,
                "_method": "POST",
            },
        )
        response.raise_for_status()
        body = response.json()
        if not body.get("success"):
            raise ClassChartsError(f"Login failed: {body.get('error', 'unknown error')}")
        self._session_id = body["meta"]["session_id"]
        # Session ID is passed raw (not base64 encoded)
        self._session.headers.update({"Authorization": f"Basic {self._session_id}"})
        # This cookie is normally set by the web app's JS after login
        cred = json.dumps({"remember_me": False, "session_id": self._session_id})
        self._session.cookies.set("parent_session_credentials", urllib.parse.quote(cred))

    def get_pupils(self) -> list[Pupil]:
        response = self._session.get(f"{BASE_URL}/pupils")
        response.raise_for_status()
        return [
            Pupil(id=p["id"], name=p["name"])
            for p in response.json().get("data", [])
        ]

    def get_homework(self, pupil: Pupil, for_date: date) -> list[Homework]:
        date_str = for_date.strftime("%Y-%m-%d")
        response = self._session.get(
            f"{BASE_URL}/homeworks/{pupil.id}",
            params={"display_date": "due_date", "from": date_str, "to": date_str},
        )
        response.raise_for_status()
        return [
            Homework(
                subject=hw.get("subject", "Unknown"),
                title=hw.get("title", ""),
                description=hw.get("description", ""),
                due_date=hw.get("due_date", date_str),
                pupil_name=pupil.name,
            )
            for hw in response.json().get("data", {}).get("due", [])
        ]

    def get_timetable(self, pupil: Pupil, for_date: date) -> list[Lesson]:
        response = self._session.get(
            f"{BASE_URL}/timetable/{pupil.id}",
            params={"date": for_date.strftime("%Y-%m-%d")},
        )
        response.raise_for_status()
        return [
            Lesson(
                subject=lesson.get("subject_name", ""),
                teacher=lesson.get("teacher_name", ""),
                room=lesson.get("room_name", ""),
                period_name=lesson.get("period_name", ""),
                start_time=lesson.get("start_time", ""),
                end_time=lesson.get("end_time", ""),
                pupil_name=pupil.name,
            )
            for lesson in response.json().get("data", [])
        ]

    def get_announcements(self, pupil: Pupil) -> list[Announcement]:
        response = self._session.get(f"{BASE_URL}/announcements/{pupil.id}")
        response.raise_for_status()
        return [
            Announcement(
                title=ann.get("title", ""),
                description=ann.get("description", ""),
                timestamp=ann.get("timestamp", ann.get("created_date", "")),
                pupil_name=pupil.name,
            )
            for ann in response.json().get("data", [])
        ]

    def fetch_all(self, pupil_names: list[str], for_date: date) -> dict:
        self.login()
        all_pupils = self.get_pupils()
        pupils = [
            p for p in all_pupils
            if any(name.lower() in p.name.lower() for name in pupil_names)
        ] if pupil_names else all_pupils

        result: dict = {"homework": [], "timetable": [], "announcements": []}
        for pupil in pupils:
            result["homework"] += [
                {"subject": h.subject, "title": h.title,
                 "description": _strip_html(h.description),
                 "due_date": h.due_date, "pupil": h.pupil_name}
                for h in self.get_homework(pupil, for_date)
            ]
            # Deduplicate consecutive slots for the same subject (each lesson appears once per 30-min slot)
            seen: set = set()
            for l in self.get_timetable(pupil, for_date):
                key = (l.pupil_name, l.subject)
                if key not in seen:
                    seen.add(key)
                    result["timetable"].append(
                        {"subject": l.subject, "teacher": l.teacher, "room": l.room,
                         "start": l.start_time, "pupil": l.pupil_name}
                    )
            cutoff = datetime.now() - timedelta(days=ANNOUNCEMENT_DAYS)
            for a in self.get_announcements(pupil):
                try:
                    ts = datetime.fromisoformat(a.timestamp.replace("Z", ""))
                    if ts < cutoff:
                        continue
                except (ValueError, AttributeError):
                    pass
                result["announcements"].append({
                    "title": a.title,
                    "description": _strip_html(a.description),
                    "pupil": a.pupil_name,
                })
        return result
