"""Injectable UTC clocks for time-dependent runtime rules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol


class Clock(Protocol):
    def now(self) -> str:
        """Return the current UTC instant as an ISO 8601 string."""


class SystemClock:
    def now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")


class FixedClock:
    def __init__(self, instant: str):
        self._instant = datetime.fromisoformat(instant.replace("Z", "+00:00")).astimezone(timezone.utc)

    def now(self) -> str:
        return self._instant.isoformat(timespec="seconds")

    def advance(self, seconds: float) -> None:
        self._instant += timedelta(seconds=seconds)
