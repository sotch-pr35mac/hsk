use hsk::{HskCatalog, HskLevel, HskSystem, LevelScope, LookupOutcome, Orthography};

const SYSTEMS: [HskSystem; 3] = [
    HskSystem::Hsk2015,
    HskSystem::ProficiencyStandard2021,
    HskSystem::HskExamSyllabus2025,
];

const BASIC_LEVELS: [HskLevel; 6] = [
    HskLevel::One,
    HskLevel::Two,
    HskLevel::Three,
    HskLevel::Four,
    HskLevel::Five,
    HskLevel::Six,
];

const NINE_LEVEL_BANDS: [HskLevel; 7] = [
    HskLevel::One,
    HskLevel::Two,
    HskLevel::Three,
    HskLevel::Four,
    HskLevel::Five,
    HskLevel::Six,
    HskLevel::SevenToNine,
];

#[test]
fn supported_systems_are_named_and_stably_ordered() {
    assert_eq!(HskCatalog::supported_systems(), SYSTEMS.as_slice());
}

#[test]
fn supported_levels_reflect_each_authoritative_document() {
    assert_eq!(
        HskCatalog::supported_levels(HskSystem::Hsk2015),
        BASIC_LEVELS.as_slice()
    );
    assert_eq!(
        HskCatalog::supported_levels(HskSystem::ProficiencyStandard2021),
        NINE_LEVEL_BANDS.as_slice()
    );
    assert_eq!(
        HskCatalog::supported_levels(HskSystem::HskExamSyllabus2025),
        NINE_LEVEL_BANDS.as_slice()
    );
}

#[test]
fn hsk_2015_exact_and_cumulative_counts_are_distinct() {
    let catalog = HskCatalog::new();
    let exact_counts = [150, 150, 300, 600, 1_300, 2_500];
    let cumulative_counts = [150, 300, 600, 1_200, 2_500, 5_000];

    for ((level, exact), cumulative) in BASIC_LEVELS
        .iter()
        .copied()
        .zip(exact_counts)
        .zip(cumulative_counts)
    {
        assert_eq!(
            catalog
                .words(HskSystem::Hsk2015, level, LevelScope::Exact)
                .expect("2015 level must be valid")
                .len(),
            exact,
            "unexpected exact count for {level:?}"
        );
        assert_eq!(
            catalog
                .words(HskSystem::Hsk2015, level, LevelScope::Cumulative)
                .expect("2015 level must be valid")
                .len(),
            cumulative,
            "unexpected cumulative count for {level:?}"
        );
    }
}

#[test]
fn proficiency_standard_exact_counts_match_the_official_standard() {
    let catalog = HskCatalog::new();
    let exact_counts = [500, 772, 973, 1_000, 1_071, 1_140, 5_636];

    for (level, expected) in NINE_LEVEL_BANDS.iter().copied().zip(exact_counts) {
        assert_eq!(
            catalog
                .words(HskSystem::ProficiencyStandard2021, level, LevelScope::Exact,)
                .expect("standard level must be valid")
                .len(),
            expected,
            "unexpected exact count for {level:?}"
        );
    }
}

#[test]
fn cumulative_enumeration_has_every_exact_assignment_in_source_order() {
    let catalog = HskCatalog::new();

    for system in SYSTEMS {
        let mut previous_len = 0;
        for &level in HskCatalog::supported_levels(system) {
            let exact = catalog
                .words(system, level, LevelScope::Exact)
                .expect("advertised level must be valid");
            let cumulative = catalog
                .words(system, level, LevelScope::Cumulative)
                .expect("advertised level must be valid");

            assert!(
                exact
                    .iter()
                    .all(|classification| classification.level() == level),
                "exact enumeration returned an assignment from another level"
            );
            assert_eq!(cumulative.len(), previous_len + exact.len());
            assert!(
                cumulative
                    .windows(2)
                    .all(|pair| pair[0].level() <= pair[1].level()),
                "cumulative enumeration is not ordered by level"
            );
            previous_len = cumulative.len();
        }
    }
}

#[test]
fn seven_to_nine_is_not_invented_for_the_six_level_exam() {
    let catalog = HskCatalog::new();
    assert!(
        catalog
            .words(HskSystem::Hsk2015, HskLevel::SevenToNine, LevelScope::Exact,)
            .is_err()
    );
}

#[test]
fn all_system_lookup_returns_one_result_per_supported_system() {
    let catalog = HskCatalog::new();
    let results = catalog
        .lookup_all(Orthography::Simplified("爱"), "ai4")
        .expect("valid pinyin must normalize");

    assert_eq!(results.len(), SYSTEMS.len());
    for (expected_system, (actual_system, outcome)) in SYSTEMS.into_iter().zip(results) {
        assert_eq!(actual_system, expected_system);
        assert!(matches!(
            outcome,
            LookupOutcome::Unique(_) | LookupOutcome::Ambiguous(_) | LookupOutcome::NotFound
        ));
    }
}

fn all_levels(word: &str, pinyin: &str) -> Vec<Option<HskLevel>> {
    HskCatalog::new()
        .lookup_all(Orthography::Simplified(word), pinyin)
        .unwrap()
        .into_iter()
        .map(|(_, outcome)| match outcome {
            LookupOutcome::Unique(found) => Some(found.classification().level()),
            LookupOutcome::NotFound => None,
            LookupOutcome::Ambiguous(found) => {
                panic!("unexpected ambiguity for {word}: {found:?}")
            }
        })
        .collect()
}

#[test]
fn all_system_lookup_exposes_stable_and_changed_levels() {
    assert_eq!(
        all_levels("是", "shi4"),
        vec![
            Some(HskLevel::One),
            Some(HskLevel::One),
            Some(HskLevel::One)
        ]
    );
    assert_eq!(
        all_levels("出租车", "chu1zu1che1"),
        vec![
            Some(HskLevel::One),
            Some(HskLevel::Two),
            Some(HskLevel::One)
        ]
    );
}

#[test]
fn all_system_lookup_keeps_system_specific_entries_explicit() {
    assert_eq!(
        all_levels("打篮球", "da3lan2qiu2"),
        vec![Some(HskLevel::Two), None, None]
    );
    assert_eq!(
        all_levels("半年", "ban4nian2"),
        vec![None, Some(HskLevel::One), None]
    );
    assert_eq!(
        all_levels("没事", "mei2shi4"),
        vec![None, None, Some(HskLevel::One)]
    );
}
