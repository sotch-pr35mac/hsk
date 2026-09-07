# Changelog

## [1.0.0] - Unreleased

### Added

- Named lookup for the 2015 HSK vocabulary, GF0025-2021 proficiency standard,
  and 2025/2026 HSK examination syllabus.
- Optional normalized-pinyin qualification through `HskQuery`.
- `levels_all` for matching classifications.

### Changed

- Replaced numeric sentinel results with `HskLevel` values and empty results.
- Replaced runtime deserialization and hash-map construction with a compact,
  embedded binary index. Startup performs no parsing or heap allocation.
- Reduced quick-benchmark lookup latency by roughly 39–47% across hits, misses,
  normalization-heavy queries, multi-level results, and all-system lookup.
- Reduced the release archive from 3.1 MiB to 625.3 KiB uncompressed and from
  563.4 KiB to 244.9 KiB compressed.
- Updated `unicode-normalization` to 0.1.25 and Criterion to 0.7.0 while
  retaining Rust 1.85 compatibility.
- Moved extraction, verification, provenance, and source data to the standalone
  `hsk_tooling` repository.

### Removed

- Removed `Hsk::new()` and `Hsk::get_hsk`.
- Removed traditional-form enrichment, vocabulary enumeration, and runtime
  provenance metadata from the public API.
