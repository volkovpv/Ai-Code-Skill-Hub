"""``skillctl`` — the management CLI of the skill library.

Entry point: ``python scripts/skillctl.py <command> ...`` (see README.md).
Every command returns a process exit code: 0 on success, 1 on failure,
2 on usage errors (argparse default).
"""

from __future__ import annotations

import argparse
import shutil
import sys
import unittest
from datetime import date
from pathlib import Path

from . import __version__, installer, lockfile, observations, yamlio
from .discovery import (
    CATALOG_FILENAME,
    SKILLS_DIRNAME,
    DiscoveryError,
    catalog_entry,
    discover_skills,
    load_catalog,
)
from .security import SecurityError, ensure_no_symlinks, validate_skill_name
from .validator import (
    LAYER_DIRS,
    validate_data_layer,
    validate_library,
    validate_skill_dir,
)

TEMPLATE_DIR = Path("templates") / "skill"
TESTS_DIRNAME = "__test__"


def _default_library_root() -> Path:
    # src/skill_library/cli.py -> <repo root>
    return Path(__file__).resolve().parents[2]


def _err(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def _skill_dir_or_none(root: Path, name: str) -> Path | None:
    try:
        validate_skill_name(name)
    except SecurityError:
        return None
    skill_dir = root / SKILLS_DIRNAME / name
    return skill_dir if skill_dir.is_dir() else None


# ----------------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------------

def cmd_list(args: argparse.Namespace) -> int:
    root = args.library_root
    skills, problems = discover_skills(root)
    try:
        catalog = {entry.name: entry for entry in load_catalog(root)}
    except DiscoveryError as exc:
        return _err(str(exc))
    if not skills and not problems:
        print(f"no skills found in {root / SKILLS_DIRNAME}")
        return 0
    width = max((len(s.name) for s in skills), default=4)
    for skill in skills:
        cat = catalog.get(skill.name)
        version = cat.version if cat else "-"
        status_ = cat.status if cat else "uncatalogued"
        print(f"{skill.name.ljust(width)}  {version:>8}  {status_:<12}  {skill.description}")
    for problem in problems:
        print(f"warning: {problem}", file=sys.stderr)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    root = args.library_root
    if args.skill:
        try:
            validate_skill_name(args.skill)
        except SecurityError as exc:
            return _err(str(exc))
        skill_dir = root / SKILLS_DIRNAME / args.skill
        if not skill_dir.is_dir():
            return _err(f"skill {args.skill!r} not found in {root / SKILLS_DIRNAME}")
        try:
            cat = catalog_entry(root, args.skill)
        except DiscoveryError as exc:
            return _err(str(exc))
        policy = cat.content_policy if cat else None
        problems = [
            f"{args.skill}: {p}"
            for p in validate_skill_dir(
                skill_dir, policy, status=cat.status if cat else None
            )
        ]
    else:
        problems = validate_library(root)
    if problems:
        for problem in problems:
            print(f"FAIL {problem}")
        print(f"{len(problems)} problem(s) found")
        return 1
    scope = args.skill or "library"
    print(f"OK: {scope} passed validation")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    try:
        message = installer.install_skill(
            args.library_root,
            args.skill,
            args.target,
            agent=args.agent,
            link=args.link,
            force=args.force,
            dry_run=args.dry_run,
            skills_dir_override=args.target_skills_dir,
            install_mode=args.mode,
        )
    except (installer.InstallError, SecurityError, lockfile.LockError) as exc:
        return _err(str(exc))
    print(message)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    try:
        rows = installer.status(args.library_root, args.target)
    except (installer.InstallError, lockfile.LockError) as exc:
        return _err(str(exc))
    if not rows:
        print(f"no skills installed in {args.target} (no {lockfile.LOCKFILE_NAME} entries)")
        return 0
    width = max(len(r["name"]) for r in rows)
    for row in rows:
        entry = row["entry"]
        print(
            f"{row['name'].ljust(width)}  v{entry.get('skill_version', '?'):<8} "
            f"state={row['state']:<9} update={row['update']:<30} "
            f"agent={entry.get('agent', '?')} mode={entry.get('install_mode', 'full')} "
            f"path={entry.get('target_path', '?')}"
        )
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    try:
        diff = installer.diff_skill(args.library_root, args.skill, args.target)
    except (installer.InstallError, SecurityError, lockfile.LockError) as exc:
        return _err(str(exc))
    if not diff:
        print(f"{args.skill}: installed copy matches the library source")
    else:
        print(diff, end="" if diff.endswith("\n") else "\n")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    try:
        diff = installer.diff_skill(args.library_root, args.skill, args.target)
        if diff:
            print("--- changes that will be applied ---")
            print(diff, end="" if diff.endswith("\n") else "\n")
            print("--- end of diff ---")
        message = installer.update_skill(
            args.library_root,
            args.skill,
            args.target,
            force=args.force,
            dry_run=args.dry_run,
        )
    except (installer.InstallError, SecurityError, lockfile.LockError) as exc:
        return _err(str(exc))
    print(message)
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    try:
        message = installer.remove_skill(
            args.library_root,
            args.skill,
            args.target,
            force=args.force,
            dry_run=args.dry_run,
        )
    except (installer.InstallError, SecurityError, lockfile.LockError) as exc:
        return _err(str(exc))
    print(message)
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    root = args.library_root
    tests_dir = root / TESTS_DIRNAME
    if not tests_dir.is_dir():
        return _err(f"tests directory {tests_dir} not found")
    if args.skill:
        rc = cmd_validate(argparse.Namespace(library_root=root, skill=args.skill))
        if rc != 0:
            return rc
        # Exact file name: a prefix wildcard (test_<slug>*.py) would match the
        # dedicated tests of another skill whose name extends this one.
        pattern = f"test_{args.skill.replace('-', '_')}.py"
    else:
        pattern = "test_*.py"
    if not args.skill:
        try:
            catalog = load_catalog(root)
        except DiscoveryError as exc:
            return _err(str(exc))
        missing = []
        for entry in catalog:
            if entry.status != "stable":
                continue
            stable_pattern = f"test_{entry.name.replace('-', '_')}.py"
            stable_suite = unittest.TestLoader().discover(
                str(tests_dir), pattern=stable_pattern, top_level_dir=str(root)
            )
            if stable_suite.countTestCases() == 0:
                missing.append(f"{entry.name} ({stable_pattern})")
        if missing:
            return _err(
                "stable skills without dedicated tests: " + ", ".join(missing)
            )
    loader = unittest.TestLoader()
    suite = loader.discover(str(tests_dir), pattern=pattern, top_level_dir=str(root))
    if args.skill and suite.countTestCases() == 0:
        try:
            cat = catalog_entry(root, args.skill)
        except DiscoveryError as exc:
            return _err(str(exc))
        if cat is not None and cat.status == "stable":
            return _err(
                f"{args.skill}: stable skill has no dedicated tests "
                f"(expected pattern {pattern})"
            )
        print(f"{args.skill}: no dedicated tests found (pattern {pattern}); validation passed")
        return 0
    runner = unittest.TextTestRunner(verbosity=2 if args.verbose else 1)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


def _parse_layers(raw: str) -> set[str]:
    layers = {part.strip() for part in raw.split(",") if part.strip()}
    unknown = layers - set(LAYER_DIRS)
    if unknown:
        raise ValueError(
            f"unknown layer(s): {', '.join(sorted(unknown))}; allowed: {', '.join(LAYER_DIRS)}"
        )
    return layers


def _copy_skill_template(
    template: Path, dest: Path, layers: set[str], name: str, today: str
) -> None:
    dest.mkdir(parents=True)
    for src in sorted(template.rglob("*")):
        rel = src.relative_to(template)
        if rel.parts[0] in LAYER_DIRS and rel.parts[0] not in layers:
            continue
        target = dest / rel
        if src.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        data = src.read_bytes()
        try:
            text = data.decode("utf-8")
            text = text.replace("__SKILL_NAME__", name).replace("__TODAY__", today)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        except UnicodeDecodeError:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)


