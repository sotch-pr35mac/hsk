"""Data types shared by source adapters and report writers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

VALID_LEVELS = frozenset({"1", "2", "3", "4", "5", "6", "7-9"})


@dataclass(frozen=True, slots=True)
class Record:
    """One classification assignment from one dataset.

    ``raw`` is retained only as review context. Comparison code deliberately does
    not inspect it, which prevents definitions or other enrichment from becoming
    lexical identity.
    """

    record_id: str
    level: str
    simplified: str | None
    traditional: str | None = None
    pinyin: str | None = None
    pinyin_normalized: str | None = None
    part_of_speech: str | None = None
    source_locator: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self) -> None:
        if not self.record_id:
            raise ValueError("record_id must not be empty")
        if self.level not in VALID_LEVELS:
            raise ValueError(f"invalid level {self.level!r}")
        if not self.simplified and not self.traditional:
            raise ValueError("at least one headword form is required")

    @property
    def forms(self) -> frozenset[str]:
        return frozenset(
            form for form in (self.simplified, self.traditional) if form is not None
        )

    @property
    def display_headword(self) -> str:
        return self.simplified or self.traditional or ""

    def public_dict(self) -> dict[str, Any]:
        """Return stable review fields, intentionally excluding arbitrary raw data."""

        return {
            "record_id": self.record_id,
            "level": self.level,
            "simplified": self.simplified,
            "traditional": self.traditional,
            "pinyin": self.pinyin,
            "pinyin_normalized": self.pinyin_normalized,
            "part_of_speech": self.part_of_speech,
            "source_locator": self.source_locator,
        }


@dataclass(slots=True)
class ComparisonReport:
    authoritative: dict[str, Any]
    verification: dict[str, Any]
    present_in_both: list[dict[str, Any]] = field(default_factory=list)
    authoritative_only: list[dict[str, Any]] = field(default_factory=list)
    verification_only: list[dict[str, Any]] = field(default_factory=list)
    pinyin_disagreements: list[dict[str, Any]] = field(default_factory=list)
    level_disagreements: list[dict[str, Any]] = field(default_factory=list)
    duplicate_disagreements: list[dict[str, Any]] = field(default_factory=list)
    headword_only_candidates: list[dict[str, Any]] = field(default_factory=list)
    parse_issues: list[dict[str, Any]] = field(default_factory=list)

    def summary(self) -> dict[str, int]:
        return {
            "present_in_both": len(self.present_in_both),
            "authoritative_only": len(self.authoritative_only),
            "verification_only": len(self.verification_only),
            "pinyin_disagreements": len(self.pinyin_disagreements),
            "level_disagreements": len(self.level_disagreements),
            "duplicate_disagreements": len(self.duplicate_disagreements),
            "headword_only_candidates": len(self.headword_only_candidates),
            "parse_issues": len(self.parse_issues),
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "generated_by": "hsk_verify/1.0.0",
            "authoritative": self.authoritative,
            "verification": self.verification,
            "policy": {
                "lexical_identity": "intersecting_headword_form+normalized_pinyin",
                "definitions_used_for_identity": False,
                "verification_can_override_authoritative": False,
                "missing_pinyin_is_exact_match": False,
            },
            "summary": self.summary(),
            "present_in_both": self.present_in_both,
            "authoritative_only": self.authoritative_only,
            "verification_only": self.verification_only,
            "pinyin_disagreements": self.pinyin_disagreements,
            "level_disagreements": self.level_disagreements,
            "duplicate_disagreements": self.duplicate_disagreements,
            "headword_only_candidates": self.headword_only_candidates,
            "parse_issues": self.parse_issues,
        }
