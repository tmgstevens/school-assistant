import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from zoneinfo import ZoneInfo

import boto3

from cache import BriefingCache
from classcharts import ClassChartsClient
from claude_client import ClaudeClient
from google_calendar import GoogleCalendarClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def _pupil_names() -> list[str]:
    raw = os.environ.get("PUPIL_NAMES", "")
    return [n.strip() for n in raw.split(",") if n.strip()]


def _get_secret(name: str) -> dict:
    sm = boto3.client("secretsmanager")
    return json.loads(sm.get_secret_value(SecretId=name)["SecretString"])


def _get_prompt() -> str:
    param_name = os.environ.get("PROMPT_PARAMETER_NAME")
    if not param_name:
        from claude_client import BRIEFING_PROMPT
        return BRIEFING_PROMPT
    ssm = boto3.client("ssm")
    return ssm.get_parameter(Name=param_name)["Parameter"]["Value"]


def _uk_now():
    from datetime import datetime
    return datetime.now(ZoneInfo("Europe/London"))

def _briefing_date(now) -> date:
    from datetime import timedelta
    if now.hour >= 15:
        return now.date() + timedelta(days=1)
    return now.date()


_NOOP_RESPONSE = {"version": "1.0", "response": {"shouldEndSession": True}}


def _is_school_day(school_data: dict) -> bool:
    return bool(school_data.get("timetable")) or bool(school_data.get("homework"))


def _fetch_school_data(today: date):
    cc_secret = _get_secret(os.environ["CLASSCHARTS_SECRET_NAME"])
    cc = ClassChartsClient(cc_secret["email"], cc_secret["password"])
    return cc.fetch_all(_pupil_names(), today)


def _fetch_calendar(secret_name: str, today: date):
    cal = GoogleCalendarClient(secret_name)
    cal.connect()
    return cal.get_today_events(today)


def _build_briefing(today: date, now) -> str | None:
    errors = []
    school_data: dict = {}
    events = []

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_cc  = pool.submit(_fetch_school_data, today)
        fut_cal = pool.submit(_fetch_calendar, os.environ["GOOGLE_CALENDAR_SECRET_NAME"], today)

        try:
            school_data = fut_cc.result()
        except Exception:
            logger.exception("ClassCharts fetch failed")
            errors.append("School data unavailable — could not reach ClassCharts. Ask the administrator to check the logs.")

        try:
            events = fut_cal.result()
        except Exception:
            logger.exception("Google Calendar fetch failed")
            errors.append("Calendar data unavailable — could not reach Google Calendar. Ask the administrator to check the logs.")

    if not errors and not _is_school_day(school_data):
        logger.info("No school today — returning noop")
        return None

    combined = {
        **school_data,
        "calendar_events": [
            {
                "summary": e.summary,
                "start": e.start,
                "end": e.end,
                "description": e.description,
                "all_day": e.all_day,
                "attendees": e.attendees,
            }
            for e in events
        ],
        **({"errors": errors} if errors else {}),
    }

    anthropic_secret = _get_secret(os.environ["ANTHROPIC_SECRET_NAME"])
    claude = ClaudeClient(api_key=anthropic_secret["api_key"])
    return claude.synthesise_briefing(combined, today, now=now, prompt_template=_get_prompt())


def _get_family_context() -> str:
    param_name = os.environ.get("FAMILY_CONTEXT_PARAMETER_NAME")
    if not param_name:
        return ""
    ssm = boto3.client("ssm")
    return ssm.get_parameter(Name=param_name)["Parameter"]["Value"]


def _fetch_school_range(from_date: date, to_date: date):
    cc_secret = _get_secret(os.environ["CLASSCHARTS_SECRET_NAME"])
    cc = ClassChartsClient(cc_secret["email"], cc_secret["password"])
    return cc.fetch_range(_pupil_names(), from_date, to_date)


def _fetch_calendar_range(secret_name: str, from_date: date, to_date: date):
    cal = GoogleCalendarClient(secret_name)
    cal.connect()
    return cal.get_events_range(from_date, to_date)


def _handle_query(query: str, now) -> str:
    from_date = now.date()
    to_date = from_date + timedelta(days=7)
    cal_secret = os.environ["GOOGLE_CALENDAR_SECRET_NAME"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_cc  = pool.submit(_fetch_school_range, from_date, to_date)
        fut_cal = pool.submit(_fetch_calendar_range, cal_secret, from_date, to_date)

        try:
            school_data = fut_cc.result()
        except Exception:
            logger.exception("ClassCharts fetch failed for query")
            return "Sorry, I couldn't reach the school system right now. Please try again later."

        try:
            calendar_events = fut_cal.result()
        except Exception:
            logger.exception("Google Calendar fetch failed for query")
            calendar_events = []

    combined = {
        **school_data,
        "calendar_events": [
            {
                "summary": e.summary,
                "start": e.start,
                "end": e.end,
                "description": e.description,
                "all_day": e.all_day,
                "attendees": e.attendees,
            }
            for e in calendar_events
        ],
    }

    anthropic_secret = _get_secret(os.environ["ANTHROPIC_SECRET_NAME"])
    claude = ClaudeClient(api_key=anthropic_secret["api_key"])
    return claude.answer_query(query, combined, now, family_context=_get_family_context())


def lambda_handler(event: dict, context) -> dict:
    logger.info("Received event: %s", json.dumps(event))

    request_type = event.get("request", {}).get("type", "")
    if request_type == "SessionEndedRequest":
        return {"version": "1.0", "response": {}}

    now = _uk_now()

    if request_type == "IntentRequest":
        intent = event.get("request", {}).get("intent", {})
        query = intent.get("slots", {}).get("query", {}).get("value", "").strip()
        if not query:
            speech = "Sorry, I didn't catch that. Try asking something like: what homework does Bob have this week?"
        else:
            logger.info("Query: %s", query)
            speech = _handle_query(query, now)
        return {
            "version": "1.0",
            "response": {
                "outputSpeech": {"type": "SSML", "ssml": f"<speak>{speech}</speak>"},
                "shouldEndSession": True,
            },
        }

    today = _briefing_date(now)
    cache = BriefingCache()

    briefing = cache.get(today)
    if briefing:
        logger.info("Cache hit for %s", today)
    elif briefing is None:
        logger.info("Cache miss for %s — fetching live data", today)
        briefing = _build_briefing(today, now)
        if briefing is None:
            return _NOOP_RESPONSE
        cache.put(today, briefing)

    return {
        "version": "1.0",
        "response": {
            "outputSpeech": {
                "type": "SSML",
                "ssml": f"<speak>{briefing}</speak>",
            },
            "shouldEndSession": True,
        },
    }
