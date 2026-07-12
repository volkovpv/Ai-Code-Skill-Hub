#!/usr/bin/env python3
"""Validate the whole library (equivalent to ``skillctl validate``). CI helper."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from skill_library.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["validate"]))
