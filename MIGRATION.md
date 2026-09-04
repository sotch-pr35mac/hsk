# Migrating from 0.1 to 1.0

Version 1.0 intentionally replaces the old single-map API. The historical API
did not identify its source edition, accepted simplified spelling only, and
used `0` for both absence and errors. The new API makes the classification,
lexical reading, and ambiguous results explicit.

## Choose a classification

Use one of the named systems rather than an undocumented number:

```rust
use hsk::HskSystem;

let exam_2015 = HskSystem::Hsk2015;
let proficiency_standard = HskSystem::ProficiencyStandard2021;
let current_exam = HskSystem::HskExamSyllabus2025;
```

`ProficiencyStandard2021` is the national “three stages, nine levels”
proficiency standard. It is related to, but is not the same dataset as, the
current HSK examination syllabus.

## Replace `get_hsk`

Before:

```rust
use hsk::Hsk;

let hsk = Hsk::new();
let numeric_level = hsk.get_hsk("爱");
assert_eq!(numeric_level, 1);
```

After, prefer a reading-qualified lookup when lexical identity matters:

```rust
use hsk::{HskCatalog, HskSystem, LookupOutcome, Orthography};

let catalog = HskCatalog::new();
let result = catalog.lookup(
    HskSystem::Hsk2015,
    Orthography::Simplified("爱"),
    "ài",
)?;

match result {
    LookupOutcome::Unique(word) => println!("{:?}", word.classification().level()),
    LookupOutcome::Ambiguous(candidates) => {
        // Refine the spelling or reading; never choose a candidate arbitrarily.
        println!("{} candidates", candidates.len());
    }
    LookupOutcome::NotFound => println!("not present in this classification"),
}
# Ok::<(), hsk::LookupError>(())
```

Pinyin input accepts equivalent tone marks and tone numbers, composed and
decomposed Unicode, `ü`/`u:`/`v`, case and spacing differences, common
apostrophes, and neutral-tone `0`/`5` conventions. Invalid input returns a
typed error rather than being silently changed into another reading.

If no pinyin is available, use the orthography-only API and handle ambiguity:

```rust
# use hsk::{HskCatalog, HskSystem, LookupOutcome, Orthography};
# let catalog = HskCatalog::new();
match catalog.lookup_orthography(
    HskSystem::Hsk2015,
    Orthography::Traditional("愛"),
)? {
    LookupOutcome::Unique(word) => println!("{:?}", word.classification().level()),
    LookupOutcome::Ambiguous(candidates) => {
        println!("a reading is required; {} candidates", candidates.len())
    }
    LookupOutcome::NotFound => println!("not present"),
}
# Ok::<(), hsk::LookupError>(())
```

Supplying both simplified and traditional forms asks the catalog to verify that
they identify the same lexical record. Conflicting forms return
`LookupError::ConflictingOrthographies`.

## Query all systems

Use `lookup_all` (with pinyin) or `lookup_all_orthography` (without pinyin) to
receive one explicit result for every value returned by
`HskCatalog::supported_systems()`. A missing entry remains `NotFound`; it is not
omitted from the result set.

This makes level changes and system-specific entries distinguishable without
performing three separate normalization passes.

## Enumerate vocabulary

```rust
use hsk::{HskCatalog, HskLevel, HskSystem, LevelScope};

let catalog = HskCatalog::new();
let introduced_at_level_two = catalog.words(
    HskSystem::Hsk2015,
    HskLevel::Two,
    LevelScope::Exact,
)?;

let expected_through_level_two = catalog.words(
    HskSystem::Hsk2015,
    HskLevel::Two,
    LevelScope::Cumulative,
)?;

assert!(expected_through_level_two.len() >= introduced_at_level_two.len());
# Ok::<(), hsk::LookupError>(())
```

`Exact` means assignments introduced at that level. `Cumulative` includes that
level and all preceding levels in authoritative source order. Source rows that
distinguish readings, senses, or parts of speech remain distinct assignments.

`HskLevel::SevenToNine` represents the shared advanced vocabulary band used by
newer documents. It is invalid for `HskSystem::Hsk2015` and returns a typed
invalid-level error; the library does not invent individual vocabulary lists
for levels seven, eight, and nine.

## Error-handling checklist

- Replace numeric comparisons with `HskLevel` matches.
- Handle `LookupOutcome::NotFound` independently from `Ambiguous`.
- Propagate or display `LookupError` for malformed pinyin, invalid levels, and
  conflicting simplified/traditional input.
- Select `LevelScope::Exact` or `LevelScope::Cumulative` explicitly.
- Do not label `ProficiencyStandard2021` as an HSK examination syllabus.