def cmd_new(args: argparse.Namespace) -> int:
    root = args.library_root
    name = args.skill
    try:
        validate_skill_name(name)
    except SecurityError as exc:
        return _err(str(exc))
    try:
        layers = _parse_layers(args.with_layers or "")
    except ValueError as exc:
        return _err(str(exc))
    template = root / TEMPLATE_DIR
    if not template.is_dir():
        return _err(f"template directory {template} not found")
    dest = root / SKILLS_DIRNAME / name
    if dest.exists():
        return _err(f"skill {name!r} already exists at {dest}")
    try:
        # Guard against a ghost entry: the skill directory may be gone while a
        # stale line lingers in skills.yaml. Without this, `new` appends a
        # second entry and load_catalog would only choke on the duplicate later.
        if catalog_entry(root, name) is not None:
            return _err(
                f"skill {name!r} is already registered in {CATALOG_FILENAME}; "
                "remove the stale catalog entry before recreating it"
            )
    except DiscoveryError as exc:
        return _err(str(exc))
    try:
        ensure_no_symlinks(template)
    except SecurityError as exc:
        return _err(str(exc))

    today = date.today().isoformat()
    try:
        _copy_skill_template(template, dest, layers, name, today)
    except OSError as exc:
        shutil.rmtree(dest, ignore_errors=True)
        return _err(f"failed to scaffold {name!r}; rolled back partial files: {exc}")

    catalog_path = root / CATALOG_FILENAME
    if catalog_path.is_file():
        # skills.yaml keeps the `skills:` list as its last top-level key, so a
        # new entry can be appended textually without disturbing comments.
        lines = [
            f"  - name: {name}",
            f"    path: {SKILLS_DIRNAME}/{name}",
            "    version: 0.1.0",
            "    status: draft",
            f"    summary: TODO describe {name}",
            "    platforms: [universal, codex, opencode, claude, hermes]",
            "    license: MIT",
        ]
        if layers:
            lines.append("    capabilities:")
            lines.extend(f"      {layer}: {'true' if layer in layers else 'false'}"
                         for layer in LAYER_DIRS)
            lines.extend(
                [
                    "    content_policy:",
                    "      max_tracked_file_bytes: 262144",
                    "      pii_allowed: false",
                    "      secrets_allowed: false",
                    "      observation_review_required: true",
                ]
            )
        original_content = catalog_path.read_text(encoding="utf-8")
        content = original_content
        if not content.endswith("\n"):
            content += "\n"
        try:
            catalog_path.write_text(content + "\n".join(lines) + "\n", encoding="utf-8")
            load_catalog(root)
        except (OSError, DiscoveryError) as exc:
            shutil.rmtree(dest, ignore_errors=True)
            try:
                catalog_path.write_text(original_content, encoding="utf-8")
            except OSError as restore_exc:
                return _err(
                    f"failed to create {name!r}: {exc}; additionally failed to "
                    f"restore {CATALOG_FILENAME}: {restore_exc}"
                )
            return _err(
                f"failed to create {name!r}; rolled back partial changes: {exc}"
            )
        catalog_note = f"and registered in {CATALOG_FILENAME} (status: draft)"
    else:
        catalog_note = f"({CATALOG_FILENAME} not found — register the skill manually)"

    layers_note = f" with layers: {', '.join(sorted(layers))}" if layers else ""
    print(f"{name}: created from template at {dest}{layers_note} {catalog_note}")
    print(f"next: edit {dest / 'SKILL.md'}, then run 'skillctl validate {name}'")
    return 0


