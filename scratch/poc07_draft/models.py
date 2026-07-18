"""Pydantic models for draft results."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

DraftSource = Literal["memory_precedent", "playbook_fallback", "llm_suggested", "none"]


class DraftResult(BaseModel):
    playbook_rule_id: str
    finding_status: str
    draft_text: Optional[str] = None
    draft_source: DraftSource = "none"
    precedent_ids: list[str] = Field(default_factory=list)
    rationale: str = ""
    provenance: dict = Field(default_factory=dict)
