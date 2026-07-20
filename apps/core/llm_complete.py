"""Shared JSON completion + provider labels for agents."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from apps.core.agent_flags import fake_llm
from apps.core.llm import FakeLlmClient, HttpLlmClient, OllamaLlmClient, get_llm_client
from apps.core.llm_providers import resolve_provider_config
from apps.security.services.redactor import redact_for_llm

logger = logging.getLogger(__name__)

# Last redaction meta for UI (request-local enough for demo; tests reset)
_last_pii_meta: dict[str, Any] = {}


def last_pii_meta() -> dict[str, Any]:
    return dict(_last_pii_meta)


def prompt_hash(system: str, user: str) -> str:
    blob = f"{system or ''}\n---\n{user or ''}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def provider_label() -> str:
    """Short badge: Fake | Ollama | NVIDIA | DeepSeek | Moonshot | HTTP."""
    client = get_llm_client()
    if isinstance(client, FakeLlmClient):
        return "Fake"
    if isinstance(client, OllamaLlmClient):
        return "Ollama"
    if isinstance(client, HttpLlmClient):
        names = {
            "nvidia": "NVIDIA",
            "deepseek": "DeepSeek",
            "moonshot": "Moonshot",
            "http": "HTTP",
            "openai": "OpenAI",
        }
        return names.get(client.provider_name, (client.provider_name or "HTTP").title())
    return "LLM"


def provider_label_from_env() -> str:
    """Label without constructing heavy clients when Fake."""
    if fake_llm():
        return "Fake"
    cfg = resolve_provider_config()
    if cfg is not None:
        return cfg.name.upper() if len(cfg.name) <= 8 else cfg.name.title()
    return "Ollama"


def complete_json(
    *, system: str, user: str, timeout_s: float | None = None
) -> dict[str, Any]:
    """Route to HTTP or Ollama complete_json. Raises if Fake.

    Redacts PII on outbound payloads for real LLM clients (not Fake).
    Optional timeout_s overrides the HTTP client's default (playbook propose).
    """
    global _last_pii_meta
    client = get_llm_client()
    if isinstance(client, FakeLlmClient):
        _last_pii_meta = {"pii_redacted": False, "pii_count": 0}
        raise RuntimeError("complete_json requires FAKE_LLM=0 (real LLM client)")

    sys_r, usr_r, meta = redact_for_llm(system, user)
    meta["prompt_hash"] = prompt_hash(sys_r, usr_r)
    _last_pii_meta = meta
    try:
        from apps.decisions.services.lifecycle import log_audit
        from apps.decisions.models import AuditEvent

        log_audit(
            kind=AuditEvent.Kind.LLM_CALL,
            summary=f"LLM complete_json · {provider_label()}",
            payload={
                "prompt_hash": meta["prompt_hash"],
                "pii_redacted": meta.get("pii_redacted"),
                "pii_count": meta.get("pii_count"),
                "provider": provider_label(),
            },
        )
    except Exception:
        pass

    if isinstance(client, HttpLlmClient):
        if timeout_s is not None:
            client = HttpLlmClient(
                api_key=client.api_key,
                base_url=client.base_url,
                model=client.model,
                prefer_json_object=client.prefer_json_object,
                timeout_s=float(timeout_s),
                provider_name=client.provider_name,
            )
        return client.complete_json(system=sys_r, user=usr_r)
    if isinstance(client, OllamaLlmClient):
        return client.engine.complete_json(system=sys_r, user=usr_r)
    raise RuntimeError("complete_json requires FAKE_LLM=0 (real LLM client)")
