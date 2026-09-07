use std::hint::black_box;

use criterion::{Criterion, criterion_group, criterion_main};
use hsk::{HskQuery, HskSystem, levels, levels_all};

fn lookup_benchmarks(c: &mut Criterion) {
    let mut group = c.benchmark_group("lookup");
    group.bench_function("word_hit", |b| {
        b.iter(|| {
            levels(
                black_box(HskSystem::Hsk2015),
                HskQuery::new(black_box("爱")),
            )
        });
    });
    group.bench_function("pinyin_hit", |b| {
        b.iter(|| {
            levels(
                HskSystem::ProficiencyStandard2021,
                HskQuery::new(black_box("长")).pinyin(black_box("zhang3")),
            )
        });
    });
    group.bench_function("normalization_heavy_hit", |b| {
        b.iter(|| {
            levels(
                HskSystem::ProficiencyStandard2021,
                HskQuery::new(black_box("爱")).pinyin(black_box("  AI4  ")),
            )
        });
    });
    group.bench_function("miss", |b| {
        b.iter(|| levels(HskSystem::Hsk2015, HskQuery::new(black_box("𠮷野家"))));
    });
    group.bench_function("multiple_levels", |b| {
        b.iter(|| {
            levels(
                HskSystem::HskExamSyllabus2025,
                HskQuery::new(black_box("一下")),
            )
        });
    });
    group.bench_function("all_systems", |b| {
        b.iter(|| levels_all(HskQuery::new(black_box("出租车"))));
    });
    group.finish();
}

criterion_group!(benches, lookup_benchmarks);
criterion_main!(benches);
