"""Adapters from pinned third-party layouts into comparison records."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from .model import Record
from .normalize import normalize_headword, normalize_pinyin


@dataclass(slots=True)
class LoadResult:
    records: list[Record] = field(default_factory=list)
    issues: list[dict[str, Any]] = field(default_factory=list)


_CHINESE_LEVELS = {
    "一级": "1",
    "二级": "2",
    "三级": "3",
    "四级": "4",
    "五级": "5",
    "六级": "6",
    "高等": "7-9",
    "七-九级": "7-9",
    "七至九级": "7-9",
}


def normalize_level(value: str) -> str:
    value = value.strip().replace("–", "-").replace("—", "-")
    if value.upper().startswith("HSK"):
        value = value[3:].strip()
    value = _CHINESE_LEVELS.get(value, value)
    if value in {"7", "8", "9", "7/9", "7-9"}:
        return "7-9"
    if value in {"1", "2", "3", "4", "5", "6"}:
        return value
    raise ValueError(f"unrecognized HSK level {value!r}")


def _strip_source_sense_suffix(value: str) -> str:
    """Remove the official table's 1/2 sense marker, not lexical digits."""

    return re.sub(r"(?<=[\u3400-\u9fff])[12]$", "", value.strip())


def _pinyin_key(
    value: str | None, locator: str, issues: list[dict[str, Any]]
) -> str | None:
    if value is None or not value.strip():
        return None
    try:
        return "/".join(normalize_pinyin(value))
    except ValueError as error:
        issues.append(
            {
                "source_locator": locator,
                "field": "pinyin",
                "value": value,
                "message": str(error),
            }
        )
        return None


