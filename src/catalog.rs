use crate::data;
use crate::model::{
    Classification, HskLevel, HskSystem, LevelScope, LookupError, LookupOutcome, Orthography,
    WordMatch,
};
use crate::normalize_shared::{normalize_headword, normalize_pinyin};

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

#[derive(Clone, Copy)]
struct Dataset {
    rows: &'static [Classification],
    simplified: &'static [(&'static str, usize)],
    traditional: &'static [(&'static str, usize)],
    offsets: &'static [usize],
}

enum NormalizedOrthography {
    Simplified(String),
    Traditional(String),
    Both {
        simplified: String,
        traditional: String,
    },
}

fn normalized_orthography(
    orthography: Orthography<'_>,
) -> Result<NormalizedOrthography, LookupError> {
    let normalize = |value| normalize_headword(value).map_err(|_| LookupError::EmptyOrthography);
    match orthography {
        Orthography::Simplified(value) => normalize(value).map(NormalizedOrthography::Simplified),
        Orthography::Traditional(value) => normalize(value).map(NormalizedOrthography::Traditional),
        Orthography::Both {
            simplified,
            traditional,
        } => Ok(NormalizedOrthography::Both {
            simplified: normalize(simplified)?,
            traditional: normalize(traditional)?,
        }),
    }
}

fn dataset(system: HskSystem) -> Dataset {
    match system {
        HskSystem::Hsk2015 => Dataset {
            rows: data::HSK2015,
            simplified: data::HSK2015_SIMPLIFIED_INDEX,
            traditional: data::HSK2015_TRADITIONAL_INDEX,
            offsets: data::HSK2015_OFFSETS,
        },
        HskSystem::ProficiencyStandard2021 => Dataset {
            rows: data::PROFICIENCY2021,
            simplified: data::PROFICIENCY2021_SIMPLIFIED_INDEX,
            traditional: data::PROFICIENCY2021_TRADITIONAL_INDEX,
            offsets: data::PROFICIENCY2021_OFFSETS,
        },
        HskSystem::HskExamSyllabus2025 => Dataset {
            rows: data::EXAM2025,
            simplified: data::EXAM2025_SIMPLIFIED_INDEX,
            traditional: data::EXAM2025_TRADITIONAL_INDEX,
            offsets: data::EXAM2025_OFFSETS,
        },
    }
}

fn indexed_candidates(
    selected: Dataset,
    index: &'static [(&'static str, usize)],
    query: &str,
) -> Vec<Classification> {
    let start = index.partition_point(|(headword, _)| *headword < query);
    let end = index.partition_point(|(headword, _)| *headword <= query);
    index[start..end]
        .iter()
        .map(|(_, row)| selected.rows[*row])
        .collect()
}

fn candidates_for(
    system: HskSystem,
    orthography: &NormalizedOrthography,
) -> Result<Vec<Classification>, LookupError> {
    let selected = dataset(system);
    match orthography {
        NormalizedOrthography::Simplified(value) => {
            Ok(indexed_candidates(selected, selected.simplified, value))
        }
        NormalizedOrthography::Traditional(value) => {
            Ok(indexed_candidates(selected, selected.traditional, value))
        }
        NormalizedOrthography::Both {
            simplified,
            traditional,
        } => {
            let simplified_rows = indexed_candidates(selected, selected.simplified, simplified);
            let traditional_rows = indexed_candidates(selected, selected.traditional, traditional);
            let common: Vec<_> = simplified_rows
                .iter()
                .copied()
                .filter(|row| traditional_rows.contains(row))
                .collect();
            if common.is_empty() && !simplified_rows.is_empty() && !traditional_rows.is_empty() {
                Err(LookupError::ConflictingOrthographies)
            } else {
                Ok(common)
            }
        }
    }
}

fn outcome(rows: impl IntoIterator<Item = Classification>) -> LookupOutcome {
    let matches: Vec<_> = rows.into_iter().map(WordMatch::new).collect();
    match matches.len() {
        0 => LookupOutcome::NotFound,
        1 => LookupOutcome::Unique(matches[0]),
        _ => LookupOutcome::Ambiguous(matches),
    }
}

/// Zero-allocation catalog handle over build-time generated static data.
#[derive(Clone, Copy, Debug, Default)]
pub struct HskCatalog;

impl HskCatalog {
    /// Construct a handle over the build-time generated static catalog.
    #[must_use]
    pub const fn new() -> Self {
        Self
    }

    /// Return every classification system supported by this crate.
    #[must_use]
    pub const fn supported_systems() -> &'static [HskSystem] {
        &SYSTEMS
    }

    /// Return the levels defined by one classification system.
    #[must_use]
    pub const fn supported_levels(system: HskSystem) -> &'static [HskLevel] {
        match system {
            HskSystem::Hsk2015 => &BASIC_LEVELS,
            HskSystem::ProficiencyStandard2021 | HskSystem::HskExamSyllabus2025 => {
                &NINE_LEVEL_BANDS
            }
        }
    }

    /// Look up a lexical reading under one explicitly selected system.
    pub fn lookup(
        &self,
        system: HskSystem,
        orthography: Orthography<'_>,
        pinyin: &str,
    ) -> Result<LookupOutcome, LookupError> {
        let orthography = normalized_orthography(orthography)?;
        let pinyin = normalize_pinyin(pinyin).map_err(LookupError::InvalidPinyin)?;
        Ok(outcome(
            candidates_for(system, &orthography)?
                .into_iter()
                .filter(|row| row.reading_matches(&pinyin)),
        ))
    }

    /// Look up spelling alone. Multiple readings/senses remain ambiguous.
    pub fn lookup_orthography(
        &self,
        system: HskSystem,
        orthography: Orthography<'_>,
    ) -> Result<LookupOutcome, LookupError> {
        let orthography = normalized_orthography(orthography)?;
        Ok(outcome(candidates_for(system, &orthography)?))
    }

    /// Perform one normalized, reading-qualified query against every system.
    pub fn lookup_all(
        &self,
        orthography: Orthography<'_>,
        pinyin: &str,
    ) -> Result<Vec<(HskSystem, LookupOutcome)>, LookupError> {
        let orthography = normalized_orthography(orthography)?;
        let pinyin = normalize_pinyin(pinyin).map_err(LookupError::InvalidPinyin)?;
        SYSTEMS
            .into_iter()
            .map(|system| {
                candidates_for(system, &orthography).map(|rows| {
                    (
                        system,
                        outcome(rows.into_iter().filter(|row| row.reading_matches(&pinyin))),
                    )
                })
            })
            .collect()
    }

    /// Perform an orthography-only query against every system.
    pub fn lookup_all_orthography(
        &self,
        orthography: Orthography<'_>,
    ) -> Result<Vec<(HskSystem, LookupOutcome)>, LookupError> {
        let orthography = normalized_orthography(orthography)?;
        SYSTEMS
            .into_iter()
            .map(|system| candidates_for(system, &orthography).map(|rows| (system, outcome(rows))))
            .collect()
    }

    /// Enumerate source assignments at exactly `level` or cumulatively through it.
    pub fn words(
        &self,
        system: HskSystem,
        level: HskLevel,
        scope: LevelScope,
    ) -> Result<&'static [Classification], LookupError> {
        if !Self::supported_levels(system).contains(&level) {
            return Err(LookupError::InvalidLevel { system, level });
        }
        let selected = dataset(system);
        let index = level.index();
        let start = match scope {
            LevelScope::Exact => selected.offsets[index],
            LevelScope::Cumulative => 0,
        };
        Ok(&selected.rows[start..selected.offsets[index + 1]])
    }
}
