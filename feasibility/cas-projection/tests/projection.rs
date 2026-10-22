use std::ffi::{OsStr, OsString};
use std::fs::{self, File, FileTimes};
use std::os::unix::ffi::OsStringExt;
use std::os::unix::fs::{PermissionsExt, symlink};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{Duration, UNIX_EPOCH};

use fuser::FileType;
use sprig::content::{Entry, EntryKind, Manifest};
use sprig_cas_projection_prototype::projection::{MAX_READ_BYTES, Projection, ROOT_INODE};
use sprig_cas_projection_prototype::store::{self, ChunkCache, ObjectStore};

static NEXT: AtomicU64 = AtomicU64::new(0);

struct Fixture {
    path: PathBuf,
}
impl Fixture {
    fn new() -> Self {
        let path = Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("target/test-work")
            .join(format!(
                "{}-{}",
                std::process::id(),
                NEXT.fetch_add(1, Ordering::Relaxed)
            ));
        fs::create_dir_all(&path).expect("create test-owned fixture");
        Self { path }
    }
    fn source(&self) -> PathBuf {
        self.path.join("source")
    }
    fn library(&self) -> PathBuf {
        self.path.join("library")
    }
    fn load(&self) -> Projection {
        Projection::load(&self.library(), OsStr::new("manifest.json"), 1000, 1000)
            .expect("load projection")
    }
    fn import(&self) {
        store::import(&self.source(), &self.library()).expect("capture fixture");
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.path);
    }
}

fn data(length: usize) -> Vec<u8> {
    let mut state = 0x5a17_9b13_291d_u64;
    (0..length)
        .map(|_| {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            state as u8
        })
        .collect()
}

fn entry(id: &str, kind: EntryKind) -> Entry {
    Entry {
        id: id.into(),
        mode: 0o755,
        modified_ns: 0,
        kind,
    }
}

fn handbuilt(fixture: &Fixture, chunks: &[Vec<u8>]) -> Vec<String> {
    let root = fixture.library();
    fs::create_dir_all(root.join("objects")).expect("create objects");
    let hashes: Vec<String> = chunks
        .iter()
        .map(|bytes| {
            let hash = blake3::hash(bytes).to_hex().to_string();
            fs::write(root.join("objects").join(&hash), bytes).expect("write chunk");
            hash
        })
        .collect();
    let manifest = Manifest::from([
        (String::new(), entry("root", EntryKind::Directory)),
        (
            "file".into(),
            entry(
                "file",
                EntryKind::File {
                    size: chunks.iter().map(|bytes| bytes.len() as u64).sum(),
                    chunks: hashes.clone(),
                },
            ),
        ),
    ]);
    fs::write(
        root.join("manifest.json"),
        serde_json::to_vec(&manifest).expect("serialize manifest"),
    )
    .expect("write manifest");
    hashes
}

