"""Time abstraction.

All timestamps in the platform are UTC ISO-8601 strings. Centralising "now"
behind a small interface keeps timestamps consistent and makes tests
deterministic (inject a ``FixedClock``) instead of patching ``datetime``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol


def utcnow_iso() -> str:
    """Current UTC time as an ISO-8601 string with timezone (seconds precision)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Clock(Protocol):
    """Anything that can tell the time as an ISO-8601 UTC string."""

    def now_iso(self) -> str: ...


class SystemClock:
    """Production clock — wraps the wall clock."""

    def now_iso(self) -> str:
        return utcnow_iso()


class FixedClock:
    """Test clock — always returns the same instant."""

    def __init__(self, instant: str) -> None:
        self._instant = instant

    def now_iso(self) -> str:
        return self._instant
