//! Identical opt-in module for baseline/candidate; not production source.
use super::*;
use std::fs;
use std::time::Instant;

fn process_memory() -> serde_json::Value {
    match fs::read_to_string("/proc/self/status") {
        Ok(status) => {
            let bytes = |name: &str| -> Option<u64> {
                let line = status.lines().find(|line| line.starts_with(name))?;
                let mut fields = line.split_whitespace().skip(1);
                let value = fields.next()?.parse::<u64>().ok()?;
                if fields.next()? != "kB" || fields.next().is_some() {
                    return None;
                }
                value.checked_mul(1024)
            };
            serde_json::json!({"source":"/proc/self/status", "rssBytes":bytes("VmRSS:"), "highWaterBytes":bytes("VmHWM:")})
        }
        Err(error) => {
            serde_json::json!({"source":"unavailable", "reason":error.to_string(), "rssBytes":null, "highWaterBytes":null})
        }
    }
}

fn assert_original_oracle(core: &WritableCas) {
    let inner = core.lock().unwrap();
    for (inode, node) in &inner.nodes {
        let expected = if node.links.is_empty() {
            0
        } else if matches!(node.entry.kind, EntryKind::Directory) {
            2 + inner
                .nodes
                .iter()
                .filter(|(i, n)| {
                    **i != ROOT_INODE
                        && u64::from(n.parent) == *inode
                        && !n.links.is_empty()
                        && matches!(n.entry.kind, EntryKind::Directory)
                })
                .count() as u32
        } else {
            node.links.len() as u32
        };
        assert_eq!(inner.attr(*inode).unwrap().nlink, expected);
    }
}

