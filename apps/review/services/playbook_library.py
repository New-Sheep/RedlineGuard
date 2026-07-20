"""Company playbook library: seed, activate/deactivate, rename/delete, combine."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Iterable, Literal
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.review.models import CompanyPlaybook, PlaybookImport
from apps.review.services.playbook_bootstrap import PlaybookDocument, _slug

CombineMode = Literal["union", "intersection"]

_SEV_RANK = {"high": 0, "medium": 1, "low": 2}


def _clause_key(clause_type: str) -> str:
    text = (clause_type or "").strip().lower().replace("-", "_")
    text = re.sub(r"[^a-z0-9_]+", "_", text).strip("_")
    return text or "general"


def _clean_document(doc: dict[str, Any] | PlaybookDocument) -> dict[str, Any]:
    if isinstance(doc, PlaybookDocument):
        payload = doc.model_dump()
    else:
        payload = dict(doc or {})
    payload.pop("_meta", None)
    payload.pop("empty", None)
    payload.setdefault("version", 1)
    payload["name"] = (payload.get("name") or "Untitled playbook").strip() or "Untitled playbook"
    payload["preferred_governing_law"] = (
        payload.get("preferred_governing_law") or "England and Wales"
    ).strip() or "England and Wales"
    payload["rules"] = list(payload.get("rules") or [])
    return payload


def _write_golden(payload: dict[str, Any]) -> Path:
    target = Path(settings.PLAYBOOK_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    versions_dir = Path(settings.MEDIA_ROOT) / "playbooks" / "versions"
    versions_dir.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        bak = target.with_suffix(target.suffix + ".bak")
        shutil.copy2(target, bak)
        stamp = timezone.now().strftime("%Y%m%dT%H%M%SZ")
        shutil.copy2(target, versions_dir / f"playbook_{stamp}.json")
    clean = _clean_document(payload)
    target.write_text(json.dumps(clean, indent=2) + "\n", encoding="utf-8")
    return target


def _write_empty_golden() -> Path:
    return _write_golden(
        {
            "version": 1,
            "name": "(no active playbook)",
            "preferred_governing_law": "",
            "rules": [],
        }
    )


def _audit(kind: str, summary: str, payload: dict | None = None) -> None:
    try:
        from apps.decisions.models import AuditEvent
        from apps.decisions.services.lifecycle import log_audit

        log_audit(
            kind=kind if kind else AuditEvent.Kind.ACTIVATE,
            summary=summary,
            payload=payload or {},
        )
    except Exception:
        pass


def list_playbooks() -> list[CompanyPlaybook]:
    ensure_library_seeded()
    return list(CompanyPlaybook.objects.all())


def get_playbook(pk: UUID | str) -> CompanyPlaybook:
    return get_object_or_404(CompanyPlaybook, pk=pk)


def ensure_library_seeded() -> CompanyPlaybook | None:
    """If library empty and golden has rules, insert one active row."""
    if CompanyPlaybook.objects.exists():
        return None
    path = Path(settings.PLAYBOOK_PATH)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    rules = data.get("rules") or []
    if not rules:
        return None
    doc = _clean_document(data)
    return CompanyPlaybook.objects.create(
        name=doc["name"],
        preferred_governing_law=doc["preferred_governing_law"],
        document=doc,
        is_active=True,
    )


@transaction.atomic
def upsert_from_activation(
    doc: dict[str, Any] | PlaybookDocument,
    *,
    source_import: PlaybookImport | None = None,
    library_id: UUID | str | None = None,
) -> CompanyPlaybook:
    """Upsert library row from Activate and mark it the sole active playbook."""
    payload = _clean_document(doc)
    CompanyPlaybook.objects.filter(is_active=True).update(is_active=False)

    row = None
    if library_id:
        row = CompanyPlaybook.objects.filter(pk=library_id).first()
    if row is None and source_import is not None:
        row = (
            CompanyPlaybook.objects.filter(source_import=source_import)
            .order_by("-updated_at")
            .first()
        )
    if row is None:
        # Prefer updating the previously active name match when re-activating same title
        row = (
            CompanyPlaybook.objects.filter(name=payload["name"], is_active=False)
            .order_by("-updated_at")
            .first()
        )

    if row is None:
        row = CompanyPlaybook(
            name=payload["name"],
            preferred_governing_law=payload["preferred_governing_law"],
            document=payload,
            is_active=True,
            source_import=source_import,
        )
    else:
        row.name = payload["name"]
        row.preferred_governing_law = payload["preferred_governing_law"]
        row.document = payload
        row.is_active = True
        if source_import is not None:
            row.source_import = source_import
    row.save()
    return row


@transaction.atomic
def activate_playbook_record(pk: UUID | str) -> CompanyPlaybook:
    row = get_playbook(pk)
    CompanyPlaybook.objects.filter(is_active=True).exclude(pk=row.pk).update(
        is_active=False
    )
    row.is_active = True
    row.save(update_fields=["is_active", "updated_at"])
    _write_golden(row.document or {})
    _audit(
        "activate",
        f"Activated library playbook “{row.name}”",
        {"playbook_id": str(row.pk), "name": row.name},
    )
    return row


@transaction.atomic
def deactivate_playbook_record(pk: UUID | str) -> CompanyPlaybook:
    row = get_playbook(pk)
    if not row.is_active:
        return row
    row.is_active = False
    row.save(update_fields=["is_active", "updated_at"])
    _write_empty_golden()
    _audit(
        "activate",
        f"Deactivated playbook “{row.name}”. No active company playbook",
        {"playbook_id": str(row.pk), "name": row.name, "deactivated": True},
    )
    return row


def rename_playbook(pk: UUID | str, name: str) -> CompanyPlaybook:
    row = get_playbook(pk)
    new_name = (name or "").strip()
    if not new_name:
        raise ValueError("Playbook name cannot be empty.")
    row.name = new_name[:200]
    doc = dict(row.document or {})
    doc["name"] = row.name
    row.document = doc
    row.preferred_governing_law = doc.get("preferred_governing_law") or row.preferred_governing_law
    row.save()
    if row.is_active:
        _write_golden(row.document)
    return row


@transaction.atomic
def delete_playbook(pk: UUID | str) -> str:
    """Remove a library playbook. If it was active, clear the golden file first.

    Returns the deleted playbook name (for flash messages).
    """
    row = get_playbook(pk)
    name = row.name
    was_active = row.is_active
    if was_active:
        row.is_active = False
        row.save(update_fields=["is_active", "updated_at"])
        _write_empty_golden()
    row.delete()
    _audit(
        "activate",
        f"Deleted playbook “{name}”"
        + (" (was active; reviews have no company rules)" if was_active else ""),
        {"playbook_id": str(pk), "name": name, "was_active": was_active, "deleted": True},
    )
    return name


def create_edit_playbook_import(pk: UUID | str) -> PlaybookImport:
    """Open an existing library playbook in the review/activate form for edits."""
    row = get_playbook(pk)
    doc = _clean_document(row.document or {})
    # Preserve name from library row (document may be slightly stale)
    doc["name"] = row.name or doc.get("name") or "Playbook"
    if row.preferred_governing_law:
        doc["preferred_governing_law"] = row.preferred_governing_law
    doc["_meta"] = {
        "origin": "edit",
        "library_id": str(row.pk),
        "was_active": bool(row.is_active),
        "proposed_not_active": True,
        "proposal_source": "edit",
    }
    return PlaybookImport.objects.create(
        filename=f"Edit: {row.name}"[:200],
        source=PlaybookImport.Source.MANUAL,
        proposed_json=doc,
        proposal_source="edit",
        proposal_model="",
        status=PlaybookImport.Status.PROPOSED,
        progress_step=PlaybookImport.ProgressStep.DONE,
        progress_label="Edit rules, then Activate to save",
        extracted_text="",
        error_message="",
    )


def _pick_better_rule(a: dict, b: dict) -> dict:
    sa = _SEV_RANK.get(str(a.get("severity") or "medium").lower(), 1)
    sb = _SEV_RANK.get(str(b.get("severity") or "medium").lower(), 1)
    if sa != sb:
        return a if sa < sb else b
    pa = len(str(a.get("preferred") or ""))
    pb = len(str(b.get("preferred") or ""))
    return a if pa >= pb else b


def _rules_by_clause(doc: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for rule in doc.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        key = _clause_key(str(rule.get("clause_type") or rule.get("id") or ""))
        existing = out.get(key)
        out[key] = rule if existing is None else _pick_better_rule(existing, rule)
    return out


def _dedupe_ids(rules: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for rule in rules:
        r = dict(rule)
        rid = str(r.get("id") or "").strip() or _slug(r.get("clause_type") or "rule")
        if rid in seen or not re.match(r"^[a-z0-9_]+$", rid):
            rid = _slug(r.get("clause_type") or "rule")
        while rid in seen:
            rid = _slug(r.get("clause_type") or "rule")
        seen.add(rid)
        r["id"] = rid
        out.append(r)
    return out


def combine_playbooks(
    ids: Iterable[UUID | str],
    *,
    mode: CombineMode,
) -> PlaybookImport:
    id_list = [str(i) for i in ids]
    if len(id_list) < 2:
        raise ValueError("Select at least two playbooks to combine.")
    if mode not in ("union", "intersection"):
        raise ValueError("Combine mode must be union or intersection.")

    rows = list(CompanyPlaybook.objects.filter(pk__in=id_list))
    by_id = {str(r.pk): r for r in rows}
    ordered = [by_id[i] for i in id_list if i in by_id]
    if len(ordered) < 2:
        raise ValueError("Select at least two playbooks to combine.")

    maps = [_rules_by_clause(r.document or {}) for r in ordered]
    if mode == "union":
        keys: set[str] = set()
        for m in maps:
            keys |= set(m.keys())
        merged: list[dict] = []
        for key in sorted(keys):
            candidates = [m[key] for m in maps if key in m]
            pick = candidates[0]
            for c in candidates[1:]:
                pick = _pick_better_rule(pick, c)
            merged.append(dict(pick))
    else:
        keys = set(maps[0].keys())
        for m in maps[1:]:
            keys &= set(m.keys())
        merged = [dict(maps[0][k]) for k in sorted(keys)]

    merged = _dedupe_ids(merged)
    first = ordered[0]
    names = " + ".join(r.name for r in ordered[:4])
    if len(ordered) > 4:
        names += "…"
    label = "union" if mode == "union" else "intersection"
    title = f"Combined ({label}): {names}"[:200]
    doc = {
        "version": 1,
        "name": title,
        "preferred_governing_law": first.preferred_governing_law
        or (first.document or {}).get("preferred_governing_law")
        or "England and Wales",
        "rules": merged,
        "_meta": {
            "origin": "manual",
            "proposed_not_active": True,
            "proposal_source": "combine",
            "combine_mode": mode,
            "source_playbook_ids": [str(r.pk) for r in ordered],
        },
    }
    return PlaybookImport.objects.create(
        filename=title,
        source=PlaybookImport.Source.MANUAL,
        proposed_json=doc,
        proposal_source="combine",
        proposal_model="",
        status=PlaybookImport.Status.PROPOSED,
        progress_step=PlaybookImport.ProgressStep.DONE,
        progress_label="Combined draft ready to review",
        extracted_text="",
        error_message="",
    )
