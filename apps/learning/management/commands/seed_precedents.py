"""Seed 2–3 Accept precedents into Chroma for Journey B demos (F19)."""

from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.learning.services import memory as memory_mod
from scratch.poc06_memory.models import DecisionRecord


class Command(BaseCommand):
    help = (
        "Load data/precedents/precedent_seed.jsonl into Chroma "
        "(skip if collection already has rows unless --force)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Load seeds even when the collection is non-empty "
            "(skips ids that already exist).",
        )
        parser.add_argument(
            "--path",
            type=str,
            default="",
            help="Optional path to a jsonl seed file",
        )

    def handle(self, *args, **options):
        seed_path = Path(options["path"]) if options["path"] else (
            Path(settings.DATA_DIR) / "precedents" / "precedent_seed.jsonl"
        )
        if not seed_path.is_file():
            self.stderr.write(self.style.ERROR(f"Seed file not found: {seed_path}"))
            return

        store = memory_mod.get_decision_store()
        count = store.count()
        if count > 0 and not options["force"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Chroma already has {count} precedents — skipping "
                    "(use --force to add missing seed ids)."
                )
            )
            return

        added = 0
        skipped = 0
        with seed_path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                raw = json.loads(line)
                rid = str(raw.get("id") or "")
                if rid and store.get_decision(rid) is not None:
                    skipped += 1
                    continue
                payload = {
                    "clause_text": raw["clause_text"],
                    "decision": raw.get("decision") or "accept",
                    "final_text": raw["final_text"],
                    "playbook_rule_id": raw.get("playbook_rule_id"),
                    "contract_id": raw.get("contract_id") or "seed",
                    "reasoning": raw.get("reasoning"),
                    "filename": raw.get("filename"),
                    "doc_kind": raw.get("doc_kind"),
                }
                if rid:
                    payload["id"] = rid
                record = DecisionRecord(**payload)
                memory_mod.add_decision_record(record)
                added += 1

        memory_mod.reset_decision_store()
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {added} precedent(s); skipped {skipped} existing id(s)."
            )
        )
