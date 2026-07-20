"""OpenAI-compatible provider presets (DeepSeek / Moonshot / NVIDIA / generic)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LlmProviderConfig:
    name: str
    api_key: str
    base_url: str
    model: str
    # Some hosts reject response_format; HttpLlmClient can retry without it.
    prefer_json_object: bool = True


_PRESETS: dict[str, tuple[str, str, str]] = {
    # (key_env, default_base, default_model)
    "deepseek": (
        "DEEPSEEK_API_KEY",
        "https://api.deepseek.com/v1",
        "deepseek-chat",
    ),
    "moonshot": (
        "MOONSHOT_API_KEY",
        "https://api.moonshot.ai/v1",
        "moonshot-v1-8k",
    ),
    "nvidia": (
        "NVIDIA_API_KEY",
        "https://integrate.api.nvidia.com/v1",
        "meta/llama-3.1-8b-instruct",
    ),
}


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def resolve_provider_config(
    provider: str | None = None,
) -> LlmProviderConfig | None:
    """Resolve cloud HTTP config from LLM_PROVIDER + keys.

    Returns None when provider is ollama/fake/empty and no auto cloud key.
    """
    raw = (provider if provider is not None else _env("LLM_PROVIDER")).lower()

    if raw in ("", "auto"):
        for name in ("nvidia", "deepseek", "moonshot"):
            key_env, base, model = _PRESETS[name]
            key = _env(key_env)
            if key and key not in ("<>",):
                return LlmProviderConfig(
                    name=name,
                    api_key=key,
                    base_url=_env(f"{name.upper()}_BASE_URL", base),
                    model=_env(f"{name.upper()}_MODEL", model),
                )
        # Generic OpenAI-compatible
        key = _env("LLM_API_KEY")
        if key and key not in ("<>",):
            return LlmProviderConfig(
                name="http",
                api_key=key,
                base_url=_env("LLM_BASE_URL", "https://api.openai.com/v1"),
                model=_env("LLM_MODEL", "gpt-4o-mini"),
            )
        return None

    if raw in ("ollama", "local", "fake"):
        return None

    if raw in _PRESETS:
        key_env, base, model = _PRESETS[raw]
        key = _env(key_env)
        if not key or key in ("<>",):
            raise ValueError(f"LLM_PROVIDER={raw} but {key_env} is missing")
        return LlmProviderConfig(
            name=raw,
            api_key=key,
            base_url=_env(f"{raw.upper()}_BASE_URL", base),
            model=_env(f"{raw.upper()}_MODEL", model),
        )

    if raw in ("http", "openai"):
        key = _env("LLM_API_KEY")
        if not key:
            raise ValueError("LLM_PROVIDER=http requires LLM_API_KEY")
        return LlmProviderConfig(
            name="http",
            api_key=key,
            base_url=_env("LLM_BASE_URL", "https://api.openai.com/v1"),
            model=_env("LLM_MODEL", "gpt-4o-mini"),
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER={raw!r}. "
        "Use nvidia|deepseek|moonshot|ollama|http|auto"
    )
