"""Conservative normalization used only for independent comparisons.

This deliberately does not simplify/traditional-convert headwords. Such aliases
must be supplied explicitly by the authoritative extraction or verification
source. Pinyin numbers are converted to tone marks so marked and numbered forms
share a deterministic key without requiring a dictionary or fuzzy matching.
"""

from __future__ import annotations

import re
import unicodedata

_TONE_MARKS = {1: "\u0304", 2: "\u0301", 3: "\u030c", 4: "\u0300"}
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'", "`": "'"})
_NUMBERED_SYLLABLE = re.compile(r"([a-züv:]+)([0-5])", re.IGNORECASE)
_ALLOWED_PINYIN = re.compile(r"[a-zü:0-5/'…\-\s\u0300-\u036f]+", re.IGNORECASE)


def normalize_headword(value: str) -> str:
    """Normalize Unicode and surrounding whitespace, but not lexical identity."""

    normalized = unicodedata.normalize("NFC", value).strip()
    if not normalized:
        raise ValueError("headword must not be blank")
    return normalized


def _mark_numbered_syllable(base: str, tone: int) -> str:
    base = base.lower().replace("u:", "ü").replace("v", "ü")
    if tone in (0, 5):
        return base

    if "a" in base:
        mark_at = base.index("a")
    elif "e" in base:
        mark_at = base.index("e")
    elif "ou" in base:
        mark_at = base.index("o")
    else:
        vowel_positions = [
            index for index, character in enumerate(base) if character in "aeiouü"
        ]
        if not vowel_positions:
            # Syllabic interjections such as m2 and ng4 are valid pinyin.
            consonant_positions = [
                index for index, character in enumerate(base) if character in "mn"
            ]
            mark_at = consonant_positions[-1] if consonant_positions else len(base) - 1
        else:
            mark_at = vowel_positions[-1]

    marked = base[: mark_at + 1] + _TONE_MARKS[tone] + base[mark_at + 1 :]
    return unicodedata.normalize("NFC", marked)


def _normalize_alternative(value: str) -> str:
    value = unicodedata.normalize("NFC", value.translate(_APOSTROPHES)).lower()
    value = value.replace("u:", "ü").replace("v", "ü")
    # These separators vary between otherwise identical transcriptions. The
    # Rust lookup normalizer intentionally treats them as spelling variants.
    value = re.sub(r"[\s\-']+", "", value)
    if not value:
        raise ValueError("pinyin alternative must not be blank")
    if not _ALLOWED_PINYIN.fullmatch(unicodedata.normalize("NFD", value)):
        raise ValueError(f"unsupported pinyin characters in {value!r}")

    if any(character.isdigit() for character in value):
        output: list[str] = []
        cursor = 0
        for match in _NUMBERED_SYLLABLE.finditer(value):
            between = value[cursor : match.start()]
            if between:
                raise ValueError(f"mixed or malformed numbered pinyin {value!r}")
            output.append(_mark_numbered_syllable(match.group(1), int(match.group(2))))
            cursor = match.end()
        if value[cursor:]:
            raise ValueError(f"mixed or malformed numbered pinyin {value!r}")
        value = "".join(output)

    return unicodedata.normalize("NFC", value)


def normalize_pinyin(value: str) -> tuple[str, ...]:
    """Return a sorted set of normalized pronunciations.

    Slash-delimited readings are identities of the same source row but remain
    separate keys. Apostrophes, whitespace, and hyphens are accepted spelling
    variants and omitted from the comparison key, matching the Rust API.
    """

    alternatives = {
        _normalize_alternative(part)
        for part in value.split("/")
        if part.strip()
    }
    if not alternatives:
        raise ValueError("pinyin must contain at least one reading")
    return tuple(sorted(alternatives))
