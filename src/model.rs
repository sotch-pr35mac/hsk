//! Public query and result types for the HSK catalogs.
//!
//! [`HskSystem`] identifies a source document, [`HskLevel`] identifies a
//! level within that document, [`HskQuery`] carries a simplified word and an
//! optional pinyin reading, and [`HskError`] describes malformed input.
//!
//! The enums are `#[non_exhaustive]` so adding a published classification,
//! level, or error in a future release does not make downstream matches fail
//! to compile.

use core::fmt;

/// A published HSK or Chinese-proficiency classification.
#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
#[non_exhaustive]
pub enum HskSystem {
    /// The six-level HSK examination vocabulary published in 2015.
    Hsk2015,
    /// The GF0025-2021 proficiency standard.
    ProficiencyStandard2021,
    /// The HSK examination syllabus published in 2025 for use from July 2026.
    HskExamSyllabus2025,
}

impl HskSystem {
    /// Return this system's zero-based slot in the embedded catalog header.
    pub(crate) const fn catalog_index(self) -> usize {
        match self {
            Self::Hsk2015 => 0,
            Self::ProficiencyStandard2021 => 1,
            Self::HskExamSyllabus2025 => 2,
        }
    }
}

impl fmt::Display for HskSystem {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(match self {
            Self::Hsk2015 => "HSK examination vocabulary (2015)",
            Self::ProficiencyStandard2021 => "GF0025-2021 proficiency standard",
            Self::HskExamSyllabus2025 => "HSK examination syllabus (2025/2026)",
        })
    }
}

/// A level assigned by a selected classification.
#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub enum HskLevel {
    /// Level 1.
    One,
    /// Level 2.
    Two,
    /// Level 3.
    Three,
    /// Level 4.
    Four,
    /// Level 5.
    Five,
    /// Level 6.
    Six,
    /// The shared advanced band used by the newer documents.
    SevenToNine,
}

impl HskLevel {
    pub(crate) const fn from_index(index: usize) -> Self {
        match index {
            0 => Self::One,
            1 => Self::Two,
            2 => Self::Three,
            3 => Self::Four,
            4 => Self::Five,
            5 => Self::Six,
            6 => Self::SevenToNine,
            _ => unreachable!(),
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

/// A simplified Chinese word with optional pinyin for disambiguation.
#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
pub struct HskQuery<'a> {
    pub(crate) simplified: &'a str,
    pub(crate) pinyin: Option<&'a str>,
}

impl<'a> HskQuery<'a> {
    /// Create a query from the simplified form printed by the selected source.
    #[must_use]
    pub const fn new(simplified: &'a str) -> Self {
        Self {
            simplified,
            pinyin: None,
        }
    }

    /// Add pinyin to distinguish entries with the same simplified form.
    #[must_use]
    pub const fn pinyin(mut self, pinyin: &'a str) -> Self {
        self.pinyin = Some(pinyin);
        self
    }
}

/// A malformed lookup query.
#[derive(Clone, Debug, Eq, PartialEq)]
#[non_exhaustive]
pub enum HskError {
    /// The simplified query was empty or contained only whitespace.
    EmptyWord,
    /// Pinyin could not be parsed; the value gives the validation reason.
    InvalidPinyin(&'static str),
}

impl fmt::Display for HskError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::EmptyWord => formatter.write_str("simplified word must not be empty"),
            Self::InvalidPinyin(reason) => write!(formatter, "invalid pinyin: {reason}"),
        }
    }
}

impl std::error::Error for HskError {}
