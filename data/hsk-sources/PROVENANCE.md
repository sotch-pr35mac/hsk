# Runtime data provenance

The checked-in CSV files are reviewed exports from the authoritative documents
listed below. The extraction observations, profiles, correction ledger, source
locks, validation reports, and regeneration code now live in the separate
[`hsk_tooling`](../../hsk_tooling/) repository.

| Runtime input | Authority and document | Extraction | Rows | SHA-256 |
| --- | --- | --- | ---: | --- |
| `canonical/hsk2015.csv` | Chinese Testing International, HSK 2015 workbook | deterministic ZIP/XML workbook reader | 5,000 | `0ed70735d9ae28bbf3473c6c61ecc377f8dd0574b095a70f706d7646e570c361` |
| `canonical/proficiency2021.csv` | MOE/State Language Commission, GF0025-2021 | native extraction assessment, then scoped RapidOCR on vocabulary pages | 11,092 | `183b4e72672344ee4dcedc9df1ed10b381b3a75a080410640c1715f6a80f18e1` |
| `canonical/hsk_exam2025.csv` | Chinese Testing International, HSK syllabus published 2025-11 | native PyMuPDF table extraction | 11,000 source rows | `2325a24beef63a525661554ae36bdc7c7ed4a5123958c9d1bdedde75e4f5932e` |
| `enrichment/hsk2015-unige.csv` | reviewed same-edition HSK 2015 enrichment | reviewed external transcription, pinyin/traditional only | 4,796 | `6ee365f2d16b4ff6987aaf852bf5af0b148af613de4411b53ec7a612612c3b95` |

Authoritative URLs: CTI HSK 2015 (`https://admin.chinesetest.cn/userfiles/file/HSK/HSK-2015.xlsx`), MOE GF0025-2021 (`https://www.moe.gov.cn/jyb_xwfb/gzdt_gzdt/s5987/202103/W020210329527301787356.pdf`), and CTI HSK syllabus 2025 (`https://hsk.cn-bj.ufileos.com/3.0/%E6%96%B0%E7%89%88HSK%E8%80%83%E8%AF%95%E5%A4%A7%E7%BA%B21219.pdf`).

The 2015 enrichment covers 4,796 rows; the remaining 204 are intentionally
orthography-only. GF0025 strict pinyin is limited to reviewed authoritative
matches and corrections. Counts, document hashes, extraction versions, page
locators, and review decisions are maintained by `hsk_tooling`.
