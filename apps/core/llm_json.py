"""Slim LLM response cleaning — fence / CoT strip + JSON extract (Mimwise-inspired)."""

from __future__ import annotations

import json
import re
from typing import Any, Optional


def strip_chain_of_thought(text: str) -> str:
    if not isinstance(text, str):
        return text
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<think>.*?$", "", text, flags=re.DOTALL | re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<think[^>]*>", "", text, flags=re.IGNORECASE)
    return text.strip()


def extract_json_from_response(response: str) -> Optional[Any]:
    """Parse JSON from plain text or markdown fences; return None on failure."""
    if not isinstance(response, str) or not response.strip():
        return None

    cleaned = strip_chain_of_thought(response)

    for pattern in (
        r"```json\s*\n(.*?)\n```",
        r"```\s*\n(.*?)\n```",
        r"```(.*?)```",
    ):
        m = re.search(pattern, cleaned, flags=re.DOTALL | re.IGNORECASE)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                pass

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Brace scrape: first {...} object
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            pass
    return None
