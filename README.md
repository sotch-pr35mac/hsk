# hsk

## About

Return versioned HSK level for Simplified Chinese characters.

This Rust crate includes the six-level HSK examination vocabulary published
in 2015, the GF0025-2021 Chinese proficiency standard, and the HSK
examination syllabus published in 2025 for use from July 2026. Lookups are
simplified-only and return typed, ordered levels.

## Usage

```rust
use hsk::{levels, HskLevel, HskQuery, HskSystem};

let found = levels(HskSystem::Hsk2015, HskQuery::new("爱"))?;
assert_eq!(found, [HskLevel::One]);

let reading = levels(
    HskSystem::ProficiencyStandard2021,
    HskQuery::new("长").pinyin("zhang3"),
)?;
assert_eq!(reading, [HskLevel::Two, HskLevel::Six]);
# Ok::<(), hsk::HskError>(())
```

Pinyin is optional and qualifies a simplified-word match. The normalizer:

- accepts exact catalog spellings, tone marks, numbered tones, and neutral
  tones `0` and `5`;
- ignores capitalization and common whitespace, apostrophe, hyphen, middle-dot,
  and similar syllable separators;
- treats `ü`, `u:`, and `v` equivalently;
- rejects empty, malformed, repeated, or unsupported pinyin input; and
- does not filter HSK 2015 matches by pinyin because that source does not
  publish pinyin.

For example, `nǚér`, `nǚ'ér`, `nv3er2`, and `nu:3 er2` are equivalent. Use
`levels_all` to search every classification. A missing word returns an empty
result, while malformed input returns `HskError`.

## Contributors

- [Preston Wang-Stosur-Bassett](https://github.com/sotch-pr35mac)

## License

Licensed under the [MIT License](LICENSE).
