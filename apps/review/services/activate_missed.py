"""Merge a proposed missed-clause rule into the active golden playbook."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from apps.review.services.playbook_audit import audit_playbook
from apps.review.services.playbook_import import load_active_playbook


def activate_missed_rule(rule: dict) -> Path:
    """Append rule to golden playbook after audit. Snapshots prior file."""
    playbook = load_active_playbook()
    if playbook.get("empty"):
        playbook = {
            "version": 1,
            "name": "Company playbook",
            "preferred_governing_law": "England and Wales",
            "rules": [],
        }
    rules = list(playbook.get("rules") or [])
    rid = str(rule.get("id") or "")
    if any(str(r.get("id")) == rid for r in rules):
        raise ValueError(f"Rule id already exists: {rid}")
    rules.append(rule)
    playbook["rules"] = rules
    playbook["empty"] = False
    report = audit_playbook(playbook)
    if not report["ok"]:
        raise ValueError("Playbook audit failed: " + "; ".join(report["errors"][:5]))

    target = Path(settings.PLAYBOOK_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    versions_dir = Path(settings.MEDIA_ROOT) / "playbooks" / "versions"
    versions_dir.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        stamp = timezone.now().strftime("%Y%m%dT%H%M%SZ")
        shutil.copy2(target, versions_dir / f"playbook_{stamp}.json")
        shutil.copy2(target, target.with_suffix(target.suffix + ".bak"))
    target.write_text(json.dumps(playbook, indent=2) + "\n", encoding="utf-8")
    return target