# ----------------------------------------------------------------------------
# Layer commands: knowledge / observation / data
# ----------------------------------------------------------------------------

def cmd_knowledge_list(args: argparse.Namespace) -> int:
    root = args.library_root
    skill_dir = _skill_dir_or_none(root, args.skill)
    if skill_dir is None:
        return _err(f"skill {args.skill!r} not found in {root / SKILLS_DIRNAME}")
    knowledge = skill_dir / "knowledge"
    files = sorted(knowledge.rglob("*.md")) if knowledge.is_dir() else []
    if not files:
        print(f"{args.skill}: no knowledge layer")
        return 0
    for path in files:
        rel = path.relative_to(skill_dir).as_posix()
        title = ""
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            lines = []  # not UTF-8: list the file without a title, don't crash
        for line in lines:
            if line.startswith("#"):
                title = line.lstrip("#").strip()
                break
        print(f"{rel}  —  {title}" if title else rel)
    return 0


def cmd_observation_add(args: argparse.Namespace) -> int:
    root = args.library_root
    skill_dir = _skill_dir_or_none(root, args.skill)
    if skill_dir is None:
        return _err(f"skill {args.skill!r} not found in {root / SKILLS_DIRNAME}")
    try:
        obs_id, dest = observations.add_observation(
            skill_dir,
            Path(getattr(args, "from")),
            scope=args.scope,
            evidence=args.evidence,
            dry_run=args.dry_run,
        )
    except observations.ObservationError as exc:
        return _err(str(exc))
    prefix = "[dry-run] would create" if args.dry_run else "created"
    print(f"{args.skill}: {prefix} candidate {obs_id} at {dest.relative_to(root)}")
    print("note: candidates are not installed in runtime mode; promote with "
          f"'skillctl observation approve {args.skill} {obs_id} --reviewed-by <name>'")
    return 0


