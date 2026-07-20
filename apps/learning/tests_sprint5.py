"""Sprint 5 — richer memory, threshold, UI, API, reject-avoid."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.test import Client, TestCase, override_settings

from apps.contracts.models import Contract
from apps.decisions.models import Decision
from apps.decisions.services.decide import record_decision
from apps.learning.services import memory as memory_mod
from apps.learning.services.catalog import unlearn_precedent
from apps.review.models import Draft, Finding
from apps.review.services.pipeline import run_pipeline


def _playbook_california(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "name": "Test playbook",
                "preferred_governing_law": "England and Wales",
                "rules": [
                    {
                        "id": "governing_law_preferred",
                        "clause_type": "governing_law",
                        "preferred": "England and Wales",
                        "hard_ceiling": "Flag non-UK governing law",
                        "fallback_text": (
                            "This Agreement shall be governed by the laws of England and Wales."
                        ),
                        "severity": "medium",
                        "match_any": [
                            "laws of the State of California",
                            "laws of California",
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


CAL_TEXT = (
    "This Agreement shall be governed by the laws of the State of California."
)
CAL_TEXT_2 = (
    "This Agreement shall be governed by the laws of California exclusively."
)


class Sprint5MemoryCoreTests(TestCase):
    def test_accept_stores_clause_excerpt(self):
        tmp = tempfile.mkdtemp()
        try:
            pb = Path(tmp) / "playbook.json"
            chroma = Path(tmp) / "chroma"
            _playbook_california(pb)
            memory_mod.reset_decision_store()
            with override_settings(
                PLAYBOOK_PATH=pb,
                CHROMA_PATH=chroma,
                CHROMA_COLLECTION="test_s5_excerpt",
                MEMORY_MAX_DISTANCE=0.95,
            ):
                memory_mod.reset_decision_store()
                c1 = Contract.objects.create(
                    filename="c1.txt",
                    source=Contract.Source.UPLOAD,
                    extracted_text=CAL_TEXT,
                    status=Contract.Status.EXTRACTED,
                    quality="ok",
                )
                run_pipeline(c1)
                f1 = Finding.objects.get(review_run__contract=c1)
                self.assertTrue(f1.clause_excerpt)
                self.assertIn("California", f1.clause_excerpt)

                decision = record_decision(
                    finding=f1,
                    contract=c1,
                    action="accept",
                    final_text="Governed by England and Wales (memory).",
                )
                self.assertTrue(decision.chroma_id)
                rec = memory_mod.get_decision_record(decision.chroma_id)
                assert rec is not None
                self.assertIn("California", rec.clause_text)
                self.assertNotIn("Playbook rule", rec.clause_text)
                self.assertEqual(rec.filename, "c1.txt")
                memory_mod.reset_decision_store()
        finally:
            memory_mod.reset_decision_store()

    def test_distance_threshold_blocks_memory(self):
        tmp = tempfile.mkdtemp()
        try:
            pb = Path(tmp) / "playbook.json"
            chroma = Path(tmp) / "chroma"
            _playbook_california(pb)
            memory_mod.reset_decision_store()
            with override_settings(
                PLAYBOOK_PATH=pb,
                CHROMA_PATH=chroma,
                CHROMA_COLLECTION="test_s5_thresh",
                MEMORY_MAX_DISTANCE=0.95,
            ):
                memory_mod.reset_decision_store()
                c1 = Contract.objects.create(
                    filename="c1.txt",
                    source=Contract.Source.UPLOAD,
                    extracted_text=CAL_TEXT,
                    status=Contract.Status.EXTRACTED,
                    quality="ok",
                )
                run_pipeline(c1)
                f1 = Finding.objects.get(review_run__contract=c1)
                record_decision(
                    finding=f1,
                    contract=c1,
                    action="accept",
                    final_text="Custom England Wales from memory.",
                )

            # Impossible threshold → never reuse memory
            with override_settings(
                PLAYBOOK_PATH=pb,
                CHROMA_PATH=chroma,
                CHROMA_COLLECTION="test_s5_thresh",
                MEMORY_MAX_DISTANCE=-1.0,
            ):
                memory_mod.reset_decision_store()
                c2 = Contract.objects.create(
                    filename="c2.txt",
                    source=Contract.Source.UPLOAD,
                    extracted_text=CAL_TEXT_2,
                    status=Contract.Status.EXTRACTED,
                    quality="ok",
                )
                run_pipeline(c2)
                draft = Draft.objects.get(finding__review_run__contract=c2)
                self.assertEqual(draft.draft_source, Draft.Source.PLAYBOOK)
                memory_mod.reset_decision_store()
        finally:
            memory_mod.reset_decision_store()


class Sprint5MemoryUiApiTests(TestCase):
    def test_memory_page_and_apis(self):
        tmp = tempfile.mkdtemp()
        try:
            pb = Path(tmp) / "playbook.json"
            chroma = Path(tmp) / "chroma"
            overrides = Path(tmp) / "overrides.json"
            overrides.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "overrides": [
                            {
                                "playbook_rule_id": "demo_rule",
                                "action": "accept_as_is",
                                "reason": "Demo override",
                                "created_at": "2026-07-01T00:00:00+00:00",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            _playbook_california(pb)
            memory_mod.reset_decision_store()
            with override_settings(
                PLAYBOOK_PATH=pb,
                PLAYBOOK_OVERRIDES_PATH=overrides,
                CHROMA_PATH=chroma,
                CHROMA_COLLECTION="test_s5_ui",
                MEMORY_MAX_DISTANCE=0.95,
            ):
                memory_mod.reset_decision_store()
                c1 = Contract.objects.create(
                    filename="seed.txt",
                    source=Contract.Source.UPLOAD,
                    extracted_text=CAL_TEXT,
                    status=Contract.Status.EXTRACTED,
                    quality="ok",
                )
                run_pipeline(c1)
                f1 = Finding.objects.get(review_run__contract=c1)
                decision = record_decision(
                    finding=f1,
                    contract=c1,
                    action="accept",
                    final_text="England and Wales (seeded).",
                )

                page = Client().get("/memory/")
                self.assertEqual(page.status_code, 200)
                self.assertContains(page, "Memory")
                self.assertContains(page, "Governing law preferred")
                self.assertContains(page, "Muted rules")
                self.assertContains(page, "Demo rule")
                self.assertContains(page, "Forget this example")

                listed = Client().get("/api/memory/")
                self.assertEqual(listed.status_code, 200)
                body = listed.json()
                self.assertTrue(body["precedents"])
                self.assertEqual(body["precedents"][0]["id"], decision.chroma_id)

                search = Client().get(
                    "/api/memory/search/",
                    {"q": "California governing", "rule_id": "governing_law_preferred"},
                )
                self.assertEqual(search.status_code, 200)
                self.assertTrue(search.json()["hits"])

                # Second contract should show provenance on rewrite
                c2 = Contract.objects.create(
                    filename="reuse.txt",
                    source=Contract.Source.UPLOAD,
                    extracted_text=CAL_TEXT_2,
                    status=Contract.Status.EXTRACTED,
                    quality="ok",
                )
                run_pipeline(c2)
                f2 = Finding.objects.get(review_run__contract=c2)
                draft = Draft.objects.get(finding=f2)
                self.assertEqual(draft.draft_source, Draft.Source.MEMORY)
                self.assertTrue(draft.provenance.get("filename"))

                rewrite = Client().get(f"/contracts/{c2.pk}/rewrite/{f2.pk}/")
                self.assertEqual(rewrite.status_code, 200)
                self.assertContains(rewrite, "Reused")
                self.assertContains(rewrite, "seed.txt")

                # Unlearn via DELETE API
                deleted = Client().delete(f"/api/memory/{decision.chroma_id}/")
                self.assertEqual(deleted.status_code, 200)
                self.assertTrue(deleted.json()["ok"])
                decision.refresh_from_db()
                self.assertFalse(decision.memory_active)
                self.assertIsNone(memory_mod.get_decision_record(decision.chroma_id))

                page2 = Client().get("/memory/")
                self.assertEqual(page2.status_code, 200)
                self.assertNotContains(page2, "England and Wales (seeded).")

                memory_mod.reset_decision_store()
        finally:
            memory_mod.reset_decision_store()


class Sprint5RejectAvoidTests(TestCase):
    def test_reject_blocks_similar_memory_reuse(self):
        tmp = tempfile.mkdtemp()
        try:
            pb = Path(tmp) / "playbook.json"
            chroma = Path(tmp) / "chroma"
            _playbook_california(pb)
            memory_mod.reset_decision_store()
            with override_settings(
                PLAYBOOK_PATH=pb,
                CHROMA_PATH=chroma,
                CHROMA_COLLECTION="test_s5_reject",
                MEMORY_MAX_DISTANCE=0.95,
            ):
                memory_mod.reset_decision_store()
                c1 = Contract.objects.create(
                    filename="accept.txt",
                    source=Contract.Source.UPLOAD,
                    extracted_text=CAL_TEXT,
                    status=Contract.Status.EXTRACTED,
                    quality="ok",
                )
                run_pipeline(c1)
                f1 = Finding.objects.get(review_run__contract=c1)
                record_decision(
                    finding=f1,
                    contract=c1,
                    action="accept",
                    final_text="Would reuse this text from Accept.",
                )

                c2 = Contract.objects.create(
                    filename="reject.txt",
                    source=Contract.Source.UPLOAD,
                    extracted_text=CAL_TEXT_2,
                    status=Contract.Status.EXTRACTED,
                    quality="ok",
                )
                run_pipeline(c2)
                f2 = Finding.objects.get(review_run__contract=c2)
                d2 = Draft.objects.get(finding=f2)
                self.assertEqual(d2.draft_source, Draft.Source.MEMORY)

                record_decision(
                    finding=f2,
                    contract=c2,
                    action="reject",
                    reasoning="Bad precedent for this paper",
                )

                c3 = Contract.objects.create(
                    filename="blocked.txt",
                    source=Contract.Source.UPLOAD,
                    extracted_text=CAL_TEXT,
                    status=Contract.Status.EXTRACTED,
                    quality="ok",
                )
                run_pipeline(c3)
                d3 = Draft.objects.get(finding__review_run__contract=c3)
                self.assertEqual(d3.draft_source, Draft.Source.PLAYBOOK)
                self.assertIn("Reject", d3.rationale)

                mem = Client().get("/memory/")
                self.assertContains(mem, "Avoid")

                memory_mod.reset_decision_store()
        finally:
            memory_mod.reset_decision_store()

    def test_unlearn_helper(self):
        tmp = tempfile.mkdtemp()
        try:
            pb = Path(tmp) / "playbook.json"
            chroma = Path(tmp) / "chroma"
            _playbook_california(pb)
            memory_mod.reset_decision_store()
            with override_settings(
                PLAYBOOK_PATH=pb,
                CHROMA_PATH=chroma,
                CHROMA_COLLECTION="test_s5_unlearn",
                MEMORY_MAX_DISTANCE=0.95,
            ):
                memory_mod.reset_decision_store()
                c1 = Contract.objects.create(
                    filename="u.txt",
                    source=Contract.Source.UPLOAD,
                    extracted_text=CAL_TEXT,
                    status=Contract.Status.EXTRACTED,
                    quality="ok",
                )
                run_pipeline(c1)
                f1 = Finding.objects.get(review_run__contract=c1)
                decision = record_decision(
                    finding=f1,
                    contract=c1,
                    action="accept",
                    final_text="To be unlearned.",
                )
                self.assertTrue(unlearn_precedent(decision.chroma_id))
                decision.refresh_from_db()
                self.assertFalse(decision.memory_active)
                memory_mod.reset_decision_store()
        finally:
            memory_mod.reset_decision_store()