fn import_preserves_bytes_modes_times_symlink_and_stable_inode_layout() {
    let fixture = Fixture::new();
    fs::create_dir_all(fixture.source().join("nested/empty")).expect("create fixture directories");
    let bytes = data(3 * MAX_READ_BYTES + 137);
    fs::write(fixture.source().join("nested/file"), &bytes).expect("write fixture file");
    fs::write(fixture.source().join("zero"), []).expect("write empty file");
    fs::set_permissions(
        fixture.source().join("nested/file"),
        fs::Permissions::from_mode(0o751),
    )
    .expect("set fixture mode");
    let time = UNIX_EPOCH + Duration::new(1_700_000_000, 123_456_789);
    File::open(fixture.source().join("nested/file"))
        .expect("open fixture")
        .set_times(FileTimes::new().set_modified(time))
        .expect("set fixture mtime");
    let target = OsString::from_vec(b"nested/\xff-target".to_vec());
    symlink(&target, fixture.source().join("link")).expect("write byte symlink");
    fixture.import();
    let mut projection = fixture.load();
    let second = fixture.load();
    let nested = projection
        .lookup(ROOT_INODE, OsStr::new("nested"))
        .expect("lookup directory");
    let file = projection
        .lookup(nested, OsStr::new("file"))
        .expect("lookup file");
    assert_eq!(
        file,
        second
            .lookup(
                second
                    .lookup(ROOT_INODE, OsStr::new("nested"))
                    .expect("nested"),
                OsStr::new("file")
            )
            .expect("file")
    );
    assert_eq!(
        projection.lookup(nested, OsStr::new(".")).expect("dot"),
        nested
    );
    assert_eq!(
        projection.lookup(nested, OsStr::new("..")).expect("dotdot"),
        ROOT_INODE
    );
    assert_eq!(
        projection
            .lookup(ROOT_INODE, OsStr::new(".."))
            .expect("root parent"),
        ROOT_INODE
    );
    let attr = projection.getattr(file).expect("file attributes");
    assert_eq!(attr.kind, FileType::RegularFile);
    assert_eq!(attr.perm, 0o751);
    assert_eq!(attr.mtime, time);
    assert_eq!(attr.size, bytes.len() as u64);
    assert_eq!(
        projection
            .getattr(nested)
            .expect("directory attributes")
            .nlink,
        3
    );
    let link = projection
        .lookup(ROOT_INODE, OsStr::new("link"))
        .expect("lookup link");
    assert_eq!(
        projection.readlink(link).expect("read link"),
        b"nested/\xff-target"
    );
    let (_, children) = projection.directory(nested).expect("directory listing");
    assert_eq!(
        children
            .iter()
            .map(|entry| entry.name.as_os_str())
            .collect::<Vec<_>>(),
        [OsStr::new("empty"), OsStr::new("file")]
    );
    for (offset, size) in [
        (0, 0),
        (0, 1),
        (15_999, 400_001),
        (262_100, 512_000),
        (MAX_READ_BYTES - 1, MAX_READ_BYTES),
        (bytes.len() - 11, 999),
        (bytes.len(), 20),
        (bytes.len() + 20, 20),
    ] {
        assert_eq!(
            projection
                .read(file, offset as i64, size as u32)
                .expect("bounded random read"),
            bytes[offset.min(bytes.len())..(offset + size).min(bytes.len())]
        );
    }
    let zero = projection
        .lookup(ROOT_INODE, OsStr::new("zero"))
        .expect("lookup zero");
    assert!(projection.read(zero, 0, 100).expect("read zero").is_empty());
    assert_eq!(
        projection
            .read(file, -1, 1)
            .expect_err("negative offset")
            .raw_os_error(),
        Some(libc::EINVAL)
    );
    assert_eq!(
        projection
            .read(file, 0, MAX_READ_BYTES as u32 + 1)
            .expect_err("oversized read")
            .raw_os_error(),
        Some(libc::EINVAL)
    );
    assert_eq!(
        projection
            .read(ROOT_INODE, 0, 1)
            .expect_err("directory read")
            .raw_os_error(),
        Some(libc::EISDIR)
    );
    assert!(projection.getattr(0).is_err());
    assert!(projection.lookup(file, OsStr::new("x")).is_err());
}

fn reading_a_file_larger_than_cache_is_bounded_and_does_not_materialize_it() {
    let fixture = Fixture::new();
    fs::create_dir(fixture.source()).expect("create source");
    let bytes = data(store::CACHE_BYTES + 3 * MAX_READ_BYTES);
    fs::write(fixture.source().join("large"), &bytes).expect("write large source");
    fixture.import();
    // The projection remains independent of the original tree.
    fs::remove_dir_all(fixture.source()).expect("remove test-owned source");
    let mut projection = fixture.load();
    assert_eq!(projection.stats()["verified_chunk_bytes"], 0);
    let inode = projection
        .lookup(ROOT_INODE, OsStr::new("large"))
        .expect("lookup large");
    let mut digest = blake3::Hasher::new();
    for offset in (0..bytes.len()).step_by(MAX_READ_BYTES) {
        let result = projection
            .read(inode, offset as i64, MAX_READ_BYTES as u32)
            .expect("stream read");
        assert!(result.len() <= MAX_READ_BYTES);
        digest.update(&result);
        assert!(
            projection.stats()["cache_bytes"]
                .as_u64()
                .expect("cache bytes")
                <= store::CACHE_BYTES as u64
        );
    }
    assert_eq!(digest.finalize(), blake3::hash(&bytes));
    let mut entries: Vec<_> = fs::read_dir(fixture.library())
        .expect("library listing")
        .map(|entry| entry.expect("library entry").file_name())
        .collect();
    entries.sort();
    assert_eq!(
        entries,
        [OsString::from("manifest.json"), OsString::from("objects")]
    );
}

