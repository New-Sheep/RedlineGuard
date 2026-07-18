"""Pydantic models for vector-memory decisions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

DecisionKind = Literal["accept", "edit", "reject"]


class DecisionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    clause_text: str
    decision: DecisionKind
    final_text: str
    playbook_rule_id: Optional[str] = None
    contract_id: str = "unknown"
    reasoning: Optional[str] = None
    filename: Optional[str] = None
    doc_kind: Optional[str] = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class PrecedentHit(BaseModel):
    record: DecisionRecord
    distance: Optional[float] = None
