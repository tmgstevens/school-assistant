"""LLM evals for the morning briefing: real Claude calls against fixed
scenarios (see scenarios.py), scored on facts that must/must-not appear.

Costs money and is non-deterministic — excluded from the default `pytest`
run (see pytest.ini) and the `make test` build gate. Run explicitly:

    make evals
    # or
    PYTHONPATH=src pytest tests/evals -m llm_eval -v -s

Point at a different model without touching this file:

    EVAL_MODEL=claude-haiku-4-5-20251001 make evals
"""

import os
import time

import pytest

from claude_client import ClaudeClient

from .common import PROD_PROMPT, check
from .scenarios import SCENARIOS

pytestmark = pytest.mark.llm_eval


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.name for s in SCENARIOS])
def test_briefing_scenario(scenario, anthropic_api_key):
    model = os.environ.get("EVAL_MODEL", "claude-sonnet-4-6")
    client = ClaudeClient(api_key=anthropic_api_key, model=model)

    t0 = time.time()
    output = client.synthesise_briefing(
        scenario.data, scenario.briefing_date, now=scenario.now, prompt_template=PROD_PROMPT,
    )
    elapsed = time.time() - t0

    failures = check(output, scenario.must_mention, scenario.must_not_mention)

    print(f"\n{'─' * 60}")
    print(f"{scenario.name}  [{model}]  ({elapsed:.2f}s)")
    print(f"{'─' * 60}")
    print(output)
    print()

    assert not failures, (
        f"{scenario.description}\n"
        + "\n".join(f"  - {f}" for f in failures)
        + f"\n\nFull output:\n{output}"
    )