#[test]
#[ignore = "ordinary directory attribute microbenchmark; fresh output directory required"]
fn ordinary_directory_attribute_pressure() {
    let initial_memory = process_memory();
    let unrelated: usize = std::env::var("SPRIG_DIRECTORY_UNRELATED")
        .unwrap()
        .parse()
        .unwrap();
    assert!(unrelated <= 16384);
    let retired: usize = std::env::var("SPRIG_DIRECTORY_RETIRED")
        .unwrap()
        .parse()
        .unwrap();
    assert!([0, 128, 2048].contains(&retired));
    let wide_children: usize = std::env::var("SPRIG_DIRECTORY_WIDE")
        .unwrap_or_else(|_| "64".into())
        .parse()
        .unwrap();
    let hot_entries: usize = std::env::var("SPRIG_DIRECTORY_HOT_ENTRIES")
        .unwrap_or_else(|_| "1".into())
        .parse()
        .unwrap();
    assert!(wide_children <= 64 && hot_entries <= 65);
    let layout = std::env::var("SPRIG_DIRECTORY_LAYOUT").unwrap_or_else(|_| "nested".into());
    assert!(
        ["nested", "flat-root", "hardlinks-root", "hardlinks-nested"].contains(&layout.as_str())
    );
    let root = PathBuf::from(std::env::var_os("SPRIG_DIRECTORY_OUTPUT").unwrap());
    assert!(root.is_absolute());
    fs::create_dir(&root).unwrap();
    let root = fs::canonicalize(root).unwrap();
    let objects = root.join("objects");
    let generation = root.join("generation");
    fs::create_dir(&objects).unwrap();
    fs::create_dir(&generation).unwrap();
    let entry = |path: &str, kind| Entry {
        id: format!("id:{path}"),
        link_group: None,
        mode: 0o755,
        modified_ns: 1,
        kind,
    };
    let mut base = Manifest::new();
    for path in ["", "hot", "wide", "unrelated"] {
        base.insert(path.into(), entry(path, EntryKind::Directory));
    }
    for i in 0..hot_entries {
        let path = if i == 0 {
            "hot/child".to_owned()
        } else {
            format!("hot/item-{i:03}")
        };
        let kind = if i == 0 {
            EntryKind::Directory
        } else {
            EntryKind::File {
                size: 0,
                chunks: vec![],
            }
        };
        base.insert(path.clone(), entry(&path, kind));
    }
    for i in 0..wide_children {
        let path = format!("wide/d{i:03}");
        base.insert(path.clone(), entry(&path, EntryKind::Directory));
        let path = format!("{path}/nested");
        base.insert(path.clone(), entry(&path, EntryKind::Directory));
    }
    for i in 0..unrelated {
        let path = if layout == "nested" || layout == "hardlinks-nested" {
            format!("unrelated/f{i:05}")
        } else {
            format!("f{i:05}")
        };
        let mut value = entry(
            &path,
            EntryKind::File {
                size: 0,
                chunks: vec![],
            },
        );
        if layout.starts_with("hardlinks-") {
            value.link_group = Some("shared-file-group".into());
        }
        base.insert(path, value);
    }
    let fixture_hash = blake3::hash(&serde_json::to_vec(&base).unwrap())
        .to_hex()
        .to_string();
    let core =
        WritableCas::create(&objects, &generation, &base, "directory-r", "directory-g").unwrap();
    let initialized_memory = process_memory();
    for i in 0..retired {
        let name = format!("retired-{i:03}");
        core.mkdir(ROOT_INODE, &name, 0o755).unwrap();
        core.rmdir(ROOT_INODE, &name).unwrap();
    }
    core.sync().unwrap();
    let unique_nodes = core.lock().unwrap().nodes.len();
    let live_nodes = core
        .lock()
        .unwrap()
        .nodes
        .values()
        .filter(|node| !node.links.is_empty())
        .count();
    let hot = core.lookup_path("hot").unwrap().inode;
    let wide = core.lookup_path("wide").unwrap().inode;
    let flat = core.lookup_path("unrelated").unwrap().inode;
    let cases = [
        ("root", ROOT_INODE, 5),
        ("hot", hot, if hot_entries == 0 { 2 } else { 3 }),
        ("wide", wide, 2 + wide_children as u32),
        ("flat", flat, 2),
    ];
    let mut rows = Vec::new();
    // Both variants check the unchanged original scan before any timers.
    assert_original_oracle(&core);
    let ready_memory = process_memory();
    for (case, inode, links) in cases {
        for _ in 0..100 {
            assert_eq!(core.getattr(inode).unwrap().nlink, links);
        }
        let mut batches = Vec::new();
        for _ in 0..32 {
            let mut observed = 0_u64;
            let start = Instant::now();
            for _ in 0..100 {
                let value =
                    std::hint::black_box(core.getattr(std::hint::black_box(inode)).unwrap());
                observed += u64::from(value.nlink);
            }
            batches.push(start.elapsed().as_nanos() as u64);
            assert_eq!(observed, u64::from(links) * 100);
        }
        rows.push(serde_json::json!({"case":case,"callsPerBatch":100,"batchesNanoseconds":batches,"expectedNlink":links}));
    }
    let timed_memory = process_memory();
    assert_original_oracle(&core);
    let snapshot = core.snapshot().unwrap();
    assert_eq!(
        snapshot.keys().collect::<Vec<_>>(),
        base.keys().collect::<Vec<_>>()
    );
    drop(core);
    let replayed =
        WritableCas::open(&objects, &generation, &base, "directory-r", "directory-g").unwrap();
    assert_original_oracle(&replayed);
    assert_eq!(replayed.snapshot().unwrap(), snapshot);
    drop(replayed);
    let report = serde_json::json!({"schema":"sprig-directory-attr-core-v3","fixtureHash":fixture_hash,
        "unrelatedFiles":unrelated,"retiredDirectories":retired,"layout":layout,
        "wideSubdirectories":wide_children,"hotSubtreeEntries":hot_entries,"uniqueNodes":unique_nodes,"liveNodes":live_nodes,
        "nodeSizeBytes":std::mem::size_of::<Node>(),"nodeAlignmentBytes":std::mem::align_of::<Node>(),
        "nodeValueBytes":unique_nodes * std::mem::size_of::<Node>(),
        "memory":{"initial":initial_memory,"initialized":initialized_memory,"ready":ready_memory,"afterTimedCalls":timed_memory},
        "cases":rows,"oraclePassed":true,"oracleBeforeTiming":true,
        "caveat":"Single-process warm core attr calls, not mounted/task tails. Setup, sync, oracle, RSS readout and post-batch assertions excluded. Timed calls include lock, attr cloning, black_box and checksum addition. Node value bytes exclude BTreeMap allocations and heap data; RSS/HWM include allocator/base/engine/process state, not isolated cache overhead."});
    fs::write(
        root.join("report.json"),
        serde_json::to_vec_pretty(&report).unwrap(),
    )
    .unwrap();
    println!("{}", report);
}
