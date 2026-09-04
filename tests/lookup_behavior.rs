use hsk::{EvidenceStatus, HskCatalog, HskSystem, LookupOutcome, Orthography};

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

    assert!(matches!(
        catalog.lookup(
            HskSystem::ProficiencyStandard2021,
            Orthography::Simplified("长"),
            "chang2",
        ),
        Ok(LookupOutcome::Unique(_))
    ));

    // The standard also classifies the suffix 长（秘书长）at level six.
    // It shares zhǎng with the standalone level-two verb, so strict lexical
    // identity correctly retains both source assignments.
    assert!(matches!(
        catalog.lookup(
            HskSystem::ProficiencyStandard2021,
            Orthography::Simplified("长"),
            "zhang3",
        ),
        Ok(LookupOutcome::Ambiguous(ref candidates)) if candidates.len() == 2
    ));
}

#[test]
fn orthography_only_absence_is_explicit() {
    let catalog = HskCatalog::new();
    assert!(matches!(
        catalog.lookup_orthography(HskSystem::Hsk2015, Orthography::Simplified("𠮷野家"),),
        Ok(LookupOutcome::NotFound)
    ));
}

#[test]
fn unresolved_source_pinyin_is_not_promoted_to_strict_identity() {
    let catalog = HskCatalog::new();
    let strict = catalog.lookup(
        HskSystem::ProficiencyStandard2021,
        Orthography::Simplified("爱"),
        "ai4",
    );
    assert!(matches!(strict, Ok(LookupOutcome::NotFound)), "{strict:?}");
    let orthography = catalog
        .lookup_orthography(
            HskSystem::ProficiencyStandard2021,
            Orthography::Simplified("爱"),
        )
        .unwrap();
    let LookupOutcome::Unique(found) = orthography else {
        panic!("unexpected outcome: {orthography:?}");
    };
    assert_eq!(
        found.classification().evidence(),
        EvidenceStatus::AuthoritativeOrthographyOnly
    );
}

#[test]
fn every_gf0025_evidence_tier_is_explicit() {
    let catalog = HskCatalog::new();
    let cases = [
        ("爱好", Some("ai4hao4"), EvidenceStatus::AuthoritativeSource),
        ("倒", Some("dao4"), EvidenceStatus::AuthoritativeCorrection),
        (
            "爸爸",
            None,
            EvidenceStatus::VerificationCandidateUnresolved,
        ),
    ];
    for (word, pinyin, expected) in cases {
        let outcome = match pinyin {
            Some(reading) => catalog
                .lookup(
                    HskSystem::ProficiencyStandard2021,
                    Orthography::Simplified(word),
                    reading,
                )
                .unwrap(),
            None => catalog
                .lookup_orthography(
                    HskSystem::ProficiencyStandard2021,
                    Orthography::Simplified(word),
                )
                .unwrap(),
        };
        let LookupOutcome::Unique(found) = outcome else {
            panic!("unexpected outcome for {word}: {outcome:?}");
        };
        assert_eq!(found.classification().evidence(), expected);
    }
}
