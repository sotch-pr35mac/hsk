# hsk

Authoritative, explicitly versioned HSK and Chinese-proficiency vocabulary for
Rust. Version 1.0 supports three classifications without conflating them:

- HSK 2.0 / **2015 examination vocabulary** (six levels);
- **GF0025-2021**, the International Chinese Education proficiency standard
  (three stages, nine levels); and
- the current **HSK examination syllabus**, published in November 2025 for
  implementation in July 2026.

The 2021 national standard is a proficiency framework used for learning,
teaching, testing, and assessment. It is related to—but is not the same
vocabulary classification as—the newer examination syllabus.

## Lookup

```rust
use hsk::{HskCatalog, HskSystem, LookupOutcome, Orthography};

let catalog = HskCatalog::new();
let result = catalog.lookup(
    HskSystem::Hsk2015,
    Orthography::Traditional("愛"),
    "ai4", // tone marks and tone numbers normalize identically
)?;

if let LookupOutcome::Unique(found) = result {
    println!("{}", found.classification().level());
}
# Ok::<(), hsk::LookupError>(())
```

Use `lookup_orthography` when no reading is known. It returns `Ambiguous` when
multiple lexical readings or senses share the supplied spelling; it never
chooses one arbitrarily. `lookup_all` and `lookup_all_orthography` return one
explicit outcome for every supported system.

Pinyin comparison accepts tone marks or numbers, composed or decomposed
Unicode, `ü`/`u:`/`v`, capitalization, spacing and apostrophe variants, and
neutral tones written without a number or as `0`/`5`.

The official 2015 workbook contains no pinyin or traditional column. Reviewed
same-edition enrichment supplies those fields for 4,796 of 5,000 rows; strict
lookup for the remaining 204 returns `NotFound`, while simplified
orthography-only classification remains available. The unresolved list is
checked in rather than filled from historical or fuzzy data.

GF0025 candidate pinyin is likewise never promoted silently: strict lookup is
enabled only for 9,905 fully OCR-matched rows plus one explicitly reviewed
authoritative correction. The remaining rows continue to classify by
orthography. `Classification::evidence()` exposes whether a result is directly
authoritative, authoritatively corrected, orthography-only, or an unresolved
verification candidate; the complete review detail remains in the validation
report.

## Enumerate levels

```rust
use hsk::{HskCatalog, HskLevel, HskSystem, LevelScope};

let catalog = HskCatalog::new();
let introduced = catalog.words(
    HskSystem::Hsk2015,
    HskLevel::Three,
    LevelScope::Exact,
)?;
let expected_by_level = catalog.words(
    HskSystem::Hsk2015,
    HskLevel::Three,
    LevelScope::Cumulative,
)?;
assert!(expected_by_level.len() >= introduced.len());
# Ok::<(), hsk::LookupError>(())
```

`SevenToNine` is the shared advanced band printed by the newer documents. The
crate does not invent separate level-seven, -eight, or -nine vocabulary lists.

## Provenance and reproduction

[`data/hsk-sources/README.md`](data/hsk-sources/README.md) records official
URLs, document dates, checksums, extraction tools, source limitations, and the
deterministic regeneration process. Official artifacts stay out of the crate;
`sources.lock.json` binds generated rows to their exact bytes. Independent
transcriptions and licenses are documented under [`verification/`](verification/)
and may produce discrepancy reports, but never overwrite source extraction.

The Rust build converts reviewed CSV to static arrays and sorted lookup indexes.
There is no runtime bincode parsing or per-catalog hash-map construction.

Version 1.0 is a breaking release. See [`MIGRATION.md`](MIGRATION.md).

## License

The library and extraction code are MIT licensed. Source documents and
third-party verification data retain their respective terms; consult the
provenance files before redistributing them.
