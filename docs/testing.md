# Testing and release gates

The HSK files are canonical library data, so tests cover both API behavior and
the path from an authoritative source row to a query result.

## Local quality gates

Run these commands before release:

```bash
cargo fmt --check
cargo clippy --all-targets --all-features -- -D warnings
cargo check --all-targets --all-features
cargo test --all-targets --all-features
python3 tools/hsk_data.py validate-config
python3 tools/hsk_data.py validate --source hsk2015 --canonical data/hsk-sources/canonical/hsk2015.csv
python3 tools/hsk_data.py validate --source proficiency2021 --canonical data/hsk-sources/canonical/proficiency2021.csv
python3 tools/hsk_data.py validate --source hsk_exam2025 --canonical data/hsk-sources/canonical/hsk_exam2025.csv
python3 -m unittest discover -s tools -p 'test_*.py' -v
python3 -m unittest discover -s verification/tests -v
```

The structural checks are offline and must not download sources. Full
byte-for-byte regeneration additionally requires the three ignored official
artifacts and the pinned non-vendored verification inputs described in
`data/hsk-sources/README.md`. Acquisition is a separate step and every artifact
must match its recorded SHA-256 before extraction.

## Required coverage

The test suite asserts:

- official source-row and expanded-assignment counts for every supported level;
- no unexpected blank fields, byte-order marks, control/replacement characters,
  malformed normalized keys, invalid levels, or index-order violations;
- known rows with source locators from every authoritative document;
- deterministic XLSX, native-PDF, and narrowly scoped OCR fixtures;
- pinyin equivalence and rejection cases, including normalization idempotence;
- simplified, traditional, dual-form, alias-collision, and conflicting-form
  queries;
- unique, ambiguous, and not-found outcomes for strict and orthography-only
  lookup;
- explicit results across all supported systems;
- exact and cumulative vocabulary semantics and authoritative ordering;
- offline byte-identical regeneration and stable discrepancy dispositions.

Tests must not make an independent transcription canonical. A verification
fixture can demonstrate or regress a discrepancy, but the expected disposition
must cite the authoritative page, sheet row, or source record.

## Benchmark policy

Benchmarks exercise strict hit/miss, normalization-heavy queries,
orthography-only ambiguity, all-system queries, and exact/cumulative
enumeration. They are diagnostic, not CI timing gates. A data-structure change
must improve representative behavior enough to justify its maintenance cost;
small synthetic wins are not sufficient.
