use std::hint::black_box;

use criterion::{BenchmarkId, Criterion, criterion_group, criterion_main};
use hsk::{HskCatalog, HskLevel, HskSystem, LevelScope, Orthography};

fn lookup_benchmarks(c: &mut Criterion) {
    let catalog = HskCatalog::new();
    let mut group = c.benchmark_group("lookup");

    group.bench_function("strict_canonical_hit", |b| {
        b.iter(|| {
            catalog.lookup(
                black_box(HskSystem::Hsk2015),
                black_box(Orthography::Simplified("爱")),
                black_box("ài"),
            )
        });
    });
    group.bench_function("strict_normalization_heavy_hit", |b| {
        b.iter(|| {
            catalog.lookup(
                black_box(HskSystem::Hsk2015),
                black_box(Orthography::Traditional("愛")),
                black_box("  AI4  "),
            )
        });
    });
    group.bench_function("strict_miss", |b| {
        b.iter(|| {
            catalog.lookup(
                black_box(HskSystem::Hsk2015),
                black_box(Orthography::Simplified("𠮷野家")),
                black_box("ji2ye3jia1"),
            )
        });
    });
    group.bench_function("orthography_ambiguous", |b| {
        b.iter(|| {
            catalog.lookup_orthography(
                black_box(HskSystem::ProficiencyStandard2021),
                black_box(Orthography::Simplified("长")),
            )
        });
    });
    group.bench_function("all_systems_normalizes_once", |b| {
        b.iter(|| catalog.lookup_all(black_box(Orthography::Simplified("爱")), black_box("AI4")));
    });
    group.finish();
}

fn enumeration_benchmarks(c: &mut Criterion) {
    let catalog = HskCatalog::new();
    let mut group = c.benchmark_group("enumeration");

    for scope in [LevelScope::Exact, LevelScope::Cumulative] {
        group.bench_with_input(
            BenchmarkId::new("hsk_2015_level_six", format!("{scope:?}")),
            &scope,
            |b, &scope| {
                b.iter(|| {
                    catalog.words(
                        black_box(HskSystem::Hsk2015),
                        black_box(HskLevel::Six),
                        black_box(scope),
                    )
                });
            },
        );
    }
    group.finish();
}

criterion_group!(benches, lookup_benchmarks, enumeration_benchmarks);
criterion_main!(benches);
