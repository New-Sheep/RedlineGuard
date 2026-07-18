"""Background analyze: extract + pipeline with progress updates."""

from __future__ import annotations

import logging
import sys
import threading

from django.conf import settings
from django.db import close_old_connections

from apps.contracts.models import Contract
from apps.contracts.services.extract import run_extract
from apps.review.services.pipeline import run_pipeline

logger = logging.getLogger(__name__)


def _analyze_sync() -> bool:
    if getattr(settings, "ANALYZE_SYNC", False):
        return True
    return "test" in sys.argv


def run_analyze_job(contract_id) -> None:
    """Run extract + pipeline for a contract (intended for a background thread)."""
    close_old_connections()
    try:
        contract = Contract.objects.get(pk=contract_id)
        contract.status = Contract.Status.PROCESSING
        contract.error_message = ""
        contract.save(update_fields=["status", "error_message"])
        contract.set_progress(Contract.ProgressStep.READING, "Reading document")

        run_extract(contract)
        contract.refresh_from_db()
        if contract.status == Contract.Status.FAILED:
            contract.set_progress(Contract.ProgressStep.DONE, "Failed")
            return

        run_pipeline(contract)
        contract.refresh_from_db()
        if contract.status == Contract.Status.READY:
            contract.set_progress(Contract.ProgressStep.DONE, "Review ready")
        elif contract.status == Contract.Status.HALTED:
            contract.set_progress(Contract.ProgressStep.DONE, "Security halt")
        elif contract.status == Contract.Status.FAILED:
            contract.set_progress(Contract.ProgressStep.DONE, "Failed")
    except Exception as exc:  # noqa: BLE001
        logger.exception("analyze job failed for %s", contract_id)
        close_old_connections()
        try:
            c = Contract.objects.get(pk=contract_id)
            c.status = Contract.Status.FAILED
            c.error_message = str(exc)
            c.progress_step = Contract.ProgressStep.DONE
            c.progress_label = "Failed"
            c.save(
                update_fields=[
                    "status",
                    "error_message",
                    "progress_step",
                    "progress_label",
                ]
            )
        except Contract.DoesNotExist:
            pass
    finally:
        close_old_connections()


def start_analyze_async(contract: Contract) -> None:
    """Mark processing and start analyze (thread, or sync under tests)."""
    contract.status = Contract.Status.PROCESSING
    contract.progress_step = Contract.ProgressStep.QUEUED
    contract.progress_label = "Queued"
    contract.error_message = ""
    contract.save(
        update_fields=[
            "status",
            "progress_step",
            "progress_label",
            "error_message",
        ]
    )
    if _analyze_sync():
        run_analyze_job(contract.pk)
        return
    thread = threading.Thread(
        target=run_analyze_job,
        args=(contract.pk,),
        daemon=True,
        name=f"analyze-{contract.pk}",
    )
    thread.start()
