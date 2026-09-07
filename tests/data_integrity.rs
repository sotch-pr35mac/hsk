use hsk::{HskLevel, HskQuery, HskSystem, levels};

#[test]
fn representative_boundary_entries_are_present() {
    let cases = [
        (HskSystem::Hsk2015, "版本", HskLevel::Six),
        (
            HskSystem::ProficiencyStandard2021,
            "做证",
            HskLevel::SevenToNine,
        ),
        (
            HskSystem::HskExamSyllabus2025,
            "座右铭",
            HskLevel::SevenToNine,
        ),
    ];
    for (system, word, expected) in cases {
        assert!(
            levels(system, HskQuery::new(word))
                .unwrap()
                .contains(&expected),
            "missing {word:?} from {system:?}"
        );
    }
}
