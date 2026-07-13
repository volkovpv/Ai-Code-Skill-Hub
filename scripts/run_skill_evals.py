#!/usr/bin/env python3
"""Validate and run versioned behavioral/trigger eval manifests."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from skill_library.installer import AGENT_TARGET_DIRS, InstallError, install_skill  # noqa: E402


class EvalError(ValueError):
    """Invalid manifest or unsafe runner configuration."""


def _strings(value: object, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise EvalError(f"{field} must be a list of strings")
    return value


def load_manifest(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvalError(f"{path}: cannot read JSON: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise EvalError(f"{path}: schema_version must be 1")
    if not isinstance(data.get("skill"), str) or not data["skill"]:
        raise EvalError(f"{path}: skill must be a non-empty string")
    platforms = _strings(data.get("platforms"), f"{path}: platforms")
    unknown = sorted(set(platforms) - set(AGENT_TARGET_DIRS))
    if unknown:
        raise EvalError(f"{path}: unknown platforms: {', '.join(unknown)}")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise EvalError(f"{path}: cases must be a non-empty list")
    seen: set[str] = set()
    for index, case in enumerate(cases):
        prefix = f"{path}: cases[{index}]"
        if not isinstance(case, dict):
            raise EvalError(f"{prefix} must be an object")
        for field in ("id", "kind", "requirement", "prompt"):
            if not isinstance(case.get(field), str) or not case[field].strip():
                raise EvalError(f"{prefix}.{field} must be a non-empty string")
        if case["kind"] not in {"trigger", "behavior", "negative"}:
            raise EvalError(f"{prefix}.kind must be trigger, behavior, or negative")
        if case["id"] in seen:
            raise EvalError(f"{path}: duplicate case id {case['id']!r}")
        seen.add(case["id"])
        expect = case.get("expect")
        if not isinstance(expect, dict):
            raise EvalError(f"{prefix}.expect must be an object")
        _strings(expect.get("stdout_contains"), f"{prefix}.expect.stdout_contains")
        _strings(expect.get("stdout_not_contains"), f"{prefix}.expect.stdout_not_contains")
        for pattern in _strings(expect.get("stdout_matches"), f"{prefix}.expect.stdout_matches"):
            try:
                re.compile(pattern)
            except re.error as exc:
                raise EvalError(f"{prefix}: invalid regex {pattern!r}: {exc}") from exc
        if not isinstance(expect.get("exit_code", 0), int):
            raise EvalError(f"{prefix}.expect.exit_code must be an integer")
    return data


def evaluate(case: dict, result: subprocess.CompletedProcess[str]) -> list[str]:
    expect = case["expect"]
    problems: list[str] = []
    expected_code = expect.get("exit_code", 0)
    if result.returncode != expected_code:
        problems.append(f"exit code {result.returncode}, expected {expected_code}")
    for value in expect.get("stdout_contains", []):
        if value not in result.stdout:
            problems.append(f"stdout does not contain {value!r}")
    for value in expect.get("stdout_not_contains", []):
        if value in result.stdout:
            problems.append(f"stdout contains forbidden value {value!r}")
    for pattern in expect.get("stdout_matches", []):
        if re.search(pattern, result.stdout, re.MULTILINE) is None:
            problems.append(f"stdout does not match /{pattern}/")
    return problems


def run_manifest(path: Path, data: dict, args: argparse.Namespace) -> int:
    if args.platform not in data.get("platforms", []):
        raise EvalError(f"{path}: platform {args.platform!r} is not declared")
    command = shlex.split(args.command)
    if not command or not any("{prompt}" in token for token in command):
        raise EvalError("--command must contain a {prompt} placeholder")

    failures = 0
    for case in data["cases"]:
        for attempt in range(1, args.repeat + 1):
            with tempfile.TemporaryDirectory(prefix="skill-eval-") as tmp:
                project = Path(tmp)
                install_skill(ROOT, data["skill"], project, agent=args.platform)
                values = {
                    "prompt": case["prompt"],
                    "project": str(project),
                    "skill": data["skill"],
                }
                argv = [token.format(**values) for token in command]
                try:
                    result = subprocess.run(
                        argv,
                        cwd=project,
                        capture_output=True,
                        text=True,
                        timeout=args.timeout,
                        check=False,
                    )
                    problems = evaluate(case, result)
                except subprocess.TimeoutExpired:
                    problems = [f"timed out after {args.timeout}s"]
                label = f"{data['skill']}:{case['id']}#{attempt}"
                if problems:
                    failures += 1
                    print(f"FAIL {label}: {'; '.join(problems)}", file=sys.stderr)
                else:
                    print(f"PASS {label}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifests", nargs="+", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--command", help="harness command with {prompt}; {project}/{skill} optional")
    parser.add_argument("--platform", default="claude", choices=sorted(AGENT_TARGET_DIRS))
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args(argv)
    if args.repeat < 1 or args.timeout <= 0:
        parser.error("--repeat and --timeout must be positive")
    if not args.validate_only and not args.command:
        parser.error("--command is required unless --validate-only is used")

    try:
        loaded = [(path, load_manifest(path)) for path in args.manifests]
        if args.validate_only:
            for path, data in loaded:
                print(f"OK {path}: {len(data['cases'])} case(s)")
            return 0
        failures = sum(run_manifest(path, data, args) for path, data in loaded)
    except (EvalError, InstallError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
