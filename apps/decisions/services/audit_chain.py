"""Hash-chain helpers for AuditEvent (vision lite — local SQLite demo ≠ HSM)."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _canonical_payload(payload: dict[str, Any] | None) -> str:
    return json.dumps(payload or {}, sort_keys=True, default=str)


def compute_entry_hash(
    *,
    kind: str,
    summary: str,
    payload: dict[str, Any] | None,
    prev_hash: str,
) -> str:
    blob = f"{prev_hash}|{kind}|{summary}|{_canonical_payload(payload)}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


GENESIS = "0" * 64


def verify_chain(events_oldest_first: list) -> tuple[bool, str]:
    """events ordered by created_at ascending. Returns (ok, message)."""
    prev = GENESIS
    for i, ev in enumerate(events_oldest_first):
        expected_prev = ev.prev_hash or GENESIS
        if expected_prev != prev:
            return False, f"Break at index {i}: prev_hash mismatch"
        expected = compute_entry_hash(
            kind=ev.kind,
            summary=ev.summary or "",
            payload=ev.payload or {},
            prev_hash=expected_prev,
        )
        if (ev.entry_hash or "") != expected:
            return False, f"Break at index {i}: entry_hash mismatch for {ev.id}"
        prev = ev.entry_hash or prev
    return True, f"OK ({len(events_oldest_first)} events)"
