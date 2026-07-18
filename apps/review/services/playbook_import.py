"""Playbook import: extract PDF + security fence + propose rules + activate."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from apps.review.models import PlaybookImport
from apps.review.services.playbook_bootstrap import PlaybookDocument, get_bootstrap
from scratch.poc01_extract.extract import extract_pdf
from scratch.poc02_security.security import (
    detect_playbook_injection,
    fence,
    sanitize,
)


def resolve_playbook_path(imp: PlaybookImport) -> Path:
    if imp.source == PlaybookImport.Source.SAMPLE:
        if not imp.sample_key:
            raise ValueError("sample_key required")
        path = (Path(settings.PLAYBOOK_CORPUS_DIR) / imp.sample_key).resolve()
        root = Path(settings.PLAYBOOK_CORPUS_DIR).resolve()
        if not str(path).startswith(str(root)) or not path.is_file():
            raise FileNotFoundError(f"Sample not found: {imp.sample_key}")
        return path
    if not imp.file:
        raise ValueError("Uploaded playbook has no file")
    return Path(imp.file.path)


def run_import_and_propose(imp: PlaybookImport) -> PlaybookImport:
    try:
        if imp.status != PlaybookImport.Status.PROCESSING:
            imp.status = PlaybookImport.Status.PROCESSING
            imp.save(update_fields=["status"])

        imp.set_progress(
            PlaybookImport.ProgressStep.READING, "Reading playbook PDF"
        )
        path = resolve_playbook_path(imp)
        extracted = extract_pdf(path)
        raw = extracted.get("text") or ""
        cleaned = sanitize(raw)
        imp.extracted_text = cleaned
        imp.save(update_fields=["extracted_text"])

        imp.set_progress(
            PlaybookImport.ProgressStep.SECURITY, "Security check"
        )
        detection = detect_playbook_injection(cleaned)
        if detection.get("halt"):
            # Fence for audit; never propose rules from hostile playbook
            _ = fence(cleaned)
            matches = detection.get("matches") or []
            imp.proposed_json = {
                "security": {
                    "halt": True,
                    "matches": matches,
                    "summary": detection.get("summary"),
                }
            }
            imp.status = PlaybookImport.Status.HALTED
            imp.error_message = (
                "Security halt: this playbook PDF looks like prompt injection "
                f"or instruction override ({', '.join(matches[:3]) or 'flagged'}). "
                "Rules were not proposed."
            )
            imp.progress_step = PlaybookImport.ProgressStep.DONE
            imp.progress_label = "Security halt"
            imp.save()
            return imp

        imp.set_progress(
            PlaybookImport.ProgressStep.PROPOSING, "Proposing rules from playbook"
        )
        doc = get_bootstrap().propose(cleaned, source_name=imp.filename)
        imp.proposed_json = doc.model_dump()
        imp.status = PlaybookImport.Status.PROPOSED
        imp.error_message = ""
        imp.progress_step = PlaybookImport.ProgressStep.DONE
        imp.progress_label = "Rules ready to review"
    except Exception as exc:  # noqa: BLE001
        imp.status = PlaybookImport.Status.FAILED
        imp.error_message = str(exc)
        imp.progress_step = PlaybookImport.ProgressStep.DONE
        imp.progress_label = "Failed"
    imp.save()
    return imp


def load_active_playbook() -> dict:
    path = Path(settings.PLAYBOOK_PATH)
    if not path.is_file():
        return {
            "version": 1,
            "name": "(none — using empty playbook)",
            "preferred_governing_law": "",
            "rules": [],
            "empty": True,
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    data["empty"] = not bool(data.get("rules"))
    return data


def document_from_form(
    *,
    name: str,
    preferred_governing_law: str,
    rules: list[dict],
) -> PlaybookDocument:
    return PlaybookDocument(
        version=1,
        name=name.strip() or "Imported playbook",
        preferred_governing_law=preferred_governing_law.strip() or "England and Wales",
        rules=rules,
    )


def activate_playbook(imp: PlaybookImport, doc: PlaybookDocument) -> Path:
    """Backup golden playbook then write new JSON. Marks import activated."""
    if imp.status == PlaybookImport.Status.HALTED:
        raise ValueError("Cannot activate a security-halted playbook import")
    target = Path(settings.PLAYBOOK_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        bak = target.with_suffix(target.suffix + ".bak")
        shutil.copy2(target, bak)
    payload = doc.model_dump()
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    imp.proposed_json = payload
    imp.status = PlaybookImport.Status.ACTIVATED
    imp.activated_at = timezone.now()
    imp.error_message = ""
    imp.save()
    return target
