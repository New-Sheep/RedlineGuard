"""Background playbook import: extract + security + propose with progress."""

from __future__ import annotations

import logging
import sys
import threading

from django.conf import settings
from django.db import close_old_connections

from apps.review.models import PlaybookImport
from apps.review.services.playbook_import import run_import_and_propose

logger = logging.getLogger(__name__)


def _import_sync() -> bool:
    if getattr(settings, "PLAYBOOK_IMPORT_SYNC", False):
        return True
    if getattr(settings, "ANALYZE_SYNC", False):
        return True
    return "test" in sys.argv


def run_import_job(import_id) -> None:
    close_old_connections()
    try:
        imp = PlaybookImport.objects.get(pk=import_id)
        imp.status = PlaybookImport.Status.PROCESSING
        imp.error_message = ""
        imp.save(update_fields=["status", "error_message"])
        run_import_and_propose(imp)
        imp.refresh_from_db()
        if imp.status == PlaybookImport.Status.PROPOSED:
            imp.set_progress(PlaybookImport.ProgressStep.DONE, "Rules ready to review")
        elif imp.status == PlaybookImport.Status.HALTED:
            imp.set_progress(PlaybookImport.ProgressStep.DONE, "Security halt")
        elif imp.status == PlaybookImport.Status.FAILED:
            imp.set_progress(PlaybookImport.ProgressStep.DONE, "Failed")
    except Exception as exc:  # noqa: BLE001
        logger.exception("playbook import job failed for %s", import_id)
        close_old_connections()
        try:
            imp = PlaybookImport.objects.get(pk=import_id)
            imp.status = PlaybookImport.Status.FAILED
            imp.error_message = str(exc)
            imp.progress_step = PlaybookImport.ProgressStep.DONE
            imp.progress_label = "Failed"
            imp.save(
                update_fields=[
                    "status",
                    "error_message",
                    "progress_step",
                    "progress_label",
                ]
            )
        except PlaybookImport.DoesNotExist:
            pass
    finally:
        close_old_connections()


def start_import_async(imp: PlaybookImport) -> None:
    """Mark processing and start import (thread, or sync under tests)."""
    imp.status = PlaybookImport.Status.PROCESSING
    imp.progress_step = PlaybookImport.ProgressStep.QUEUED
    imp.progress_label = "Queued"
    imp.error_message = ""
    imp.save(
        update_fields=[
            "status",
            "progress_step",
            "progress_label",
            "error_message",
        ]
    )
    if _import_sync():
        run_import_job(imp.pk)
        return
    thread = threading.Thread(
        target=run_import_job,
        args=(imp.pk,),
        daemon=True,
        name=f"playbook-import-{imp.pk}",
    )
    thread.start()