def cmd_observation_list(args: argparse.Namespace) -> int:
    root = args.library_root
    skill_dir = _skill_dir_or_none(root, args.skill)
    if skill_dir is None:
        return _err(f"skill {args.skill!r} not found in {root / SKILLS_DIRNAME}")
    try:
        records = observations.list_observations(skill_dir, status=args.status)
    except observations.ObservationError as exc:
        return _err(str(exc))
    if not records:
        suffix = f" with status {args.status!r}" if args.status else ""
        print(f"{args.skill}: no observations{suffix}")
        return 0
    for record in records:
        meta = record["meta"]
        title = record["body"].strip().splitlines()[0].lstrip("#").strip() if record["body"].strip() else ""
        print(
            f"{record['id']}  {str(record['status']):<9}  observed={meta.get('observed_at', '?')}  "
            f"scope={meta.get('scope', '?')}  {title}"
        )
    return 0


def _cmd_observation_review(args: argparse.Namespace, decision: str) -> int:
    root = args.library_root
    skill_dir = _skill_dir_or_none(root, args.skill)
    if skill_dir is None:
        return _err(f"skill {args.skill!r} not found in {root / SKILLS_DIRNAME}")
    try:
        dest = observations.review_observation(
            skill_dir,
            args.observation_id,
            decision,
            reviewed_by=args.reviewed_by,
            note=args.note,
            dry_run=args.dry_run,
        )
    except observations.ObservationError as exc:
        return _err(str(exc))
    prefix = "[dry-run] would move" if args.dry_run else "moved"
    print(f"{args.skill}: {args.observation_id} {decision}; {prefix} to {dest.relative_to(root)}")
    return 0


def cmd_observation_approve(args: argparse.Namespace) -> int:
    return _cmd_observation_review(args, "accepted")


def cmd_observation_reject(args: argparse.Namespace) -> int:
    return _cmd_observation_review(args, "rejected")


def cmd_data_validate(args: argparse.Namespace) -> int:
    root = args.library_root
    skill_dir = _skill_dir_or_none(root, args.skill)
    if skill_dir is None:
        return _err(f"skill {args.skill!r} not found in {root / SKILLS_DIRNAME}")
    try:
        cat = catalog_entry(root, args.skill)
    except DiscoveryError as exc:
        return _err(str(exc))
    problems = validate_data_layer(skill_dir, cat.content_policy if cat else None)
    if problems:
        for problem in problems:
            print(f"FAIL {args.skill}: {problem}")
        print(f"{len(problems)} problem(s) found")
        return 1
    if not (skill_dir / "data").is_dir():
        print(f"OK: {args.skill} has no data layer")
    else:
        print(f"OK: {args.skill} data layer passed validation")
    return 0


