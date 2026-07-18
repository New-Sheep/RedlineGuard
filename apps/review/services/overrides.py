"""Playbook overrides (Journey B2) — append-only exceptions; never rewrite golden playbook."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from django.conf import settings


def overrides_path() -> Path:
    return Path(
        getattr(settings, "PLAYBOOK_OVERRIDES_PATH", settings.DATA_DIR / "playbook_overrides.json")
    )


def load_overrides() -> dict[str, Any]:
    path = overrides_path()
    if not path.is_file():
        return {"version": 1, "overrides": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if "overrides" not in data:
        data["overrides"] = []
    return data


def suppressed_rule_ids(data: dict[str, Any] | None = None) -> set[str]:
    data = data or load_overrides()
    out: set[str] = set()
    for row in data.get("overrides") or []:
        rid = (row.get("playbook_rule_id") or "").strip()
        if rid and row.get("action") in ("accept_as_is", "override"):
            out.add(rid)
    return out


def append_override(
    *,
    playbook_rule_id: str,
    contract_id: str = "",
    reason: str = "",
    clause_excerpt: str = "",
) -> dict[str, Any]:
    """Append an accept-as-is exception. Does not touch playbook_config.json."""
    path = overrides_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_overrides()
    entry = {
        "playbook_rule_id": playbook_rule_id,
        "action": "accept_as_is",
        "reason": reason or "Override & accept as-is",
        "contract_id": contract_id,
        "clause_excerpt": (clause_excerpt or "")[:500],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    data.setdefault("overrides", []).append(entry)
    data["version"] = int(data.get("version") or 1)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return entry


def merge_playbook_with_overrides(playbook: dict[str, Any]) -> dict[str, Any]:
    """Return a playbook copy with overridden rules removed from compare."""
    merged = deepcopy(playbook)
    skip = suppressed_rule_ids()
    if not skip:
        return merged
    rules = [r for r in (merged.get("rules") or []) if r.get("id") not in skip]
    merged["rules"] = rules
    merged["empty"] = not bool(rules)
    merged["overrides_applied"] = sorted(skip)
    return merged
