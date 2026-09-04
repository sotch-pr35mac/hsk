"""Stable JSON and review-oriented Markdown report serialization."""

from __future__ import annotations

import json
from typing import Any

from .model import ComparisonReport


def json_report(report: ComparisonReport) -> str:
    return json.dumps(report.as_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = ", ".join(str(item) for item in value)
    return str(value).replace("|", "\\|").replace("\n", " ")


def _pair_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Headword | Authoritative ID | A level | A pinyin | Verification ID | V level | V pinyin |",
        "|---|---|---:|---|---|---:|---|",
    ]
    for row in rows:
        authoritative = row["authoritative"]
        verification = row["verification"]
        lines.append(
            "| "
            + " | ".join(
                _cell(value)
                for value in (
                    row.get("matched_headword"),
                    authoritative.get("record_id"),
                    authoritative.get("level"),
                    authoritative.get("pinyin_normalized"),
                    verification.get("record_id"),
                    verification.get("level"),
                    verification.get("pinyin_normalized"),
                )
            )
            + " |"
        )
    return "\n".join(lines)


def _record_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| ID | Headword | Level | Pinyin | Source locator |",
        "|---|---|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                _cell(value)
                for value in (
                    row.get("record_id"),
                    row.get("simplified") or row.get("traditional"),
                    row.get("level"),
                    row.get("pinyin_normalized"),
                    row.get("source_locator"),
                )
            )
            + " |"
        )
    return "\n".join(lines)


def markdown_report(report: ComparisonReport) -> str:
    data = report.as_dict()
    source_name = data["verification"].get("name") or data["verification"].get(
        "source_id", "verification source"
    )
    lines = [
        "# HSK independent verification report",
        "",
        f"Verification source: **{_cell(source_name)}**",
        "",
        "> This report is diagnostic. Verification data never overwrites the authoritative extraction, and definitions are never used as lexical identity.",
        "",
        "## Summary",
        "",
        "| Category | Count |",
        "|---|---:|",
    ]
    for category, count in data["summary"].items():
        lines.append(f"| `{category}` | {count} |")

    sections = (
        ("Present in both", report.present_in_both, _pair_table),
        ("Authoritative only", report.authoritative_only, _record_table),
        ("Verification only", report.verification_only, _record_table),
        ("Pinyin disagreements", report.pinyin_disagreements, _pair_table),
        ("Level disagreements", report.level_disagreements, _pair_table),
        ("Headword-only candidates (not matches)", report.headword_only_candidates, _pair_table),
    )
    for heading, rows, renderer in sections:
        lines.extend(["", f"## {heading}", "", renderer(rows)])

    lines.extend(
        [
            "",
            "## Duplicate disagreements",
            "",
            "| Headword | Pinyin | Authoritative count | Verification count |",
            "|---|---|---:|---:|",
        ]
    )
    for row in report.duplicate_disagreements:
        lines.append(
            "| "
            + " | ".join(
                _cell(row[key])
                for key in (
                    "headword",
                    "pinyin_normalized",
                    "authoritative_count",
                    "verification_count",
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Parse issues",
            "",
            "| Side | Source locator | Field | Value | Message |",
            "|---|---|---|---|---|",
        ]
    )
    for row in report.parse_issues:
        lines.append(
            "| "
            + " | ".join(
                _cell(row.get(key))
                for key in ("side", "source_locator", "field", "value", "message")
            )
            + " |"
        )
    return "\n".join(lines) + "\n"