# ----------------------------------------------------------------------------
# Parser
# ----------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skillctl",
        description="Manage the Agent Skills library: list, validate, install, "
        "update, diff, remove, test, scaffold.",
    )
    parser.add_argument("--version", action="version", version=f"skillctl {__version__}")
    parser.add_argument(
        "--library-root",
        type=Path,
        default=_default_library_root(),
        help="library repository root (default: auto-detected)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="list skills available in the library")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("validate", help="validate one skill or the whole library")
    p.add_argument("skill", nargs="?", default=None)
    p.set_defaults(func=cmd_validate)

    def add_target(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--target", type=Path, required=True, help="target project root")

    p = sub.add_parser("install", help="install a skill into a target project")
    p.add_argument("skill")
    add_target(p)
    p.add_argument(
        "--agent",
        default="universal",
        choices=sorted(installer.AGENT_TARGET_DIRS),
        help="harness to install for (default: universal)",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--copy", action="store_true", help="copy files (default)")
    mode.add_argument(
        "--link", action="store_true", help="symlink to the library instead of copying"
    )
    p.add_argument(
        "--target-skills-dir",
        type=Path,
        default=None,
        help="explicit skills directory (required for --agent hermes)",
    )
    p.add_argument(
        "--mode",
        default="runtime",
        choices=installer.INSTALL_MODES,
        help="runtime: without candidate/rejected observations and test fixtures; "
        "full: the whole skill module (default: runtime)",
    )
    p.add_argument("--force", action="store_true", help="overwrite unmanaged/modified files")
    p.add_argument("--dry-run", action="store_true", help="print actions without changing anything")
    p.set_defaults(func=cmd_install)

    p = sub.add_parser("status", help="show installed skills and update availability")
    add_target(p)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("diff", help="diff installed skill vs library source")
    p.add_argument("skill")
    add_target(p)
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("update", help="update an installed skill (shows diff first)")
    p.add_argument("skill")
    add_target(p)
    p.add_argument("--force", action="store_true", help="overwrite local modifications")
    p.add_argument("--dry-run", action="store_true", help="show diff without applying")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("remove", help="remove an installed skill (managed files only)")
    p.add_argument("skill")
    add_target(p)
    p.add_argument("--force", action="store_true", help="remove even if files were modified")
    p.add_argument("--dry-run", action="store_true", help="print actions without changing anything")
    p.set_defaults(func=cmd_remove)

    p = sub.add_parser("test", help="run tests for one skill or the whole library")
    p.add_argument("skill", nargs="?", default=None)
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_test)

    p = sub.add_parser("new", help="scaffold a new skill from templates/skill")
    p.add_argument("skill")
    p.add_argument(
        "--with",
        dest="with_layers",
        default="",
        metavar="LAYERS",
        help="comma-separated optional layers to scaffold: knowledge,data,observations",
    )
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("knowledge", help="inspect the knowledge layer of a skill")
    ksub = p.add_subparsers(dest="subcommand", required=True)
    kp = ksub.add_parser("list", help="list knowledge files with their titles")
    kp.add_argument("skill")
    kp.set_defaults(func=cmd_knowledge_list)

    p = sub.add_parser("observation", help="manage the observation lifecycle of a skill")
    osub = p.add_subparsers(dest="subcommand", required=True)

    op = osub.add_parser("add", help="create a CANDIDATE observation from a markdown file")
    op.add_argument("skill")
    op.add_argument("--from", required=True, metavar="FILE", help="markdown file with the observation body")
    op.add_argument("--scope", default=None, help="applicability scope (default: skill name)")
    op.add_argument(
        "--evidence",
        action="append",
        default=None,
        help="evidence entry (test, fixture, issue, commit); repeatable",
    )
    op.add_argument("--dry-run", action="store_true")
    op.set_defaults(func=cmd_observation_add)

    op = osub.add_parser("list", help="list observations")
    op.add_argument("skill")
    op.add_argument("--status", choices=observations.STATUSES, default=None)
    op.set_defaults(func=cmd_observation_list)

    for decision, func in (("approve", cmd_observation_approve), ("reject", cmd_observation_reject)):
        op = osub.add_parser(decision, help=f"{decision} a candidate observation (audit metadata is recorded)")
        op.add_argument("skill")
        op.add_argument("observation_id")
        op.add_argument("--reviewed-by", required=True, help="human or role performing the review")
        op.add_argument("--note", default=None, help="optional review note stored in the observation")
        op.add_argument("--dry-run", action="store_true")
        op.set_defaults(func=func)

    p = sub.add_parser("data", help="inspect the data layer of a skill")
    dsub = p.add_subparsers(dest="subcommand", required=True)
    dp = dsub.add_parser("validate", help="validate data/README.md contract and content policy")
    dp.add_argument("skill")
    dp.set_defaults(func=cmd_data_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.library_root = Path(args.library_root).resolve()
    try:
        return args.func(args)
    except (OSError, UnicodeDecodeError, DiscoveryError, SecurityError) as exc:
        # Fail-closed safety net: an untrusted/broken input (non-UTF-8 file,
        # unreadable path) must yield 'error: ...' and exit 1, never a bare
        # traceback. Commands still catch these first for tailored messages;
        # this only guards paths that slip through.
        return _err(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
