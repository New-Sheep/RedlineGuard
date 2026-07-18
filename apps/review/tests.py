from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.test import Client, TestCase, override_settings

from apps.review.models import PlaybookImport
from apps.review.services.playbook_bootstrap import FakePlaybookBootstrap
from apps.review.services.playbook_import import (
    activate_playbook,
    document_from_form,
    run_import_and_propose,
)
from scratch.poc02_security.security import detect_injection, detect_playbook_injection


class BootstrapTests(TestCase):
    def test_propose_from_sample_cues(self):
        text = """
        PortSwigger Commercial Contract Playbook
        1. Governing Law & Jurisdiction — England and Wales
        2. Limitation of Liability — capped at 12 months fees; unlimited forbidden
        3. Intellectual Property — retain background IP
        4. Confidentiality — 3 to 5 years
        5. Non-Compete — we do not accept
        """
        doc = FakePlaybookBootstrap().propose(text, source_name="Sample Playbook1.pdf")
        self.assertGreaterEqual(len(doc.rules), 4)
        types = {r.clause_type for r in doc.rules}
        self.assertIn("governing_law", types)
        self.assertIn("liability_cap", types)


class PlaybookSecurityTests(TestCase):
    def test_playbook2_halts_on_calibration(self):
        corpus = Path(settings.PLAYBOOK_CORPUS_DIR)
        sample = "Sample Playbook2.pdf"
        if not (corpus / sample).is_file():
            self.skipTest("Sample Playbook2.pdf missing")
        imp = PlaybookImport.objects.create(
            filename=sample,
            source=PlaybookImport.Source.SAMPLE,
            sample_key=sample,
        )
        run_import_and_propose(imp)
        self.assertEqual(imp.status, PlaybookImport.Status.HALTED)
        self.assertTrue((imp.proposed_json or {}).get("security", {}).get("halt"))

    def test_playbook1_still_proposes(self):
        corpus = Path(settings.PLAYBOOK_CORPUS_DIR)
        sample = "Sample Playbook1.pdf"
        if not (corpus / sample).is_file():
            self.skipTest("Sample Playbook1.pdf missing")
        imp = PlaybookImport.objects.create(
            filename=sample,
            source=PlaybookImport.Source.SAMPLE,
            sample_key=sample,
        )
        run_import_and_propose(imp)
        self.assertEqual(imp.status, PlaybookImport.Status.PROPOSED)
        self.assertGreater(len(imp.proposed_json.get("rules") or []), 0)

    def test_playbook_mode_ignores_gemini_chrome_only(self):
        chrome_only = "expand tune chat_spark https://gemini.google.com/app/xyz"
        self.assertFalse(detect_playbook_injection(chrome_only)["halt"])
        self.assertTrue(detect_injection(chrome_only)["halt"])


class PlaybookImportFlowTests(TestCase):
    def test_import_page_get_200(self):
        r = Client().get("/playbook/import/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Import a playbook PDF")

    def test_sample_import_shows_processing_then_detail(self):
        corpus = Path(settings.PLAYBOOK_CORPUS_DIR)
        sample = "Sample Playbook1.pdf"
        if not (corpus / sample).is_file():
            self.skipTest("Sample Playbook1.pdf missing")
        r = Client().post("/playbook/import/", {"sample_key": sample})
        self.assertEqual(r.status_code, 302)
        self.assertIn("/processing/", r["Location"])
        # Under tests, import runs sync — follow to detail
        imp = PlaybookImport.objects.latest("created_at")
        self.assertEqual(imp.status, PlaybookImport.Status.PROPOSED)
        status = Client().get(f"/playbook/imports/{imp.pk}/status.json")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["status"], "proposed")
        detail = Client().get(f"/playbook/imports/{imp.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Activate")

    def test_active_page_get_200(self):
        r = Client().get("/playbook/")
        self.assertEqual(r.status_code, 200)

    def test_activate_writes_bak(self):
        corpus = Path(settings.PLAYBOOK_CORPUS_DIR)
        sample = "Sample Playbook1.pdf"
        if not (corpus / sample).is_file():
            self.skipTest("Sample Playbook1.pdf missing")

        with override_settings(
            PLAYBOOK_PATH=Path(settings.BASE_DIR) / "media" / "test_playbook.json"
        ):
            path = Path(settings.PLAYBOOK_PATH)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "name": "old",
                        "preferred_governing_law": "England and Wales",
                        "rules": [],
                    }
                ),
                encoding="utf-8",
            )

            imp = PlaybookImport.objects.create(
                filename=sample,
                source=PlaybookImport.Source.SAMPLE,
                sample_key=sample,
            )
            run_import_and_propose(imp)
            self.assertEqual(imp.status, PlaybookImport.Status.PROPOSED)
            self.assertGreater(len(imp.proposed_json.get("rules") or []), 0)

            doc = document_from_form(
                name="Activated test playbook",
                preferred_governing_law="England and Wales",
                rules=imp.proposed_json["rules"],
            )
            activate_playbook(imp, doc)
            imp.refresh_from_db()
            self.assertEqual(imp.status, PlaybookImport.Status.ACTIVATED)
            bak = path.with_suffix(path.suffix + ".bak")
            self.assertTrue(bak.is_file())
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["name"], "Activated test playbook")
            self.assertGreater(len(saved["rules"]), 0)
