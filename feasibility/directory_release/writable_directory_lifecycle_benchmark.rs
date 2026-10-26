//! Identical opt-in lifecycle instrumentation for both production revisions.
//! This module is not part of either production revision.
use super::*;
use std::fs;
use std::time::Instant;

const SAMPLES: usize = 8;
const BATCHES: usize = 12;
const CALLS_PER_BATCH: usize = 8;
const TOTAL_CALLS: usize = BATCHES * CALLS_PER_BATCH;
const REPLAY_ROUNDS: usize = 32;

fn original_nlink(inner: &Inner, inode: u64, node: &Node) -> u32 {
    if node.links.is_empty() {
        0
    } else if matches!(node.entry.kind, EntryKind::Directory) {
        2 + inner
            .nodes
            .iter()
            .filter(|(i, n)| {
                **i != ROOT_INODE
                    && u64::from(n.parent) == inode
                    && !n.links.is_empty()
                    && matches!(n.entry.kind, EntryKind::Directory)
            })
            .count() as u32
    } else {
        node.links.len() as u32
    }
}

fn check_original_oracle(core: &WritableCas) {
    let inner = core.lock().unwrap();
    for (inode, node) in &inner.nodes {
        let expected = original_nlink(&inner, *inode, node);
        assert_eq!(inner.attr(*inode).unwrap().nlink, expected, "inode {inode}");
        for path in node.links.keys() {
            assert_eq!(inner.paths.get(path), Some(inode), "path {path}");
        }
    }
    for (path, inode) in &inner.paths {
        assert!(inner.nodes[inode].links.contains_key(path), "path {path}");
    }
}

fn memory_readout() -> serde_json::Value {
    match fs::read_to_string("/proc/self/status") {
        Ok(status) => {
            let kib = |field: &str| {
                status.lines().find_map(|line| {
                    let value = line.strip_prefix(field)?;
                    let mut parts = value.split_whitespace();
                    let number = parts.next()?.parse::<u64>().ok()?;
                    (parts.next() == Some("kB") && parts.next().is_none()).then_some(number)
                })
            };
            let rss = kib("VmRSS:");
            let hwm = kib("VmHWM:");
            serde_json::json!({
                "source": "/proc/self/status",
                "available": rss.is_some() && hwm.is_some(),
                "vmRssKiB": rss,
                "vmHwmKiB": hwm,
            })
        }
        Err(error) => serde_json::json!({
            "source": "/proc/self/status",
            "available": false,
            "vmRssKiB": null,
            "vmHwmKiB": null,
            "unavailableReason": error.to_string(),
        }),
    }
}

fn state_readout(core: &WritableCas) -> serde_json::Value {
    let inner = core.lock().unwrap();
    assert!(
        inner.journal_bytes <= 1024 * 1024,
        "bounded fixture journal exceeded 1 MiB"
    );
    // Timestamps are intentionally omitted: real mutation APIs timestamp each
    // process independently. Identity, parent, kind, mode, links and tombstones
    // remain deterministic, and are checked across baseline/candidate reports.
    let topology: Vec<_> = inner
        .nodes
        .iter()
        .map(|(inode, node)| {
            (
                *inode,
                u64::from(node.parent),
                node.entry.id.clone(),
                node.entry.link_group.clone(),
                node.entry.mode,
                node.entry.kind.clone(),
                node.links.clone(),
            )
        })
        .collect();
    let fingerprint = blake3::hash(&serde_json::to_vec(&topology).unwrap())
        .to_hex()
        .to_string();
    let directories = inner
        .nodes
        .values()
        .filter(|node| matches!(node.entry.kind, EntryKind::Directory));
    let live_directories = directories
        .clone()
        .filter(|node| !node.links.is_empty())
        .count();
    let retired_directories = directories.filter(|node| node.links.is_empty()).count();
    serde_json::json!({
        "uniqueNodes": inner.nodes.len(),
        "namespacePaths": inner.paths.len(),
        "liveDirectoryNodes": live_directories,
        "retiredDirectoryNodes": retired_directories,
        "journalFrames": inner.next_sequence,
        "journalBytes": inner.journal_bytes,
        "topologyFingerprint": fingerprint,
        "inlineNodePayloadBytes": inner.nodes.len() * std::mem::size_of::<Node>(),
    })
}

fn entry(path: &str, kind: EntryKind) -> Entry {
    Entry {
        id: format!("lifecycle-id:{path}"),
        link_group: None,
        mode: 0o755,
        modified_ns: 1,
        kind,
    }
}

