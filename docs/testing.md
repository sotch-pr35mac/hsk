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
cargo xtask data check --offline
```

The data check regenerates tracked canonical data, static Rust indexes, and
discrepancy reports into a temporary directory and compares them byte-for-byte.
It must not download sources. Source downloads belong to the separately invoked
acquisition step and must match the checksums in the source manifest.

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
