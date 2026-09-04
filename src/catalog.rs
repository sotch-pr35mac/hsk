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

type IndexRange = &'static [(&'static str, usize)];
type CandidateRanges = (Dataset, IndexRange, Option<IndexRange>);

enum NormalizedOrthography<'a> {
    Simplified(std::borrow::Cow<'a, str>),
    Traditional(std::borrow::Cow<'a, str>),
    Both {
        simplified: std::borrow::Cow<'a, str>,
        traditional: std::borrow::Cow<'a, str>,
    },
}

fn normalized_orthography<'a>(
    orthography: Orthography<'a>,
) -> Result<NormalizedOrthography<'a>, LookupError> {
    fn normalize<'a>(value: &'a str) -> Result<std::borrow::Cow<'a, str>, LookupError> {
        normalize_headword(value).map_err(|_| LookupError::EmptyOrthography)
    }
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
    index: &'static [(&'static str, usize)],
    query: &str,
) -> &'static [(&'static str, usize)] {
    let start = index.partition_point(|(headword, _)| *headword < query);
    let tail = &index[start..];
    let end = tail.partition_point(|(headword, _)| *headword <= query);
    &tail[..end]
}

fn candidate_ranges(
    system: HskSystem,
    orthography: &NormalizedOrthography<'_>,
) -> Result<CandidateRanges, LookupError> {
    let selected = dataset(system);
    match orthography {
        NormalizedOrthography::Simplified(value) => Ok((
            selected,
            indexed_candidates(selected.simplified, value),
            None,
        )),
        NormalizedOrthography::Traditional(value) => Ok((
            selected,
            indexed_candidates(selected.traditional, value),
            None,
        )),
        NormalizedOrthography::Both {
            simplified,
            traditional,
        } => Ok((
            selected,
            indexed_candidates(selected.simplified, simplified),
            Some(indexed_candidates(selected.traditional, traditional)),
        )),
    }
}

fn outcome(mut rows: impl Iterator<Item = Classification>) -> LookupOutcome {
    let Some(first) = rows.next() else {
        return LookupOutcome::NotFound;
    };
    let Some(second) = rows.next() else {
        return LookupOutcome::Unique(WordMatch::new(first));
    };
    let mut matches = vec![WordMatch::new(first), WordMatch::new(second)];
    matches.extend(rows.map(WordMatch::new));
    match matches.len() {
        0 => LookupOutcome::NotFound,
        1 => unreachable!(),
        _ => LookupOutcome::Ambiguous(matches),
    }
}

struct MatchingRows<'a> {
    selected: Dataset,
    primary: &'static [(&'static str, usize)],
    secondary: Option<&'static [(&'static str, usize)]>,
    pinyin: Option<&'a str>,
    position: usize,
}

impl Iterator for MatchingRows<'_> {
    type Item = Classification;

    fn next(&mut self) -> Option<Self::Item> {
        while let Some((_, row)) = self.primary.get(self.position) {
            self.position += 1;
            if self
                .secondary
                .is_none_or(|secondary| secondary.iter().any(|(_, candidate)| candidate == row))
                && self
                    .pinyin
                    .is_none_or(|key| self.selected.rows[*row].reading_matches(key))
            {
                return Some(self.selected.rows[*row]);
            }
        }
        None
    }
}

fn matching_rows<'a>(
    selected: Dataset,
    primary: &'static [(&'static str, usize)],
    secondary: Option<&'static [(&'static str, usize)]>,
    pinyin: Option<&'a str>,
) -> Result<MatchingRows<'a>, LookupError> {
    if let Some(secondary) = secondary {
        if primary.is_empty() || secondary.is_empty() {
            return Ok(MatchingRows {
                selected,
                primary,
                secondary: Some(secondary),
                pinyin,
                position: 0,
            });
        }
        let has_common = primary
            .iter()
            .any(|(_, row)| secondary.iter().any(|(_, candidate)| candidate == row));
        if !has_common {
            return Err(LookupError::ConflictingOrthographies);
        }
    }
    Ok(MatchingRows {
        selected,
        primary,
        secondary,
        pinyin,
        position: 0,
    })
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
        let (selected, primary, secondary) = candidate_ranges(system, &orthography)?;
        Ok(outcome(matching_rows(
            selected,
            primary,
            secondary,
            Some(&pinyin),
        )?))
    }

    /// Look up spelling alone. Multiple readings/senses remain ambiguous.
    pub fn lookup_orthography(
        &self,
        system: HskSystem,
        orthography: Orthography<'_>,
    ) -> Result<LookupOutcome, LookupError> {
        let orthography = normalized_orthography(orthography)?;
        let (selected, primary, secondary) = candidate_ranges(system, &orthography)?;
        Ok(outcome(matching_rows(selected, primary, secondary, None)?))
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
                candidate_ranges(system, &orthography).and_then(|(selected, primary, secondary)| {
                    matching_rows(selected, primary, secondary, Some(&pinyin))
                        .map(|rows| (system, outcome(rows)))
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
            .map(|system| {
                candidate_ranges(system, &orthography).and_then(|(selected, primary, secondary)| {
                    matching_rows(selected, primary, secondary, None)
                        .map(|rows| (system, outcome(rows)))
                })
            })
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
