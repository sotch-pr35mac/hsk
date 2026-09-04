#!/usr/bin/env python3
"""Extract lexical forms for the official 2015 rows from the UNIGE edition.

The official CTI workbook establishes membership and level.  It does not carry
pinyin or traditional forms.  The University of Geneva edition explicitly
states that its syllabus sections reproduce that 2015 corpus and is therefore
used only as a lexical enrichment source.  Implicit/recombined sections and
French definitions are never read.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import unicodedata
from collections import Counter
from pathlib import Path

import fitz


LEVEL_PAGES = {
    1: range(3, 9),
    2: range(12, 17),
    3: range(20, 30),
    4: range(36, 55),
    5: range(65, 108),
    6: range(116, 207),
}
LEVEL_COUNTS = {1: 150, 2: 150, 3: 300, 4: 600, 5: 1300, 6: 2500}


def normalized(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip()


def is_pinyin(value: str) -> bool:
    if not value or any(character.isdigit() for character in value):
        return False
    allowed_ascii = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ:'’- ")
    for character in unicodedata.normalize("NFD", value):
        if character in allowed_ascii or unicodedata.combining(character):
            continue
        return False
    return True


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as output:
        output.write(content)
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("official_csv", type=Path)
    parser.add_argument("unige_pdf", type=Path)
    parser.add_argument("output_csv", type=Path)
    args = parser.parse_args()

    official = list(csv.DictReader(args.official_csv.open(encoding="utf-8", newline="")))
    if Counter(int(row["level"]) for row in official) != Counter(LEVEL_COUNTS):
        parser.error("official CSV does not have the expected 2015 level counts")

    document = fitz.open(args.unige_pdf)
    page_lines: dict[int, list[tuple[int, list[str]]]] = {}
    for level, pages in LEVEL_PAGES.items():
        page_lines[level] = []
        for page_number in pages:
            lines = [normalized(line) for line in document[page_number - 1].get_text().splitlines()]
            page_lines[level].append((page_number, [line for line in lines if line]))

    offsets = {1: 0, 2: 150, 3: 300, 4: 600, 5: 1200, 6: 2500}
    enriched: list[dict[str, str]] = []
    unresolved: list[dict[str, object]] = []
    for row in official:
        level = int(row["level"])
        local_sequence = int(row["source_sequence"]) - offsets[level]
        simplified = normalized(row["simplified"])
        matches: list[tuple[int, str, str]] = []
        for page_number, lines in page_lines[level]:
            for index in range(len(lines) - 3):
                if lines[index] != str(local_sequence) or lines[index + 1] != simplified:
                    continue
                traditional = lines[index + 2]
                pinyin = lines[index + 3]
                if not is_pinyin(pinyin):
                    continue
                matches.append((page_number, traditional, pinyin))
        unique = list(dict.fromkeys(matches))
        if len(unique) != 1:
            unresolved.append(
                {
                    "level": level,
                    "local_sequence": local_sequence,
                    "simplified": simplified,
                    "matches": unique,
                }
            )
            continue
        page_number, traditional, pinyin = unique[0]
        enriched.append(
            {
                "source_sequence": row["source_sequence"],
                "level": str(level),
                "simplified": simplified,
                "traditional": traditional,
                "pinyin": pinyin,
                "enrichment_locator": f"unige-pdf-page:{page_number};level-sequence:{local_sequence}",
            }
        )

    fields = [
        "source_sequence",
        "level",
        "simplified",
        "traditional",
        "pinyin",
        "enrichment_locator",
    ]
    from io import StringIO

    buffer = StringIO(newline="\n")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(enriched)
    write_atomic(args.output_csv, buffer.getvalue())
    report = {
        "classification_source": "hsk2015",
        "enriched_rows": len(enriched),
        "enrichment_document_sha256": sha256(args.unige_pdf),
        "enrichment_source": "University of Geneva 2015-syllabus-based annotated vocabulary",
        "excluded_sections": ["implicit-recombined", "implicit-reduced", "special-cases", "definitions"],
        "official_rows": len(official),
        "summary": {
            "present_in_both": len(enriched),
            "authoritative_only": len(unresolved),
            "verification_only": 0,
            "pinyin_disagreements": 0,
            "level_disagreements": 0,
            "duplicate_disagreements": 0,
            "manual_or_definition_matches": 0,
        },
        "unresolved": unresolved,
    }
    report_path = args.output_csv.with_suffix(".report.json")
    write_atomic(report_path, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    if unresolved:
        print(f"{len(unresolved)} rows require lexical review; see {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
