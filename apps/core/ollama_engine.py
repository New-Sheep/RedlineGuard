"""Sync Ollama chat client (Mimwise /api/chat pattern, stdlib only)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from apps.core.llm_json import extract_json_from_response

logger = logging.getLogger(__name__)


class OllamaEngineError(RuntimeError):
    """Ollama HTTP or parse failure."""


class OllamaEngine:
    """POST {host}/api/chat — sync, stream=false."""

    def __init__(
        self,
        *,
        host: str = "http://127.0.0.1:11434",
        model: str = "llama3.1:8b",
        timeout_s: float = 120.0,
    ) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.timeout_s = float(timeout_s)

    def list_tags(self) -> list[str]:
        """Return installed model names from GET /api/tags."""
        url = f"{self.host}/api/tags"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=min(10.0, self.timeout_s)) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise OllamaEngineError(f"Ollama tags failed: {exc}") from exc
        models = body.get("models") or []
        names: list[str] = []
        for m in models:
            name = m.get("name") or m.get("model") or ""
            if name:
                names.append(str(name))
        return names

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        json_mode: bool = False,
        temperature: float = 0.2,
        num_predict: int = 1024,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": num_predict,
            },
        }
        if json_mode:
            payload["format"] = "json"

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise OllamaEngineError(f"Ollama chat failed: {exc}") from exc

        message = body.get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise OllamaEngineError("Ollama returned empty message content")
        return content

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.2,
        num_predict: int = 1024,
    ) -> dict[str, Any]:
        raw = self.chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            json_mode=True,
            temperature=temperature,
            num_predict=num_predict,
        )
        parsed = extract_json_from_response(raw)
        if not isinstance(parsed, dict):
            raise OllamaEngineError(
                f"Ollama JSON parse failed; raw starts: {raw[:200]!r}"
            )
        return parsed
