"""PII redactor unit tests."""

from django.test import SimpleTestCase

from apps.security.services.redactor import redact_for_llm, redact_pii


class RedactorTests(SimpleTestCase):
    def test_email_redacted(self):
        text, mapping = redact_pii("Contact alice@portswigger.net for details.")
        self.assertNotIn("alice@portswigger.net", text)
        self.assertTrue(any("EMAIL" in k for k in mapping))
        self.assertIn("alice@portswigger.net", mapping.values())

    def test_redact_for_llm_meta(self):
        _s, u, meta = redact_for_llm("sys", "Email bob@example.com please")
        self.assertTrue(meta["pii_redacted"])
        self.assertNotIn("bob@example.com", u)
