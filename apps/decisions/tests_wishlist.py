"""Wishlist sprints: catalogue, undo, FP, auditor, APIs, help."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.test import Client, TestCase, override_settings

from apps.contracts.models import Contract
from apps.decisions.models import AuditEvent, Decision
from apps.decisions.services.decide import record_decision
from apps.decisions.services.lifecycle import undo_decision
from apps.learning.services import memory as memory_mod
from apps.review.models import Finding, ReviewRun
from apps.review.services.overrides import append_override, load_overrides, revoke_override
from apps.review.services.playbook_audit import audit_playbook
from apps.review.services.playbook_import import activate_playbook, restore_playbook_version
from apps.review.services.playbook_bootstrap import PlaybookDocument, PlaybookRule
from apps.review.models import PlaybookImport


class CatalogueHistoryTests(TestCase):
    def test_contracts_list_paginated(self):
        for i in range(3):
            Contract.objects.create(
                filename=f"c{i}.txt",
                source=Contract.Source.UPLOAD,
                status=Contract.Status.READY,
            )
        r = Client().get("/contracts/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "c0.txt")
        self.assertContains(r, "Catalogue")

    def test_history_filters(self):
        c = Contract.objects.create(
            filename="nda.txt", source=Contract.Source.UPLOAD, status=Contract.Status.READY
        )
        run = ReviewRun.objects.create(contract=c, risk_score=10)
        f = Finding.objects.create(
            review_run=run,
            playbook_rule_id="governing_law",
            status=Finding.Status.FLAGGED,
            severity="medium",
        )
        record_decision(finding=f, contract=c, action="accept", final_text="ok")
        r = Client().get("/history/?action=accept")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "governing_law")


class UndoOverrideTests(TestCase):
    def test_undo_accept(self):
        tmp = tempfile.mkdtemp()
        chroma = Path(tmp) / "chroma"
        memory_mod.reset_decision_store()
        with override_settings(CHROMA_PATH=chroma, CHROMA_COLLECTION="test_undo"):
            memory_mod.reset_decision_store()
            c = Contract.objects.create(
                filename="nda.txt",
                source=Contract.Source.UPLOAD,
                status=Contract.Status.READY,
                triage_kind="nda",
            )
            run = ReviewRun.objects.create(contract=c, risk_score=10)
            f = Finding.objects.create(
                review_run=run,
                playbook_rule_id="governing_law",
                status=Finding.Status.FLAGGED,
                severity="medium",
                clause_excerpt="laws of California",
            )
            d = record_decision(
                finding=f, contract=c, action="accept", final_text="England and Wales"
            )
            self.assertTrue(d.chroma_id)
            undo_decision(d)
            d.refresh_from_db()
            self.assertTrue(d.superseded)
            self.assertTrue(
                AuditEvent.objects.filter(kind=AuditEvent.Kind.UNDO).exists()
            )
            memory_mod.reset_decision_store()

    def test_revoke_override(self):
        tmp = tempfile.mkdtemp()
        path = Path(tmp) / "overrides.json"
        with override_settings(PLAYBOOK_OVERRIDES_PATH=path):
            append_override(playbook_rule_id="r1", contract_id="c1", reason="test")
            self.assertEqual(len(load_overrides()["overrides"]), 1)
            n = revoke_override(playbook_rule_id="r1", contract_id="c1")
            self.assertEqual(n, 1)
            self.assertEqual(load_overrides()["overrides"], [])


class PlaybookAuditorTests(TestCase):
    def test_audit_catches_empty_rules(self):
        report = audit_playbook({"name": "X", "rules": []})
        self.assertFalse(report["ok"])

    def test_audit_ok_minimal_rule(self):
        report = audit_playbook(
            {
                "name": "X",
                "rules": [
                    {
                        "id": "a",
                        "clause_type": "governing_law",
                        "preferred": "UK",
                        "hard_ceiling": "UK",
                        "match_any": ["California"],
                    }
                ],
            }
        )
        self.assertTrue(report["ok"])


class FalsePositiveApiHelpTests(TestCase):
    def test_false_positive_decision(self):
        c = Contract.objects.create(
            filename="nda.txt", source=Contract.Source.UPLOAD, status=Contract.Status.READY
        )
        run = ReviewRun.objects.create(contract=c, risk_score=10)
        f = Finding.objects.create(
            review_run=run,
            playbook_rule_id="r1",
            status=Finding.Status.FLAGGED,
            severity="low",
        )
        d = record_decision(
            finding=f, contract=c, action="false_positive", reasoning="not a hit"
        )
        self.assertEqual(d.action, Decision.Action.FALSE_POSITIVE)
        self.assertFalse(d.memory_active)

    def test_api_contracts(self):
        Contract.objects.create(
            filename="a.txt", source=Contract.Source.UPLOAD, status=Contract.Status.READY
        )
        r = Client().get("/api/contracts/")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(r.json()["count"], 1)

    def test_help_page(self):
        r = Client().get("/help/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Playbook vs Memory")

    def test_audit_page(self):
        r = Client().get("/audit/")
        self.assertEqual(r.status_code, 200)
