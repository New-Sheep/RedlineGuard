"""Unit tests for Ollama LLM path (offline — mocked HTTP)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from apps.core.llm import FakeLlmClient, OllamaLlmClient, get_llm_client
from apps.core.llm_json import extract_json_from_response, strip_chain_of_thought
from apps.core.ollama_engine import OllamaEngine, OllamaEngineError


class LlmJsonTests(SimpleTestCase):
    def test_strip_think_tags(self):
        raw = "<think>secret</think>{\"draft_text\": \"ok\", \"rationale\": \"r\"}"
        cleaned = strip_chain_of_thought(raw)
        self.assertNotIn("secret", cleaned)
        self.assertIn("draft_text", cleaned)

    def test_extract_fenced_json(self):
        raw = 'Here:\n```json\n{"draft_text": "Clause A.", "rationale": "playbook"}\n```\n'
        data = extract_json_from_response(raw)
        self.assertEqual(data["draft_text"], "Clause A.")
        self.assertEqual(data["rationale"], "playbook")


class OllamaEngineTests(SimpleTestCase):
    @patch("apps.core.ollama_engine.urllib.request.urlopen")
    def test_chat_returns_content(self, mock_urlopen):
        payload = {"message": {"content": '{"draft_text": "Hi", "rationale": "x"}'}}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False
        mock_urlopen.return_value = mock_resp

        engine = OllamaEngine(host="http://127.0.0.1:11434", model="test")
        text = engine.chat([{"role": "user", "content": "hi"}], json_mode=True)
        self.assertIn("draft_text", text)

    @patch("apps.core.ollama_engine.urllib.request.urlopen")
    def test_complete_json(self, mock_urlopen):
        payload = {
            "message": {
                "content": '```json\n{"draft_text": "Counter clause.", "rationale": "align"}\n```'
            }
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False
        mock_urlopen.return_value = mock_resp

        engine = OllamaEngine(host="http://127.0.0.1:11434", model="test")
        data = engine.complete_json(system="sys", user="usr")
        self.assertEqual(data["draft_text"], "Counter clause.")


class OllamaLlmClientTests(SimpleTestCase):
    def test_suggest_draft_via_engine(self):
        engine = MagicMock(spec=OllamaEngine)
        engine.complete_json.return_value = {
            "draft_text": "Governed by England and Wales.",
            "rationale": "playbook preferred",
        }
        client = OllamaLlmClient(engine=engine)
        suggestion = client.suggest_draft(
            playbook_rule={"id": "governing_law", "preferred": "England and Wales"},
            finding={"playbook_rule_id": "governing_law", "status": "REQUIRES_HUMAN"},
            fenced_contract_excerpt="<untrusted_document>California</untrusted_document>",
        )
        self.assertIn("England", suggestion.draft_text)
        engine.complete_json.assert_called_once()


class GetLlmClientFactoryTests(SimpleTestCase):
    @override_settings(FAKE_LLM="1")
    def test_fake_default(self):
        self.assertIsInstance(get_llm_client(), FakeLlmClient)

    @override_settings(
        FAKE_LLM="0",
        LLM_PROVIDER="ollama",
        OLLAMA_HOST="http://127.0.0.1:11434",
        OLLAMA_MODEL="llama3.1:8b",
    )
    def test_ollama_when_fake_off(self):
        client = get_llm_client()
        self.assertIsInstance(client, OllamaLlmClient)

    @override_settings(FAKE_LLM="0", LLM_PROVIDER="nvidia")
    @patch.dict(
        "os.environ",
        {"NVIDIA_API_KEY": "nvapi-test-key", "LLM_PROVIDER": "nvidia"},
        clear=False,
    )
    def test_nvidia_http_when_provider_set(self):
        from apps.core.llm import HttpLlmClient

        client = get_llm_client()
        self.assertIsInstance(client, HttpLlmClient)
        self.assertEqual(client.provider_name, "nvidia")
        self.assertIn("nvidia.com", client.base_url)
