#!/usr/bin/env python3
"""bump_version.py — единственный правильный способ поднять версию проекта.

Атомарно проставляет новую версию во всех файлах-носителях:

- ``pyproject.toml`` — [project].version (источник истины);
- ``src/skill_library/__init__.py`` — ``__version__``;
- ``CHANGELOG.md`` — вставляет заготовку записи ``## [X.Y.Z] — YYYY-MM-DD``
  перед предыдущей записью; текст изменений вписывается вручную;
- ``uv.lock`` (если присутствует) — версия пакета проекта. Правится тем же
  текстовым способом, без вызова ``uv``: скрипт остаётся stdlib-only и
  офлайн, а результат байт-в-байт совпадает с тем, что записал бы
  ``uv lock``. Иначе lock отставал бы от pyproject на один шаг: ``uv run``
  фиксирует lock ДО запуска скрипта.

После правки сам прогоняет гейт дрейфа (scripts/check_version_drift.py) и
падает, если файлы разошлись. Версию руками в трёх файлах не правим —
и разработчик, и агент пользуются только этим скриптом (см. AGENTS.md
«Release discipline» и README «Версия проекта и авторелизы на GitHub»).

Запуск:
    python3 scripts/bump_version.py 0.0.1        # явная версия
    python3 scripts/bump_version.py --patch      # 0.0.0 -> 0.0.1
    python3 scripts/bump_version.py --minor      # 0.0.1 -> 0.1.0
    python3 scripts/bump_version.py --major      # 0.1.0 -> 1.0.0

Новая версия обязана быть строго больше текущей (SemVer, монотонный рост).
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_version_drift import VERSION_RE, check, read_pyproject_version  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

CHANGELOG_STUB = """## [{version}] — {date}

- TODO: опишите изменения этой версии (текст станет release notes на GitHub).

"""


def parse_version(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def next_version(current: str, part: str) -> str:
    major, minor, patch = (list(parse_version(current)) + [0, 0, 0])[:3]
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def _substitute(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    new_text, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"ERROR: no version line matched in {path}")
    path.write_text(new_text, encoding="utf-8")


def _project_name(root: Path) -> str:
    """Имя пакета из pyproject.toml, нормализованное по правилам uv (PEP 503)."""
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^name\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if match is None:
        raise SystemExit("ERROR: no [project].name found in pyproject.toml")
    return re.sub(r"[-_.]+", "-", match.group(1)).lower()


def bump(root: Path, new_version: str, date: datetime.date) -> None:
    current = read_pyproject_version(root)
    if not VERSION_RE.match(new_version):
        raise SystemExit(f"ERROR: '{new_version}' is not a valid X.Y.Z version")
    if parse_version(new_version) <= parse_version(current):
        raise SystemExit(
            f"ERROR: new version {new_version} must be greater than current {current}"
        )

    _substitute(
        root / "pyproject.toml",
        r'^version\s*=\s*"[^"]*"',
        f'version = "{new_version}"',
    )
    _substitute(
        root / "src" / "skill_library" / "__init__.py",
        r'^__version__\s*=\s*"[^"]*"',
        f'__version__ = "{new_version}"',
    )

    # uv.lock опционален (zero-tooling fallback живёт без uv), но если он
    # есть — версия пакета проекта обязана совпасть с pyproject.toml.
    uv_lock = root / "uv.lock"
    if uv_lock.is_file():
        _substitute(
            uv_lock,
            rf'^(name = "{re.escape(_project_name(root))}"\nversion) = "[^"]*"',
            rf'\1 = "{new_version}"',
        )

    changelog = root / "CHANGELOG.md"
    text = changelog.read_text(encoding="utf-8")
    match = re.search(r"^## \[", text, re.MULTILINE)
    if match is None:
        raise SystemExit("ERROR: CHANGELOG.md has no '## [X.Y.Z]' entry to insert before")
    stub = CHANGELOG_STUB.format(version=new_version, date=date.isoformat())
    changelog.write_text(text[: match.start()] + stub + text[match.start():], encoding="utf-8")

    problems = check(root)
    if problems:  # самопроверка: после bump дрейфа быть не может
        for problem in problems:
            print(f"FAIL(bump): {problem}", file=sys.stderr)
        raise SystemExit(1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", nargs="?", help="явная новая версия X.Y.Z")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--patch", action="store_true")
    group.add_argument("--minor", action="store_true")
    group.add_argument("--major", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    part = "major" if args.major else "minor" if args.minor else "patch" if args.patch else None
    if bool(args.version) == bool(part):
        parser.error("укажите либо явную версию, либо ровно один из --patch/--minor/--major")

    root = args.root.resolve()
    current = read_pyproject_version(root)
    new_version = args.version or next_version(current, part)
    bump(root, new_version, datetime.date.today())

    print(f"Версия поднята: {current} -> {new_version}")
    print("Осталось: заполнить запись в CHANGELOG.md (строка TODO) — "
          "её текст станет release notes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
