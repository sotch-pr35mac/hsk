# hsk

Versioned HSK vocabulary level lookup for Rust. The crate includes:

- the six-level HSK examination vocabulary published in 2015;
- the GF0025-2021 Chinese proficiency standard; and
- the HSK examination syllabus published in 2025 for use from July 2026.

```rust
use hsk::{HskLevel, HskQuery, HskSystem, levels};

let found = levels(HskSystem::Hsk2015, HskQuery::new("爱"))?;
assert_eq!(found, [HskLevel::One]);

let reading = levels(
    HskSystem::ProficiencyStandard2021,
    HskQuery::new("长").pinyin("zhang3"),
)?;
assert_eq!(reading, [HskLevel::Two, HskLevel::Six]);
# Ok::<(), hsk::HskError>(())
```

Queries use simplified Chinese. Pinyin is optional and can distinguish entries
with the same simplified form. `levels_all` returns matches across all three
classifications. Pinyin accepts tone marks or numbers, `ü`/`u:`/`v`, and common
spacing and apostrophe variants. The 2015 source does not publish pinyin, so a
valid pinyin qualifier does not filter its simplified-word matches.

Version 1.0 changes the API from earlier releases. See [MIGRATION.md](MIGRATION.md).

## License

MIT
