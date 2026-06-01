import json
import logging
import os
from datetime import date
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


def _build_briefing(today: date, now) -> str | None:
    errors = []

    try:
        cc_secret = _get_secret(os.environ["CLASSCHARTS_SECRET_NAME"])
        cc = ClassChartsClient(cc_secret["email"], cc_secret["password"])
        school_data = cc.fetch_all(_pupil_names(), today)
    except Exception:
        logger.exception("ClassCharts fetch failed")
        errors.append("School data unavailable — could not reach ClassCharts. Ask the administrator to check the logs.")
        school_data = {}

    if not errors and not _is_school_day(school_data):
        logger.info("No school today — returning noop")
        return None

    try:
        cal = GoogleCalendarClient(os.environ["GOOGLE_CALENDAR_SECRET_NAME"])
        cal.connect()
        events = cal.get_today_events(today)
    except Exception:
        logger.exception("Google Calendar fetch failed")
        errors.append("Calendar data unavailable — could not reach Google Calendar. Ask the administrator to check the logs.")
        events = []

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


def lambda_handler(event: dict, context) -> dict:
    logger.info("Received event: %s", json.dumps(event))

    request_type = event.get("request", {}).get("type", "")
    if request_type == "SessionEndedRequest":
        return {"version": "1.0", "response": {}}

    now = _uk_now()
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
