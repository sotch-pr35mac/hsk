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

[`sources.lock.json`](sources.lock.json) records the retrieved byte sizes and
SHA-256 fingerprints. The official hosts timed out from the extraction
environment on 2026-09-04, so exact official-path copies were recovered through
transport mirrors. The current-exam PDF was byte-identical across two
independent mirrors. All three locks remain explicitly
`pending-official-byte-comparison`; a release maintainer should compare them to
fresh bytes from each `document_url` when CTI/MOE connectivity permits. This
transport caveat does not make any mirror a classification authority.

## Reproduction sequence

Use Python 3.9 or newer. PDF assessment additionally needs Poppler's
`pdftotext`; the isolated GF0025 fallback uses the versions pinned in
[`tools/requirements-ocr.lock`](../../tools/requirements-ocr.lock). Keep
official binaries in the ignored `artifacts` directory.

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

Inspect every workbook sheet or PDF vocabulary page and record the page ranges
and anchored row layouts. Commit the lock, raw observations, extraction
metadata, canonical CSV, validation reports, reviewed profiles, and correction
ledger together. The large authoritative binaries themselves are not committed.

The normal native-extraction/canonicalization path is performed one source at a
time:

```bash
python3 tools/hsk_data.py canonicalize \
  --source hsk2015 \
  --raw data/hsk-sources/raw/hsk2015.jsonl \
  --profile data/hsk-sources/profiles/hsk2015.json \
  --output data/hsk-sources/canonical/hsk2015.csv \
  --report data/hsk-sources/reports/hsk2015.validation.json
```

After all outputs have been reviewed, regenerate in temporary storage and
compare exact bytes. The checked-in outputs are deterministic for the locked
artifacts:

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

## Per-source extraction

The 2015 XLSX reader uses only ZIP/XML primitives and preserves workbook sheet
and row locations. It produces exactly 5,000 official level/headword rows. The
workbook has no pinyin or traditional column. A separately identified
University of Geneva 2015-syllabus transcription enriches 4,796 rows; 204 are
left without lexical enrichment rather than guessed. Its report excludes
definitions and implicit/recombined sections.

The current HSK examination PDF has usable embedded text. PyMuPDF 1.26.4
extracts its vocabulary tables from PDF pages 80-354 into 11,000 numbered rows.
Rows printed with additional level labels expand deterministically to 11,105
classification assignments. No OCR is used for this document.

Native extraction was attempted first for GF0025-2021. Both `pdftotext -layout`
and PyMuPDF expose only the four-character access watermark `仅供查阅`: 12 Han
characters across the 260-page scan. The recorded assessment therefore permits
OCR only for vocabulary appendix pages 42-175. The committed positioned OCR
observations use a scale of 3.0, PyMuPDF 1.26.4, RapidOCR 1.4.4, and ONNX Runtime
1.19.2; each page range has its own SHA-256-bound metadata file.

Reproduce the isolated OCR in page ranges to keep memory bounded:

```bash
python3 tools/ocr_gf0025.py data/hsk-sources/artifacts/gf0025-2021.pdf \
  /tmp/gf-42-75.jsonl --first-page 42 --last-page 75 --scale 3
# Repeat for 76-109, 110-142, and 143-175.
python3 tools/canonicalize_gf0025.py \
  '/path/to/hanyu-hsk/data/GF 0025-2021/国际中文教育中文水平等级标准-词汇表.txt' \
  data/hsk-sources/canonical/proficiency2021.csv \
  data/hsk-sources/raw/proficiency2021-ocr/gf-ocr-*.jsonl \
  --corrections data/hsk-sources/corrections.json
```

The level-ordered candidate is the file named in the validation report, pinned
to `zispace/hanyu-hsk` commit
`ca0a5662a95ecc8522983d24bfbef5ab5b8cda0a` and SHA-256
`d34106d7b96a0c143db248c9fdf838076d33a5a92102139c8c6e612bb09f052f`.
It supplies candidate cell boundaries only. Of 11,092 rows, 9,905 have a unique
authoritative sequence/headword/pinyin OCR match. Another 986 have a unique
authoritative headword row but unreadable OCR pinyin, and 201 remain
candidate-only. The latter two groups retain distinct unresolved statuses and
their full OCR candidates in the validation report. They are not misrepresented
as fully OCR-verified. Independent data never overrides a row.

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

Verification tools consume canonical CSV without feeding changes back into it.
The current syllabus agrees with the pinned Punpuf transcription on all 11,105
assignments. The conservative GF0025 report finds 9,905 exact lexical matches,
1,185 one-to-one headword-only review candidates, one pinyin disagreement
(`称 chēng` in the verifier versus document `称 chèn`), and an apparent verifier
headword typo (`会 huìlǜ` where the OCR row visibly reads `汇率`). Candidate
pinyin is withheld from strict runtime identity. Separately, two errors in the
level-ordered candidate (`倒 dào` and
verbal `长 zhǎng`) were resolved from PDF pages 49 and 57 and recorded in
[`corrections.json`](corrections.json). See
[`reports/README.md`](reports/README.md).

## Tests

The tests create a tiny XLSX from XML and exercise rich/shared strings, source
locators, PDF page splitting, fingerprints and drift, parser profiles,
corrections, structural validation, and byte-stable serialization:

```bash
PYTHONPYCACHEPREFIX=/tmp/hsk-python-cache \
  python3 -m unittest discover -s tools -p 'test_hsk_data.py' -v
```