fn chunk_lru_checks_hashes_before_caching_and_evicts_the_least_recently_used() {
    let fixture = Fixture::new();
    let chunks = [vec![1; 65_536], vec![2; 65_536], vec![3; 65_536]];
    let hashes = handbuilt(&fixture, &chunks);
    let (store, _) =
        ObjectStore::load(&fixture.library(), OsStr::new("manifest.json")).expect("load store");
    let mut cache = ChunkCache::new(131_072);
    assert_eq!(cache.get(&store, &hashes[0]).expect("A"), chunks[0]);
    cache.get(&store, &hashes[1]).expect("B");
    cache.get(&store, &hashes[0]).expect("A hit");
    cache.get(&store, &hashes[2]).expect("C evicts B");
    assert_eq!(cache.bytes(), 131_072);
    assert_eq!((cache.hits, cache.misses), (1, 3));
    cache.get(&store, &hashes[1]).expect("B reload");
    assert_eq!(cache.misses, 4);
    // Cached data is the previously verified immutable content, not a new disk read.
    fs::write(
        fixture.library().join("objects").join(&hashes[1]),
        vec![9; 65_536],
    )
    .expect("corrupt object");
    assert_eq!(
        cache.get(&store, &hashes[1]).expect("cached verified B"),
        chunks[1]
    );
    let mut cold = ChunkCache::new(131_072);
    assert!(cold.get(&store, &hashes[1]).is_err());
    assert_eq!(cold.bytes(), 0);
    for hash in [
        "../escape".to_owned(),
        "A".repeat(64),
        "0".repeat(63),
        format!("{}\0", "0".repeat(63)),
    ] {
        assert!(cold.get(&store, &hash).is_err());
    }
}

fn missing_symlink_oversize_and_length_mismatch_objects_are_rejected() {
    let fixture = Fixture::new();
    let hashes = handbuilt(&fixture, &[vec![1; 32]]);
    let object = fixture.library().join("objects").join(&hashes[0]);
    fs::remove_file(&object).expect("remove test chunk");
    assert!(Projection::load(&fixture.library(), OsStr::new("manifest.json"), 0, 0).is_err());
    fs::write(fixture.path.join("outside"), vec![1; 32]).expect("write symlink target");
    symlink(fixture.path.join("outside"), &object).expect("replace object with symlink");
    assert!(Projection::load(&fixture.library(), OsStr::new("manifest.json"), 0, 0).is_err());
    fs::remove_file(&object).expect("remove test symlink");
    fs::write(&object, vec![1; 33]).expect("wrong length chunk");
    assert!(Projection::load(&fixture.library(), OsStr::new("manifest.json"), 0, 0).is_err());
    fs::write(&object, vec![1; store::MAX_CHUNK_BYTES + 1]).expect("oversize chunk");
    assert!(Projection::load(&fixture.library(), OsStr::new("manifest.json"), 0, 0).is_err());
    for name in ["../manifest.json", "objects/x", ".", "/tmp/manifest.json"] {
        assert!(ObjectStore::load(&fixture.library(), OsStr::new(name)).is_err());
    }
}

fn readonly_permissions_reject_every_write_intent_and_respect_mode() {
    let fixture = Fixture::new();
    handbuilt(&fixture, &[vec![1; 32]]);
    let projection = fixture.load();
    let inode = projection
        .lookup(ROOT_INODE, OsStr::new("file"))
        .expect("lookup");
    assert!(projection.open(inode, libc::O_RDONLY, false).is_ok());
    for flag in [
        libc::O_WRONLY,
        libc::O_RDWR,
        libc::O_RDONLY | libc::O_TRUNC,
        libc::O_RDONLY | libc::O_APPEND,
        libc::O_RDONLY | libc::O_CREAT,
    ] {
        assert_eq!(
            projection
                .open(inode, flag, false)
                .expect_err("write rejected")
                .raw_os_error(),
            Some(libc::EROFS)
        );
    }
    assert!(projection.open(ROOT_INODE, libc::O_RDONLY, true).is_ok());
    assert!(projection.open(inode, libc::O_RDONLY, true).is_err());
    assert!(
        projection
            .access(inode, 1001, 1001, libc::R_OK | libc::X_OK)
            .is_ok()
    );
    assert_eq!(
        projection
            .access(inode, 0, 0, libc::W_OK)
            .expect_err("root write rejected")
            .raw_os_error(),
        Some(libc::EROFS)
    );
}

fn import_refuses_existing_root_and_does_not_publish_manifest_on_failure() {
    let fixture = Fixture::new();
    fs::create_dir(fixture.source()).expect("source");
    // Capture rejects non-UTF-8 filenames before it can publish a manifest.
    fs::write(
        fixture.source().join(OsString::from_vec(vec![0xff])),
        b"bytes",
    )
    .expect("invalid filename fixture");
    assert!(store::import(&fixture.source(), &fixture.library()).is_err());
    assert!(!fixture.library().join("manifest.json").exists());
    assert!(store::import(&fixture.source(), &fixture.library()).is_err());
    assert!(store::import(&fixture.source(), &fixture.source().join("inside")).is_err());
}

