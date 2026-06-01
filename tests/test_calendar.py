import json
from datetime import date
from pathlib import Path

import pytest
import responses as resp

from google_calendar import GoogleCalendarClient

FIXTURES = Path(__file__).parent / "fixtures"
CALENDAR_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def client():
    c = GoogleCalendarClient("school-assistant/google-calendar")
    c._access_token = "fake-token"
    return c


@resp.activate
def test_returns_all_events(client):
    resp.add(resp.GET, CALENDAR_URL, json=fixture("calendar_events.json"))
    events = client.get_today_events(date(2026, 5, 20))
    assert len(events) == 3


@resp.activate
def test_all_day_flag(client):
    resp.add(resp.GET, CALENDAR_URL, json=fixture("calendar_events.json"))
    events = client.get_today_events(date(2026, 5, 20))
    by_name = {e.summary: e for e in events}
    assert by_name["Put bins out"].all_day is True
    assert by_name["Alice football training"].all_day is False
    assert by_name["Bob dentist"].all_day is False


@resp.activate
def test_event_fields(client):
    resp.add(resp.GET, CALENDAR_URL, json=fixture("calendar_events.json"))
    events = client.get_today_events(date(2026, 5, 20))
    football = next(e for e in events if e.summary == "Alice football training")
    assert football.start == "2026-05-20T16:00:00Z"
    assert football.description == "At the rec ground, remember boots"
    assert football.attendees == []


@resp.activate
def test_attendees_populated(client):
    data = fixture("calendar_events.json")
    data["items"][0]["attendees"] = [
        {"email": "child@gmail.com"},
        {"email": "parent@gmail.com", "self": True},
    ]
    resp.add(resp.GET, CALENDAR_URL, json=data)
    events = client.get_today_events(date(2026, 5, 20))
    football = next(e for e in events if e.summary == "Alice football training")
    assert football.attendees == ["child@gmail.com"]
