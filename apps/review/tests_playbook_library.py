"""Company playbook library catalogue tests."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.test import Client, TestCase, override_settings

from apps.review.models import CompanyPlaybook, PlaybookImport
from apps.review.services.playbook_import import load_active_playbook
from apps.review.services.playbook_library import (
    activate_playbook_record,
    combine_playbooks,
    deactivate_playbook_record,
    delete_playbook,
    ensure_library_seeded,
    upsert_from_activation,
)


def _doc(name: str, rules: list[dict], law: str = "England and Wales") -> dict:
    return {
        "version": 1,
        "name": name,
        "preferred_governing_law": law,
        "rules": rules,
    }


def _rule(clause: str, preferred: str, severity: str = "medium") -> dict:
    return {
        "id": f"{clause}_x",
        "clause_type": clause,
        "preferred": preferred,
        "hard_ceiling": f"Refuse conflict with {clause}",
        "fallback_text": None,
        "severity": severity,
        "match_any": [clause.replace("_", " ")],
    }


class PlaybookLibraryTests(TestCase):
    def test_seed_from_golden_when_empty(self):
        tmp = tempfile.mkdtemp()
        pb = Path(tmp) / "playbook.json"
        pb.write_text(
            json.dumps(
                _doc(
                    "Seeded golden",
                    [_rule("governing_law", "England and Wales", "high")],
                )
            ),
            encoding="utf-8",
        )
        with override_settings(PLAYBOOK_PATH=pb, MEDIA_ROOT=Path(tmp) / "media"):
            self.assertEqual(CompanyPlaybook.objects.count(), 0)
            seeded = ensure_library_seeded()
            self.assertIsNotNone(seeded)
            self.assertEqual(CompanyPlaybook.objects.count(), 1)
            self.assertTrue(seeded.is_active)
            self.assertEqual(seeded.name, "Seeded golden")
            # Idempotent
            self.assertIsNone(ensure_library_seeded())
            self.assertEqual(CompanyPlaybook.objects.count(), 1)

    def test_activate_exclusivity_and_golden(self):
        tmp = tempfile.mkdtemp()
        pb = Path(tmp) / "playbook.json"
        pb.write_text(json.dumps(_doc("Empty", [])), encoding="utf-8")
        with override_settings(PLAYBOOK_PATH=pb, MEDIA_ROOT=Path(tmp) / "media"):
            a = CompanyPlaybook.objects.create(
                name="Playbook A",
                preferred_governing_law="England and Wales",
                document=_doc("Playbook A", [_rule("liability_cap", "12 months", "high")]),
                is_active=False,
            )
            b = CompanyPlaybook.objects.create(
                name="Playbook B",
                preferred_governing_law="England and Wales",
                document=_doc("Playbook B", [_rule("confidentiality", "3 years")]),
                is_active=False,
            )
            activate_playbook_record(a.pk)
            a.refresh_from_db()
            b.refresh_from_db()
            self.assertTrue(a.is_active)
            self.assertFalse(b.is_active)
            active = load_active_playbook()
            self.assertEqual(active.get("name"), "Playbook A")

            activate_playbook_record(b.pk)
            a.refresh_from_db()
            b.refresh_from_db()
            self.assertFalse(a.is_active)
            self.assertTrue(b.is_active)
            active = load_active_playbook()
            self.assertEqual(active.get("name"), "Playbook B")
            self.assertFalse(active.get("empty"))

    def test_deactivate_empties_golden(self):
        tmp = tempfile.mkdtemp()
        pb = Path(tmp) / "playbook.json"
        with override_settings(PLAYBOOK_PATH=pb, MEDIA_ROOT=Path(tmp) / "media"):
            row = upsert_from_activation(
                _doc("Live", [_rule("governing_law", "England and Wales", "high")])
            )
            activate_playbook_record(row.pk)
            deactivate_playbook_record(row.pk)
            row.refresh_from_db()
            self.assertFalse(row.is_active)
            active = load_active_playbook()
            self.assertTrue(active.get("empty"))
            self.assertEqual(active.get("rules") or [], [])

    def test_delete_active_clears_golden(self):
        tmp = tempfile.mkdtemp()
        pb = Path(tmp) / "playbook.json"
        with override_settings(PLAYBOOK_PATH=pb, MEDIA_ROOT=Path(tmp) / "media"):
            row = CompanyPlaybook.objects.create(
                name="Active one",
                document=_doc("Active one", [_rule("ip_ownership", "Retain IP")]),
                is_active=True,
            )
            other = CompanyPlaybook.objects.create(
                name="Spare",
                document=_doc("Spare", [_rule("process", "Negotiable")]),
                is_active=False,
            )
            name = delete_playbook(row.pk)
            self.assertEqual(name, "Active one")
            self.assertFalse(CompanyPlaybook.objects.filter(pk=row.pk).exists())
            active = load_active_playbook()
            self.assertTrue(active.get("empty"))
            delete_playbook(other.pk)
            self.assertFalse(CompanyPlaybook.objects.filter(pk=other.pk).exists())

    def test_union_and_intersection(self):
        a = CompanyPlaybook.objects.create(
            name="Alpha",
            preferred_governing_law="England and Wales",
            document=_doc(
                "Alpha",
                [
                    _rule("governing_law", "E&W", "high"),
                    _rule("liability_cap", "12 months", "high"),
                ],
            ),
        )
        b = CompanyPlaybook.objects.create(
            name="Beta",
            preferred_governing_law="England and Wales",
            document=_doc(
                "Beta",
                [
                    _rule("governing_law", "E&W preferred", "medium"),
                    _rule("confidentiality", "3 years"),
                ],
            ),
        )
        union_imp = combine_playbooks([a.pk, b.pk], mode="union")
        self.assertEqual(union_imp.status, PlaybookImport.Status.PROPOSED)
        u_rules = (union_imp.proposed_json or {}).get("rules") or []
        u_types = {r["clause_type"] for r in u_rules}
        self.assertEqual(u_types, {"governing_law", "liability_cap", "confidentiality"})
        gov = next(r for r in u_rules if r["clause_type"] == "governing_law")
        self.assertEqual(gov["severity"], "high")  # severity wins

        inter_imp = combine_playbooks([a.pk, b.pk], mode="intersection")
        i_rules = (inter_imp.proposed_json or {}).get("rules") or []
        self.assertEqual(len(i_rules), 1)
        self.assertEqual(i_rules[0]["clause_type"], "governing_law")
        self.assertEqual(i_rules[0]["preferred"], "E&W")  # first playbook body

    def test_library_page_lists_and_combine_redirect(self):
        tmp = tempfile.mkdtemp()
        pb = Path(tmp) / "playbook.json"
        pb.write_text(json.dumps(_doc("Empty", [])), encoding="utf-8")
        with override_settings(PLAYBOOK_PATH=pb, MEDIA_ROOT=Path(tmp) / "media"):
            a = CompanyPlaybook.objects.create(
                name="Lib A",
                document=_doc("Lib A", [_rule("governing_law", "E&W")]),
            )
            b = CompanyPlaybook.objects.create(
                name="Lib B",
                document=_doc("Lib B", [_rule("liability_cap", "Cap")]),
            )
            client = Client()
            page = client.get("/playbook/")
            self.assertEqual(page.status_code, 200)
            self.assertContains(page, "Your playbooks")
            self.assertContains(page, "Lib A")
            self.assertContains(page, "Lib B")
            self.assertContains(page, "library-cards")
            self.assertContains(page, "Combine playbooks")
            self.assertNotContains(page, "library-table")
            self.assertContains(page, "Edit rules")
            self.assertContains(page, "Activate")
            self.assertContains(page, "Delete")
            self.assertContains(page, "Rename")
            self.assertContains(page, "View")

            detail = client.get(f"/playbook/library/{a.pk}/")
            self.assertEqual(detail.status_code, 200)
            self.assertContains(detail, "Lib A")
            self.assertContains(detail, "Edit rules")

            edit = client.get(f"/playbook/library/{a.pk}/edit/")
            self.assertEqual(edit.status_code, 302)
            self.assertIn("/playbook/imports/", edit["Location"])
            imp_edit = PlaybookImport.objects.latest("created_at")
            self.assertEqual(imp_edit.proposal_source, "edit")
            self.assertEqual(
                (imp_edit.proposed_json or {}).get("_meta", {}).get("library_id"),
                str(a.pk),
            )
            rules = list((imp_edit.proposed_json or {}).get("rules") or [])
            self.assertEqual(len(rules), 1)
            rules[0]["preferred"] = "England and Wales only"
            from apps.review.services.playbook_bootstrap import PlaybookDocument
            from apps.review.services.playbook_import import activate_playbook

            doc = PlaybookDocument.model_validate(
                {
                    "version": 1,
                    "name": "Lib A",
                    "preferred_governing_law": "England and Wales",
                    "rules": rules,
                }
            )
            activate_playbook(imp_edit, doc)
            a.refresh_from_db()
            self.assertEqual(a.document["rules"][0]["preferred"], "England and Wales only")
            self.assertTrue(a.is_active)
            self.assertEqual(CompanyPlaybook.objects.count(), 2)

            combined = client.post(
                "/playbook/",
                {
                    "action": "combine",
                    "combine_mode": "union",
                    "playbook_ids": [str(a.pk), str(b.pk)],
                },
            )
            self.assertEqual(combined.status_code, 302)
            self.assertIn("/playbook/imports/", combined["Location"])
            imp = PlaybookImport.objects.latest("created_at")
            self.assertEqual(imp.proposal_source, "combine")
            self.assertGreaterEqual(len((imp.proposed_json or {}).get("rules") or []), 2)
