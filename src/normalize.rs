//! Normalize query spellings to the catalog's comparison keys.
//!
//! Headwords use NFC: already-normalized or ASCII input is borrowed through a
//! [`Cow`], while other input gets one owned normalized string. Pinyin is
//! streamed through NFD decomposition so precomposed and combining tone marks
//! are equivalent. Tone placement follows standard pinyin (`a`, then `e`, then
//! `ou`, otherwise the final eligible vowel); numbered and marked tones become
//! the same numbered representation, including neutral tones `0` and `5`.
//!
//! Separators end syllables, while a second marked vowel can also establish a
//! syllable boundary (so `nǚér` and `nǚ'ér` agree). Umlauts become `v`, accepting
//! `ü`, `u:`, and `v`. Invalid tone placement, repeated tones, unsupported
//! characters, and malformed separators are rejected. The parser reuses its
//! syllable buffer and allocates one output string for the normalized key.

use std::borrow::Cow;

use unicode_normalization::UnicodeNormalization;

fn tone_position(syllable: &[char]) -> Option<usize> {
    if let Some(position) = syllable.iter().position(|character| *character == 'a') {
        return Some(position);
    }
    if let Some(position) = syllable.iter().position(|character| *character == 'e') {
        return Some(position);
    }
    if let Some(position) = syllable.windows(2).position(|window| window == ['o', 'u']) {
        return Some(position);
    }
    syllable
        .iter()
        .rposition(|character| matches!(character, 'a' | 'e' | 'i' | 'o' | 'u' | 'v' | 'm' | 'n'))
}

fn append_syllable(
    output: &mut String,
    syllable: &mut Vec<char>,
    tone: &mut Option<(u8, Option<usize>)>,
) -> Result<(), &'static str> {
    if syllable.is_empty() {
        return Ok(());
    }
    let selected = match *tone {
        Some((0 | 5, _)) | None => None,
        Some((number, Some(position))) => Some((number, position)),
        Some((number, None)) => Some((
            number,
            tone_position(syllable).ok_or("tone number has no pinyin vowel")?,
        )),
    };
    for (position, character) in syllable.drain(..).enumerate() {
        output.push(character);
        if let Some((number, selected_position)) = selected {
            if position == selected_position {
                output.push(char::from(b'0' + number));
            }
        }
    }
    *tone = None;
    Ok(())
}

pub(crate) fn normalize_pinyin(input: &str) -> Result<String, &'static str> {
    let mut output = String::with_capacity(input.len());
    let mut syllable = Vec::with_capacity(8);
    let mut tone: Option<(u8, Option<usize>)> = None;
    let mut saw_content = false;

    let mut decomposed = input.nfd().enumerate().peekable();
    while let Some((_, raw)) = decomposed.next() {
        if raw.is_whitespace() || matches!(raw, '\'' | '’' | '‘' | 'ʼ' | '-' | '·' | '∥' | '…')
        {
            if matches!(raw, '\'' | '’' | '‘' | 'ʼ') && syllable.is_empty() && output.is_empty()
            {
                return Err("apostrophe does not follow a syllable");
            }
            append_syllable(&mut output, &mut syllable, &mut tone)?;
            continue;
        }

        if let Some(number) = raw.to_digit(10) {
            let number = u8::try_from(number).map_err(|_| "invalid tone number")?;
            if number > 5 || syllable.is_empty() || tone.is_some() {
                return Err("invalid or repeated tone number");
            }
            if let Some((_, next)) = decomposed.peek().copied() {
                if next.is_ascii_alphabetic()
                    && matches!(next.to_ascii_lowercase(), 'a' | 'e' | 'i' | 'o' | 'u')
                    && syllable.last() != Some(&'v')
                {
                    // A following vowel is ambiguous after an ordinary
                    // syllable, but `nv3e...` is the unseparated spelling of
                    // `nǚ ér`: `v` marks the end of the umlaut syllable.
                    return Err("a numbered syllable must end before a following vowel");
                }
            }
            tone = Some((number, None));
            append_syllable(&mut output, &mut syllable, &mut tone)?;
            saw_content = true;
            continue;
        }

        match raw {
            '\u{0308}' => {
                let last = syllable.last_mut().ok_or("umlaut has no base vowel")?;
                if *last != 'u' {
                    return Err("umlaut is only valid on u");
                }
                *last = 'v';
            }
            '\u{0304}' | '\u{0301}' | '\u{030c}' | '\u{0306}' | '\u{0300}' => {
                if syllable.is_empty() {
                    return Err("tone mark has no base vowel");
                }
                if let Some((_, Some(previous_vowel))) = tone {
                    let current_vowel = syllable.len() - 1;
                    if current_vowel == previous_vowel {
                        return Err("repeated tone mark on one vowel");
                    }
                    let boundary = ((previous_vowel + 1)..current_vowel)
                        .find(|index| {
                            !matches!(syllable[*index], 'a' | 'e' | 'i' | 'o' | 'u' | 'v')
                        })
                        .unwrap_or(current_vowel);
                    let mut following = syllable.split_off(boundary);
                    append_syllable(&mut output, &mut syllable, &mut tone)?;
                    syllable.append(&mut following);
                }
                let number = match raw {
                    '\u{0304}' => 1,
                    '\u{0301}' => 2,
                    '\u{030c}' | '\u{0306}' => 3,
                    '\u{0300}' => 4,
                    _ => unreachable!(),
                };
                tone = Some((number, Some(syllable.len() - 1)));
            }
            // The uncommon pinyin vowel ê decomposes to e + circumflex.
            '\u{0302}' => {
                if syllable.last() != Some(&'e') {
                    return Err("circumflex is only valid on e");
                }
            }
            ':' => {
                let last = syllable.last_mut().ok_or("colon has no base vowel")?;
                if *last != 'u' {
                    return Err("u: must use an ASCII u");
                }
                *last = 'v';
            }
            character if character.is_ascii_alphabetic() => {
                syllable.push(character.to_ascii_lowercase());
                saw_content = true;
            }
            _ => return Err("pinyin contains an unsupported character"),
        }
    }
    append_syllable(&mut output, &mut syllable, &mut tone)?;
    if !saw_content || output.is_empty() {
        return Err("pinyin is empty");
    }
    Ok(output)
}

pub(crate) fn normalize_headword(input: &str) -> Result<Cow<'_, str>, &'static str> {
    let trimmed = input.trim();
    if trimmed.is_empty() {
        Err("orthography is empty")
    } else if trimmed.is_ascii() || trimmed.nfc().eq(trimmed.chars()) {
        Ok(Cow::Borrowed(trimmed))
    } else {
        Ok(Cow::Owned(trimmed.nfc().collect()))
    }
}

#[cfg(test)]
mod tests {
    use super::normalize_pinyin;

    #[test]
    fn equivalent_forms_share_a_canonical_key() {
        for group in [
            &["ài", "a\u{0300}i", "ai4", "AI4"][..],
            &["nǚ'ér", "nv3'er2", "nu:3 er2", "NV3’ER2"][..],
            &["māma", "ma1ma", "ma1ma0", "ma1ma5", "MA1 MA"][..],
        ] {
            let expected = normalize_pinyin(group[0]).unwrap();
            for value in group {
                assert_eq!(normalize_pinyin(value).as_ref(), Ok(&expected), "{value:?}");
            }
        }
    }

    #[test]
    fn malformed_forms_are_rejected() {
        for value in ["ai9", "a4i", "nü:", "'"] {
            assert!(normalize_pinyin(value).is_err(), "{value:?}");
        }
    }
}
