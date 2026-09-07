# Changelog

## [1.0.0] - 2026-09-07

Version 1.0.0 is a breaking redesign from the published 0.1.1 release.

### Added

- Named lookup for the 2015 HSK vocabulary, GF0025-2021 proficiency standard,
  and 2025 HSK examination syllabus.
- `HskSystem`, `HskLevel`, `HskQuery`, and typed `HskError` values.
- Optional normalized-pinyin qualification and `levels_all`.

### Changed

- Lookup now returns ordered `HskLevel` values instead of numeric sentinel
  results.
- Catalog data is embedded in a compact binary index and queried by binary
  search.

### Removed

- The 0.1.1 `Hsk::new()` and `Hsk::get_hsk()` API.
