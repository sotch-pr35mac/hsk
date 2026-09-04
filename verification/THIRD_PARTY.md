# Verification-source notices

No third-party dataset is included in this repository. The links and checksums
below identify optional diagnostic inputs; [`sources.json`](sources.json) is the
machine-readable source of truth for exact revisions and artifact hashes.

| Source | Claimed edition | License / redistribution | Derivation and independence |
|---|---|---|---|
| University of Geneva HSK vocabulary transcription | Hanban 2015 examination syllabus | No explicit reuse license located; reference/download only unless permission is established | Separately maintained university transcription of the same edition, with annotations and implicit/recomposed vocabulary; not row-equivalent by assumption |
| `shawkynasr/HSK-official-Query-System` | GF0025-2021 | MIT | Separately maintained export of the former official query system; its README documents typo corrections, so every difference still requires MOE-document review |
| `krmanik/HSK-3.0`, 2021 list | GF0025-2021 | CC BY-SA 4.0 for the HSK word lists | Independent OCR of the MOE PDF; 11,091 headword-only rows, including a known one-row shortfall |
| `zispace/hanyu-hsk`, GF0025 list | GF0025-2021 | No explicit license located; reference only | Level-ordered transcription citing the MOE PDF and shawkynasr; used only to propose OCR row boundaries, never to mark a row authoritative |
| `Punpuf/hsk-syllabus-vocabulary-parser` | 2025-11 syllabus, effective 2026-07 | MIT | Independent programmatic extraction of the CTI PDF; CC-CEDICT enrichment is explicitly excluded from comparison identity |
| `profesorm/hsk30` | 2025-11 syllabus / “2026” exam dataset | CC BY 4.0 | Described as an official-provider API export; independent of PDF parsing but the repository does not pin a per-row API retrieval URL/time |
| `krmanik/HSK-3.0`, 2025 list | 2025-11 examination syllabus | CC BY-SA 4.0 for the HSK word lists | Separately maintained same-document transcription; exact extraction method is undocumented and pinyin is absent |

Licenses apply to the upstream works, not to the authoritative government/CTI
documents themselves. Consult upstream license files and applicable law before
redistributing any downloaded artifact. The verifier reports source identifiers
and record locators but omits arbitrary raw/enrichment fields from serialized
report records.
