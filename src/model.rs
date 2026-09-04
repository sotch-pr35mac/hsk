use core::fmt;

/// One of the three separately sourced classifications bundled by the crate.
#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
#[non_exhaustive]
pub enum HskSystem {
    /// The six-level 汉语水平考试（HSK）词汇表（2015版）.
    Hsk2015,
    /// The GF0025-2021 national proficiency standard (三等九级).
    ProficiencyStandard2021,
    /// The examination syllabus published in November 2025 for July 2026 use.
    HskExamSyllabus2025,
}

impl fmt::Display for HskSystem {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(match self {
            Self::Hsk2015 => "HSK 2.0 / 2015 examination vocabulary",
            Self::ProficiencyStandard2021 => "GF0025-2021 proficiency standard",
            Self::HskExamSyllabus2025 => "HSK examination syllabus (2025/2026)",
        })
    }
}

/// A vocabulary level. Newer sources publish a shared advanced 7–9 band.
#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub enum HskLevel {
    /// Level one.
    One,
    /// Level two.
    Two,
    /// Level three.
    Three,
    /// Level four.
    Four,
    /// Level five.
    Five,
    /// Level six.
    Six,
    /// The shared advanced vocabulary band printed by the newer documents.
    SevenToNine,
}

impl HskLevel {
    pub(crate) const fn index(self) -> usize {
        match self {
            Self::One => 0,
            Self::Two => 1,
            Self::Three => 2,
            Self::Four => 3,
            Self::Five => 4,
            Self::Six => 5,
            Self::SevenToNine => 6,
        }
    }
}

impl fmt::Display for HskLevel {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(match self {
            Self::One => "1",
            Self::Two => "2",
            Self::Three => "3",
            Self::Four => "4",
            Self::Five => "5",
            Self::Six => "6",
            Self::SevenToNine => "7–9",
        })
    }
}

/// Whether level enumeration is exact or includes all preceding levels.
#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
pub enum LevelScope {
    /// Assignments introduced at exactly the requested level.
    Exact,
    /// Assignments through and including the requested level.
    Cumulative,
}

/// How directly a generated assignment is supported by the authoritative row.
#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
pub enum EvidenceStatus {
    /// The relevant row fields were extracted directly from the authoritative source.
    AuthoritativeSource,
    /// A reviewed correction is tied to a cited authoritative page or row.
    AuthoritativeCorrection,
    /// Orthography is visible in the authoritative row, but its pinyin is unresolved.
    AuthoritativeOrthographyOnly,
    /// The row remains a non-authoritative verification candidate requiring review.
    VerificationCandidateUnresolved,
}

