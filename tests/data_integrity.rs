use std::collections::HashSet;

use hsk::{HskCatalog, HskLevel, HskSystem, LevelScope, LookupOutcome, Orthography};

const LEVELS: [HskLevel; 7] = [
    HskLevel::One,
    HskLevel::Two,
    HskLevel::Three,
    HskLevel::Four,
    HskLevel::Five,
    HskLevel::Six,
    HskLevel::SevenToNine,
];

#[test]
fn current_exam_expands_only_explicit_cross_level_assignments() {
    let catalog = HskCatalog::new();
    let expected = [300, 204, 507, 1_019, 1_638, 1_815, 5_622];
    for (level, expected) in LEVELS.into_iter().zip(expected) {
        assert_eq!(
            catalog
                .words(HskSystem::HskExamSyllabus2025, level, LevelScope::Exact)
                .unwrap()
                .len(),
            expected
        );
    }
}

#[test]
fn every_assignment_has_source_identity_and_valid_orthography() {
    let catalog = HskCatalog::new();
    for &system in HskCatalog::supported_systems() {
        let final_level = *HskCatalog::supported_levels(system).last().unwrap();
        let rows = catalog
            .words(system, final_level, LevelScope::Cumulative)
            .unwrap();
        assert!(rows.iter().all(|row| {
            row.system() == system
                && !row.simplified().trim().is_empty()
                && row.source_sequence() > 0
                && !row.source_locator().is_empty()
        }));
    }
}

#[test]
fn source_rows_have_no_accidental_duplicate_sequence_and_level() {
    let catalog = HskCatalog::new();
    for &system in HskCatalog::supported_systems() {
        let final_level = *HskCatalog::supported_levels(system).last().unwrap();
        let rows = catalog
            .words(system, final_level, LevelScope::Cumulative)
            .unwrap();
        let mut seen = HashSet::new();
        assert!(
            rows.iter()
                .all(|row| seen.insert((row.source_sequence(), row.level())))
        );
    }
}

#[test]
fn authoritative_samples_are_in_the_expected_systems() {
    let catalog = HskCatalog::new();
    let samples = [
        (HskSystem::Hsk2015, "爱", "ai4", HskLevel::One),
        (HskSystem::Hsk2015, "版本", "ban3ben3", HskLevel::Six),
        (
            HskSystem::ProficiencyStandard2021,
            "爱好",
            "ai4hao4",
            HskLevel::One,
        ),
        (
            HskSystem::HskExamSyllabus2025,
            "白天",
            "bai2tian1",
            HskLevel::One,
        ),
    ];
    for (system, word, pinyin, expected_level) in samples {
        let outcome = catalog
            .lookup(system, Orthography::Simplified(word), pinyin)
            .unwrap();
        match outcome {
            LookupOutcome::Unique(found) => {
                assert_eq!(found.classification().level(), expected_level)
            }
            other => panic!("unexpected sample outcome for {word}: {other:?}"),
        }
    }
}

#[test]
fn exact_and_cumulative_enumeration_preserve_level_order() {
    let catalog = HskCatalog::new();
    for &system in HskCatalog::supported_systems() {
        let mut cumulative_count = 0;
        for &level in HskCatalog::supported_levels(system) {
            let exact = catalog.words(system, level, LevelScope::Exact).unwrap();
            cumulative_count += exact.len();
            let cumulative = catalog
                .words(system, level, LevelScope::Cumulative)
                .unwrap();
            assert_eq!(cumulative.len(), cumulative_count);
            assert!(
                cumulative
                    .windows(2)
                    .all(|pair| pair[0].level() <= pair[1].level())
            );
        }
    }
}
