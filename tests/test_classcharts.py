import json
from datetime import date
from pathlib import Path

import pytest
import responses as resp

from classcharts import ClassChartsClient, ClassChartsError, Pupil

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "https://www.classcharts.com/apiv2parent"
SITE_URL = "https://www.classcharts.com/mobile/parent"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def client():
    return ClassChartsClient("test@example.com", "testpassword")


@resp.activate
def test_login_sets_session_id(client):
    resp.add(resp.GET, SITE_URL, body="")
    resp.add(resp.POST, f"{BASE}/login", json=fixture("classcharts_login.json"))
    client.login()
    assert client._session_id == "test_session_abc123"


@resp.activate
def test_login_raises_on_failure(client):
    resp.add(resp.GET, SITE_URL, body="")
    resp.add(resp.POST, f"{BASE}/login", json={"success": 0, "error": "Invalid credentials"})
    with pytest.raises(ClassChartsError, match="Invalid credentials"):
        client.login()


@resp.activate
def test_get_pupils(client):
    resp.add(resp.GET, SITE_URL, body="")
    resp.add(resp.POST, f"{BASE}/login", json=fixture("classcharts_login.json"))
    resp.add(resp.GET, f"{BASE}/pupils", json=fixture("classcharts_pupils.json"))
    client.login()
    pupils = client.get_pupils()
    assert len(pupils) == 2
    assert pupils[0].name == "Alice Smith"
    assert pupils[1].name == "Bob Smith"


@resp.activate
def test_get_homework_returns_due_items(client):
    resp.add(resp.GET, SITE_URL, body="")
    resp.add(resp.POST, f"{BASE}/login", json=fixture("classcharts_login.json"))
    resp.add(resp.GET, f"{BASE}/homeworks/11111", json=fixture("classcharts_homework.json"))
    client.login()
    hw = client.get_homework(Pupil(id=11111, name="Alice Smith"), date(2026, 5, 20))
    assert len(hw) == 1
    assert hw[0].subject == "Mathematics"
    assert hw[0].pupil_name == "Alice Smith"


@resp.activate
def test_timetable_includes_pe(client):
    resp.add(resp.GET, SITE_URL, body="")
    resp.add(resp.POST, f"{BASE}/login", json=fixture("classcharts_login.json"))
    resp.add(resp.GET, f"{BASE}/timetable/11111", json=fixture("classcharts_timetable.json"))
    client.login()
    lessons = client.get_timetable(Pupil(id=11111, name="Alice Smith"), date(2026, 5, 20))
    subjects = [l.subject for l in lessons]
    assert "PE" in subjects
    assert len(lessons) == 3


@resp.activate
def test_get_announcements(client):
    resp.add(resp.GET, SITE_URL, body="")
    resp.add(resp.POST, f"{BASE}/login", json=fixture("classcharts_login.json"))
    resp.add(resp.GET, f"{BASE}/announcements/11111", json=fixture("classcharts_announcements.json"))
    client.login()
    anns = client.get_announcements(Pupil(id=11111, name="Alice Smith"))
    assert len(anns) == 1
    assert "London" in anns[0].title
    assert anns[0].pupil_name == "Alice Smith"


@resp.activate
def test_fetch_all_filters_by_pupil_name(client):
    resp.add(resp.GET, SITE_URL, body="")
    resp.add(resp.POST, f"{BASE}/login", json=fixture("classcharts_login.json"))
    resp.add(resp.GET, f"{BASE}/pupils", json=fixture("classcharts_pupils.json"))
    resp.add(resp.GET, f"{BASE}/homeworks/11111", json=fixture("classcharts_homework.json"))
    resp.add(resp.GET, f"{BASE}/timetable/11111", json=fixture("classcharts_timetable.json"))
    resp.add(resp.GET, f"{BASE}/announcements/11111", json=fixture("classcharts_announcements.json"))

    result = client.fetch_all(["Alice"], date(2026, 5, 20))
    assert all(h["pupil"] == "Alice Smith" for h in result["homework"])
    assert all(l["pupil"] == "Alice Smith" for l in result["timetable"])