/// The spelling supplied for a lookup.
#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
pub enum Orthography<'a> {
    /// A simplified form.
    Simplified(&'a str),
    /// A traditional form.
    Traditional(&'a str),
    /// Both forms, which must identify the same source assignment.
    Both {
        /// The simplified form.
        simplified: &'a str,
        /// The traditional form.
        traditional: &'a str,
    },
}

/// One source-backed vocabulary assignment.
#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
pub struct Classification {
    system: HskSystem,
    level: HskLevel,
    evidence: EvidenceStatus,
    simplified: &'static str,
    traditional: &'static str,
    pinyin: &'static str,
    normalized_pinyin: &'static str,
    part_of_speech: &'static str,
    sense_label: &'static str,
    source_sequence: usize,
    source_locator: &'static str,
}

impl Classification {
    #[allow(clippy::too_many_arguments)]
    pub(crate) const fn from_static(
        system: HskSystem,
        level: HskLevel,
        evidence: EvidenceStatus,
        simplified: &'static str,
        traditional: &'static str,
        pinyin: &'static str,
        normalized_pinyin: &'static str,
        part_of_speech: &'static str,
        sense_label: &'static str,
        source_sequence: usize,
        source_locator: &'static str,
    ) -> Self {
        Self {
            system,
            level,
            evidence,
            simplified,
            traditional,
            pinyin,
            normalized_pinyin,
            part_of_speech,
            sense_label,
            source_sequence,
            source_locator,
        }
    }

    /// The authoritative classification system.
    pub const fn system(&self) -> HskSystem {
        self.system
    }
    /// The level assigned by that system.
    pub const fn level(&self) -> HskLevel {
        self.level
    }
    /// The review/evidence status of this generated assignment.
    pub const fn evidence(&self) -> EvidenceStatus {
        self.evidence
    }
    /// The simplified headword retained by the canonical dataset.
    pub const fn simplified(&self) -> &'static str {
        self.simplified
    }

    /// The reviewed traditional form, when one is available.
    pub const fn traditional(&self) -> Option<&'static str> {
        if self.traditional.is_empty() {
            None
        } else {
            Some(self.traditional)
        }
    }

    /// Raw pinyin as printed by the source or documented enrichment source.
    pub const fn pinyin(&self) -> Option<&'static str> {
        if self.pinyin.is_empty() {
            None
        } else {
            Some(self.pinyin)
        }
    }

    /// The printed part of speech, when supplied by the source.
    pub const fn part_of_speech(&self) -> Option<&'static str> {
        if self.part_of_speech.is_empty() {
            None
        } else {
            Some(self.part_of_speech)
        }
    }

    /// A printed sense marker used to distinguish otherwise identical rows.
    pub const fn sense_label(&self) -> Option<&'static str> {
        if self.sense_label.is_empty() {
            None
        } else {
            Some(self.sense_label)
        }
    }

    /// The stable sequence number in the authoritative document.
    pub const fn source_sequence(&self) -> usize {
        self.source_sequence
    }
    /// A sheet/row or PDF page/sequence locator for review.
    pub const fn source_locator(&self) -> &'static str {
        self.source_locator
    }

    pub(crate) fn reading_matches(&self, normalized: &str) -> bool {
        self.normalized_pinyin
            .split('|')
            .any(|reading| !reading.is_empty() && reading == normalized)
    }
}

/// A matched assignment. Kept separate so match metadata can evolve.
#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
pub struct WordMatch {
    classification: Classification,
}

impl WordMatch {
    pub(crate) const fn new(classification: Classification) -> Self {
        Self { classification }
    }
    /// The matching source-backed classification.
    pub const fn classification(&self) -> &Classification {
        &self.classification
    }
}

/// An explicit lookup result; ambiguity is never resolved arbitrarily.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum LookupOutcome {
    /// No assignment has the requested identity.
    NotFound,
    /// Exactly one assignment matches.
    Unique(WordMatch),
    /// Multiple source assignments match; callers must not choose arbitrarily.
    Ambiguous(Vec<WordMatch>),
}

/// Errors in a query itself, distinct from a well-formed query with no match.
#[derive(Clone, Debug, Eq, PartialEq)]
#[non_exhaustive]
pub enum LookupError {
    /// A supplied simplified or traditional form is empty.
    EmptyOrthography,
    /// Pinyin contains malformed or unsupported input.
    InvalidPinyin(&'static str),
    /// The supplied simplified and traditional forms identify different rows.
    ConflictingOrthographies,
    /// The selected system does not define the requested level.
    InvalidLevel {
        /// The selected classification system.
        system: HskSystem,
        /// The invalid level.
        level: HskLevel,
    },
}

impl fmt::Display for LookupError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::EmptyOrthography => formatter.write_str("orthography must not be empty"),
            Self::InvalidPinyin(reason) => write!(formatter, "invalid pinyin: {reason}"),
            Self::ConflictingOrthographies => {
                formatter.write_str("simplified and traditional forms identify different rows")
            }
            Self::InvalidLevel { system, level } => {
                write!(formatter, "level {level} is not defined by {system}")
            }
        }
    }
}

impl std::error::Error for LookupError {}
