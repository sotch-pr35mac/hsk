#!/usr/bin/env python3
"""Export canonical CSV assignments to the verifier's JSONL contract."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


def comparison_pinyin(value: str) -> str:
    """Expand source notation without changing the retained raw value."""

    value = value.replace("∥", "").replace("·", "").replace("∣", "/")
    value = value.replace("（", "(").replace("）", ")")
    alternatives: list[str] = []
    for part in value.split("/"):
        match = re.fullmatch(r"([^()]*)\(([^()]*)\)([^()]*)", part.strip())
        if match:
            prefix, optional, suffix = match.groups()
            alternatives.extend((prefix + suffix, prefix + optional + suffix))
        elif part.strip():
            alternatives.append(part)
    return "/".join(alternatives)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("canonical_csv", type=Path)
    parser.add_argument("output_jsonl", type=Path)
    parser.add_argument("--enrichment", type=Path)
    args = parser.parse_args()

    enrichment = {}
    if args.enrichment:
        enrichment = {
            row["source_sequence"]: row
            for row in csv.DictReader(args.enrichment.open(encoding="utf-8", newline=""))
        }

    output = []
    for row in csv.DictReader(args.canonical_csv.open(encoding="utf-8", newline="")):
        extra = enrichment.get(row["source_sequence"], {})
        pinyin = extra.get("pinyin", row["pinyin_raw"])
        if (
            row["source_id"] == "proficiency2021"
            and row["extraction_method"] != "rapidocr-authoritative-row"
            and not row["correction_ids"]
        ):
            pinyin = ""
        levels = [row["level"], *filter(None, row["additional_levels"].split(";"))]
        for level in levels:
            record = {
                "record_id": f"{row['source_id']}:{row['source_sequence']}:{level}",
                "level": level,
                "simplified": row["simplified"],
                "traditional": extra.get("traditional", row["traditional"]),
                "pinyin": pinyin,
                "part_of_speech": row["part_of_speech_raw"],
                "source_locator": row["source_locator"],
            }
            if record["pinyin"]:
                record["pinyin_normalized"] = comparison_pinyin(record["pinyin"])
            output.append(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    args.output_jsonl.write_text("\n".join(output) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
