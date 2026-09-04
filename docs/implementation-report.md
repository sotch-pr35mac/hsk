# HSK modernization implementation report

## Result

Version 1.0.0 replaces the former unversioned HSK map with three independently
selectable classifications and generated static indexes. The GF0025-2021
proficiency standard remains separate from the current HSK examination
syllabus.

## Authoritative documents and extraction

| System | Locked artifact | Extraction | Final counts |
|---|---|---|---|
| HSK 2.0 / 2015 exam vocabulary | CTI `HSK-2015.xlsx`, SHA-256 `7e3c8cac…70c76c` | Deterministic stdlib ZIP/XML workbook reader | 150 / 150 / 300 / 600 / 1,300 / 2,500 = 5,000 |
| GF0025-2021 proficiency standard | MOE 260-page PDF, SHA-256 `e451fdf0…d73a63` | Native extraction rejected (only watermark text); RapidOCR limited to vocabulary pages 42-175 at scale 3 | 500 / 772 / 973 / 1,000 / 1,071 / 1,140 / 5,636 = 11,092 |
| Current HSK exam syllabus | CTI 406-page PDF, SHA-256 `ec74ce04…04941` | Native PyMuPDF 1.26.4 table extraction, pages 80-354 | 11,000 source rows; 11,105 expanded level assignments |

The exact CTI current-syllabus URL is recorded in the tooling repository's
`sources.json`; the document
is published 2025-11 and effective 2026-07-01. The official hosts timed out in
the extraction environment, so the lock transparently records mirror transport
and pending direct official-byte comparison. Two independent transport copies
of the current syllabus were byte-identical.

The 2015 workbook supplies only level and simplified headword. A separately
identified University of Geneva 2015-syllabus transcription provides pinyin and
traditional enrichment for 4,796 rows. The other 204 retain official
classification and orthography-only lookup but no invented strict-reading
metadata.

For GF0025, 9,905 rows have a unique authoritative OCR
sequence+headword+pinyin match and 986 more have a unique authoritative
headword row with pinyin still unresolved by OCR. The remaining 201 candidate
rows are explicitly marked unresolved. All are listed with locators and OCR
evidence in `proficiency2021.validation.json`; third-party candidates are not
described as authoritative extraction or indexed for strict runtime lookup.
Strict lookup covers the 9,905 fully matched rows plus the explicit reviewed
`倒 dào` correction.

## Independent verification and decisions

- The current exam output matches the pinned Punpuf transcription on all 11,105
  expanded assignments, with zero one-sided, pinyin, level, duplicate, or parse
  disagreements.
- The conservative GF0025 comparison reports 9,905 exact lexical matches and
  1,185 one-to-one headword-only candidates against the pinned shawkynasr
  export. Its remaining value differences are `称 chēng` versus the document's
  `称 chèn`, and an apparent verifier headword typo `会 huìlǜ` where the
  authoritative OCR row reads `汇率`.
- Two separate level-ordered candidate errors were resolved from the
  authoritative document: page 49 row 111 prints `倒 dào`, and page 57 row 715
  prints verbal `长 zhǎng`. Both are explicit correction-ledger entries.
- HSK 2015 enrichment matches 4,796 official rows. The 204 unresolved rows are
  preserved rather than filled from the project’s historical data.
- English definitions are excluded from comparison identity. Matching uses
  explicit orthography plus normalized pinyin only.

## API and performance

The breaking API introduces `HskSystem`, `HskLevel`, `Orthography`,
`LookupOutcome`, `LookupError`, `EvidenceStatus`, and `LevelScope`. Strict and
orthography-only queries work for one or all systems; ambiguity and absence are
distinct. Every returned classification exposes its evidence tier. Enumeration
names exact versus cumulative semantics.

Build-time generation replaces runtime bincode decoding and per-instance hash
map construction. `HskCatalog` is zero-sized; level enumeration is a static
slice; lookup uses borrowed normalized headwords, streaming decomposition,
borrowed equal-key index ranges, direct dual-form intersection, and one-pass
outcome construction. An all-system strict query normalizes both orthography
and pinyin once. Representative Criterion benchmarks are included but timing
is intentionally not a CI gate.

A Criterion 0.7 quick run measured strict canonical hits at 0.48 µs, heavy
normalization hits at 0.58 µs, misses at 0.48 µs, orthography ambiguity at
0.44 µs, all-system lookup at 1.12 µs, and exact/cumulative enumeration at
about 5.5 ns. The earlier Criterion 0.5 measurements in the historical report
are not directly comparable; these figures are environment-specific diagnostic
baselines.

## Release and validation

The crate version is 1.0.0 and the minimum supported compiler is Rust 1.85
(edition 2024). `CHANGELOG.md` and `MIGRATION.md` document all breaking changes.
The final release gate results are recorded here after execution:

- `cargo fmt --check`: passed
- `cargo clippy --all-targets --all-features -- -D warnings`: passed
- `cargo check --all-targets --all-features`: passed
- `cargo test --all-targets --all-features`: passed (28 Rust assertions/tests,
  plus seven Criterion smoke targets; none ignored)
- extraction tests: passed (8, in `hsk_tooling`)
- verification tests: not runnable on this host's Python 3.9; the existing
  verifier requires Python 3.10+
- `cargo package --allow-dirty`: passed; 25 listed files, no Python,
  requirements, raw observations, verification fixtures, or Python CI files;
  3.1 MiB unpacked / 563.5 KiB compressed
- `hsk_tooling` initialized as a standalone local Git repository
