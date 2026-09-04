# Independent HSK verification

This directory compares authoritative extractions with separately maintained
transcriptions. It is deliberately outside the Rust crate and uses only the
Python 3.10+ standard library.

Verification data is never canonical. A report can reveal a discrepancy, but
it cannot modify, merge into, or adjudicate the authoritative input. Definitions
are not accepted by the canonical record schema and adapters never use them for
identity.

## Pinned sources

[`sources.json`](sources.json) records the exact revision, last update, claimed
edition, license, expected counts, derivation route, independence limitations,
artifact URL, and SHA-256 for six verification sources spanning all three
systems. The JSON shape is documented by
[`schema/source-manifest.schema.json`](schema/source-manifest.schema.json).

The referenced third-party artifacts are not vendored. This avoids silently
redistributing a source with unclear terms (notably the University of Geneva
PDF) and ensures a maintainer consciously obtains the pinned artifact. See
[`THIRD_PARTY.md`](THIRD_PARTY.md) for the source-by-source license assessment.

Validate the manifest itself:

```bash
python3 verification/verify.py validate-manifest
```

To verify downloaded artifacts, clone a source, check out the manifest's full
commit, and bind its checkout to the source ID:

```bash
python3 verification/verify.py validate-manifest \
  --checkout shawkynasr-gf0025-2021=/path/to/HSK-official-Query-System \
  --checkout punpuf-hsk-syllabus-2025=/path/to/hsk-syllabus-vocabulary-parser
```

Every listed `repository_path` must exist and match its pinned SHA-256. A hash
change requires review and an explicit manifest update; it is never accepted as
an implicit upstream refresh.

## Canonical comparison input

The authoritative pipeline exports one JSON object per classification
assignment. Required and optional fields are defined by
[`schema/record.schema.json`](schema/record.schema.json):

```json
{"record_id":"gf0025:page-75:row-4","level":"2","simplified":"行","traditional":"行","pinyin":"xíng","pinyin_normalized":"xing2","part_of_speech":"动","source_locator":"page 75, row 4"}
```

`pinyin_normalized` is preferred when the authoritative generator supplies it.
The comparison normalizer recognizes tone marks and numbers, NFC/NFD, `ü`/`u:`/
`v`, case, spaces, hyphens, straight/curly apostrophes, neutral `0`/`5`, and
slash-separated readings. Apostrophes normalize to straight ASCII but remain in
the key because erasing one can merge different syllabifications. Headwords get
Unicode normalization and trimming only—there is no implicit script conversion.

Primary lexical identity is the intersection of explicitly supplied simplified
or traditional forms plus an intersecting normalized-pinyin reading. A
headword-only row is reported as a candidate and remains in both one-sided
lists; it is never promoted to an exact match.

## Inspect and compare

Inspect a pinned source before comparing it. `inspect` checks parsed assignment
counts and per-level counts against the manifest:

```bash
python3 verification/verify.py inspect \
  --source-id punpuf-hsk-syllabus-2025 \
  --input /path/to/hsk_word_list.tsv
```

Adapters included:

| Adapter | Input | Identity fields used |
|---|---|---|
| `canonical-jsonl` | authoritative JSONL | explicit headword forms + pinyin |
| `shawkynasr-2021-csv` | `词汇.csv` | query-export headword + pinyin; source boundary/variant notation is normalized |
| `krmanik-headword-directory` | 2021 or 2025 level directory | headword + filename level; always candidate-only because pinyin is absent |
| `punpuf-2025-tsv` | `hsk_word_list.tsv` | syllabus headword + pinyin + expanded level; CC-CEDICT traditional/definition columns are ignored |
| `profesorm-2025-csv` | `data/hsk_vocabulary.csv` | headword + pinyin; parenthesized secondary levels are expanded |

Generate deterministic JSON and Markdown reports:

```bash
python3 verification/verify.py compare \
  --source-id punpuf-hsk-syllabus-2025 \
  --authoritative generated/hsk_exam_syllabus_2025.jsonl \
  --verification /path/to/hsk_word_list.tsv \
  --verification-adapter punpuf-2025-tsv \
  --json-output reports/hsk-2025-punpuf.json \
  --markdown-output reports/hsk-2025-punpuf.md
```

The JSON contract is [`schema/report.schema.json`](schema/report.schema.json).
Both formats contain:

- exact lexical matches;
- authoritative-only and verification-only rows;
- headword matches with pinyin disagreements;
- exact lexical matches with level disagreements;
- duplicate-count disagreements;
- headword-only candidates that lack enough information to match; and
- adapter/normalization issues with source locators.

Comparison discrepancies are expected and do not make `compare` fail. It exits
nonzero only for parse/normalization issues. `inspect` exits nonzero for issues
or unexpected counts, and manifest validation exits nonzero for invalid metadata
or mismatched local artifacts.

## Tests

```bash
python3 -m unittest discover -s verification/tests -v
```

Fixtures exercise every report category, source-specific layouts, multi-level
expansion, source sense suffixes, pinyin equivalence, ambiguity, and the rule
that dictionary definitions/enrichment never establish identity.

## Reviewing a discrepancy

1. Open both source locators and the authoritative document page/row.
2. Classify the difference as extraction error, verifier error, source-document
   peculiarity, or unresolved.
3. Correct only the authoritative extraction pipeline or its explicit correction
   ledger, with a documentary citation. Never copy the verifier value over.
4. Regenerate both report formats and retain the unresolved/review disposition
   in the authoritative pipeline's discrepancy ledger.

The University of Geneva 2015 artifact has no direct adapter because it is a
table-heavy, annotated PDF containing derived/implicit vocabulary. Feed output
from a separately reviewed PDF parser through `canonical-jsonl`; do not pretend
its rows are structurally identical to the CTI 2015 workbook.
