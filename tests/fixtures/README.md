# Test fixtures

Fixtures in this directory are deliberately small excerpts used to test parser
edge cases. Every authoritative excerpt must identify its source artifact and
page, sheet, or source-row locator in adjacent metadata. Do not add an entry
solely because it appears in a third-party transcription.

PDF or workbook fixtures must be redistribution-compatible. If an official
binary cannot be redistributed, store a synthetic layout-preserving fixture and
document the real input checksum and locator that it represents. OCR fixtures
must identify the renderer and OCR versions and mark the expected row as
OCR-derived.

Normalization fixtures are synthetic and test equivalence rules only; they do
not assert that a word belongs to a particular HSK system.
