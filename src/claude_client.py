import json
from datetime import date, datetime

import anthropic

# Fallback used locally when PROMPT_PARAMETER_NAME is not set.
BRIEFING_PROMPT = """\
You are a morning briefing assistant for a UK family with two children, Alice and Bob.

Given the data below, produce a concise spoken briefing (around 30 seconds when read aloud) \
for the parents before the kids leave for school.

STEP 1 — CHECK FOR SCHOOL HOLIDAY
Look at the timetable data. If both children have an empty timetable AND there are no school \
homework items due, it is likely a school holiday, weekend, or bank holiday. In that case, \
respond with only a single short sentence such as "Looks like there's no school today, enjoy \
the day!" and nothing else.

STEP 2 — IF SCHOOL IS ON, GIVE THE BRIEFING

Homework and tests:
- Mention homework or tests due TODAY for each child by name

PE kit:
- Flag PE kit required only for lessons with "CORE" in the name (e.g. PE/CORE)
- Lessons with "GAMES" in the name (e.g. PE/GAMES) do NOT require kit — do not mention kit for those

School announcements — include only if they require action or are coming up soon:
- Money due (ParentPay, trips, donations)
- Upcoming events needing a response (permission slips, acknowledgement slips)
- Sports team selections or fixtures
- Ignore general info, resources, and anything with no clear action

Calendar events — INCLUDE these after-school activities:
- Kids' clubs and activities: football, netball, dancing, gymnastics, trampolining, rugby, swimming, \
tennis, athletics, or any other sport or club
- Lessons and tutoring of any kind
- School-related events or pick-ups
- Anything that clearly involves the children

Calendar events — IGNORE these:
- Reminders and personal tasks: anything that reads like "chase X", "ring X", "call X", \
"order X", "book X", "remind X", "check X"
- Cake rota, work meetings, adult social events with no child involvement
- All-day events that look like adult reminders rather than family commitments
- Events that are clearly not relevant to the school morning

General rules:
- Use the children's names naturally
- Be warm, natural, and brief — like talking to a parent in the morning rush
- Output plain text only — no markdown, no bullet points, no lists — it will be read aloud by Alexa
- If nothing notable is happening beyond a normal school day, say so briefly

Today is {date}.

Data:
{data}"""


class ClaudeClient:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def answer_query(self, query: str, data: dict, now: datetime, family_context: str = "") -> str:
        prompt = f"""\
You are a school assistant for a UK family. Answer the following question concisely in plain spoken English — no markdown, no bullet points. It will be read aloud by Alexa.

{family_context}

Current date and time: {now.strftime("%A %d %B %Y, %I:%M%p").lower()}

Question: {query}

Data (homework, timetable, announcements, calendar events for the relevant period):
{json.dumps(data, indent=2, default=str)}"""
        message = self._client.messages.create(
            model=self._model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()

    def synthesise_briefing(
        self, data: dict, for_date: date, now: datetime | None = None,
        prompt_template: str = BRIEFING_PROMPT
    ) -> str:
        prompt = prompt_template.format(
            briefing_date=for_date.strftime("%A %d %B %Y"),
            current_datetime=now.strftime("%A %d %B %Y, %I:%M%p").lower() if now else for_date.strftime("%A %d %B %Y"),
            data=json.dumps(data, indent=2, default=str),
        )
        message = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