fn cli_import_reports_structured_stats_and_rejects_unknown_arguments() {
    let fixture = Fixture::new();
    fs::create_dir(fixture.source()).expect("source");
    fs::write(fixture.source().join("file"), b"CLI bytes").expect("fixture");
    let binary = env!("CARGO_BIN_EXE_sprig-cas-projection-prototype");
    let output = Command::new(binary)
        .args(["import", "--source"])
        .arg(fixture.source())
        .arg("--root")
        .arg(fixture.library())
        .output()
        .expect("run import");
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let stats: serde_json::Value = serde_json::from_slice(&output.stdout).expect("JSON stats");
    assert_eq!(stats["event"], "imported");
    assert_eq!(stats["logical_bytes"], 9);
    assert_eq!(stats["entries"], 2);
    for args in [
        vec!["mount", "--unknown"],
        vec!["import", "--root"],
        vec!["import", "--allow-other"],
    ] {
        assert!(
            !Command::new(binary)
                .args(args)
                .status()
                .expect("CLI validation")
                .success()
        );
    }
}

fn pre_epoch_timestamps_fail_closed_without_changing_the_manifest() {
    let fixture = Fixture::new();
    handbuilt(&fixture, &[vec![1; 32]]);
    let path = fixture.library().join("manifest.json");
    let mut manifest: Manifest =
        serde_json::from_slice(&fs::read(&path).expect("read manifest")).expect("decode manifest");
    for nanoseconds in [-1_000_000_000, -500_000_000, -1] {
        manifest.get_mut("file").expect("file entry").modified_ns = nanoseconds;
        let encoded = serde_json::to_vec(&manifest).expect("encode timestamp fixture");
        fs::write(&path, &encoded).expect("write timestamp fixture");
        let error = match Projection::load(&fixture.library(), OsStr::new("manifest.json"), 0, 0) {
            Ok(_) => panic!("pre-epoch metadata must not be exposed incorrectly"),
            Err(error) => error,
        };
        assert!(error.to_string().contains("pre-1970 mtime"));
        assert_eq!(fs::read(&path).expect("unchanged manifest"), encoded);
    }
    for nanoseconds in [0, 1, 500_000_000] {
        manifest.get_mut("file").expect("file entry").modified_ns = nanoseconds;
        fs::write(
            &path,
            serde_json::to_vec(&manifest).expect("encode timestamp"),
        )
        .expect("write valid timestamp");
        let projection = fixture.load();
        let inode = projection
            .lookup(ROOT_INODE, OsStr::new("file"))
            .expect("lookup");
        assert_eq!(
            projection.getattr(inode).expect("attributes").mtime,
            UNIX_EPOCH + Duration::from_nanos(nanoseconds as u64)
        );
    }
}

fn symlink_targets_fit_the_linux_readlink_reply() {
    let fixture = Fixture::new();
    handbuilt(&fixture, &[vec![1; 32]]);
    let path = fixture.library().join("manifest.json");
    let mut manifest: Manifest =
        serde_json::from_slice(&fs::read(&path).expect("read manifest")).expect("decode manifest");
    for length in [4095, 4096] {
        manifest.insert(
            "link".into(),
            entry(
                "link",
                EntryKind::Symlink {
                    target: vec![b'x'; length],
                },
            ),
        );
        fs::write(
            &path,
            serde_json::to_vec(&manifest).expect("encode symlink"),
        )
        .expect("write symlink fixture");
        let result = Projection::load(&fixture.library(), OsStr::new("manifest.json"), 0, 0);
        if length == 4095 {
            let projection = result.expect("maximum safe readlink reply accepted");
            let inode = projection
                .lookup(ROOT_INODE, OsStr::new("link"))
                .expect("lookup link");
            assert_eq!(projection.readlink(inode).expect("read link").len(), length);
        } else {
            let error = match result {
                Ok(_) => panic!("oversized readlink reply must be rejected before mount"),
                Err(error) => error,
            };
            assert!(error.to_string().contains("4095-byte"));
        }
    }
}

// Keep the public test surface small while grouping related invariant checks.
#[test]
fn projection_roundtrip_and_cli_contract() {
    import_preserves_bytes_modes_times_symlink_and_stable_inode_layout();
    reading_a_file_larger_than_cache_is_bounded_and_does_not_materialize_it();
    readonly_permissions_reject_every_write_intent_and_respect_mode();
    import_refuses_existing_root_and_does_not_publish_manifest_on_failure();
    cli_import_reports_structured_stats_and_rejects_unknown_arguments();
}

#[test]
fn bounded_cache_and_invalid_store_contract() {
    chunk_lru_checks_hashes_before_caching_and_evicts_the_least_recently_used();
    missing_symlink_oversize_and_length_mismatch_objects_are_rejected();
    pre_epoch_timestamps_fail_closed_without_changing_the_manifest();
    symlink_targets_fit_the_linux_readlink_reply();
}
