# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - Unreleased

### Added

- Separate, explicitly selectable classifications for the HSK 2.0 / 2015
  examination vocabulary, the 2021 International Chinese Education proficiency
  standard, and the current HSK 3.0 examination syllabus.
- Reading-aware lookup using simplified or traditional orthography and
  normalized pinyin.
- Orthography-only lookup with explicit `Unique`, `Ambiguous`, and `NotFound`
  outcomes.
- Queries across every supported classification and exact-level or cumulative
  vocabulary enumeration.
- Deterministic extraction and generation tooling, source fingerprints,
  machine-readable discrepancy reports, and data-integrity checks.

### Changed

- Replaced the bundled, unattributed HSK map with data generated from official
  CTI and Ministry of Education publications.
- Lookups now return typed classification results rather than numeric sentinel
  values.
- Static generated indexes replace per-instance bincode deserialization and
  `HashMap` construction.
- Runtime and benchmark dependencies were refreshed to
  `unicode-normalization` 0.1.25 and Criterion 0.7.0 (Rust 1.85 compatible).
- Extraction and verification tooling moved to the standalone `hsk_tooling`
  repository; the published crate now has an explicit Rust-only file list.

### Removed

- Removed `Hsk::new()` and `Hsk::get_hsk(&str) -> u8`. See
  [`MIGRATION.md`](MIGRATION.md) for equivalent versioned queries.
- Removed the convention that level `0` means “not found.” Absence and
  ambiguity are now separate outcomes.

### Compatibility

- This is a major-version release. Callers must select an `HskSystem`, use the
  `HskLevel` enum instead of numeric levels, and handle ambiguous readings.
- The minimum supported Rust version is Rust 1.85, required by Rust edition
  2024.
