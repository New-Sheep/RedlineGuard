"""Background NVIDIA/Ollama upgrade after instant Fake playbook propose."""

from __future__ import annotations

import logging
import threading

from django.conf import settings
from django.db import close_old_connections

from apps.review.models import PlaybookImport

logger = logging.getLogger(__name__)


def _upgrade_sync() -> bool:
    """Only force sync when explicitly requested (not tied to Django tests)."""
    return bool(getattr(settings, "PLAYBOOK_UPGRADE_SYNC", False))


def _set_upgrade_status(imp: PlaybookImport, status: str) -> None:
    proposed = dict(imp.proposed_json or {})
    meta = dict(proposed.get("_meta") or {})
    meta["llm_upgrade"] = status
    proposed["_meta"] = meta
    imp.proposed_json = proposed
    imp.save(update_fields=["proposed_json"])


def apply_llm_upgrade(imp: PlaybookImport, doc, *, meta: dict) -> bool:
    """Replace Fake draft with LLM rules if still eligible. Returns True if applied."""
    imp.refresh_from_db()
    if imp.status != PlaybookImport.Status.PROPOSED:
        return False
    proposed = dict(imp.proposed_json or {})
    cur_meta = dict(proposed.get("_meta") or {})
    if cur_meta.get("llm_upgrade") != "pending":
        return False
    if cur_meta.get("user_touched"):
        _set_upgrade_status(imp, "skipped")
        return False

    new_json = doc.model_dump()
    # Preserve origin / starter / manual flags; refresh upgrade meta.
    keep = {
        k: v
        for k, v in cur_meta.items()
        if k
        in (
            "origin",
            "proposed_not_active",
            "contract_count",
            "draft_briefs",
        )
    }
    keep["llm_upgrade"] = "done"
    keep["user_touched"] = False
    keep["proposal_source"] = meta["proposal_source"]
    new_json["_meta"] = keep
    imp.proposed_json = new_json
    imp.proposal_source = meta["proposal_source"]
    imp.proposal_model = meta["proposal_model"]
    imp.save(
        update_fields=["proposed_json", "proposal_source", "proposal_model"]
    )
    return True


def run_llm_upgrade_job(import_id) -> None:
    close_old_connections()
    try:
        from apps.review.services.playbook_bootstrap_llm import (
            LlmPlaybookBootstrap,
            bootstrap_meta,
            wants_llm_upgrade,
        )

        if not wants_llm_upgrade():
            return

        imp = PlaybookImport.objects.get(pk=import_id)
        if imp.status != PlaybookImport.Status.PROPOSED:
            return
        meta0 = (imp.proposed_json or {}).get("_meta") or {}
        if meta0.get("llm_upgrade") != "pending":
            return
        if meta0.get("user_touched"):
            _set_upgrade_status(imp, "skipped")
            return

        text = imp.extracted_text or ""
        source_name = imp.filename or "playbook"
        if imp.source == PlaybookImport.Source.STARTER:
            n = len(imp.starter_manifest or [])
            source_name = f"starter from {n} past contracts"

        doc = LlmPlaybookBootstrap().propose(
            text, source_name=source_name, fallback_to_fake=False
        )
        if imp.source == PlaybookImport.Source.STARTER:
            n = len(imp.starter_manifest or [])
            doc.name = f"Starter playbook (from {n} past contracts)"

        applied = apply_llm_upgrade(imp, doc, meta=bootstrap_meta())
        if applied:
            logger.info("playbook LLM upgrade applied for %s", import_id)
        else:
            logger.info("playbook LLM upgrade skipped for %s", import_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("playbook LLM upgrade failed for %s: %s", import_id, exc)
        close_old_connections()
        try:
            imp = PlaybookImport.objects.get(pk=import_id)
            meta = (imp.proposed_json or {}).get("_meta") or {}
            if meta.get("llm_upgrade") == "pending" and not meta.get("user_touched"):
                _set_upgrade_status(imp, "skipped")
        except PlaybookImport.DoesNotExist:
            pass
    finally:
        close_old_connections()


def start_llm_upgrade_async(imp: PlaybookImport) -> None:
    """After Fake propose, optionally refine with real LLM in the background."""
    from apps.review.services.playbook_bootstrap_llm import wants_llm_upgrade

    if not wants_llm_upgrade():
        return
    proposed = dict(imp.proposed_json or {})
    meta = dict(proposed.get("_meta") or {})
    if meta.get("llm_upgrade") != "pending":
        return

    if _upgrade_sync():
        run_llm_upgrade_job(imp.pk)
        return
    thread = threading.Thread(
        target=run_llm_upgrade_job,
        args=(imp.pk,),
        daemon=True,
        name=f"playbook-upgrade-{imp.pk}",
    )
    thread.start()
