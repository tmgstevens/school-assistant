# School Assistant

An Alexa skill that gives a spoken morning briefing for kids before school — homework, PE kit, school announcements, and after-school activities, pulled together from ClassCharts and Google Calendar and summarised by Claude into about 30 seconds of plain spoken English.

> "Alexa, ask school briefing" → *"Good morning! Alice has her maths worksheet due today, and she'll need her PE kit. There's football training at four, don't forget her boots..."*

## How it works

- **ClassCharts** (unofficial API) — homework due, today's timetable (for PE kit detection), and school announcements (trips, money due, permission slips)
- **Google Calendar** — after-school activities and events, filtered by the LLM rather than hardcoded rules
- **Claude** — synthesises everything into a short, natural-sounding briefing, following rules defined in [`terraform/prompt.txt`](terraform/prompt.txt) (e.g. only flag PE kit for practical lessons, resurface weekly reminders on Mondays, resolve relative dates like "next Wednesday" against when an announcement was posted, ignore adult personal-task reminders mixed into the calendar)

Two intents:

- **BriefingIntent** — the cached morning briefing, invoked by the daily Alexa routine. Runs on a 2-hour DynamoDB cache (see [Architecture](#architecture)) so the slow data-fetch path only runs once per day.
- **QueryIntent** — ad-hoc questions ("what homework does Bob have this week?"), skipping the cache and hitting the APIs live.

## Architecture

```
Alexa → Lambda (ARM64 container) → DynamoDB cache (briefing path only)
                                 → ClassCharts + Google Calendar (parallel fetch)
                                 → Claude API
                                 → Alexa SSML response
```

- Lambda runs in `eu-west-1`, built from the `Dockerfile` here
- The briefing prompt lives in SSM Parameter Store, templated from [`terraform/prompt.txt`](terraform/prompt.txt) at deploy time — no rebuild needed to tweak prompt wording
- An EventBridge rule pre-warms the cache at 7:15am on weekdays, ahead of the usual Alexa routine trigger
- Secrets (ClassCharts, Google OAuth, Anthropic) live in Secrets Manager

Full setup, deploy, and Alexa-skill-registration steps are in [`INSTALL.md`](INSTALL.md).

## Development

```bash
cp .env.example .env    # fill in real credentials
make install             # venv + dependencies
make test                # unit tests (mocked APIs/LLM — fast, free, deterministic)
python scripts/run_local.py             # full dry run against live APIs
python scripts/run_local.py --query "what homework does Bob have this week"
```

### Evals

`make test` never calls a real LLM — `ClaudeClient` is mocked throughout, so it checks plumbing, not briefing quality. Actual prompt/model correctness is checked by a separate eval suite: real Claude calls against fixed scenarios in [`tests/evals/scenarios.py`](tests/evals/scenarios.py), scored on facts that must or must not appear in the output (e.g. "must mention kit," "must not mention the stale announcement"). It costs money and is non-deterministic, so it's excluded from `make test`/`make build` and run explicitly:

```bash
make evals
EVAL_MODEL=claude-haiku-4-5-20251001 make evals    # try a different model
```

[`scripts/compare_eval_models.py`](scripts/compare_eval_models.py) runs the same scenarios across several Claude models at once and reports pass rate + latency side by side, for comparing a candidate model against production before switching.

## Project layout

```
src/                  Lambda handler, ClassCharts/Calendar/Claude clients, DynamoDB cache
tests/                Unit tests (mocked) + tests/evals/ (real LLM calls, opt-in)
scripts/              Local dry-run, Google OAuth token helper, model benchmarking
terraform/            Infra (Lambda, DynamoDB, EventBridge, SSM, Secrets Manager) + prompt.txt
```

## License

[MIT](LICENSE)