fn manifest(files: usize, directories: usize) -> Manifest {
    let mut base = Manifest::new();
    for path in ["", "left", "right", "padding"] {
        base.insert(path.into(), entry(path, EntryKind::Directory));
    }
    for index in 0..files {
        let path = format!("padding/file-{index:05}");
        base.insert(
            path.clone(),
            entry(
                &path,
                EntryKind::File {
                    size: 0,
                    chunks: vec![],
                },
            ),
        );
    }
    for index in 0..directories {
        let path = format!("padding/directory-{index:05}");
        base.insert(path.clone(), entry(&path, EntryKind::Directory));
    }
    content::validate_manifest(&base).unwrap();
    base
}

fn create_core(objects: &Path, directory: &Path, base: &Manifest, label: &str) -> WritableCas {
    fs::create_dir(directory).unwrap();
    WritableCas::create(objects, directory, base, "directory-lifecycle-r", label).unwrap()
}

fn retire_directories(core: &WritableCas, count: usize) {
    for index in 0..count {
        let name = format!("retired-{index:03}");
        core.mkdir(ROOT_INODE, &name, 0o755).unwrap();
        core.rmdir(ROOT_INODE, &name).unwrap();
    }
}

fn initialization_samples(root: &Path, objects: &Path, base: &Manifest) -> serde_json::Value {
    // There is no existing engine before create(). A separate equivalent
    // validated control engine is slow-oracle checked before any timed create.
    let seed_directory = root.join("create-oracle");
    let seed = create_core(objects, &seed_directory, base, "create-oracle");
    check_original_oracle(&seed);
    assert_eq!(seed.snapshot().unwrap(), *base);
    drop(seed);
    fs::remove_dir_all(&seed_directory).unwrap();
    let before = memory_readout();
    let mut durations = Vec::with_capacity(SAMPLES);
    let mut states = Vec::with_capacity(SAMPLES);
    let mut memory = Vec::with_capacity(SAMPLES);
    for sample in 0..SAMPLES {
        let label = format!("create-{sample:02}");
        let directory = root.join(&label);
        fs::create_dir(&directory).unwrap();
        let started = Instant::now();
        let core = std::hint::black_box(
            WritableCas::create(objects, &directory, base, "directory-lifecycle-r", &label)
                .unwrap(),
        );
        let elapsed = started.elapsed().as_nanos() as u64;
        durations.push(elapsed);
        memory.push(memory_readout());
        check_original_oracle(&core);
        states.push(state_readout(&core));
        drop(core);
        fs::remove_dir_all(&directory).unwrap();
    }
    serde_json::json!({
        "case": "create-initialization",
        "callsPerBatch": 1,
        "batchesNanoseconds": durations,
        "samples": SAMPLES,
        "stateAfterSamples": states,
        "memoryBeforeSamples": before,
        "memoryAfterSamples": memory,
        "oraclePassedBeforeTiming": true,
        "oraclePassedAfterEverySample": true,
        "ownedGenerationsRemovedAfterVerification": true,
        "scope": "One WritableCas::create per sample: validated base construction, lease creation/acquisition, Init frame append, journal and directory durability syncs included. Generation directory creation, oracle, RSS, drop and reports excluded. Warm process/filesystem-cache observations, not cold boot latency.",
    })
}

fn replay_samples(
    root: &Path,
    objects: &Path,
    base: &Manifest,
    retired: usize,
) -> serde_json::Value {
    let label = "replay-history";
    let directory = root.join(label);
    let seed = create_core(objects, &directory, base, label);
    retire_directories(&seed, retired);
    let left = seed.lookup_path("left").unwrap().inode;
    let right = seed.lookup_path("right").unwrap().inode;
    for index in 0..REPLAY_ROUNDS {
        let name = format!("replay-{index:03}");
        let inode = seed.mkdir(left, &name, 0o755).unwrap().inode;
        seed.mkdir(inode, "nested", 0o755).unwrap();
        seed.rename(left, &name, right, &name).unwrap();
        seed.rmdir(inode, "nested").unwrap();
        seed.rmdir(right, &name).unwrap();
    }
    seed.sync().unwrap();
    check_original_oracle(&seed);
    let expected = seed.snapshot().unwrap();
    let initial_state = state_readout(&seed);
    drop(seed);
    let before = memory_readout();
    let mut durations = Vec::with_capacity(SAMPLES);
    let mut memory = Vec::with_capacity(SAMPLES);
    for _ in 0..SAMPLES {
        let started = Instant::now();
        let replayed = std::hint::black_box(
            WritableCas::open(objects, &directory, base, "directory-lifecycle-r", label).unwrap(),
        );
        let elapsed = started.elapsed().as_nanos() as u64;
        durations.push(elapsed);
        memory.push(memory_readout());
        check_original_oracle(&replayed);
        assert_eq!(replayed.snapshot().unwrap(), expected);
        assert_eq!(state_readout(&replayed), initial_state);
        drop(replayed);
    }
    fs::remove_dir_all(&directory).unwrap();
    serde_json::json!({
        "case": "replay-history",
        "callsPerBatch": 1,
        "batchesNanoseconds": durations,
        "samples": SAMPLES,
        "setupRetiredDirectories": retired,
        "setupSubtreeRounds": REPLAY_ROUNDS,
        "setupMutationCalls": retired * 2 + REPLAY_ROUNDS * 5,
        "initialState": initial_state,
        "memoryBeforeSamples": before,
        "memoryAfterSamples": memory,
        "oraclePassedBeforeTiming": true,
        "oraclePassedAfterEverySample": true,
        "ownedGenerationsRemovedAfterVerification": true,
        "scope": "One WritableCas::open per sample: lease acquisition, base validation/construction, complete checksummed journal parsing/validation/apply and session inspection included. Journal setup/sync, snapshots, original oracle, RSS, drop and reports excluded. Same warmed immutable journal reopened in one process; not cold recovery latency.",
    })
}

