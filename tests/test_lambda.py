import os
from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

# All AWS and external clients are patched — no real network calls

INTENT_EVENT = {
    "request": {
        "type": "IntentRequest",
        "intent": {
            "name": "QueryIntent",
            "slots": {
                "query": {"value": "what homework does Alice have this week"}
            },
        },
    }
}

LAUNCH_EVENT = {"request": {"type": "LaunchRequest"}}

SCHOOL_DATA = {
    "homework": [{"subject": "Maths", "title": "Worksheet", "due_date": "2026-06-09", "pupil": "Alice Smith"}],
    "timetable": [{"subject": "English", "pupil": "Alice Smith"}],
    "announcements": [],
}

FIXED_NOW = datetime(2026, 6, 6, 8, 0, tzinfo=ZoneInfo("Europe/London"))

ENV = {
    "CLASSCHARTS_SECRET_NAME": "school-assistant/classcharts",
    "GOOGLE_CALENDAR_SECRET_NAME": "school-assistant/google-calendar",
    "ANTHROPIC_SECRET_NAME": "school-assistant/anthropic",
    "PROMPT_PARAMETER_NAME": "/school-assistant/briefing-prompt",
    "PUPIL_NAMES": "Alice,Bob",
}


def _make_mock_cc(data):
    cc = MagicMock()
    cc.fetch_range.return_value = data
    cc.fetch_all.return_value = data
    return cc


def _make_mock_cal(events=None):
    cal = MagicMock()
    cal.get_today_events.return_value = events or []
    return cal


def _fake_secret(name):
    if "classcharts" in name:
        return {"email": "test@example.com", "password": "pw"}
    if "google" in name:
        return {"client_id": "id", "client_secret": "secret", "refresh_token": "token"}
    return {"api_key": "fake"}


@patch.dict("os.environ", ENV)
@patch("lambda_function._uk_now", return_value=FIXED_NOW)
@patch("lambda_function._get_secret", side_effect=_fake_secret)
@patch("lambda_function.ClassChartsClient")
@patch("lambda_function.GoogleCalendarClient")
@patch("lambda_function.ClaudeClient")
@patch("lambda_function._get_family_context", return_value="The children are Alice and Bob.")
@patch("lambda_function._get_prompt", return_value="prompt: {briefing_date} {current_datetime} {data}")
@patch("lambda_function.BriefingCache")
def test_intent_request_returns_speech(
    mock_cache_cls, mock_prompt, mock_family_ctx,
    mock_claude_cls, mock_cal_cls, mock_cc_cls,
    mock_secret, mock_now,
):
    mock_cc_cls.return_value = _make_mock_cc(SCHOOL_DATA)
    mock_cal_cls.return_value = _make_mock_cal()
    mock_claude = MagicMock()
    mock_claude.answer_query.return_value = "Alice has a Maths worksheet due Monday."
    mock_claude_cls.return_value = mock_claude

    from lambda_function import lambda_handler
    response = lambda_handler(INTENT_EVENT, None)

    assert response["response"]["outputSpeech"]["ssml"] == "<speak>Alice has a Maths worksheet due Monday.</speak>"
    mock_claude.answer_query.assert_called_once()
    # confirm the query text was passed through
    call_args = mock_claude.answer_query.call_args
    assert "what homework does Alice have this week" in call_args.args[0]


@patch.dict("os.environ", ENV)
@patch("lambda_function._uk_now", return_value=FIXED_NOW)
@patch("lambda_function._get_secret", side_effect=_fake_secret)
@patch("lambda_function.ClassChartsClient")
@patch("lambda_function.GoogleCalendarClient")
@patch("lambda_function.ClaudeClient")
@patch("lambda_function._get_family_context", return_value="")
@patch("lambda_function._get_prompt", return_value="prompt: {briefing_date} {current_datetime} {data}")
@patch("lambda_function.BriefingCache")
def test_intent_request_empty_query_returns_help(
    mock_cache_cls, mock_prompt, mock_family_ctx,
    mock_claude_cls, mock_cal_cls, mock_cc_cls,
    mock_secret, mock_now,
):
    event = {
        "request": {
            "type": "IntentRequest",
            "intent": {"name": "QueryIntent", "slots": {"query": {"value": ""}}},
        }
    }
    mock_cc_cls.return_value = _make_mock_cc(SCHOOL_DATA)
    mock_cal_cls.return_value = _make_mock_cal()
    mock_claude_cls.return_value = MagicMock()

    from lambda_function import lambda_handler
    response = lambda_handler(event, None)

    ssml = response["response"]["outputSpeech"]["ssml"]
    assert "didn't catch that" in ssml


@patch("lambda_function._uk_now", return_value=FIXED_NOW)
def test_session_ended_returns_empty(mock_now):
    from lambda_function import lambda_handler
    response = lambda_handler({"request": {"type": "SessionEndedRequest"}}, None)
    assert response == {"version": "1.0", "response": {}}


@patch.dict("os.environ", ENV)
@patch("lambda_function._uk_now", return_value=FIXED_NOW)
@patch("lambda_function._get_secret", side_effect=_fake_secret)
@patch("lambda_function.ClassChartsClient")
@patch("lambda_function.GoogleCalendarClient")
@patch("lambda_function.ClaudeClient")
@patch("lambda_function._get_prompt", return_value="prompt: {briefing_date} {current_datetime} {data}")
@patch("lambda_function.BriefingCache")
def test_launch_request_uses_cache(
    mock_cache_cls, mock_prompt,
    mock_claude_cls, mock_cal_cls, mock_cc_cls,
    mock_secret, mock_now,
):
    mock_cache = MagicMock()
    mock_cache.get.return_value = "Good morning! Cached briefing."
    mock_cache_cls.return_value = mock_cache

    from lambda_function import lambda_handler
    response = lambda_handler(LAUNCH_EVENT, None)

    assert "Cached briefing" in response["response"]["outputSpeech"]["ssml"]
    mock_cc_cls.assert_not_called()
