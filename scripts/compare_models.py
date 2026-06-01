#!/usr/bin/env python3
"""Compare Claude and Gemini models for speed and output quality."""

import json
import os
import sys
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
load_dotenv(Path(__file__).parent.parent / ".env")

import anthropic
from classcharts import ClassChartsClient
from claude_client import BRIEFING_PROMPT
from google_calendar import GoogleCalendarClient
import requests as _req


def run_gemini(prompt: str, model: str) -> str:
    from google import genai
    client = genai.Client(api_key=os.environ["GOOGLE_AI_STUDIO_KEY"])
    response = client.models.generate_content(model=model, contents=prompt)
    return response.text.strip()


CLAUDE_MODELS = [
    "claude-opus-4-8",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
]

GEMINI_MODELS = [
    "gemini-3.1-flash-lite-preview",
    "gemma-4-26b-a4b-it",
    "gemma-4-31b-it",
]

print("Fetching data from ClassCharts and Google Calendar...")
t0 = time.time()

pupil_names = [n.strip() for n in os.environ.get("PUPIL_NAMES", "").split(",") if n.strip()]
target_date = date.today()

cc = ClassChartsClient(os.environ["CLASSCHARTS_EMAIL"], os.environ["CLASSCHARTS_PASSWORD"])
school_data = cc.fetch_all(pupil_names, target_date)

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

combined = {
    **school_data,
    "calendar_events": [
        {"summary": e.summary, "start": e.start, "end": e.end,
         "description": e.description, "all_day": e.all_day}
        for e in events
    ],
}

print(f"Data fetched in {time.time() - t0:.1f}s\n")

full_prompt = BRIEFING_PROMPT.format(
    date=target_date.strftime("%A %d %B %Y"),
    data=json.dumps(combined, indent=2, default=str),
)

claude_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

for model in CLAUDE_MODELS:
    t1 = time.time()
    message = claude_client.messages.create(
        model=model,
        max_tokens=512,
        messages=[{"role": "user", "content": full_prompt}],
    )
    elapsed = time.time() - t1
    result = message.content[0].text.strip()
    usage = message.usage
    print(f"{'─' * 60}")
    print(f"  {model}  ({elapsed:.2f}s)  in={usage.input_tokens} out={usage.output_tokens}")
    print(f"{'─' * 60}")
    print(result)
    print()

for model in GEMINI_MODELS:
    t1 = time.time()
    result = run_gemini(full_prompt, model)
    elapsed = time.time() - t1
    print(f"{'─' * 60}")
    print(f"  {model}  ({elapsed:.2f}s)")
    print(f"{'─' * 60}")
    print(result)
    print()