fn mutation_samples(
    root: &Path,
    objects: &Path,
    base: &Manifest,
    retired: usize,
    case: &str,
) -> serde_json::Value {
    let directory = root.join(case);
    let core = create_core(objects, &directory, base, case);
    retire_directories(&core, retired);
    let left = core.lookup_path("left").unwrap().inode;
    let right = core.lookup_path("right").unwrap().inode;
    let names: Vec<_> = (0..TOTAL_CALLS)
        .map(|index| format!("item-{index:03}"))
        .collect();
    let destinations: Vec<_> = (0..TOTAL_CALLS)
        .map(|index| format!("renamed-{index:03}"))
        .collect();
    let mut setup_calls = retired * 2;
    let shared_file = if case == "file-hardlink" {
        let inode = core.create_file(left, "shared", 0o644).unwrap().inode;
        core.link(inode, left, "shared-setup-alias").unwrap();
        setup_calls += 2;
        Some(inode)
    } else {
        None
    };
    for name in &names {
        match case {
            "directory-remove"
            | "directory-rename-same-parent"
            | "directory-rename-cross-parent" => {
                core.mkdir(left, name, 0o755).unwrap();
                setup_calls += 1;
            }
            "directory-overwrite" => {
                core.mkdir(left, name, 0o755).unwrap();
                core.mkdir(right, name, 0o755).unwrap();
                setup_calls += 2;
            }
            "directory-subtree-rename" => {
                let tree = core.mkdir(left, name, 0o755).unwrap().inode;
                let child = core.mkdir(tree, "child", 0o755).unwrap().inode;
                core.mkdir(child, "deep", 0o755).unwrap();
                core.create_file(child, "file", 0o644).unwrap();
                setup_calls += 4;
            }
            "directory-create" | "file-create" | "file-hardlink" => {}
            _ => panic!("unknown lifecycle mutation case"),
        }
    }
    core.sync().unwrap();
    check_original_oracle(&core);
    let initial_state = state_readout(&core);
    let memory_before = memory_readout();
    let mut durations = Vec::with_capacity(BATCHES);
    let mut memory = Vec::with_capacity(BATCHES);
    for batch in 0..BATCHES {
        check_original_oracle(&core);
        let first = batch * CALLS_PER_BATCH;
        let end = first + CALLS_PER_BATCH;
        let started = Instant::now();
        for index in first..end {
            match case {
                "directory-create" => {
                    std::hint::black_box(core.mkdir(left, &names[index], 0o755).unwrap());
                }
                "directory-remove" => core.rmdir(left, &names[index]).unwrap(),
                "directory-rename-same-parent" => {
                    core.rename(left, &names[index], left, &destinations[index])
                        .unwrap();
                }
                "directory-rename-cross-parent"
                | "directory-overwrite"
                | "directory-subtree-rename" => {
                    core.rename(left, &names[index], right, &names[index])
                        .unwrap();
                }
                "file-create" => {
                    std::hint::black_box(core.create_file(left, &names[index], 0o644).unwrap());
                }
                "file-hardlink" => {
                    std::hint::black_box(
                        core.link(shared_file.unwrap(), right, &names[index])
                            .unwrap(),
                    );
                }
                _ => unreachable!(),
            }
        }
        let elapsed = started.elapsed().as_nanos() as u64;
        durations.push(elapsed);
        memory.push(memory_readout());
        check_original_oracle(&core);
    }
    // Durability work is deliberately outside buffered mutation timers.
    core.sync().unwrap();
    let final_state = state_readout(&core);
    let expected = core.snapshot().unwrap();
    drop(core);
    let replayed =
        WritableCas::open(objects, &directory, base, "directory-lifecycle-r", case).unwrap();
    check_original_oracle(&replayed);
    assert_eq!(replayed.snapshot().unwrap(), expected);
    assert_eq!(state_readout(&replayed), final_state);
    drop(replayed);
    fs::remove_dir_all(&directory).unwrap();
    serde_json::json!({
        "case": case,
        "callsPerBatch": CALLS_PER_BATCH,
        "batchesNanoseconds": durations,
        "batches": BATCHES,
        "totalTimedApiCalls": TOTAL_CALLS,
        "setupMutationCalls": setup_calls,
        "subtreeEntriesMovedPerCall": if case == "directory-subtree-rename" { 4 } else { 1 },
        "initialState": initial_state,
        "finalState": final_state,
        "memoryBeforeBatches": memory_before,
        "memoryAfterBatches": memory,
        "oraclePassedBeforeEveryBatch": true,
        "oraclePassedAfterEveryBatch": true,
        "replayVerifiedAfterTiming": true,
        "ownedGenerationsRemovedAfterVerification": true,
        "scope": "Buffered real WritableCas API calls in a warm process; operation validation, journal append, apply and each API's ordinary return-value construction included. Name allocation, fixture creation, sync, slow oracle, snapshots, replay validation and RSS readout excluded. Inode/tombstone arena evolves across the 12 batches; batches are correlated, not independent trials.",
    })
}

