"""Configuration layer: the single place allowed to read os.environ.

Scanned by path (a *_config.py name) the checker stays silent; piped
through stdin, with no path for context, it flags the env reads — the
documented limitation of path-based layer detection.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

_DEFAULT_DATABASE_URL = "postgres://localhost/app"
_DEFAULT_PORT = "3000"


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Typed, immutable snapshot of the process environment."""

    database_url: str
    port: int


def load_config() -> AppConfig:
    """Read and validate the environment once, at startup."""
    raw_url = os.environ.get("DATABASE_URL")
    raw_port = os.environ.get("PORT")
    return AppConfig(
        database_url=raw_url if raw_url is not None else _DEFAULT_DATABASE_URL,
        port=int(raw_port if raw_port is not None else _DEFAULT_PORT),
    )
