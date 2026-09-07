//! Return versioned HSK level for Simplified Chinese characters.
//!
//! The crate embeds the published simplified-word catalogs and performs
//! allocation-free catalog lookup. Query normalization allocates only when
//! normalization or a returned result requires it.
//!
//! ```
//! use hsk::{HskLevel, HskQuery, HskSystem};
//!
//! let result = hsk::levels(
//!     HskSystem::Hsk2015,
//!     HskQuery::new("爱").pinyin("ai4"),
//! )?;
//! assert_eq!(result, [HskLevel::One]);
//! # Ok::<(), hsk::HskError>(())
//! ```

mod catalog;
mod model;
mod normalize;

pub use catalog::{levels, levels_all};
pub use model::{HskError, HskLevel, HskQuery, HskSystem};
