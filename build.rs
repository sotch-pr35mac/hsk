#[allow(dead_code)]
#[path = "src/normalize_shared.rs"]
mod normalize_shared;

use std::collections::HashMap;
use std::env;
use std::fmt::Write as _;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Clone)]
struct Row {
    system: &'static str,
    level: usize,
    evidence: &'static str,
    simplified: String,
    headword_raw: String,
    traditional: String,
    pinyin: String,
    normalized_pinyin: String,
    part_of_speech: String,
    sense_label: String,
    source_sequence: usize,
    source_locator: String,
}

fn read_rows(path: &Path) -> Vec<Vec<String>> {
    let text =
        fs::read_to_string(path).unwrap_or_else(|error| panic!("{}: {error}", path.display()));
    text.lines()
        .skip(1)
        .filter(|line| !line.is_empty())
        .map(|line| {
            assert!(
                !line.contains('"'),
                "quoted CSV is not supported: {}",
                path.display()
            );
            line.split(',').map(str::to_owned).collect()
        })
        .collect()
}

fn level_index(value: &str) -> usize {
    match value {
        "1" => 0,
        "2" => 1,
        "3" => 2,
        "4" => 3,
        "5" => 4,
        "6" => 5,
        "7-9" => 6,
        _ => panic!("unexpected level {value:?}"),
    }
}

fn normalized_readings(raw: &str) -> String {
    if raw.is_empty() {
        return String::new();
    }
    let raw = raw.replace('（', "(").replace('）', ")");
    raw.split(['/', '∣'])
        .flat_map(|reading| {
            if let Some((prefix, remainder)) = reading.split_once('(') {
                let (inside, suffix) = remainder
                    .split_once(')')
                    .unwrap_or_else(|| panic!("unclosed pinyin parenthesis in {reading:?}"));
                if suffix.trim().is_empty() {
                    vec![prefix.trim().to_owned()]
                } else {
                    vec![
                        format!("{prefix}{suffix}"),
                        format!("{prefix}{inside}{suffix}"),
                    ]
                }
            } else {
                vec![reading.to_owned()]
            }
        })
        .map(|reading| {
            normalize_shared::normalize_pinyin(&reading)
                .unwrap_or_else(|error| panic!("invalid generated pinyin {reading:?}: {error}"))
        })
        .collect::<Vec<_>>()
        .join("|")
}

fn load_enrichment(path: &Path) -> HashMap<usize, (String, String)> {
    read_rows(path)
        .into_iter()
        .map(|fields| {
            assert_eq!(fields.len(), 6, "unexpected enrichment schema");
            (
                fields[0].parse().expect("numeric enrichment sequence"),
                (fields[3].clone(), fields[4].clone()),
            )
        })
        .collect()
}

fn load_dataset(
    path: &Path,
    system: &'static str,
    enrichment: Option<&HashMap<usize, (String, String)>>,
) -> Vec<Row> {
    let mut rows = Vec::new();
    for fields in read_rows(path) {
        assert_eq!(
            fields.len(),
            14,
            "unexpected canonical schema in {}",
            path.display()
        );
        let source_sequence = fields[2].parse().expect("numeric source sequence");
        let (traditional, mut pinyin) = enrichment
            .and_then(|values| values.get(&source_sequence).cloned())
            .unwrap_or_else(|| (fields[7].clone(), fields[10].clone()));
        if fields[0] == "proficiency2021"
            && fields[12] != "rapidocr-authoritative-row"
            && fields[13].is_empty()
        {
            // Preserve unresolved candidate pinyin in the review CSV/report,
            // but never promote it to strict runtime lexical identity.
            pinyin.clear();
        }
        let levels = std::iter::once(fields[3].as_str()).chain(
            fields[5]
                .split(';')
                .filter(|additional| !additional.is_empty()),
        );
        for level in levels {
            let evidence = if !fields[13].is_empty() {
                "AuthoritativeCorrection"
            } else {
                match fields[12].as_str() {
                    "rapidocr-authoritative-headword-pinyin-unresolved" => {
                        "AuthoritativeOrthographyOnly"
                    }
                    "verification-candidate-unresolved" => "VerificationCandidateUnresolved",
                    _ => "AuthoritativeSource",
                }
            };
            rows.push(Row {
                system,
                level: level_index(level),
                evidence,
                simplified: fields[6].clone(),
                headword_raw: fields[8].clone(),
                traditional: traditional.clone(),
                normalized_pinyin: normalized_readings(&pinyin),
                pinyin: pinyin.clone(),
                part_of_speech: fields[11].clone(),
                sense_label: fields[9].clone(),
                source_sequence,
                source_locator: fields[1].clone(),
            });
        }
    }
    rows.sort_by_key(|row| (row.level, row.source_sequence));
    rows
}

fn rust_string(value: &str) -> String {
    format!("{value:?}")
}

