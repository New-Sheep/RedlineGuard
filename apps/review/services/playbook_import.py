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


def _resolve_starter_paths(imp: PlaybookImport) -> list[tuple[str, Path]]:
    """Return (label, path) for each starter contract."""
    media_root = Path(settings.MEDIA_ROOT).resolve()
    scratch = Path(settings.SCRATCH_CORPUS_DIR).resolve()
    out: list[tuple[str, Path]] = []
    for item in imp.starter_manifest or []:
        kind = (item.get("kind") or "").strip()
        label = item.get("name") or item.get("key") or "contract"
        if kind == "sample":
            key = item.get("key") or ""
            path = (scratch / key).resolve()
            if not str(path).startswith(str(scratch)) or not path.is_file():
                raise FileNotFoundError(f"Starter sample not found: {key}")
            out.append((label, path))
        elif kind == "upload":
            rel = item.get("rel") or ""
            path = (media_root / rel).resolve()
            if not str(path).startswith(str(media_root)) or not path.is_file():
                raise FileNotFoundError(f"Starter upload missing: {rel}")
            out.append((label, path))
        else:
            raise ValueError(f"Unknown starter manifest kind: {kind}")
    if not out:
        raise ValueError("Starter import has empty manifest")
    return out


def _halt_import(imp: PlaybookImport, detection: dict) -> PlaybookImport:
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
        "Security halt: this playbook source looks like prompt injection "
        f"or instruction override ({', '.join(matches[:3]) or 'flagged'}). "
        "Rules were not proposed."
    )
    imp.progress_step = PlaybookImport.ProgressStep.DONE
    imp.progress_label = "Security halt"
    imp.save()
    return imp


def run_import_and_propose(imp: PlaybookImport) -> PlaybookImport:
    try:
        if imp.status != PlaybookImport.Status.PROCESSING:
            imp.status = PlaybookImport.Status.PROCESSING
            imp.save(update_fields=["status"])

        if imp.source == PlaybookImport.Source.STARTER:
            return _run_starter_and_propose(imp)

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
            _ = fence(cleaned)
            return _halt_import(imp, detection)

        imp.set_progress(
            PlaybookImport.ProgressStep.PROPOSING, "Proposing rules from playbook"
        )
        doc = get_bootstrap().propose(cleaned, source_name=imp.filename)
        from apps.review.services.playbook_bootstrap_llm import bootstrap_meta

        meta = bootstrap_meta()
        imp.proposed_json = doc.model_dump()
        imp.proposal_source = meta["proposal_source"]
        imp.proposal_model = meta["proposal_model"]
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


def _run_starter_and_propose(imp: PlaybookImport) -> PlaybookImport:
    """E2: extract 3–5 past contracts, propose starter playbook."""
    try:
        imp.set_progress(
            PlaybookImport.ProgressStep.READING, "Reading past contracts"
        )
        chunks: list[str] = []
        for label, path in _resolve_starter_paths(imp):
            extracted = extract_pdf(path)
            text = sanitize(extracted.get("text") or "")
            liked = True
            for item in imp.starter_manifest or []:
                if item.get("name") == label or item.get("key") == label:
                    liked = bool(item.get("liked", True))
                    break
            tag = "liked" if liked else "disliked"
            chunks.append(f"=== PAST CONTRACT ({tag}): {label} ===\n{text}\n")

        combined = "\n".join(chunks)
        imp.extracted_text = combined
        imp.save(update_fields=["extracted_text"])

        imp.set_progress(
            PlaybookImport.ProgressStep.SECURITY, "Security check"
        )
        detection = detect_playbook_injection(combined)
        if detection.get("halt"):
            _ = fence(combined)
            return _halt_import(imp, detection)

        n = len(imp.starter_manifest or [])
        imp.set_progress(
            PlaybookImport.ProgressStep.PROPOSING,
            "Proposing starter rules from past contracts",
        )
        doc = get_bootstrap().propose(
            combined, source_name=f"starter from {n} past contracts"
        )
        # Prefer a clear starter name for Activate UI
        doc.name = f"Starter playbook (from {n} past contracts)"
        from apps.review.services.playbook_bootstrap_llm import bootstrap_meta

        meta = bootstrap_meta()
        imp.proposed_json = doc.model_dump()
        # Mark provenance for F28 labels
        imp.proposed_json["_meta"] = {
            "origin": "starter",
            "proposed_not_active": True,
            "contract_count": n,
            "proposal_source": meta["proposal_source"],
        }
        imp.proposal_source = meta["proposal_source"]
        imp.proposal_model = meta["proposal_model"]
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
            "name": "(none - using empty playbook)",
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
    """Version previous golden playbook then write new JSON. Marks import activated."""
    if imp.status == PlaybookImport.Status.HALTED:
        raise ValueError("Cannot activate a security-halted playbook import")
    target = Path(settings.PLAYBOOK_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    versions_dir = Path(settings.MEDIA_ROOT) / "playbooks" / "versions"
    versions_dir.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        bak = target.with_suffix(target.suffix + ".bak")
        shutil.copy2(target, bak)
        stamp = timezone.now().strftime("%Y%m%dT%H%M%SZ")
        shutil.copy2(target, versions_dir / f"playbook_{stamp}.json")
    payload = doc.model_dump()
    # Never write UI-only meta into the golden file
    payload.pop("_meta", None)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    imp.proposed_json = {**payload, "_meta": {"activated": True, "origin": imp.source}}
    imp.status = PlaybookImport.Status.ACTIVATED
    imp.activated_at = timezone.now()
    imp.error_message = ""
    imp.save()
    try:
        from apps.decisions.services.lifecycle import log_audit
        from apps.decisions.models import AuditEvent

        log_audit(
            kind=AuditEvent.Kind.ACTIVATE,
            summary=f"Activated playbook “{payload.get('name') or 'untitled'}”",
            payload={"import_id": str(imp.id), "name": payload.get("name")},
        )
    except Exception:
        pass
    return target


def list_playbook_versions(limit: int = 20) -> list[dict]:
    versions_dir = Path(settings.MEDIA_ROOT) / "playbooks" / "versions"
    if not versions_dir.is_dir():
        return []
    files = sorted(versions_dir.glob("playbook_*.json"), reverse=True)
    out = []
    for p in files[:limit]:
        out.append({"name": p.name, "path": str(p), "mtime": p.stat().st_mtime})
    return out


def restore_playbook_version(filename: str) -> Path:
    """Restore a versioned snapshot over the active playbook (explicit human action)."""
    versions_dir = Path(settings.MEDIA_ROOT) / "playbooks" / "versions"
    src = (versions_dir / Path(filename).name).resolve()
    if not str(src).startswith(str(versions_dir.resolve())) or not src.is_file():
        raise FileNotFoundError(f"Version not found: {filename}")
    target = Path(settings.PLAYBOOK_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        stamp = timezone.now().strftime("%Y%m%dT%H%M%SZ")
        versions_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, versions_dir / f"playbook_pre_restore_{stamp}.json")
        shutil.copy2(target, target.with_suffix(target.suffix + ".bak"))
    shutil.copy2(src, target)
    try:
        from apps.decisions.services.lifecycle import log_audit
        from apps.decisions.models import AuditEvent

        log_audit(
            kind=AuditEvent.Kind.RESTORE,
            summary=f"Restored playbook from {src.name}",
            payload={"version": src.name},
        )
    except Exception:
        pass
    return target
