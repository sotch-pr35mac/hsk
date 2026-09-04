use hsk::{HskCatalog, HskSystem, LookupOutcome, Orthography};

fn assert_unique(catalog: &HskCatalog, orthography: Orthography<'_>, pinyin: &str) {
    assert!(matches!(
        catalog.lookup(HskSystem::Hsk2015, orthography, pinyin),
        Ok(LookupOutcome::Unique(_))
    ));
}

#[test]
fn tone_marks_numbers_unicode_and_case_identify_the_same_reading() {
    let catalog = HskCatalog::new();

    // 爱 / 愛, ài is an authoritative HSK 2015 level-one row. The
    // decomposed spelling is intentionally built without normalizing the test
    // source file itself.
    for pinyin in ["ài", "a\u{0300}i", "ai4", "AI4", "  ai4  "] {
        assert_unique(&catalog, Orthography::Simplified("爱"), pinyin);
    }
}

#[test]
fn umlaut_conventions_and_apostrophe_spacing_are_equivalent() {
    let catalog = HskCatalog::new();

    // 女儿 nǚ'ér is present in the official 2015 workbook. These inputs
    // exercise spelling equivalence; they must not create new lexical readings.
    for pinyin in ["nǚ'ér", "nv3'er2", "nu:3 er2", "NV3’ER2"] {
        assert_unique(&catalog, Orthography::Simplified("女儿"), pinyin);
    }
}

#[test]
fn neutral_tone_zero_and_five_are_equivalent() {
    let catalog = HskCatalog::new();

    for pinyin in ["māma", "ma1ma", "ma1ma0", "ma1ma5", "MA1 MA"] {
        assert_unique(&catalog, Orthography::Simplified("妈妈"), pinyin);
    }
}

#[test]
fn simplified_traditional_and_consistent_dual_input_match() {
    let catalog = HskCatalog::new();

    assert_unique(&catalog, Orthography::Simplified("爱"), "ai4");
    assert_unique(&catalog, Orthography::Traditional("愛"), "ai4");
    assert_unique(
        &catalog,
        Orthography::Both {
            simplified: "爱",
            traditional: "愛",
        },
        "ai4",
    );
}

#[test]
fn conflicting_dual_input_is_an_error() {
    let catalog = HskCatalog::new();

    let result = catalog.lookup(
        HskSystem::Hsk2015,
        Orthography::Both {
            simplified: "爱",
            traditional: "學習",
        },
        "ai4",
    );
    assert!(result.is_err());
}

#[test]
fn malformed_pinyin_is_rejected_instead_of_guessed() {
    let catalog = HskCatalog::new();

    for malformed in ["ai9", "a4i", "nü:", "'"] {
        assert!(
            catalog
                .lookup(HskSystem::Hsk2015, Orthography::Simplified("爱"), malformed,)
                .is_err(),
            "{malformed:?} must be rejected"
        );
    }
}

#[test]
fn missing_word_is_not_a_numeric_level_or_an_error() {
    let catalog = HskCatalog::new();
    assert!(matches!(
        catalog.lookup(
            HskSystem::Hsk2015,
            Orthography::Simplified("𠮷野家"),
            "ji2ye3jia1",
        ),
        Ok(LookupOutcome::NotFound)
    ));
}

#[test]
fn orthography_only_lookup_does_not_choose_a_polyphonic_reading() {
    let catalog = HskCatalog::new();
    let result = catalog
        .lookup_orthography(
            HskSystem::ProficiencyStandard2021,
            Orthography::Simplified("长"),
        )
        .expect("orthography is valid");

    assert!(matches!(
        result,
        LookupOutcome::Ambiguous(ref candidates) if candidates.len() >= 2
    ));
}

#[test]
fn strict_lookup_resolves_known_polyphonic_readings_independently() {
    let catalog = HskCatalog::new();

    for pinyin in ["chang2", "zhang3"] {
        assert!(matches!(
            catalog.lookup(
                HskSystem::ProficiencyStandard2021,
                Orthography::Simplified("长"),
                pinyin,
            ),
            Ok(LookupOutcome::Unique(_))
        ));
    }
}

#[test]
fn orthography_only_absence_is_explicit() {
    let catalog = HskCatalog::new();
    assert!(matches!(
        catalog.lookup_orthography(HskSystem::Hsk2015, Orthography::Simplified("𠮷野家"),),
        Ok(LookupOutcome::NotFound)
    ));
}
