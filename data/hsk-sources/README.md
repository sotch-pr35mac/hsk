# Authoritative HSK data pipeline

This directory describes how the library's three HSK/proficiency datasets are
derived. The authoritative CTI and Ministry documents are the only sources of
canonical classifications. Machine-readable projects may be compared against
the result, but they cannot modify it.

## Source status

| ID | Classification | Authority | Official artifact | Official row counts |
| --- | --- | --- | --- | --- |
| `hsk2015` | HSK 2.0 / 2015 examination vocabulary | Chinese Testing International | `hsk-2015.xlsx` | 150 / 150 / 300 / 600 / 1,300 / 2,500 = 5,000 |
| `proficiency2021` | GF0025-2021 proficiency standard | Ministry of Education and State Language Commission | `gf0025-2021.pdf` | 500 / 772 / 973 / 1,000 / 1,071 / 1,140 / 5,636 = 11,092 |
| `hsk_exam2025` | Current HSK 3.0 examination syllabus | Chinese Testing International | `hsk3-syllabus-1219.pdf` | 300 / 200 / 500 / 1,000 / 1,600 / 1,800 / 5,600 = 11,000 numbered rows |

The GF0025-2021 standard and the current HSK examination syllabus are related
but distinct datasets. They must not be merged. For the current syllabus,
repeated level/POS annotations can expand the 11,000 numbered rows into more
than 11,000 classification assignments. Those quantities remain separate.

The source hosts were unreachable from the build environment on 2026-09-04,
and no artifacts had been supplied under `/private/tmp`. Consequently, this
change does **not** claim a retrieval date, byte size, or checksum. Draft parser
profiles remain deliberately marked `reviewed: false`, and no canonical rows
are committed. This is a fail-closed state, not permission to use a mirror.

## Reproduction sequence

Use Python 3.9 or newer. PDF extraction additionally needs Poppler's
`pdftotext`. Keep official binaries in an ignored local directory.

```bash
python3 tools/hsk_data.py validate-config
python3 tools/hsk_data.py download --artifact-dir data/hsk-sources/artifacts
python3 tools/hsk_data.py lock \
  --artifact-dir data/hsk-sources/artifacts \
  --retrieval-date 2026-09-04 \
  --output data/hsk-sources/sources.lock.json
python3 tools/hsk_data.py verify-sources \
  --artifact-dir data/hsk-sources/artifacts \
  --lock data/hsk-sources/sources.lock.json
python3 tools/hsk_data.py extract \
  --artifact-dir data/hsk-sources/artifacts \
  --lock data/hsk-sources/sources.lock.json \
  --raw-dir data/hsk-sources/raw
```

Inspect every workbook sheet or PDF vocabulary page before changing a profile
to `reviewed: true`. Record the page ranges and exact anchored row layouts.
Commit `sources.lock.json`, the raw JSONL, extraction metadata, canonical CSV,
validation reports, reviewed profiles, and any correction ledger entries
together. Do not commit the artifacts.

Canonicalization is performed one source at a time:

```bash
python3 tools/hsk_data.py canonicalize \
  --source hsk2015 \
  --raw data/hsk-sources/raw/hsk2015.jsonl \
  --profile data/hsk-sources/profiles/hsk2015.json \
  --output data/hsk-sources/canonical/hsk2015.csv \
  --report data/hsk-sources/reports/hsk2015.validation.json
```

After all outputs have been reviewed, regenerate in temporary storage and
compare exact bytes:

```bash
python3 tools/hsk_data.py check \
  --artifact-dir data/hsk-sources/artifacts \
  --lock data/hsk-sources/sources.lock.json \
  --tracked-raw-dir data/hsk-sources/raw \
  --canonical-dir data/hsk-sources/canonical
```

The serializer fixes UTF-8, NFC, LF line endings, column order, source order,
and compact sorted-key JSONL. The lock binds source IDs, exact URLs, filenames,
byte sizes, retrieval dates, and SHA-256 hashes. Extraction metadata binds raw
outputs to input checksums and records the Python or `pdftotext` version.

## Native extraction and OCR

The XLSX reader uses only ZIP/XML primitives and preserves workbook sheet and
row locations. The PDF path invokes `pdftotext -layout -enc UTF-8`, retains
page/line locations, and rejects implausibly empty native extraction.

OCR is not automated here because its model and renderer must be pinned and its
scope decided from the actual source. If native extraction fails:

1. identify the minimum vocabulary pages that failed;
2. record renderer, resolution, OCR engine, language model, and versions;
3. append OCR lines in the same raw JSONL schema with `extraction_method` set to
   `ocr-page` and the authoritative page locator retained;
4. review every OCR-derived row, using independent data only as a diagnostic;
5. explain any canonical repair in `corrections.json`.

Never repeatedly OCR the entire document when native text is usable elsewhere.

## Corrections and validation

Raw extracted values are immutable evidence. Canonical corrections use
`replace_fields`, `exclude`, or `insert`; each entry requires a stable ID,
reason, source locator, and authoritative evidence. The JSON Schema documents
the allowed fields. Apparent typos in an official document remain authoritative
unless another authoritative passage resolves them.

Validation asserts official total and per-level counts, required fields, source
IDs, Han content, forbidden BOM/NUL/replacement characters, and duplicate
lexical rows. Duplicates are reported rather than silently removed because the
documents may intentionally distinguish readings, senses, or parts of speech.

Verification/discrepancy tools should consume canonical CSV and write reports
without feeding changes back into it. Required report categories are: common,
authoritative-only, verifier-only, pinyin disagreements, level/POS
disagreements, duplicate disagreements, and reviewed disposition.

## Tests

The tests create a tiny XLSX from XML and exercise rich/shared strings, source
locators, PDF page splitting, fingerprints and drift, parser profiles,
corrections, structural validation, and byte-stable serialization:

```bash
PYTHONPYCACHEPREFIX=/tmp/hsk-python-cache \
  python3 -m unittest discover -s tools -p 'test_hsk_data.py' -v
```
