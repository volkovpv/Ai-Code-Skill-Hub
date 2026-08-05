#!/usr/bin/env python3
"""Validate and run versioned behavioral/trigger eval manifests."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from skill_library.installer import AGENT_TARGET_DIRS, InstallError, install_skill  # noqa: E402
from skill_library.security import SecurityError, safe_join  # noqa: E402
from skill_library.vendors import Registry, VendorError, load_registry  # noqa: E402

# A case id names a file under --save-output, so it may not carry separators.
CASE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")

# Which environment a manifest expects, by purpose.
#   gate  — the vendor, model and effort the skill's users actually run; a green
#           gate is green for that triple and says nothing about any other.
#   debug — a cheap, fast triple for shaking manifest defects out between live
#           runs. Its failures may be the environment's limits, not the skill's,
#           so a debug run never promotes anything.
TIERS = ("gate", "debug")

# Two of the three reach the harness through the command line; the vendor is the
# environment they belong to and is resolved against vendors.yaml instead.
TIER_DIALS = ("model", "effort")
TIER_KEYS = ("vendor", *TIER_DIALS)


class EvalError(ValueError):
    """Invalid manifest or unsafe runner configuration."""


def _strings(value: object, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise EvalError(f"{field} must be a list of strings")
    return value


def check_environment(
    registry: Registry, vendor: str | None, model: str | None, effort: str | None, label: str
) -> None:
    """A declared environment must exist in the registry, exactly as declared.

    Unknown vendor, unknown model, a model belonging to another vendor, or an
    effort level that model does not accept are all manifest defects — never a
    silent fallback to whatever the harness would have picked.
    """
    if vendor is not None:
        if registry.vendor(vendor) is None:
            raise EvalError(
                f"{label}: unknown vendor {vendor!r} (known: {', '.join(registry.vendor_names)})"
            )
    if model is not None:
        entry = registry.model(model)
        if entry is None:
            raise EvalError(f"{label}: model {model!r} is not registered in vendors.yaml")
        if vendor is not None and entry.vendor != vendor:
            raise EvalError(
                f"{label}: model {model!r} belongs to vendor {entry.vendor!r}, not {vendor!r}"
            )
    if effort is None:
        return
    if model is not None:
        levels = registry.effort_levels_for(registry.model(model).vendor, model)
        if not levels:
            raise EvalError(
                f"{label}: model {model!r} takes no effort level at all — declare a model "
                "that does, or run without the effort dial"
            )
        if effort not in levels:
            raise EvalError(
                f"{label}: effort {effort!r} is not accepted by model {model!r} "
                f"(accepted: {', '.join(levels)})"
            )
        return
    known = sorted({level for v in registry.vendors for level in v.effort_levels})
    if effort not in known:
        raise EvalError(f"{label}: effort {effort!r} is not a level any vendor declares")


def load_manifest(path: Path, registry: Registry) -> dict:
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
    tiers = data.get("tiers")
    if tiers is not None:
        if not isinstance(tiers, dict) or not tiers:
            raise EvalError(f"{path}: tiers must be a non-empty object")
        unknown_tiers = sorted(set(tiers) - set(TIERS))
        if unknown_tiers:
            raise EvalError(
                f"{path}: unknown tiers: {', '.join(unknown_tiers)} (known: {', '.join(TIERS)})"
            )
        for tier, dials in tiers.items():
            if not isinstance(dials, dict) or not dials:
                raise EvalError(f"{path}: tiers.{tier} must be a non-empty object")
            unknown_dials = sorted(set(dials) - set(TIER_KEYS))
            if unknown_dials:
                raise EvalError(
                    f"{path}: unknown dials in tiers.{tier}: {', '.join(unknown_dials)} "
                    f"(known: {', '.join(TIER_KEYS)})"
                )
            missing_dials = [key for key in TIER_KEYS if key not in dials]
            if missing_dials:
                raise EvalError(
                    f"{path}: tiers.{tier} is missing {', '.join(missing_dials)}; a declared "
                    f"environment names all of {', '.join(TIER_KEYS)}"
                )
            for dial, value in dials.items():
                if not isinstance(value, str) or not value.strip():
                    raise EvalError(f"{path}: tiers.{tier}.{dial} must be a non-empty string")
            check_environment(
                registry,
                dials["vendor"],
                dials["model"],
                dials["effort"],
                f"{path}: tiers.{tier}",
            )
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
        if not CASE_ID_RE.fullmatch(case["id"]):
            raise EvalError(
                f"{prefix}.id must match /{CASE_ID_RE.pattern}/ — it names a file "
                "when --save-output is used"
            )
        if case["id"] in seen:
            raise EvalError(f"{path}: duplicate case id {case['id']!r}")
        seen.add(case["id"])
        expect = case.get("expect")
        if not isinstance(expect, dict):
            raise EvalError(f"{prefix}.expect must be an object")
        _strings(expect.get("stdout_contains"), f"{prefix}.expect.stdout_contains")
        _strings(expect.get("stdout_not_contains"), f"{prefix}.expect.stdout_not_contains")
        for field in ("stdout_matches", "stdout_not_matches"):
            for pattern in _strings(expect.get(field), f"{prefix}.expect.{field}"):
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
    for pattern in expect.get("stdout_not_matches", []):
        if re.search(pattern, result.stdout, re.MULTILINE) is not None:
            problems.append(f"stdout matches forbidden pattern /{pattern}/")
    return problems


def save_output(directory: Path, skill: str, case_id: str, attempt: int, text: str) -> Path:
    """Write one harness stdout under *directory*, named after the case.

    A failing expectation says which oracle missed but not what the harness
    actually answered, and the temporary project is gone by then — without
    this the only way to read a failure is to run the case again.
    """
    target = safe_join(directory, f"{skill}--{case_id}--{attempt}.txt")
    target.write_text(text, encoding="utf-8")
    return target


def resolve_dial(
    dial: str, path: Path, data: dict, args: argparse.Namespace, command: list[str]
) -> str | None:
    """One dial of the run environment, from its flag or the manifest's tier.

    Fail closed in both directions: a run that knows a dial must put it in the
    command, and a command asking for one must be given one. Otherwise the
    header would name an environment the harness never received.
    """
    value = getattr(args, dial) or data.get("tiers", {}).get(args.tier, {}).get(dial)
    placeholder = "{%s}" % dial
    asks = any(placeholder in token for token in command)
    if value and not asks:
        raise EvalError(
            f"{path}: {dial} {value!r} is set for tier {args.tier!r} but --command has no "
            f"{placeholder} placeholder — the harness would silently use its own default"
        )
    if asks and not value:
        raise EvalError(
            f"--command has a {placeholder} placeholder but no {dial} is set: pass --{dial}, "
            f"or declare tiers.{args.tier}.{dial} in {path}"
        )
    return value


def run_manifest(path: Path, data: dict, registry: Registry, args: argparse.Namespace) -> int:
    if args.platform not in data.get("platforms", []):
        raise EvalError(f"{path}: platform {args.platform!r} is not declared")
    command = shlex.split(args.command)
    if not command or not any("{prompt}" in token for token in command):
        raise EvalError("--command must contain a {prompt} placeholder")
    dials = {dial: resolve_dial(dial, path, data, args, command) for dial in TIER_DIALS}
    vendor = data.get("tiers", {}).get(args.tier, {}).get("vendor")
    # An override on the command line is held to the same registry as the
    # manifest — otherwise --model/--effort would be the way around the gate.
    check_environment(registry, vendor, dials["model"], dials["effort"], f"{path}: tier {args.tier}")

    # Effort also reaches the harness through the shell that launched this run;
    # drop it so the manifest is the only thing that decides. A run that names
    # no vendor scrubs every vendor's variable rather than guessing.
    inherited = registry.effort_env_vars(vendor)
    child_env = {k: v for k, v in os.environ.items() if k not in inherited}

    # A green run is green for one environment; the log has to name it.
    named = " ".join(f"{dial}={dials[dial] or '(harness default)'}" for dial in TIER_DIALS)
    print(
        f"RUN {data['skill']} platform={args.platform} tier={args.tier} "
        f"vendor={vendor or '(not declared)'} {named} "
        f"repeat={args.repeat} cases={len(data['cases'])} command={args.command!r}"
    )

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
                    **{dial: dials[dial] or "" for dial in TIER_DIALS},
                }
                argv = [token.format(**values) for token in command]
                try:
                    result = subprocess.run(
                        argv,
                        cwd=project,
                        capture_output=True,
                        text=True,
                        timeout=args.timeout,
                        env=child_env,
                        check=False,
                    )
                    problems = evaluate(case, result)
                    if args.save_output is not None:
                        save_output(
                            args.save_output, data["skill"], case["id"], attempt, result.stdout
                        )
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
    parser.add_argument(
        "--command",
        help="harness command with {prompt}; {project}/{skill}/{model}/{effort} optional",
    )
    parser.add_argument("--platform", default="claude", choices=sorted(AGENT_TARGET_DIRS))
    parser.add_argument(
        "--tier",
        default="gate",
        choices=TIERS,
        help="which declared environment to run: gate (promotion) or debug (cheap iteration)",
    )
    parser.add_argument("--model", help="override the model declared for the tier")
    parser.add_argument(
        "--effort",
        help="override the reasoning effort declared for the tier; validated against "
        "the levels vendors.yaml records for the model, not a list frozen here",
    )
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--save-output",
        type=Path,
        metavar="DIR",
        help="write each harness stdout to DIR/<skill>--<case>--<attempt>.txt",
    )
    args = parser.parse_args(argv)
    if args.repeat < 1 or args.timeout <= 0:
        parser.error("--repeat and --timeout must be positive")
    if not args.validate_only and not args.command:
        parser.error("--command is required unless --validate-only is used")
    if args.save_output is not None:
        args.save_output.mkdir(parents=True, exist_ok=True)

    try:
        registry = load_registry(ROOT)
        loaded = [(path, load_manifest(path, registry)) for path in args.manifests]
        if args.validate_only:
            for path, data in loaded:
                tiers = data.get("tiers", {})
                declared = "; ".join(
                    f"{tier}: " + " ".join(f"{d}={tiers[tier][d]}" for d in TIER_KEYS if d in tiers[tier])
                    for tier in TIERS
                    if tier in tiers
                )
                suffix = f" — {declared}" if declared else ""
                print(f"OK {path}: {len(data['cases'])} case(s){suffix}")
            return 0
        failures = sum(run_manifest(path, data, registry, args) for path, data in loaded)
    except (EvalError, InstallError, SecurityError, VendorError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
