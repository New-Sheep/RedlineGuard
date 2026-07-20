"""Verify local AuditEvent hash chain (demo integrity — not HSM)."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.decisions.models import AuditEvent
from apps.decisions.services.audit_chain import verify_chain


class Command(BaseCommand):
    help = "Verify AuditEvent hash chain (local SQLite demo ≠ production HSM)"

    def handle(self, *args, **options):
        events = list(AuditEvent.objects.order_by("created_at"))
        ok, msg = verify_chain(events)
        if ok:
            self.stdout.write(self.style.SUCCESS(msg))
        else:
            self.stderr.write(self.style.ERROR(msg))
            raise SystemExit(1)
