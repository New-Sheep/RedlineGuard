"""Playbook JSON auditor - validate rules before Activate (Sprint 3)."""

from __future__ import annotations

from typing import Any


def audit_playbook(doc: dict[str, Any]) -> dict[str, Any]:
    """Return {ok, errors[], warnings[], rule_count, duplicate_ids[]}."""
    errors: list[str] = []
    warnings: list[str] = []
    rules = list(doc.get("rules") or [])
    ids: list[str] = []
    seen: set[str] = set()
    duplicates: list[str] = []

    if not (doc.get("name") or "").strip():
        warnings.append("Playbook name is empty.")

    for i, r in enumerate(rules):
        rid = str(r.get("id") or "").strip()
        if not rid:
            errors.append(f"Rule #{i + 1}: missing id.")
        else:
            if rid in seen:
                duplicates.append(rid)
                errors.append(f"Duplicate rule id: {rid}")
            seen.add(rid)
            ids.append(rid)
        if not (r.get("preferred") or "").strip():
            errors.append(f"Rule {rid or i + 1}: missing preferred.")
        if not (r.get("hard_ceiling") or "").strip():
            warnings.append(f"Rule {rid or i + 1}: missing hard_ceiling.")
        needles = r.get("match_any") or []
        if not needles:
            warnings.append(f"Rule {rid or i + 1}: empty match_any - may never flag.")
        clause = (r.get("clause_type") or "").strip()
        if not clause:
            warnings.append(f"Rule {rid or i + 1}: missing clause_type.")

    if not rules:
        errors.append("No rules in playbook.")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "rule_count": len(rules),
        "duplicate_ids": duplicates,
        "rule_ids": ids,
    }
