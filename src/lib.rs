//! Versioned HSK and Chinese-proficiency level lookup.
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
mod normalize_shared;

pub use catalog::{levels, levels_all};
pub use model::{HskError, HskLevel, HskQuery, HskSystem};