def _read_delimited(path: Path, delimiter: str) -> Iterable[tuple[int, dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        for line_number, row in enumerate(
            csv.DictReader(source, delimiter=delimiter), start=2
        ):
            yield line_number, dict(row)


def load_canonical_jsonl(path: Path) -> LoadResult:
    result = LoadResult()
    with path.open(encoding="utf-8-sig") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            locator = f"{path.name}:{line_number}"
            try:
                row = json.loads(line)
                pinyin = row.get("pinyin")
                provided_key = row.get("pinyin_normalized")
                key = _pinyin_key(provided_key or pinyin, locator, result.issues)
                result.records.append(
                    Record(
                        record_id=str(row["record_id"]),
                        level=normalize_level(str(row["level"])),
                        simplified=(
                            normalize_headword(str(row["simplified"]))
                            if row.get("simplified")
                            else None
                        ),
                        traditional=(
                            normalize_headword(str(row["traditional"]))
                            if row.get("traditional")
                            else None
                        ),
                        pinyin=str(pinyin) if pinyin else None,
                        pinyin_normalized=key,
                        part_of_speech=row.get("part_of_speech"),
                        source_locator=row.get("source_locator", locator),
                        raw=row,
                    )
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                result.issues.append(
                    {"source_locator": locator, "message": str(error)}
                )
    return result


def load_shawkynasr_2021(path: Path) -> LoadResult:
    result = LoadResult()
    for line_number, row in _read_delimited(path, ","):
        locator = f"{path.name}:{line_number}"
        try:
            headword = normalize_headword(_strip_source_sense_suffix(row["词语"]))
            pinyin = _shawkynasr_pinyin(row.get("拼音") or "")
            result.records.append(
                Record(
                    record_id=f"shawkynasr:{row['No.']}",
                    level=normalize_level(row["级别"]),
                    simplified=headword,
                    pinyin=row.get("拼音") or None,
                    pinyin_normalized=_pinyin_key(
                        pinyin, locator, result.issues
                    ),
                    part_of_speech=row.get("词性") or None,
                    source_locator=locator,
                    raw=row,
                )
            )
        except (KeyError, TypeError, ValueError) as error:
            result.issues.append({"source_locator": locator, "message": str(error)})
    return result


def _shawkynasr_pinyin(value: str) -> str:
    """Translate documented query-export notation into comparison notation.

    ``∥`` and ``·`` are internal word boundaries, ``∣`` separates variants,
    and parenthesized text denotes an optional/expanded form. Both parenthesis
    variants are retained as readings; no choice is made between them.
    """

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


def load_punpuf_2025(path: Path) -> LoadResult:
    result = LoadResult()
    for line_number, row in _read_delimited(path, "\t"):
        locator = f"{path.name}:{line_number}"
        try:
            # traditional_cc-cedict and definition_cc-cedict are enrichment, not
            # syllabus fields, and are deliberately excluded from identity.
            headword = normalize_headword(_strip_source_sense_suffix(row["word"]))
            pinyin = row.get("pinyin_numbered") or row.get("pinyin")
            result.records.append(
                Record(
                    record_id=f"punpuf:{row['word_index']}:{row['level']}",
                    level=normalize_level(row["level"]),
                    simplified=headword,
                    pinyin=row.get("pinyin") or None,
                    pinyin_normalized=_pinyin_key(pinyin, locator, result.issues),
                    part_of_speech=row.get("part_of_speech") or None,
                    source_locator=locator,
                    raw=row,
                )
            )
        except (KeyError, TypeError, ValueError) as error:
            result.issues.append({"source_locator": locator, "message": str(error)})
    return result


def _profesorm_levels(value: str) -> list[str]:
    labels = re.findall(r"[一二三四五六]级|七[-至]九级", value)
    if not labels:
        labels = [value]
    return [normalize_level(label) for label in labels]


def load_profesorm_2025(path: Path) -> LoadResult:
    result = LoadResult()
    for line_number, row in _read_delimited(path, ","):
        locator = f"{path.name}:{line_number}"
        try:
            headword = normalize_headword(_strip_source_sense_suffix(row["word"]))
            levels = _profesorm_levels(row["levelName"])
            for level in levels:
                result.records.append(
                    Record(
                        record_id=f"profesorm:{row['sort']}:{level}",
                        level=level,
                        simplified=headword,
                        pinyin=row.get("pinyin") or None,
                        pinyin_normalized=_pinyin_key(
                            row.get("pinyin"), locator, result.issues
                        ),
                        part_of_speech=row.get("cixing") or None,
                        source_locator=locator,
                        raw=row,
                    )
                )
        except (KeyError, TypeError, ValueError) as error:
            result.issues.append({"source_locator": locator, "message": str(error)})
    return result


def _level_from_krmanik_name(name: str) -> str:
    match = re.search(r"(?:HSK(?:_Level)?[ _])([1-6]|7-9)", name)
    if not match:
        raise ValueError(f"cannot infer level from {name!r}")
    return normalize_level(match.group(1))


def load_krmanik_headword_directory(path: Path) -> LoadResult:
    result = LoadResult()
    for source_file in sorted(path.glob("*.txt")):
        try:
            level = _level_from_krmanik_name(source_file.name)
        except ValueError as error:
            result.issues.append(
                {"source_locator": source_file.name, "message": str(error)}
            )
            continue
        with source_file.open(encoding="utf-8-sig") as source:
            for line_number, line in enumerate(source, start=1):
                if not line.strip():
                    continue
                locator = f"{source_file.name}:{line_number}"
                try:
                    headword = normalize_headword(_strip_source_sense_suffix(line))
                    result.records.append(
                        Record(
                            record_id=f"krmanik:{level}:{line_number}",
                            level=level,
                            simplified=headword,
                            source_locator=locator,
                            raw={"word": line.rstrip("\r\n")},
                        )
                    )
                except ValueError as error:
                    result.issues.append(
                        {"source_locator": locator, "message": str(error)}
                    )
    return result


ADAPTERS: dict[str, Callable[[Path], LoadResult]] = {
    "canonical-jsonl": load_canonical_jsonl,
    "shawkynasr-2021-csv": load_shawkynasr_2021,
    "punpuf-2025-tsv": load_punpuf_2025,
    "profesorm-2025-csv": load_profesorm_2025,
    "krmanik-headword-directory": load_krmanik_headword_directory,
}


def load_records(adapter: str, path: Path) -> LoadResult:
    try:
        loader = ADAPTERS[adapter]
    except KeyError as error:
        choices = ", ".join(sorted(ADAPTERS))
        raise ValueError(f"unknown adapter {adapter!r}; choose one of: {choices}") from error
    return loader(path)
