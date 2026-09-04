"""Deterministic comparison using headword plus normalized pinyin identity."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable

from .model import ComparisonReport, Record


def _readings(record: Record) -> frozenset[str]:
    if not record.pinyin_normalized:
        return frozenset()
    return frozenset(
        reading for reading in record.pinyin_normalized.split("/") if reading
    )


def _pair(
    authoritative: Record, verification: Record, matched_headword: str
) -> dict[str, Any]:
    return {
        "matched_headword": matched_headword,
        "authoritative": authoritative.public_dict(),
        "verification": verification.public_dict(),
    }


def _stable_sort(rows: list[dict[str, Any]]) -> None:
    rows.sort(
        key=lambda row: (
            str(row.get("matched_headword", row.get("headword", ""))),
            str(row.get("pinyin_normalized", "")),
            str(row.get("authoritative", {}).get("record_id", "")),
            str(row.get("verification", {}).get("record_id", "")),
            str(row.get("record_id", "")),
        )
    )


def _duplicate_counts(records: Iterable[Record]) -> Counter[tuple[str, str]]:
    counts: Counter[tuple[str, str]] = Counter()
    for record in records:
        headword = record.display_headword
        for reading in _readings(record):
            counts[(headword, reading)] += 1
    return counts


def compare_records(
    authoritative_records: list[Record],
    verification_records: list[Record],
    *,
    authoritative_metadata: dict[str, Any] | None = None,
    verification_metadata: dict[str, Any] | None = None,
    authoritative_issues: list[dict[str, Any]] | None = None,
    verification_issues: list[dict[str, Any]] | None = None,
) -> ComparisonReport:
    """Compare datasets without mutating or adjudicating authoritative records."""

    report = ComparisonReport(
        authoritative=authoritative_metadata or {},
        verification=verification_metadata or {},
    )
    verification_by_form: dict[str, list[tuple[int, Record]]] = defaultdict(list)
    for index, record in enumerate(verification_records):
        for form in record.forms:
            verification_by_form[form].append((index, record))

    matched_authoritative: set[int] = set()
    matched_verification: set[int] = set()
    seen_pinyin_disagreements: set[tuple[str, str, str]] = set()
    seen_headword_candidates: set[tuple[str, str, str]] = set()

    for auth_index, authoritative in enumerate(authoritative_records):
        candidates_by_index: dict[int, Record] = {}
        for form in authoritative.forms:
            for verify_index, verification in verification_by_form.get(form, []):
                candidates_by_index[verify_index] = verification

        authoritative_readings = _readings(authoritative)
        for verify_index, verification in sorted(candidates_by_index.items()):
            matched_headword = sorted(authoritative.forms & verification.forms)[0]
            verification_readings = _readings(verification)
            pair = _pair(authoritative, verification, matched_headword)

            if authoritative_readings and verification_readings:
                common_readings = authoritative_readings & verification_readings
                if common_readings:
                    pair["matched_pinyin"] = sorted(common_readings)
                    report.present_in_both.append(pair)
                    matched_authoritative.add(auth_index)
                    matched_verification.add(verify_index)
                    if authoritative.level != verification.level:
                        report.level_disagreements.append(pair)
                else:
                    key = (
                        authoritative.record_id,
                        verification.record_id,
                        matched_headword,
                    )
                    if key not in seen_pinyin_disagreements:
                        report.pinyin_disagreements.append(pair)
                        seen_pinyin_disagreements.add(key)
            else:
                key = (
                    authoritative.record_id,
                    verification.record_id,
                    matched_headword,
                )
                if key not in seen_headword_candidates:
                    pair["reason"] = (
                        "authoritative pinyin missing"
                        if not authoritative_readings
                        else "verification pinyin missing"
                    )
                    report.headword_only_candidates.append(pair)
                    seen_headword_candidates.add(key)

    report.authoritative_only = [
        record.public_dict()
        for index, record in enumerate(authoritative_records)
        if index not in matched_authoritative
    ]
    report.verification_only = [
        record.public_dict()
        for index, record in enumerate(verification_records)
        if index not in matched_verification
    ]

    authoritative_duplicates = _duplicate_counts(authoritative_records)
    verification_duplicates = _duplicate_counts(verification_records)
    for headword, pinyin in sorted(
        set(authoritative_duplicates) | set(verification_duplicates)
    ):
        authoritative_count = authoritative_duplicates[(headword, pinyin)]
        verification_count = verification_duplicates[(headword, pinyin)]
        if max(authoritative_count, verification_count) > 1 and (
            authoritative_count != verification_count
        ):
            report.duplicate_disagreements.append(
                {
                    "headword": headword,
                    "pinyin_normalized": pinyin,
                    "authoritative_count": authoritative_count,
                    "verification_count": verification_count,
                }
            )

    report.parse_issues = [
        {"side": "authoritative", **issue}
        for issue in (authoritative_issues or [])
    ] + [
        {"side": "verification", **issue}
        for issue in (verification_issues or [])
    ]

    for rows in (
        report.present_in_both,
        report.authoritative_only,
        report.verification_only,
        report.pinyin_disagreements,
        report.level_disagreements,
        report.duplicate_disagreements,
        report.headword_only_candidates,
        report.parse_issues,
    ):
        _stable_sort(rows)
    return report
