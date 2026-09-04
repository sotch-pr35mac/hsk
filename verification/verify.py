#!/usr/bin/env python3
"""CLI for pinned-source validation and authoritative/verification comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from hsk_verify.adapters import ADAPTERS, load_records
from hsk_verify.compare import compare_records
from hsk_verify.manifest import (
    check_source_artifacts,
    load_manifest,
    source_by_id,
)
from hsk_verify.report import json_report, markdown_report

ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = ROOT / "sources.json"


def _input_digest(path: Path) -> str:
    digest = hashlib.sha256()
    paths = [path] if path.is_file() else sorted(item for item in path.rglob("*") if item.is_file())
    for item in paths:
        if path.is_dir():
            digest.update(item.relative_to(path).as_posix().encode("utf-8"))
            digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _source_metadata(source: dict[str, Any], input_path: Path) -> dict[str, Any]:
    return {
        "source_id": source["id"],
        "name": source["name"],
        "dataset": source["dataset"],
        "revision": source["revision"],
        "input_sha256": _input_digest(input_path),
        "canonical": False,
    }


def _validate_manifest(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    errors: list[str] = []
    for assignment in args.checkout:
        source_id, separator, path = assignment.partition("=")
        if not separator:
            errors.append(f"invalid --checkout {assignment!r}; expected SOURCE_ID=PATH")
            continue
        source = source_by_id(manifest, source_id)
        errors.extend(check_source_artifacts(source, Path(path)))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"validated {len(manifest['sources'])} pinned verification sources")
    return 0


def _inspect(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    source = source_by_id(manifest, args.source_id)
    adapter = args.adapter or next(
        (artifact["adapter"] for artifact in source["artifacts"] if artifact["adapter"]),
        None,
    )
    if adapter is None:
        raise ValueError(f"{args.source_id} has no machine-readable adapter")
    loaded = load_records(adapter, args.input)
    actual = Counter(record.level for record in loaded.records)
    output = {
        "source_id": args.source_id,
        "adapter": adapter,
        "records": len(loaded.records),
        "counts_by_level": dict(sorted(actual.items())),
        "parse_issues": loaded.issues,
        "expected": source["expected"],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    expected_counts = source["expected"].get("counts_by_level")
    if loaded.issues or (expected_counts is not None and dict(actual) != expected_counts):
        return 1
    expected_assignments = source["expected"].get("classification_assignments")
    return int(expected_assignments is not None and len(loaded.records) != expected_assignments)


def _compare(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    source = source_by_id(manifest, args.source_id)
    verification_adapter = args.verification_adapter or next(
        (artifact["adapter"] for artifact in source["artifacts"] if artifact["adapter"]),
        None,
    )
    if verification_adapter is None:
        raise ValueError(f"{args.source_id} has no machine-readable adapter")
    authoritative = load_records(args.authoritative_adapter, args.authoritative)
    verification = load_records(verification_adapter, args.verification)
    report = compare_records(
        authoritative.records,
        verification.records,
        authoritative_metadata={
            "name": args.authoritative.name,
            "input_sha256": _input_digest(args.authoritative),
            "canonical": True,
        },
        verification_metadata=_source_metadata(source, args.verification),
        authoritative_issues=authoritative.issues,
        verification_issues=verification.issues,
    )
    json_text = json_report(report)
    markdown_text = markdown_report(report)
    if args.json_output:
        args.json_output.write_text(json_text, encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.write_text(markdown_text, encoding="utf-8")
    if not args.json_output and not args.markdown_output:
        sys.stdout.write(json_text)
    return int(bool(report.parse_issues))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    subparsers = result.add_subparsers(dest="command", required=True)

    manifest_parser = subparsers.add_parser("validate-manifest")
    manifest_parser.add_argument(
        "--checkout",
        action="append",
        default=[],
        metavar="SOURCE_ID=PATH",
        help="also verify pinned artifact hashes in a local source checkout",
    )
    manifest_parser.set_defaults(handler=_validate_manifest)

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--source-id", required=True)
    inspect_parser.add_argument("--input", required=True, type=Path)
    inspect_parser.add_argument("--adapter", choices=sorted(ADAPTERS))
    inspect_parser.set_defaults(handler=_inspect)

    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("--source-id", required=True)
    compare_parser.add_argument("--authoritative", required=True, type=Path)
    compare_parser.add_argument("--verification", required=True, type=Path)
    compare_parser.add_argument(
        "--authoritative-adapter",
        choices=sorted(ADAPTERS),
        default="canonical-jsonl",
    )
    compare_parser.add_argument(
        "--verification-adapter",
        choices=sorted(ADAPTERS),
        help="defaults to the first machine-readable adapter in the source manifest",
    )
    compare_parser.add_argument("--json-output", type=Path)
    compare_parser.add_argument("--markdown-output", type=Path)
    compare_parser.set_defaults(handler=_compare)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        return args.handler(args)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
