# HSK modernization implementation plan

This plan was established before replacing the core API. Workstreams were kept
separate until their artifacts and contracts were stable:

1. Inventory the historical public API, data loading, tests, and release
   metadata.
2. Pin all three authoritative documents, assess native extraction first, and
   record exact URLs, dates, hashes, tools, and page/sheet locators.
3. Generate canonical CSV deterministically; isolate OCR only where native text
   demonstrably fails and preserve unresolved rows.
4. Pin independent same-edition transcriptions, normalize identity fields, and
   generate non-mutating discrepancy reports.
5. Replace the unversioned numeric API with typed systems, levels, lexical and
   orthography-only outcomes, all-system lookup, and exact/cumulative
   enumeration.
6. Generate static arrays and sorted orthographic indexes at build time; share
   pinyin normalization across systems in a query.
7. Add integrity, normalization, traditional/simplified, ambiguity,
   multi-version, enumeration, regression, and benchmark coverage.
8. Publish the 0.1-to-1.0 migration guide, provenance documentation, changelog,
   and implementation report, then run all Rust and data quality gates.

The authoritative documents remain classification truth throughout. External
transcriptions can identify review work but cannot rewrite a canonical row.
