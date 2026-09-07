use hsk::{HskLevel, HskQuery, HskSystem, levels};

#[test]
fn pinyin_forms_normalize_identically() {
    for pinyin in ["ài", "a\u{0300}i", "ai4", "AI4", "  ai4  "] {
        assert_eq!(
            levels(
                HskSystem::ProficiencyStandard2021,
                HskQuery::new("爱").pinyin(pinyin),
            )
            .unwrap(),
            [HskLevel::One]
        );
    }
}

#[test]
fn apostrophe_free_umlaut_pinyin_matches_documented_equivalents() {
    for pinyin in ["nǚér", "nǚ'ér", "nv3er2", "nu:3 er2"] {
        assert_eq!(
            levels(
                HskSystem::ProficiencyStandard2021,
                HskQuery::new("女儿").pinyin(pinyin),
            )
            .unwrap(),
            [HskLevel::One]
        );
    }
}

#[test]
fn pinyin_can_disambiguate_polyphonic_entries() {
    assert_eq!(
        levels(
            HskSystem::ProficiencyStandard2021,
            HskQuery::new("长").pinyin("chang2"),
        )
        .unwrap(),
        [HskLevel::Two]
    );
    assert_eq!(
        levels(
            HskSystem::ProficiencyStandard2021,
            HskQuery::new("长").pinyin("zhang3"),
        )
        .unwrap(),
        [HskLevel::Two, HskLevel::Six]
    );
}

#[test]
fn word_only_lookup_returns_every_assigned_level() {
    assert_eq!(
        levels(HskSystem::HskExamSyllabus2025, HskQuery::new("一下")).unwrap(),
        [HskLevel::One, HskLevel::Four]
    );
}

#[test]
fn duplicate_source_rows_do_not_duplicate_a_level() {
    assert_eq!(
        levels(
            HskSystem::ProficiencyStandard2021,
            HskQuery::new("面").pinyin("mian4"),
        )
        .unwrap(),
        [HskLevel::Two]
    );
}

#[test]
fn explanatory_parentheses_are_not_part_of_runtime_headwords() {
    assert_eq!(
        levels(HskSystem::Hsk2015, HskQuery::new("喂")).unwrap(),
        [HskLevel::One, HskLevel::Six]
    );
    assert!(
        levels(HskSystem::Hsk2015, HskQuery::new("喂（叹词）"))
            .unwrap()
            .is_empty()
    );
    assert!(
        levels(
            HskSystem::ProficiencyStandard2021,
            HskQuery::new("老（老王）"),
        )
        .unwrap()
        .is_empty()
    );
}

#[test]
fn optional_written_components_keep_their_matching_pinyin() {
    assert_eq!(
        levels(
            HskSystem::ProficiencyStandard2021,
            HskQuery::new("有些").pinyin("you3xie1"),
        )
        .unwrap(),
        [HskLevel::One]
    );
    assert_eq!(
        levels(
            HskSystem::ProficiencyStandard2021,
            HskQuery::new("有一些").pinyin("you3yi4xie1"),
        )
        .unwrap(),
        [HskLevel::One]
    );
    assert!(
        levels(
            HskSystem::ProficiencyStandard2021,
            HskQuery::new("有些").pinyin("you3yi4xie1"),
        )
        .unwrap()
        .is_empty()
    );
}

#[test]
fn hsk_2015_pinyin_does_not_filter_a_word_match() {
    assert_eq!(
        levels(
            HskSystem::Hsk2015,
            HskQuery::new("爱").pinyin("not-a-real-reading"),
        )
        .unwrap(),
        [HskLevel::One]
    );
}

#[test]
fn matching_is_simplified_only() {
    assert!(
        levels(HskSystem::Hsk2015, HskQuery::new("愛"))
            .unwrap()
            .is_empty()
    );
}

#[test]
fn absence_is_an_empty_level_list() {
    assert!(
        levels(HskSystem::Hsk2015, HskQuery::new("𠮷野家"))
            .unwrap()
            .is_empty()
    );
}

#[test]
fn malformed_queries_are_rejected() {
    assert!(levels(HskSystem::Hsk2015, HskQuery::new("  ")).is_err());
    for malformed in ["ai9", "a4i", "nü:", "'"] {
        assert!(
            levels(
                HskSystem::ProficiencyStandard2021,
                HskQuery::new("爱").pinyin(malformed),
            )
            .is_err(),
            "{malformed:?} must be rejected"
        );
    }
}