fn aliases(row: &Row, traditional: bool) -> Vec<String> {
    let value = if traditional {
        &row.traditional
    } else {
        &row.simplified
    };
    let mut aliases = Vec::new();
    let alias_source = if traditional {
        value
    } else {
        &row.headword_raw
    };
    for component in value
        .split(['∣', '|', '、'])
        .chain(alias_source.split(['∣', '|']))
    {
        let component = component.trim();
        let component = component.trim_end_matches(|character: char| character.is_ascii_digit());
        if let Some((base, remainder)) = component.split_once('（') {
            let (inside, suffix) = remainder.split_once('）').unwrap_or((remainder, ""));
            if !base.is_empty() {
                aliases.push(format!("{base}{suffix}"));
            }
            if traditional || !suffix.is_empty() {
                aliases.push(format!("{base}{inside}{suffix}"));
            }
        } else if !component.is_empty() {
            aliases.push(component.to_owned());
        }
    }
    aliases.sort();
    aliases.dedup();
    aliases
}

fn emit_dataset(output: &mut String, name: &str, rows: &[Row], level_count: usize) {
    writeln!(output, "pub(crate) static {name}: &[Classification] = &[").unwrap();
    for row in rows {
        writeln!(
            output,
            "    Classification::from_static(HskSystem::{}, HskLevel::{}, EvidenceStatus::{}, {}, {}, {}, {}, {}, {}, {}, {}),",
            row.system,
            ["One", "Two", "Three", "Four", "Five", "Six", "SevenToNine"][row.level],
            row.evidence,
            rust_string(&row.simplified),
            rust_string(&row.traditional),
            rust_string(&row.pinyin),
            rust_string(&row.normalized_pinyin),
            rust_string(&row.part_of_speech),
            rust_string(&row.sense_label),
            row.source_sequence,
            rust_string(&row.source_locator),
        )
        .unwrap();
    }
    writeln!(output, "];\n").unwrap();

    let mut offsets = vec![0usize];
    for level in 0..level_count {
        offsets.push(offsets[level] + rows.iter().filter(|row| row.level == level).count());
    }
    writeln!(
        output,
        "pub(crate) const {name}_OFFSETS: &[usize] = &{:?};",
        offsets
    )
    .unwrap();

    for (suffix, traditional) in [("SIMPLIFIED", false), ("TRADITIONAL", true)] {
        let mut indices: Vec<(String, usize)> = rows
            .iter()
            .enumerate()
            .flat_map(|(index, row)| {
                aliases(row, traditional)
                    .into_iter()
                    .map(move |key| (key, index))
            })
            .collect();
        indices.sort_by(|(left_key, left), (right_key, right)| {
            left_key
                .cmp(right_key)
                .then_with(|| {
                    rows[*left]
                        .normalized_pinyin
                        .cmp(&rows[*right].normalized_pinyin)
                })
                .then_with(|| {
                    rows[*left]
                        .source_sequence
                        .cmp(&rows[*right].source_sequence)
                })
                .then_with(|| rows[*left].level.cmp(&rows[*right].level))
        });
        indices.dedup();
        writeln!(
            output,
            "pub(crate) static {name}_{suffix}_INDEX: &[(&str, usize)] = &["
        )
        .unwrap();
        for (key, index) in indices {
            writeln!(output, "    ({}, {index}),", rust_string(&key)).unwrap();
        }
        writeln!(output, "];\n").unwrap();
    }
}

fn main() {
    let root = PathBuf::from(env::var_os("CARGO_MANIFEST_DIR").expect("manifest directory"));
    let data = root.join("data/hsk-sources");
    let inputs = [
        data.join("canonical/hsk2015.csv"),
        data.join("canonical/proficiency2021.csv"),
        data.join("canonical/hsk_exam2025.csv"),
        data.join("enrichment/hsk2015-unige.csv"),
    ];
    for input in &inputs {
        println!("cargo:rerun-if-changed={}", input.display());
    }
    println!("cargo:rerun-if-changed=src/normalize_shared.rs");

    let enrichment = load_enrichment(&inputs[3]);
    let hsk2015 = load_dataset(&inputs[0], "Hsk2015", Some(&enrichment));
    let proficiency2021 = load_dataset(&inputs[1], "ProficiencyStandard2021", None);
    let exam2025 = load_dataset(&inputs[2], "HskExamSyllabus2025", None);

    assert_eq!(hsk2015.len(), 5_000);
    assert_eq!(proficiency2021.len(), 11_092);
    assert_eq!(exam2025.len(), 11_105);

    let mut generated = String::from("// @generated by build.rs; do not edit.\n\n");
    emit_dataset(&mut generated, "HSK2015", &hsk2015, 6);
    emit_dataset(&mut generated, "PROFICIENCY2021", &proficiency2021, 7);
    emit_dataset(&mut generated, "EXAM2025", &exam2025, 7);
    let destination =
        PathBuf::from(env::var_os("OUT_DIR").expect("output directory")).join("hsk_generated.rs");
    fs::write(destination, generated).expect("write generated Rust data");
}
