import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from google_calendar import GoogleCalendarClient

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def client():
    c = GoogleCalendarClient("school-assistant/google-calendar")
    mock_service = MagicMock()
    mock_service.events().list().execute.return_value = fixture("calendar_events.json")
    c._service = mock_service
    return c


def test_returns_all_events(client):
    events = client.get_today_events(date(2026, 5, 20))
    assert len(events) == 3


def test_all_day_flag(client):
    events = client.get_today_events(date(2026, 5, 20))
    by_name = {e.summary: e for e in events}
    assert by_name["Put bins out"].all_day is True
    assert by_name["Alice football training"].all_day is False
    assert by_name["Bob dentist"].all_day is False


def test_event_fields(client):
    events = client.get_today_events(date(2026, 5, 20))
    football = next(e for e in events if e.summary == "Alice football training")
    assert football.start == "2026-05-20T16:00:00Z"
    assert football.description == "At the rec ground, remember boots"
