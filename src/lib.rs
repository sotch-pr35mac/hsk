//! Authoritative, explicitly versioned HSK and Chinese-proficiency data.
//!
//! The 2021 GF0025 proficiency standard and the current HSK examination
//! syllabus are related but distinct classifications. Callers always select a
//! [`HskSystem`], and reading ambiguity is represented by [`LookupOutcome`].
//!
//! ```
//! use hsk::{HskCatalog, HskSystem, LookupOutcome, Orthography};
//!
//! let catalog = HskCatalog::new();
//! let result = catalog.lookup(
//!     HskSystem::Hsk2015,
//!     Orthography::Traditional("愛"),
//!     "ai4",
//! )?;
//! assert!(matches!(result, LookupOutcome::Unique(_)));
//! # Ok::<(), hsk::LookupError>(())
//! ```

mod catalog;
mod model;
mod normalize_shared;

mod data {
    use crate::{Classification, EvidenceStatus, HskLevel, HskSystem};

    include!(concat!(env!("OUT_DIR"), "/hsk_generated.rs"));
}

pub use catalog::HskCatalog;
pub use model::{
    Classification, EvidenceStatus, HskLevel, HskSystem, LevelScope, LookupError, LookupOutcome,
    Orthography, WordMatch,
};
