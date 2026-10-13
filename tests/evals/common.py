"""Shared prompt-loading and scoring logic for the briefing evals, used by
both the pytest suite (test_briefing_evals.py) and the model-comparison
script (scripts/compare_eval_models.py)."""

import re
from pathlib import Path

from .scenarios import FAMILY_CONTEXT

PROMPT_PATH = Path(__file__).parent.parent.parent / "terraform" / "prompt.txt"
PROD_PROMPT = PROMPT_PATH.read_text().replace("${family_context}", FAMILY_CONTEXT)


def _contains_phrase(lowered: str, phrase: str) -> bool:
    # Word-boundary match so e.g. "fair" doesn't match inside "fairly".
    return re.search(rf"\b{re.escape(phrase.lower())}\b", lowered) is not None


def check(output: str, must_mention: list, must_not_mention: list[str]) -> list[str]:
    """must_mention entries may be a phrase, or a tuple/list of alternative
    phrasings (e.g. ("spain", "spanish")) where any one satisfies the check —
    models vary their exact wording between runs."""
    lowered = output.lower()
    failures = []
    for item in must_mention:
        alternatives = (item,) if isinstance(item, str) else item
        if not any(_contains_phrase(lowered, alt) for alt in alternatives):
            failures.append(f"expected to find one of {alternatives!r} but none are present")
    for phrase in must_not_mention:
        if _contains_phrase(lowered, phrase):
            failures.append(f"expected {phrase!r} to be absent but it's present")
    return failures
