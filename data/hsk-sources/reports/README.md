# Generated reports

These deterministic reports identify authoritative raw/canonical hashes and
pinned verification revisions. A report can recommend review; it never rewrites
canonical data automatically.

| Dataset | Independent source | Result |
|---|---|---|
| HSK 2.0 / 2015 | University of Geneva same-edition transcription | 4,796 official rows received lexical enrichment; 204 remain explicitly unresolved in `../enrichment/hsk2015-unige.report.json` |
| GF0025-2021 | `shawkynasr/HSK-official-Query-System` at `11694d5…` | 9,905 exact lexical matches; 1,185 one-to-one headword-only candidates; verifier differences for `称 chēng` and `会 huìlǜ` remain visible |
| Current HSK exam syllabus | `Punpuf/hsk-syllabus-vocabulary-parser` at `2adf7c9…` | 11,105/11,105 expanded assignments match |

The JSON reports contain all matching records and every required discrepancy
category. Their Markdown counterparts are review-oriented renderings. The
GF0025 native-extraction assessment separately explains why OCR was justified
and restricted to pages 42-175.
