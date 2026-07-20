"""Session-lite analyze rate limit (demable, not enterprise WAF)."""

from __future__ import annotations

import time

from django.conf import settings


def check_analyze_rate(session) -> tuple[bool, str]:
    """Return (ok, error_message). Mutates session timestamps list."""
    limit = int(getattr(settings, "MAX_ANALYZES_PER_HOUR", 30))
    now = time.time()
    window = 3600.0
    key = "analyze_timestamps"
    stamps = [float(t) for t in (session.get(key) or []) if now - float(t) < window]
    if len(stamps) >= limit:
        return False, f"Rate limit: max {limit} analyzes per hour. Try again later."
    stamps.append(now)
    session[key] = stamps
    session.modified = True
    return True, ""
