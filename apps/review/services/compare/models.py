"""Layered playbook compare: L0 regex + L1 local semantic (no LLM)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Status = Literal["APPROVED", "FLAGGED", "REQUIRES_HUMAN"]
SourceKind = Literal["rule", "semantic", "llm"]


class LayeredFinding(BaseModel):
    clause_name: str
    status: Status
    playbook_rule_id: str
    deviation_reason: str
    suggested_counter_proposal: Optional[str] = None
    severity: str = "medium"
    clause_excerpt: str = ""
    start_offset: int = 0
    end_offset: int = 0
    sources: list[SourceKind] = Field(default_factory=lambda: ["rule"])
    confidence: float = 1.0
    match_distance: Optional[float] = None
    llm_disagrees: bool = False
    llm_rationale: str = ""


class LayeredReport(BaseModel):
    overall_risk_score: int = Field(ge=0, le=100)
    reviews: list[LayeredFinding]
    score_breakdown: dict[str, Any] = Field(default_factory=dict)


class FindingCandidate(BaseModel):
    """Internal merge unit before status/reason is finalized."""

    playbook_rule_id: str
    clause_name: str
    severity: str = "medium"
    clause_excerpt: str = ""
    start_offset: int = 0
    end_offset: int = 0
    sources: list[SourceKind] = Field(default_factory=list)
    confidence: float = 1.0
    match_distance: Optional[float] = None
    fallback_text: Optional[str] = None
    preferred: str = ""
    hard_ceiling: str = ""
