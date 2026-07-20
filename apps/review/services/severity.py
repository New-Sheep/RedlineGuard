"""Severity ordering: High → Medium → Low (strict priority)."""

from __future__ import annotations

from typing import Any, Callable, TypeVar

T = TypeVar("T")

# Lower rank = higher priority (sort ascending).
SEVERITY_RANK: dict[str, int] = {
    "high": 0,
    "medium": 1,
    "low": 2,
}


def severity_rank(severity: str | None) -> int:
    return SEVERITY_RANK.get((severity or "medium").lower().strip(), 3)


def sort_by_severity(
    items: list[T],
    *,
    get_severity: Callable[[T], str | None],
    tiebreak: Callable[[T], Any] | None = None,
) -> list[T]:
    """Stable High → Medium → Low, then optional tiebreak (e.g. rule id)."""

    def key(item: T) -> tuple:
        sev = severity_rank(get_severity(item))
        if tiebreak is None:
            return (sev,)
        return (sev, tiebreak(item))

    return sorted(items, key=key)
