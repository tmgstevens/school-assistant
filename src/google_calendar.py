import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

import boto3
import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"
CALENDAR_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


@dataclass
class CalendarEvent:
    summary: str
    start: str
    end: str
    description: Optional[str]
    all_day: bool
    attendees: list[str]


class GoogleCalendarClient:
    def __init__(self, secret_name: str):
        self._secret_name = secret_name
        self._access_token: Optional[str] = None

    def connect(self) -> None:
        sm = boto3.client("secretsmanager")
        secret = json.loads(sm.get_secret_value(SecretId=self._secret_name)["SecretString"])
        resp = requests.post(TOKEN_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": secret["refresh_token"],
            "client_id": secret["client_id"],
            "client_secret": secret["client_secret"],
        }, timeout=10)
        resp.raise_for_status()
        self._access_token = resp.json()["access_token"]

    def _fetch_events(self, time_min: str, time_max: str) -> list[CalendarEvent]:
        resp = requests.get(CALENDAR_URL, headers={
            "Authorization": f"Bearer {self._access_token}",
        }, params={
            "timeMin": time_min,
            "timeMax": time_max,
            "singleEvents": "true",
            "orderBy": "startTime",
        }, timeout=10)
        resp.raise_for_status()
        events = []
        for item in resp.json().get("items", []):
            all_day = "date" in item["start"] and "dateTime" not in item["start"]
            attendees = [a["email"] for a in item.get("attendees", []) if not a.get("self")]
            events.append(CalendarEvent(
                summary=item.get("summary", ""),
                start=item["start"].get("dateTime") or item["start"].get("date", ""),
                end=item["end"].get("dateTime") or item["end"].get("date", ""),
                description=item.get("description"),
                all_day=all_day,
                attendees=attendees,
            ))
        return events

    def get_today_events(self, for_date: date) -> list[CalendarEvent]:
        time_min = datetime(for_date.year, for_date.month, for_date.day,
                            0, 0, 0, tzinfo=timezone.utc).isoformat()
        time_max = datetime(for_date.year, for_date.month, for_date.day,
                            23, 59, 59, tzinfo=timezone.utc).isoformat()
        return self._fetch_events(time_min, time_max)

    def get_events_range(self, from_date: date, to_date: date) -> list[CalendarEvent]:
        time_min = datetime(from_date.year, from_date.month, from_date.day,
                            0, 0, 0, tzinfo=timezone.utc).isoformat()
        time_max = datetime(to_date.year, to_date.month, to_date.day,
                            23, 59, 59, tzinfo=timezone.utc).isoformat()
        return self._fetch_events(time_min, time_max)
