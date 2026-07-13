#!/usr/bin/env python3
"""Fail when mutmut CI/CD statistics are below the configured score."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def score(stats: dict) -> float:
    killed = int(stats.get("killed", 0))
    survived = int(stats.get("survived", 0))
    timeout = int(stats.get("timeout", 0))
    suspicious = int(stats.get("suspicious", 0))
    no_tests = int(stats.get("no_tests", 0))
    denominator = killed + survived + timeout + suspicious + no_tests
    return 100.0 if denominator == 0 else killed * 100.0 / denominator


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stats", type=Path)
    parser.add_argument("--minimum", type=float, default=75.0)
    args = parser.parse_args(argv)
    if not 0 <= args.minimum <= 100:
        parser.error("--minimum must be between 0 and 100")
    try:
        data = json.loads(args.stats.read_text(encoding="utf-8"))
        actual = score(data)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"FAIL(mutation): cannot read {args.stats}: {exc}", file=sys.stderr)
        return 2
    summary = (
        f"mutation score {actual:.2f}% "
        f"(killed={data.get('killed', 0)}, survived={data.get('survived', 0)}, "
        f"timeout={data.get('timeout', 0)})"
    )
    if actual < args.minimum:
        print(f"FAIL(mutation): {summary}; required >= {args.minimum:.2f}%", file=sys.stderr)
        return 1
    print(f"OK(mutation): {summary}; required >= {args.minimum:.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
