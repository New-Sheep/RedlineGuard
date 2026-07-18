from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import Client, TestCase

from apps.contracts.models import Contract
from apps.contracts.services.extract import run_extract


class UploadViewTests(TestCase):
    def test_upload_page_get_200(self):
        client = Client()
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "RedlineGuard")


class ExtractServiceTests(TestCase):
    def test_extract_sample_txt(self):
        corpus = Path(settings.SCRATCH_CORPUS_DIR)
        sample = "injection_hostile.txt"
        self.assertTrue((corpus / sample).is_file())

        contract = Contract.objects.create(
            filename=sample,
            source=Contract.Source.SAMPLE,
            sample_key=sample,
            status=Contract.Status.UPLOADED,
        )
        run_extract(contract)
        contract.refresh_from_db()
        self.assertEqual(contract.status, Contract.Status.EXTRACTED)
        self.assertGreater(contract.char_count, 0)
        self.assertIn("ignore", contract.extracted_text.lower())
