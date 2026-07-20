"""Sprint V1 — upload size + DOCX extract."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings

from apps.contracts.forms import ContractIngestForm
from apps.contracts.services.extract import extract_path
from apps.core.uploads import validate_upload_size


class UploadSizeTests(SimpleTestCase):
    @override_settings(MAX_UPLOAD_BYTES=100)
    def test_rejects_oversized(self):
        f = SimpleUploadedFile("big.txt", b"x" * 200, content_type="text/plain")
        with self.assertRaises(Exception):
            validate_upload_size(f)

    @override_settings(MAX_UPLOAD_BYTES=10 * 1024 * 1024)
    def test_form_rejects_bad_ext(self):
        f = SimpleUploadedFile("x.exe", b"MZ", content_type="application/octet-stream")
        form = ContractIngestForm(data={"sample_key": ""}, files={"upload": f})
        self.assertFalse(form.is_valid())


class DocxExtractTests(TestCase):
    def test_extract_docx(self):
        try:
            from docx import Document
        except ImportError:
            self.skipTest("python-docx not installed")
        tmp = Path(tempfile.mkdtemp()) / "t.docx"
        doc = Document()
        doc.add_paragraph("This Agreement shall be governed by the laws of England and Wales.")
        doc.save(str(tmp))
        result = extract_path(tmp)
        self.assertIn("England and Wales", result["text"])
        self.assertGreater(result["char_count"], 20)