#[test]
#[ignore = "bounded lifecycle microbenchmark; fresh output directory required"]
fn ordinary_directory_lifecycle_pressure() {
    let profile = std::env::var("SPRIG_DIRECTORY_LIFECYCLE_PROFILE").unwrap();
    let (files, directories, retired) = match profile.as_str() {
        "tiny" => (0, 0, 0),
        "file-heavy" => (2048, 0, 0),
        "directory-heavy" => (0, 512, 0),
        "retired-history" => (128, 0, 128),
        _ => panic!("unsupported bounded lifecycle profile"),
    };
    let root = PathBuf::from(std::env::var_os("SPRIG_DIRECTORY_OUTPUT").unwrap());
    assert!(root.is_absolute());
    fs::create_dir(&root).unwrap();
    let root = fs::canonicalize(root).unwrap();
    let objects = root.join("objects");
    fs::create_dir(&objects).unwrap();
    let base = manifest(files, directories);
    let fixture_hash = blake3::hash(&serde_json::to_vec(&base).unwrap())
        .to_hex()
        .to_string();
    let memory_before = memory_readout();
    let mut rows = vec![
        initialization_samples(&root, &objects, &base),
        replay_samples(&root, &objects, &base, retired),
    ];
    for case in [
        "directory-create",
        "directory-remove",
        "directory-rename-same-parent",
        "directory-rename-cross-parent",
        "directory-overwrite",
        "directory-subtree-rename",
        "file-create",
        "file-hardlink",
    ] {
        rows.push(mutation_samples(&root, &objects, &base, retired, case));
    }
    let report = serde_json::json!({
        "schema": "sprig-directory-lifecycle-core-v1",
        "profile": profile,
        "fixtureHash": fixture_hash,
        "baseEntries": base.len(),
        "paddingFiles": files,
        "paddingDirectories": directories,
        "setupRetiredDirectories": retired,
        "nodeSizeBytes": std::mem::size_of::<Node>(),
        "nodeAlignmentBytes": std::mem::align_of::<Node>(),
        "memoryBeforeCases": memory_before,
        "memoryAfterCases": memory_readout(),
        "cases": rows,
        "oraclePassed": true,
        "successfulGenerationsRetained": 0,
        "maximumFixtureJournalBytes": 1024 * 1024,
        "maximumReportBytes": 1024 * 1024,
        "memoryCaveat": "Node size is actual inline Rust layout; inlineNodePayloadBytes excludes BTreeMap allocation overhead and separately allocated strings/vectors. VmRSS/VmHWM are process-wide KiB snapshots outside timers, include fixture/oracle/test-harness allocator effects, and are not isolated per-inode heap measurements. Missing proc status fields are reported explicitly, not zero-filled.",
        "caveat": "Bounded unmounted core lifecycle evidence, not mounted throughput or task latency. Each process uses all fixed cases in fixed order; alternate baseline/candidate process order and retain every negative control. Durability barriers are included only in the create-initialization API scope, not hidden inside buffered mutation timings.",
    });
    let report_bytes = serde_json::to_vec_pretty(&report).unwrap();
    assert!(
        report_bytes.len() <= 1024 * 1024,
        "bounded report exceeded 1 MiB"
    );
    fs::write(root.join("report.json"), report_bytes).unwrap();
    println!("{}", report);
}
