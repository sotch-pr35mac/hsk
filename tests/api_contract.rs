use hsk::{HskLevel, HskQuery, HskSystem, levels, levels_all};

#[test]
fn each_supported_classification_can_be_queried() {
    let cases = [
        (HskSystem::Hsk2015, "爱", HskLevel::One),
        (HskSystem::ProficiencyStandard2021, "爱好", HskLevel::One),
        (HskSystem::HskExamSyllabus2025, "白天", HskLevel::One),
    ];
    for (system, word, expected) in cases {
        assert_eq!(levels(system, HskQuery::new(word)).unwrap(), [expected]);
    }
}

#[test]
fn all_system_lookup_omits_non_matches() {
    assert_eq!(
        levels_all(HskQuery::new("半年")).unwrap(),
        [(HskSystem::ProficiencyStandard2021, vec![HskLevel::One])]
    );
}

#[test]
fn all_system_lookup_exposes_changed_levels() {
    assert_eq!(
        levels_all(HskQuery::new("出租车")).unwrap(),
        [
            (HskSystem::Hsk2015, vec![HskLevel::One]),
            (HskSystem::ProficiencyStandard2021, vec![HskLevel::Two]),
            (HskSystem::HskExamSyllabus2025, vec![HskLevel::One]),
        ]
    );
}
