"""Run the briefing eval scenarios (tests/evals/scenarios.py) against several
Claude models to compare correctness and latency side by side.

Unlike `make evals` (which checks one model, EVAL_MODEL or the prod default,
and fails the build on a bad result), this is a reporting tool: it always
runs to completion and prints a table, so you can see how a candidate model
compares to the current production model before switching.

Usage:
    PYTHONPATH=src python scripts/compare_eval_models.py
    PYTHONPATH=src python scripts/compare_eval_models.py --models claude-sonnet-4-6,claude-haiku-5-5
"""

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "tests"))

from dotenv import load_dotenv

from claude_client import ClaudeClient
from evals.common import PROD_PROMPT, check
from evals.scenarios import SCENARIOS

load_dotenv(Path(__file__).parent.parent / ".env")

DEFAULT_MODELS = [
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6",
    "claude-haiku-5-5",
    "claude-sonnet-5-5",
]

# Reasoning-capable models spend part of the budget on a hidden thinking
# block before any visible text — 512 tokens can come back empty for them.
MAX_TOKENS = 2048


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS))
    args = parser.parse_args()
    models = [m.strip() for m in args.models.split(",") if m.strip()]

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY not set — add it to .env")

    results = []  # (model, scenario_name, passed, elapsed, failures, output)

    for model in models:
        client = ClaudeClient(api_key=api_key, model=model)
        for scenario in SCENARIOS:
            t0 = time.time()
            try:
                output = client.synthesise_briefing(
                    scenario.data, scenario.briefing_date, now=scenario.now,
                    prompt_template=PROD_PROMPT, max_tokens=MAX_TOKENS,
                )
                elapsed = time.time() - t0
                failures = check(output, scenario.must_mention, scenario.must_not_mention)
            except Exception as exc:
                elapsed = time.time() - t0
                failures = [f"ERROR: {exc}"]
                output = ""

            passed = not failures
            results.append((model, scenario.name, passed, elapsed, failures, output))
            mark = "PASS" if passed else "FAIL"
            print(f"[{mark}] {model:30s} {scenario.name:45s} {elapsed:5.1f}s")
            if not passed:
                for f in failures:
                    print(f"       - {f}")

    print("\n" + "=" * 100)
    print("Summary")
    print("=" * 100)
    header = f"{'Model':30s} {'Pass rate':12s} {'Avg latency':12s}"
    print(header)
    print("-" * len(header))
    for model in models:
        rows = [r for r in results if r[0] == model]
        n_pass = sum(1 for r in rows if r[2])
        avg_latency = sum(r[3] for r in rows) / len(rows)
        print(f"{model:30s} {n_pass}/{len(rows):<10d} {avg_latency:6.1f}s")


if __name__ == "__main__":
    main()
