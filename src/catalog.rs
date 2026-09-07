use crate::model::{HskError, HskLevel, HskQuery, HskSystem};
use crate::normalize_shared::{normalize_headword, normalize_pinyin};

const DATA: &[u8] = include_bytes!("../data/hsk.bin");
#[cfg(test)]
const MAGIC: &[u8; 4] = b"HSK1";
const HEADER_LEN: usize = 40;
const RECORD_LEN: usize = 16;

#[derive(Clone, Copy)]
struct Record {
    word_offset: usize,
    pinyin_offset: usize,
    word_len: usize,
    pinyin_len: usize,
    levels: u8,
}

fn u16_at(offset: usize) -> u16 {
    u16::from_le_bytes(
        DATA.get(offset..offset + 2)
            .expect("bundled HSK data is truncated")
            .try_into()
            .expect("two-byte field"),
    )
}

fn u32_at(offset: usize) -> u32 {
    u32::from_le_bytes(
        DATA.get(offset..offset + 4)
            .expect("bundled HSK data is truncated")
            .try_into()
            .expect("four-byte field"),
    )
}

#[cfg(test)]
fn validate_header() {
    assert_eq!(
        DATA.get(..4),
        Some(MAGIC.as_slice()),
        "invalid HSK data magic"
    );
    assert_eq!(u16_at(4), 1, "unsupported HSK data version");
    assert_eq!(
        usize::from(u16_at(6)),
        RECORD_LEN,
        "invalid HSK record size"
    );
    let strings = u32_at(8) as usize;
    let string_len = u32_at(12) as usize;
    assert_eq!(
        strings.checked_add(string_len),
        Some(DATA.len()),
        "invalid HSK string table"
    );
}

fn system_range(system: HskSystem) -> (usize, usize) {
    let offset = 16 + system.index() * 8;
    (u32_at(offset) as usize, u32_at(offset + 4) as usize)
}

fn record(index: usize) -> Record {
    let offset = HEADER_LEN + index * RECORD_LEN;
    Record {
        word_offset: u32_at(offset) as usize,
        pinyin_offset: u32_at(offset + 4) as usize,
        word_len: usize::from(u16_at(offset + 8)),
        pinyin_len: usize::from(u16_at(offset + 10)),
        levels: *DATA
            .get(offset + 12)
            .expect("bundled HSK record is truncated"),
    }
}

fn string(offset: usize, len: usize) -> &'static str {
    let strings = u32_at(8) as usize;
    let start = strings
        .checked_add(offset)
        .expect("HSK string offset overflow");
    let end = start.checked_add(len).expect("HSK string length overflow");
    let bytes = DATA
        .get(start..end)
        .expect("HSK string points outside the bundled data");
    core::str::from_utf8(bytes).expect("HSK string table is not UTF-8")
}

fn word(index: usize) -> &'static str {
    let item = record(index);
    string(item.word_offset, item.word_len)
}

fn partition_point(mut start: usize, mut end: usize, predicate: impl Fn(usize) -> bool) -> usize {
    while start < end {
        let middle = start + (end - start) / 2;
        if predicate(middle) {
            start = middle + 1;
        } else {
            end = middle;
        }
    }
    start
}

fn equal_range(system: HskSystem, query: &str) -> core::ops::Range<usize> {
    let (start, count) = system_range(system);
    let end = start.checked_add(count).expect("HSK record range overflow");
    let lower = partition_point(start, end, |index| word(index) < query);
    let upper = partition_point(lower, end, |index| word(index) <= query);
    lower..upper
}

fn levels_from_mask(mask: u8) -> Vec<HskLevel> {
    (0..7)
        .filter(|index| mask & (1 << index) != 0)
        .map(HskLevel::from_index)
        .collect()
}

fn levels_normalized(system: HskSystem, simplified: &str, pinyin: Option<&str>) -> Vec<HskLevel> {
    let mut mask = 0;
    for index in equal_range(system, simplified) {
        let item = record(index);
        let stored_pinyin = string(item.pinyin_offset, item.pinyin_len);
        if pinyin.is_none_or(|value| stored_pinyin.is_empty() || stored_pinyin == value) {
            mask |= item.levels;
        }
    }
    levels_from_mask(mask)
}

/// Return every level matching a query in one classification.
pub fn levels(system: HskSystem, query: HskQuery<'_>) -> Result<Vec<HskLevel>, HskError> {
    let simplified = normalize_headword(query.simplified).map_err(|_| HskError::EmptyWord)?;
    let pinyin = query
        .pinyin
        .map(normalize_pinyin)
        .transpose()
        .map_err(HskError::InvalidPinyin)?;
    Ok(levels_normalized(system, &simplified, pinyin.as_deref()))
}

/// Return matching levels from every classification containing the word.
pub fn levels_all(query: HskQuery<'_>) -> Result<Vec<(HskSystem, Vec<HskLevel>)>, HskError> {
    let simplified = normalize_headword(query.simplified).map_err(|_| HskError::EmptyWord)?;
    let pinyin = query
        .pinyin
        .map(normalize_pinyin)
        .transpose()
        .map_err(HskError::InvalidPinyin)?;
    Ok([
        HskSystem::Hsk2015,
        HskSystem::ProficiencyStandard2021,
        HskSystem::HskExamSyllabus2025,
    ]
    .into_iter()
    .filter_map(|system| {
        let found = levels_normalized(system, &simplified, pinyin.as_deref());
        if found.is_empty() {
            None
        } else {
            Some((system, found))
        }
    })
    .collect())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bundled_data_is_well_formed_and_sorted() {
        validate_header();
        for system in [
            HskSystem::Hsk2015,
            HskSystem::ProficiencyStandard2021,
            HskSystem::HskExamSyllabus2025,
        ] {
            let (start, count) = system_range(system);
            let mut previous = None;
            for index in start..start + count {
                let item = record(index);
                let current = word(index);
                assert!(!current.is_empty());
                assert!(!current.contains(['（', '）', '(', ')']));
                assert_ne!(item.levels, 0);
                let pinyin = string(item.pinyin_offset, item.pinyin_len);
                assert!(
                    pinyin
                        .chars()
                        .all(|character| character.is_ascii_lowercase()
                            || matches!(character, '1'..='4'))
                );
                if let Some(previous) = previous {
                    assert!(previous <= current);
                }
                previous = Some(current);
            }
        }
    }
}
