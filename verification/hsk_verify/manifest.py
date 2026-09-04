"""Validation and optional local fingerprint checks for verification sources."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

_SHA256 = re.compile(r"[0-9a-f]{64}")
_GIT_COMMIT = re.compile(r"[0-9a-f]{40}")
_DATASETS = {
    "hsk_2015_exam",
    "proficiency_standard_2021",
    "hsk_exam_syllabus_2025",
}


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        manifest = json.load(source)
    validate_manifest(manifest)
    return manifest


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != 1:
        raise ValueError("manifest schema_version must be 1")
    if not manifest.get("retrieval_date"):
        raise ValueError("manifest retrieval_date is required")
    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("manifest sources must be a non-empty list")

    identifiers: set[str] = set()
    for source in sources:
        source_id = source.get("id")
        if not source_id or source_id in identifiers:
            raise ValueError(f"missing or duplicate source id {source_id!r}")
        identifiers.add(source_id)
        if source.get("dataset") not in _DATASETS:
            raise ValueError(f"{source_id}: invalid dataset")
        for required in (
            "name",
            "provider",
            "claimed_edition",
            "last_update",
            "license",
            "derivation",
            "revision",
            "artifacts",
        ):
            if required not in source:
                raise ValueError(f"{source_id}: missing {required}")
        revision = source["revision"]
        if revision.get("type") == "git_commit" and not _GIT_COMMIT.fullmatch(
            revision.get("value", "")
        ):
            raise ValueError(f"{source_id}: git revision must be a full commit")
        if not source["license"].get("redistribution"):
            raise ValueError(f"{source_id}: license redistribution status is required")
        if "same_authoritative_source" not in source["derivation"]:
            raise ValueError(
                f"{source_id}: derivation.same_authoritative_source is required"
            )
        for artifact in source["artifacts"]:
            digest = artifact.get("sha256", "")
            if not _SHA256.fullmatch(digest):
                raise ValueError(f"{source_id}: artifact has invalid SHA-256")
            if not artifact.get("url"):
                raise ValueError(f"{source_id}: artifact URL is required")


def source_by_id(manifest: dict[str, Any], source_id: str) -> dict[str, Any]:
    for source in manifest["sources"]:
        if source["id"] == source_id:
            return source
    raise ValueError(f"source id {source_id!r} is not in the manifest")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_source_artifacts(source: dict[str, Any], repository_root: Path) -> list[str]:
    """Return mismatch messages for artifacts present beneath a local checkout."""

    errors: list[str] = []
    for artifact in source["artifacts"]:
        relative_path = artifact.get("repository_path")
        if relative_path is None:
            continue
        path = repository_root / relative_path
        if not path.is_file():
            errors.append(f"missing artifact: {path}")
            continue
        actual = sha256_file(path)
        if actual != artifact["sha256"]:
            errors.append(
                f"SHA-256 mismatch for {path}: expected {artifact['sha256']}, got {actual}"
            )
    return errors
