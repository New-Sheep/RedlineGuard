"""Playbook document schema + FakePlaybookBootstrap (FAKE_LLM path)."""

from __future__ import annotations

import re
from typing import Optional, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field


class PlaybookRule(BaseModel):
    id: str
    clause_type: str
    preferred: str
    hard_ceiling: str
    fallback_text: Optional[str] = None
    severity: str = "medium"
    match_any: list[str] = Field(default_factory=list)


class PlaybookDocument(BaseModel):
    version: int = 1
    name: str
    preferred_governing_law: str = "England and Wales"
    rules: list[PlaybookRule] = Field(default_factory=list)


class PlaybookBootstrap(Protocol):
    def propose(self, text: str, source_name: str = "playbook") -> PlaybookDocument: ...


def _slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
    return (s[:48] or "rule") + "_" + uuid4().hex[:6]


# Keyword → rule templates. Matched if any needle appears in text (case-insensitive).
_RULE_TEMPLATES: list[dict] = [
    {
        "needles": ["governing law", "jurisdiction", "england and wales"],
        "clause_type": "governing_law",
        "id_prefix": "governing_law",
        "preferred": "England and Wales",
        "hard_ceiling": "Flag non-UK governing law without Head of Legal approval",
        "fallback_text": (
            "This Agreement shall be governed by the laws of England and Wales."
        ),
        "severity": "medium",
        "match_any": [
            "laws of the State of California",
            "laws of California",
            "State of New York",
            "laws of the State of",
            "Delaware",
        ],
        "preferred_law": True,
    },
    {
        "needles": ["limitation of liability", "aggregate liability", "unlimited liability"],
        "clause_type": "liability_cap",
        "id_prefix": "liability_cap",
        "preferred": "Cap aggregate liability at 12 months fees (or documented hard cap)",
        "hard_ceiling": "Unlimited liability is forbidden except standard carve-outs",
        "fallback_text": (
            "Each party's aggregate liability shall not exceed the fees paid under "
            "this Agreement in the twelve (12) months preceding the claim."
        ),
        "severity": "high",
        "match_any": [
            "unlimited liability",
            "uncapped liability",
            "without limitation of liability",
        ],
    },
    {
        "needles": ["indemnif", "hold harmless"],
        "clause_type": "indemnity",
        "id_prefix": "indemnity",
        "preferred": "Mutual, capped indemnity aligned to fees",
        "hard_ceiling": "No uncapped or one-sided broad indemnification",
        "fallback_text": (
            "Each party's aggregate indemnification obligations shall not exceed the "
            "fees paid under this Agreement in the twelve (12) months preceding the claim."
        ),
        "severity": "high",
        "match_any": [
            "shall indemnify",
            "indemnify and hold harmless",
            "INDEMNIFICATION",
        ],
    },
    {
        "needles": ["intellectual property", "background ip", "retains all rights"],
        "clause_type": "ip_ownership",
        "id_prefix": "ip_ownership",
        "preferred": "Retain 100% ownership of background IP; customer gets limited license",
        "hard_ceiling": "Never assign or transfer background IP / software copyrights",
        "fallback_text": (
            "PortSwigger retains all rights, title, and interest in its pre-existing "
            "Intellectual Property. Customer is granted a limited license to use "
            "deliverables as intended."
        ),
        "severity": "high",
        "match_any": [
            "assign all intellectual property",
            "transfer ownership of",
            "IP Surrender",
            "work made for hire",
        ],
    },
    {
        "needles": ["confidential", "nda", "trade secret"],
        "clause_type": "confidentiality",
        "id_prefix": "confidentiality_term",
        "preferred": "Confidentiality term of 3–5 years after termination",
        "hard_ceiling": "No perpetual/indefinite confidentiality except trade secrets",
        "fallback_text": (
            "Confidentiality obligations shall survive for three (3) years from the "
            "date of disclosure (except for Trade Secrets, which remain protected "
            "while they qualify as such)."
        ),
        "severity": "medium",
        "match_any": [
            "perpetual confidentiality",
            "indefinite confidentiality",
            "in perpetuity",
        ],
    },
    {
        "needles": ["non-compete", "non compete", "restrictive covenant"],
        "clause_type": "non_compete",
        "id_prefix": "non_compete",
        "preferred": "Do not accept non-compete clauses",
        "hard_ceiling": "Non-competes require senior counsel exception",
        "fallback_text": None,
        "severity": "high",
        "match_any": ["non-compete", "noncompete", "shall not compete"],
    },
    {
        "needles": ["non-negotiable", "non negotiable"],
        "clause_type": "process",
        "id_prefix": "non_negotiable",
        "preferred": "Inbound paper should be negotiable",
        "hard_ceiling": "Documents marked non-negotiable need senior counsel",
        "fallback_text": None,
        "severity": "high",
        "match_any": ["Non-Negotiable", "non-negotiable"],
    },
    {
        "needles": ["50%", "majority", "ownership", "control"],
        "clause_type": "equity_control",
        "id_prefix": "equity_control",
        "preferred": "Counterparty must not retain majority ownership/control",
        "hard_ceiling": "Never accept >=50% ownership or control by counterparty",
        "fallback_text": None,
        "severity": "high",
        "match_any": ["50.1%", "majority ownership", "maintain control"],
    },
]


class FakePlaybookBootstrap:
    """Deterministic PDF→rules bootstrap (no network LLM)."""

    def propose(self, text: str, source_name: str = "playbook") -> PlaybookDocument:
        lower = text.lower()
        name = f"Imported playbook ({source_name})"
        m = re.search(
            r"(portswigger[^\n]{0,80}playbook|commercial contract playbook[^\n]*)",
            text,
            flags=re.IGNORECASE,
        )
        if m:
            name = re.sub(r"\s+", " ", m.group(1)).strip()[:120]

        preferred_law = "England and Wales"
        if "england and wales" in lower:
            preferred_law = "England and Wales"

        rules: list[PlaybookRule] = []
        for tmpl in _RULE_TEMPLATES:
            if any(n in lower for n in tmpl["needles"]):
                rules.append(
                    PlaybookRule(
                        id=_slug(tmpl["id_prefix"]),
                        clause_type=tmpl["clause_type"],
                        preferred=tmpl["preferred"],
                        hard_ceiling=tmpl["hard_ceiling"],
                        fallback_text=tmpl["fallback_text"],
                        severity=tmpl["severity"],
                        match_any=list(tmpl["match_any"]),
                    )
                )
                if tmpl.get("preferred_law"):
                    preferred_law = tmpl["preferred"]

        if not rules:
            # Thin PDF: still return a minimal usable starter set
            rules = [
                PlaybookRule(
                    id=_slug("review_required"),
                    clause_type="process",
                    preferred="Manual playbook review required — few cues detected in PDF",
                    hard_ceiling="Do not auto-approve until rules are curated",
                    fallback_text=None,
                    severity="medium",
                    match_any=["TODO_CURATE_PLAYBOOK"],
                )
            ]

        return PlaybookDocument(
            version=1,
            name=name,
            preferred_governing_law=preferred_law,
            rules=rules,
        )


def get_bootstrap() -> PlaybookBootstrap:
    """FAKE_LLM path for now; swap for LlmPlaybookBootstrap later."""
    return FakePlaybookBootstrap()
