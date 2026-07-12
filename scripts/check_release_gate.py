#!/usr/bin/env python3
"""check_release_gate.py — гейт релизной дисциплины «версия ↔ изменения кода».

Сравнивает изменения с последнего релизного тега (``vX.Y.Z``) с текущей
версией из ``pyproject.toml`` и проверяет три правила:

1. Изменился используемый код → версия обязана быть поднята (иначе мерж в
   main не даст релиза, а изменения уйдут «в никуда»).
2. Изменения только в инфраструктуре (тесты, CI, документация) → версия
   обязана остаться прежней: инфраструктурные правки не публикуются релизом.
3. Версия растёт монотонно — откат версии назад запрещён.

«Используемый код» — то, что получает потребитель библиотеки:
``skills/``, ``src/``, ``scripts/``, ``templates/``, ``skills.yaml``,
``pyproject.toml``, ``LICENSE``. Всё остальное (``__test__/``, ``.github/``,
``README.md``, ``CHANGELOG.md``, ``AGENTS.md`` и т.п.) — инфраструктура.
В файлах-носителях версии (pyproject.toml, __init__.py) строки самой версии
не считаются изменением кода — иначе любой bump сам себя оправдывал бы.

Если релизных тегов ещё нет, гейт всегда проходит: базовая линия ``0.0.0``
живёт без релиза, а первый bump создаст первый тег.

Запуск: ``python3 scripts/check_release_gate.py [--root DIR]``.
Требует полной git-истории с тегами (в CI — checkout с fetch-depth: 0).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_version_drift import read_pyproject_version  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

# Каталоги — со слэшем на конце, файлы — точным именем.
RELEASE_PATHS = (
    "skills/",
    "src/",
    "scripts/",
    "templates/",
    "skills.yaml",
    "pyproject.toml",
    "LICENSE",
)

# Файлы-носители версии: строки, совпадающие с шаблоном, не считаются
# изменением используемого кода.
VERSION_LINE_RE = {
    "pyproject.toml": re.compile(r'^\s*version\s*=\s*"[^"]*"\s*$'),
    "src/skill_library/__init__.py": re.compile(r'^__version__\s*=\s*"[^"]*"\s*$'),
}

TAG_RE = re.compile(r"^v\d+(\.\d+)*$")


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def parse_version(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def last_release_tag(root: Path) -> str | None:
    """Старший (по SemVer) релизный тег, достижимый из HEAD."""
    tags = [
        tag
        for tag in git(root, "tag", "--list", "v*", "--merged", "HEAD").splitlines()
        if TAG_RE.match(tag)
    ]
    if not tags:
        return None
    return max(tags, key=lambda tag: parse_version(tag[1:]))


def is_release_relevant(root: Path, tag: str, path: str) -> bool:
    """Считается ли изменение файла изменением используемого кода."""
    if not any(
        path.startswith(prefix) if prefix.endswith("/") else path == prefix
        for prefix in RELEASE_PATHS
    ):
        return False
    version_line = VERSION_LINE_RE.get(path)
    if version_line is None:
        return True
    # Носитель версии: смотрим содержимое диффа без строк самой версии.
    diff = git(root, "diff", tag, "HEAD", "--", path)
    for line in diff.splitlines():
        if line.startswith(("+++", "---")) or not line.startswith(("+", "-")):
            continue
        if not version_line.match(line[1:]):
            return True
    return False


def check(root: Path) -> list[str]:
    """Вернуть список нарушений релизной дисциплины; пустой список — всё ок."""
    version = read_pyproject_version(root)
    tag = last_release_tag(root)
    if tag is None:
        return []
    released = tag[1:]

    changed = [
        path
        for path in git(root, "diff", "--name-only", tag, "HEAD").splitlines()
        if path
    ]
    relevant = [path for path in changed if is_release_relevant(root, tag, path)]

    problems: list[str] = []
    if relevant and version == released:
        listing = ", ".join(relevant[:10])
        problems.append(
            f"used code changed since {tag} ({listing}) but version is still "
            f"{released} — bump the version in pyproject.toml, __init__.py "
            "and CHANGELOG.md"
        )
    if not relevant and version != released:
        problems.append(
            f"only infrastructure changed since {tag} — version must stay "
            f"{released}, but pyproject.toml says {version}; no release is "
            "published for infra-only changes"
        )
    if relevant and version != released and parse_version(version) < parse_version(released):
        problems.append(
            f"version went backwards: {version} < already released {released}"
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    root = args.root.resolve()

    problems = check(root)
    if problems:
        for problem in problems:
            print(f"FAIL(release-gate): {problem}", file=sys.stderr)
        return 1

    tag = last_release_tag(root)
    baseline = tag or "no release tags yet (baseline)"
    print(f"  ok (rel)  version {read_pyproject_version(root)} vs {baseline}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
