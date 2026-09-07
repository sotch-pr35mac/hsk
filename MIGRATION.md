# Migrating from 0.1.1 to 1.0.0

Version 1.0.0 replaces the unversioned numeric lookup from 0.1.1 with named
classifications and typed levels.

Before:

```rust
use hsk::Hsk;

let hsk = Hsk::new();
assert_eq!(hsk.get_hsk("爱"), 1);
```

After:

```rust
use hsk::{HskLevel, HskQuery, HskSystem, levels};

let found = levels(HskSystem::Hsk2015, HskQuery::new("爱"))?;
assert_eq!(found, [HskLevel::One]);
# Ok::<(), hsk::HskError>(())
```

Choose the document explicitly with `HskSystem::Hsk2015`,
`HskSystem::ProficiencyStandard2021`, or
`HskSystem::HskExamSyllabus2025`. An absent word returns an empty vector rather
than level `0`.

Pinyin is optional. Add it when a reading should qualify the lookup. Tone marks,
tone numbers, `ü`/`u:`/`v`, capitalization, and common separators normalize to
the same key:

```rust
# use hsk::{HskQuery, HskSystem, levels};
let levels_for_reading = levels(
    HskSystem::ProficiencyStandard2021,
    HskQuery::new("长").pinyin("cháng"),
)?;
# Ok::<(), hsk::HskError>(())
```

The source documents publish simplified forms, so version 1.0 does not accept
traditional forms as aliases. Use `levels_all` to return only the systems in
which a query appears. The 2015 source does not publish pinyin, so a valid
pinyin qualifier does not filter that classification's simplified-word match.
