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


class PlaybookBlankScratchTests(TestCase):
    def test_blank_create_add_rule_activate_loads_active(self):
        import tempfile

        tmp = tempfile.mkdtemp()
        pb = Path(tmp) / "playbook.json"
        pb.write_text(
            json.dumps(
                {
                    "version": 1,
                    "name": "Prior demo",
                    "preferred_governing_law": "England and Wales",
                    "rules": [
                        {
                            "id": "old",
                            "clause_type": "general",
                            "preferred": "x",
                            "hard_ceiling": "y",
                            "severity": "low",
                            "match_any": ["z"],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        with override_settings(PLAYBOOK_PATH=pb, MEDIA_ROOT=Path(tmp) / "media"):
            client = Client()
            page = client.get("/playbook/write/")
            self.assertEqual(page.status_code, 200)
            self.assertContains(page, "Write your own rules")

            create = client.post("/playbook/write/")
            self.assertEqual(create.status_code, 302)
            imp = PlaybookImport.objects.latest("created_at")
            self.assertEqual(imp.source, PlaybookImport.Source.MANUAL)
            self.assertEqual(imp.status, PlaybookImport.Status.PROPOSED)
            self.assertEqual(len((imp.proposed_json or {}).get("rules") or []), 1)

            detail = client.get(f"/playbook/imports/{imp.pk}/")
            self.assertEqual(detail.status_code, 200)
            self.assertContains(detail, "Written by you")
            self.assertContains(detail, "Preferred position")

            add = client.post(
                f"/playbook/imports/{imp.pk}/",
                {
                    "action": "add_rule",
                    "name": "Scratch firm playbook",
                    "preferred_governing_law": "England and Wales",
                    "rule_0_id": "rule_1",
                    "rule_0_clause_type": "governing_law",
                    "rule_0_preferred": "England and Wales",
                    "rule_0_hard_ceiling": "No foreign exclusive courts",
                    "rule_0_fallback_text": "",
                    "rule_0_severity": "high",
                    "rule_0_match_any": "governed by, exclusive jurisdiction",
                },
            )
            self.assertEqual(add.status_code, 302)
            imp.refresh_from_db()
            self.assertEqual(len((imp.proposed_json or {}).get("rules") or []), 2)

            activate = client.post(
                f"/playbook/imports/{imp.pk}/",
                {
                    "action": "activate",
                    "name": "Scratch firm playbook",
                    "preferred_governing_law": "England and Wales",
                    "confirm": "on",
                    "rule_0_id": "rule_1",
                    "rule_0_clause_type": "governing_law",
                    "rule_0_preferred": "England and Wales",
                    "rule_0_hard_ceiling": "No foreign exclusive courts",
                    "rule_0_fallback_text": "",
                    "rule_0_severity": "high",
                    "rule_0_match_any": "governed by, exclusive jurisdiction",
                    "rule_1_id": "rule_2",
                    "rule_1_clause_type": "liability_cap",
                    "rule_1_preferred": "Cap at 12 months fees",
                    "rule_1_hard_ceiling": "Unlimited liability forbidden",
                    "rule_1_fallback_text": "Liability capped at 12 months fees",
                    "rule_1_severity": "high",
                    "rule_1_match_any": "unlimited liability, no cap",
                },
            )
            self.assertEqual(activate.status_code, 302)
            self.assertIn("/playbook/", activate["Location"])
            imp.refresh_from_db()
            self.assertEqual(imp.status, PlaybookImport.Status.ACTIVATED)

            from apps.review.services.playbook_import import load_active_playbook

            active = load_active_playbook()
            self.assertFalse(active.get("empty"))
            self.assertEqual(active.get("name"), "Scratch firm playbook")
            self.assertEqual(len(active.get("rules") or []), 2)

    def test_import_page_links_scratch(self):
        r = Client().get("/playbook/import/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Write rules from scratch")

    def test_active_page_links_scratch(self):
        r = Client().get("/playbook/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Write your own rules")


class PlaybookRuleDraftAssistTests(TestCase):
    @override_settings(FAKE_LLM="1")
    def test_draft_rule_from_brief_fills_fields(self):
        from apps.review.services.rule_draft import draft_rule_from_brief

        rule = draft_rule_from_brief(
            brief="Liability: cap at 12 months fees; no unlimited",
            playbook_name="Test playbook",
            governing_law="England and Wales",
        )
        self.assertTrue(rule.get("preferred"))
        self.assertTrue(rule.get("hard_ceiling"))
        self.assertTrue(rule.get("match_any"))
        self.assertIn(rule.get("severity"), ("high", "medium", "low"))
        self.assertTrue(rule.get("clause_type"))

    @override_settings(FAKE_LLM="1")
    def test_blank_then_draft_rule_fills_form(self):
        client = Client()
        create = client.post("/playbook/write/")
        self.assertEqual(create.status_code, 302)
        imp = PlaybookImport.objects.latest("created_at")

        detail = client.get(f"/playbook/imports/{imp.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Draft with AI")
        self.assertContains(detail, "Draft this rule")

        drafted = client.post(
            f"/playbook/imports/{imp.pk}/",
            {
                "action": "draft_rule:0",
                "name": "My firm playbook",
                "preferred_governing_law": "England and Wales",
                "draft_brief_0": "Liability: cap at 12 months fees; no unlimited",
                "rule_0_id": "rule_1",
                "rule_0_clause_type": "general",
                "rule_0_preferred": "",
                "rule_0_hard_ceiling": "",
                "rule_0_fallback_text": "",
                "rule_0_severity": "medium",
                "rule_0_match_any": "",
            },
        )
        self.assertEqual(drafted.status_code, 302)
        imp.refresh_from_db()
        rules = (imp.proposed_json or {}).get("rules") or []
        self.assertEqual(len(rules), 1)
        self.assertTrue((rules[0].get("preferred") or "").strip())
        self.assertTrue((rules[0].get("hard_ceiling") or "").strip())
        self.assertTrue(rules[0].get("match_any"))

        again = client.get(f"/playbook/imports/{imp.pk}/")
        self.assertEqual(again.status_code, 200)
        self.assertContains(again, rules[0]["preferred"][:40])
        self.assertContains(again, "Draft with AI")
        # Brief preserved for re-draft
        self.assertContains(again, "Liability: cap at 12 months fees")
