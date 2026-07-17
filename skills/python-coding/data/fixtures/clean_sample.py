"""Reference of the target style: strictly-typed, framework-free Python.

The convention checker reports zero findings for this file.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from typing import Final, NewType, Protocol, assert_never

# --- Branded identifier ------------------------------------------------------
UserId = NewType("UserId", str)

_USER_ID_RE: Final = re.compile(r"[a-z0-9-]{4,64}")


class InvalidUserIdError(ValueError):
    """Raised when a raw string does not conform to the user-id format."""

    code: Final = "invalid_user_id"


def parse_user_id(raw: str) -> UserId:
    """Validate raw input and brand it as a UserId at the boundary."""
    if _USER_ID_RE.fullmatch(raw) is None:
        raise InvalidUserIdError(f"not a user id: {raw!r}")
    return UserId(raw)


# --- Closed set: an enum, never loose strings --------------------------------
class UserStatus(enum.StrEnum):
    """Lifecycle states a user account can be in."""

    ACTIVE = "active"
    BLOCKED = "blocked"


# --- Typed error with a stable code and a cause-preserving wrap --------------
class LookupFailedError(Exception):
    """Raised when the user source cannot answer a lookup."""

    code: Final = "lookup_failed"


@dataclass(frozen=True, slots=True)
class User:
    """Immutable snapshot of a user account."""

    id: UserId
    status: UserStatus


class UserSource(Protocol):
    """Minimal structural seam a user lookup depends on."""

    def find_by_id(self, user_id: UserId) -> User | None: ...


# --- Errors: narrow catch, wrap once at the source, keep the cause -----------
def get_user(source: UserSource, user_id: UserId) -> User:
    """Fetch a user or raise a typed error with the original cause chained."""
    try:
        user = source.find_by_id(user_id)
    except OSError as err:
        raise LookupFailedError(f"lookup failed for {user_id}") from err
    if user is None:
        raise LookupFailedError(f"user {user_id} not found")
    return user


# --- Exhaustive match over a closed set --------------------------------------
def describe(status: UserStatus) -> str:
    """Human-readable label for every status; new members break this match."""
    match status:
        case UserStatus.ACTIVE:
            return "active account"
        case UserStatus.BLOCKED:
            return "blocked account"
        case _:
            assert_never(status)
