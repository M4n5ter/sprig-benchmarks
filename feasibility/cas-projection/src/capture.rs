//! Experimental incremental capture of a validated, quiescent OverlayFS view.
//!
//! This is not a writer freeze, lease, or hostile-tree sandbox. The caller must
//! keep the store, mount topology, and trees trusted and quiescent throughout.
//! mtime/inode equality detects some races; it NEVER authorizes content reuse.

use std::collections::{BTreeMap, BTreeSet};
use std::ffi::{CString, OsStr, OsString};
use std::fs::{self, File, Metadata, OpenOptions};
use std::io::{self, Read};
use std::os::fd::{AsRawFd, FromRawFd};
use std::os::unix::ffi::{OsStrExt, OsStringExt};
use std::os::unix::fs::{MetadataExt, OpenOptionsExt};
use std::path::{Component, Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{Instant, SystemTime, UNIX_EPOCH};

use fastcdc::v2020::FastCDC;
use serde::Serialize;
use sprig::content::{self, Entry, EntryKind, Manifest};

use crate::projection::ORIGIN_XATTR;
use crate::store::{self, ObjectStore, Result};

const MIN_CHUNK: usize = 16 * 1024;
const AVG_CHUNK: usize = 64 * 1024;
const MAX_CHUNK: usize = 256 * 1024;
const MAX_ORIGIN: usize = 64 * 1024;
static NONCE: AtomicU64 = AtomicU64::new(0);

/// Seconds measured in-process, not attribution to kernel or remote services.
/// Walk categories are disjoint; walk_total_seconds includes them all. Lower
/// proof includes its own opens, metadata, origin and chunk metadata checks.
/// Unaccounted walk time includes readlink, validation, bookkeeping,
/// recursion, and timer overhead. Setup/finalize are outside walk.
#[derive(Debug, Default, Clone, Serialize)]
pub struct CaptureTimings {
    pub setup_seconds: f64,
    pub walk_total_seconds: f64,
    pub regular_merged_open_seconds: f64,
    pub directory_open_seconds: f64,
    pub descriptor_close_seconds: f64,
    pub metadata_seconds: f64,
    pub origin_xattr_seconds: f64,
    pub native_upper_state_seconds: f64,
    pub lower_reusable_proof_seconds: f64,
    pub content_hash_put_stream_seconds: f64,
    pub directory_enumeration_seconds: f64,
    pub finalize_seconds: f64,
}

#[derive(Debug, Default, Clone, Serialize)]
pub struct CaptureStats {
    pub timings: CaptureTimings,
    pub entries: u64,
    pub directories: u64,
    pub symlinks: u64,
    pub files_hashed: u64,
    pub files_reused: u64,
    pub bytes_hashed: u64,
    pub bytes_reused: u64,
    /// Files hashed because lower provenance or upper absence was uncertain.
    pub fallback_files: u64,
    pub lower_reuse_enabled: bool,
    pub fallback_reason: Option<String>,
}

impl CaptureStats {
    pub fn json(&self) -> serde_json::Value {
        serde_json::to_value(self).expect("numeric capture statistics serialize")
    }
}

pub struct CaptureResult {
    pub manifest: Manifest,
    pub stats: CaptureStats,
}

impl CaptureResult {
    /// Reconcile logical identities against a previous checkpoint, which may
    /// differ from the immutable manifest still mounted as the lower layer.
    /// This changes IDs only; it never broadens content-reuse provenance.
    /// Same-path IDs win, then unique capture/origin IDs, then fresh identities.
    /// New upper-only renames without an origin remain new identities: this is
    /// not a writable-operation journal.
    pub fn reconcile_identities(&mut self, previous: &Manifest) -> Result<()> {
        content::validate_manifest(previous)?;
        content::validate_manifest(&self.manifest)?;
        let candidates: BTreeMap<_, _> = self
            .manifest
            .iter()
            .map(|(path, entry)| (path.clone(), entry.id.clone()))
            .collect();
        let mut used = BTreeSet::new();
        for (path, entry) in self.manifest.iter_mut() {
            entry.id.clear();
            if let Some(old) = previous.get(path)
                && used.insert(old.id.clone())
            {
                entry.id.clone_from(&old.id);
            }
        }
        for (path, entry) in self.manifest.iter_mut() {
            if entry.id.is_empty() && used.insert(candidates[path].clone()) {
                entry.id.clone_from(&candidates[path]);
            }
            while entry.id.is_empty() {
                let id = fresh_id(path);
                if used.insert(id.clone()) {
                    entry.id = id;
                }
            }
        }
        content::validate_manifest(&self.manifest)
    }
}

/// Produces a fresh manifest without publishing a head or changing the mount.
/// Only actual upper files or files without complete lower proof are read.
pub fn capture(
    root: &Path,
    base_manifest: &OsStr,
    merged: &Path,
    upper: &Path,
    lower: &Path,
) -> Result<CaptureResult> {
    let setup_started = Instant::now();
    // SAFETY: geteuid is a side-effect-free query.
    if unsafe { libc::geteuid() } != 0 {
        return Err(
            store::invalid("incremental capture requires the rootful CI experiment").into(),
        );
    }
    let root = real_directory(root)?;
    let merged = real_directory(merged)?;
    let upper = real_directory(upper)?;
    let lower = real_directory(lower)?;
    disjoint(&[&root, &merged, &upper, &lower])?;
    let binding = current_binding(&root, &merged, &upper, &lower)?;
    let (store, base) = ObjectStore::load(&root, base_manifest)?;
    let digest = blake3::hash(&serde_json::to_vec(&base)?)
        .to_hex()
        .to_string();
    let lower_fd = open_directory(&lower)?;
    let upper_fd = open_directory(&upper)?;
    let lower_origin_valid = origin(&lower_fd, &digest, &base).as_deref() == Some("");
    let enabled = binding.metacopy_off && lower_origin_valid;
    let fallback_reason = if !binding.metacopy_off {
        Some("metacopy state cannot be proven off; every file will be hashed".into())
    } else if !lower_origin_valid {
        Some(
            "lower root origin does not authenticate the base manifest; every file will be hashed"
                .into(),
        )
    } else {
        None
    };
    let mut context = Capture {
        base: &base,
        digest: &digest,
        store: &store,
        upper: &upper_fd,
        lower: &lower_fd,
        objects: root.join("objects"),
        buffer: vec![0; MAX_CHUNK],
        manifest: Manifest::new(),
        origins: BTreeMap::new(),
        stats: CaptureStats {
            lower_reuse_enabled: enabled,
            fallback_reason,
            ..Default::default()
        },
    };
    context.stats.timings.setup_seconds = setup_started.elapsed().as_secs_f64();
    let walk_started = Instant::now();
    context.walk(&merged, "")?;
    context.stats.timings.walk_total_seconds = walk_started.elapsed().as_secs_f64();
    let finalize_started = Instant::now();
    assign_ids(&mut context.manifest, &base, &context.origins);
    content::validate_manifest(&context.manifest)?;
    File::open(&context.objects)?.sync_all()?;
    // Topology changes during traversal invalidate all reuse evidence.
    if current_binding(&root, &merged, &upper, &lower)? != binding
        || (enabled && origin(&lower_fd, &digest, &base).as_deref() != Some(""))
    {
        return Err(store::invalid("mount or lower origin changed during capture").into());
    }
    context.stats.timings.finalize_seconds = finalize_started.elapsed().as_secs_f64();
    Ok(CaptureResult {
        manifest: context.manifest,
        stats: context.stats,
    })
}

struct Capture<'a> {
    base: &'a Manifest,
    digest: &'a str,
    store: &'a ObjectStore,
    upper: &'a File,
    lower: &'a File,
    objects: PathBuf,
    buffer: Vec<u8>,
    manifest: Manifest,
    origins: BTreeMap<String, String>,
    stats: CaptureStats,
}

impl Capture<'_> {
    fn walk(&mut self, path: &Path, relative: &str) -> Result<()> {
        let started = Instant::now();
        let before = fs::symlink_metadata(path)?;
        self.stats.timings.metadata_seconds += started.elapsed().as_secs_f64();
        let advisory;
        let kind = if before.is_file() {
            let started = Instant::now();
            let mut file = OpenOptions::new()
                .read(true)
                .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK | libc::O_CLOEXEC)
                .open(path)?;
            self.stats.timings.regular_merged_open_seconds += started.elapsed().as_secs_f64();
            let started = Instant::now();
            let opened = file.metadata()?;
            self.stats.timings.metadata_seconds += started.elapsed().as_secs_f64();
            require_unchanged(path, &before, &opened)?;
            let started = Instant::now();
            advisory = origin(&file, self.digest, self.base);
            self.stats.timings.origin_xattr_seconds += started.elapsed().as_secs_f64();
            let started = Instant::now();
            let upper_status = upper_state(self.upper, relative);
            self.stats.timings.native_upper_state_seconds += started.elapsed().as_secs_f64();
            let reusable = if self.stats.lower_reuse_enabled && upper_status == UpperState::Absent {
                advisory.as_deref().and_then(|original| {
                    let started = Instant::now();
                    let reusable = self.reusable(original, &opened);
                    self.stats.timings.lower_reusable_proof_seconds +=
                        started.elapsed().as_secs_f64();
                    reusable
                })
            } else {
                None
            };
            let kind = if let Some(kind) = reusable {
                self.stats.files_reused += 1;
                self.stats.bytes_reused += opened.len();
                // A copied-up/faked origin cannot make an upper file reusable.
                let started = Instant::now();
                let upper_status = upper_state(self.upper, relative);
                self.stats.timings.native_upper_state_seconds += started.elapsed().as_secs_f64();
                if upper_status != UpperState::Absent {
                    return Err(store::invalid("upper changed during capture").into());
                }
                kind
            } else {
                if upper_status != UpperState::Present {
                    self.stats.fallback_files += 1;
                }
                let started = Instant::now();
                let kind = put_stream(&mut file, &self.objects, &mut self.buffer)?;
                self.stats.timings.content_hash_put_stream_seconds +=
                    started.elapsed().as_secs_f64();
                let EntryKind::File { size, .. } = &kind else {
                    unreachable!()
                };
                self.stats.files_hashed += 1;
                self.stats.bytes_hashed += *size;
                if *size != opened.len() {
                    return Err(store::invalid("file length changed during capture").into());
                }
                kind
            };
            let started = Instant::now();
            let after = file.metadata()?;
            self.stats.timings.metadata_seconds += started.elapsed().as_secs_f64();
            require_unchanged(path, &opened, &after)?;
            let started = Instant::now();
            drop(file);
            self.stats.timings.descriptor_close_seconds += started.elapsed().as_secs_f64();
            kind
        } else if before.is_dir() {
            self.stats.directories += 1;
            let started = Instant::now();
            let directory = open_directory(path)?;
            self.stats.timings.directory_open_seconds += started.elapsed().as_secs_f64();
            let started = Instant::now();
            let opened = directory.metadata()?;
            self.stats.timings.metadata_seconds += started.elapsed().as_secs_f64();
            require_unchanged(path, &before, &opened)?;
            let started = Instant::now();
            advisory = origin(&directory, self.digest, self.base);
            self.stats.timings.origin_xattr_seconds += started.elapsed().as_secs_f64();
            let started = Instant::now();
            drop(directory);
            self.stats.timings.descriptor_close_seconds += started.elapsed().as_secs_f64();
            EntryKind::Directory
        } else if before.file_type().is_symlink() {
            self.stats.symlinks += 1;
            // Linux forbids user.* xattrs on symlinks. Same-path IDs remain
            // stable, but symlink renames have no origin hint in this prototype.
            advisory = None;
            EntryKind::Symlink {
                target: fs::read_link(path)?.as_os_str().as_bytes().to_vec(),
            }
        } else {
            return Err(
                store::invalid(format!("special file rejected: {}", path.display())).into(),
            );
        };
        if let Some(original) = advisory {
            self.origins.insert(relative.to_owned(), original);
        }
        self.manifest.insert(
            relative.to_owned(),
            Entry {
                id: String::new(),
                mode: before.mode() & 0o777,
                modified_ns: modified_ns(&before),
                kind,
            },
        );
        self.stats.entries += 1;
        if before.is_dir() {
            let started = Instant::now();
            let mut children = fs::read_dir(path)?.collect::<io::Result<Vec<_>>>()?;
            children.sort_by_key(|child| child.file_name());
            self.stats.timings.directory_enumeration_seconds += started.elapsed().as_secs_f64();
            for child in children {
                let name = child
                    .file_name()
                    .into_string()
                    .map_err(|_| store::invalid("non-UTF-8 path rejected"))?;
                let child_relative = if relative.is_empty() {
                    name
                } else {
                    format!("{relative}/{name}")
                };
                self.walk(&child.path(), &child_relative)?;
            }
        }
        let started = Instant::now();
        let after = fs::symlink_metadata(path)?;
        self.stats.timings.metadata_seconds += started.elapsed().as_secs_f64();
        require_unchanged(path, &before, &after)?;
        Ok(())
    }

    /// The merged payload is only a candidate. Independently query the exact
    /// original path on the validated immutable lower, without symlink traversal.
    fn reusable(&self, original: &str, merged: &Metadata) -> Option<EntryKind> {
        let entry = self.base.get(original)?;
        let EntryKind::File { size, chunks } = &entry.kind else {
            return None;
        };
        if merged.len() != *size {
            return None;
        }
        let lower = open_beneath(self.lower, original, false).ok()?;
        let before = lower.metadata().ok()?;
        if !before.is_file()
            || before.len() != *size
            || (before.mode() & 0o777) != entry.mode
            || modified_ns(&before) != entry.modified_ns
            || origin(&lower, self.digest, self.base).as_deref() != Some(original)
        {
            return None;
        }
        // Object metadata is checked, but lower content is intentionally not
        // reread or rehashed. Its immutable provenance is the reuse proof.
        let total = chunks.iter().try_fold(0_u64, |sum, hash| {
            sum.checked_add(self.store.chunk_length(hash).ok()? as u64)
        })?;
        if total != *size || !unchanged(&before, &lower.metadata().ok()?) {
            return None;
        }
        Some(entry.kind.clone())
    }
}

fn modified_ns(metadata: &Metadata) -> i128 {
    metadata.mtime() as i128 * 1_000_000_000 + metadata.mtime_nsec() as i128
}

fn unchanged(left: &Metadata, right: &Metadata) -> bool {
    left.dev() == right.dev()
        && left.ino() == right.ino()
        && left.mode() == right.mode()
        && left.len() == right.len()
        && left.mtime() == right.mtime()
        && left.mtime_nsec() == right.mtime_nsec()
        && left.ctime() == right.ctime()
        && left.ctime_nsec() == right.ctime_nsec()
}

fn require_unchanged(path: &Path, before: &Metadata, after: &Metadata) -> io::Result<()> {
    if unchanged(before, after) {
        Ok(())
    } else {
        Err(store::invalid(format!(
            "source changed during capture: {}",
            path.display()
        )))
    }
}

fn origin(file: &File, digest: &str, base: &Manifest) -> Option<String> {
    let name = CString::new(ORIGIN_XATTR).ok()?;
    // One bounded read. ENODATA, EACCES, ERANGE, malformed JSON, and every other
    // failure are uncertainty, never evidence of an absent upper inode.
    let mut bytes = vec![0_u8; MAX_ORIGIN];
    // SAFETY: file owns its descriptor; name and writable buffer remain live.
    let length = unsafe {
        libc::fgetxattr(
            file.as_raw_fd(),
            name.as_ptr(),
            bytes.as_mut_ptr().cast(),
            bytes.len(),
        )
    };
    if length < 0 {
        return None;
    }
    bytes.truncate(length as usize);
    parse_origin(&bytes, digest, base)
}

fn parse_origin(bytes: &[u8], digest: &str, base: &Manifest) -> Option<String> {
    let [found, original]: [String; 2] = serde_json::from_slice(bytes).ok()?;
    if found != digest || !base.contains_key(&original) {
        return None;
    }
    Some(original)
}

#[derive(Debug, Eq, PartialEq)]
enum UpperState {
    Absent,
    Present,
    Unknown,
}

fn upper_state(upper: &File, relative: &str) -> UpperState {
    let mut parent = match upper.try_clone() {
        Ok(file) => file,
        Err(_) => return UpperState::Unknown,
    };
    let parts: Vec<_> = relative.split('/').collect();
    if relative.is_empty() || parts.iter().any(|part| matches!(*part, "" | "." | "..")) {
        return UpperState::Unknown;
    }
    for (index, part) in parts.iter().enumerate() {
        let name = match CString::new(*part) {
            Ok(name) => name,
            Err(_) => return UpperState::Unknown,
        };
        if index + 1 == parts.len() {
            let mut metadata = std::mem::MaybeUninit::<libc::stat>::uninit();
            // SAFETY: parent/name are valid and the output points to a stat.
            let result = unsafe {
                libc::fstatat(
                    parent.as_raw_fd(),
                    name.as_ptr(),
                    metadata.as_mut_ptr(),
                    libc::AT_SYMLINK_NOFOLLOW,
                )
            };
            return if result == 0 {
                UpperState::Present
            } else {
                absence_or_unknown(io::Error::last_os_error())
            };
        }
        match open_at(&parent, OsStr::new(part), true) {
            Ok(directory) => parent = directory,
            Err(error) => return absence_or_unknown(error),
        }
    }
    UpperState::Unknown
}

fn absence_or_unknown(error: io::Error) -> UpperState {
    // ENOTDIR may mean an upper symlink ancestor. Never traverse it or mistake
    // it, EACCES, EIO, or ELOOP for positive absence evidence.
    if error.raw_os_error() == Some(libc::ENOENT) {
        UpperState::Absent
    } else {
        UpperState::Unknown
    }
}

fn open_at(parent: &File, name: &OsStr, directory: bool) -> io::Result<File> {
    let name = CString::new(name.as_bytes()).map_err(|_| store::invalid("NUL path"))?;
    let flags = libc::O_RDONLY
        | libc::O_CLOEXEC
        | libc::O_NOFOLLOW
        | libc::O_NONBLOCK
        | if directory { libc::O_DIRECTORY } else { 0 };
    // SAFETY: valid descriptor and terminated name; returned fd adopted once.
    let fd = unsafe { libc::openat(parent.as_raw_fd(), name.as_ptr(), flags) };
    if fd < 0 {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: openat returned a new owned descriptor.
    let file = unsafe { File::from_raw_fd(fd) };
    let metadata = file.metadata()?;
    if !(if directory {
        metadata.is_dir()
    } else {
        metadata.is_file()
    }) {
        return Err(store::invalid("unexpected entry type"));
    }
    Ok(file)
}

fn open_directory(path: &Path) -> io::Result<File> {
    OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_DIRECTORY | libc::O_NOFOLLOW | libc::O_CLOEXEC)
        .open(path)
}

fn open_beneath(root: &File, relative: &str, directory: bool) -> io::Result<File> {
    let mut file = root.try_clone()?;
    let parts: Vec<_> = Path::new(relative).components().collect();
    for (index, component) in parts.iter().enumerate() {
        let Component::Normal(name) = component else {
            return Err(store::invalid("invalid origin path"));
        };
        file = open_at(&file, name, index + 1 != parts.len() || directory)?;
    }
    Ok(file)
}

fn real_directory(path: &Path) -> io::Result<PathBuf> {
    let absolute = if path.is_absolute() {
        path.to_owned()
    } else {
        std::env::current_dir()?.join(path)
    };
    let mut directory = open_directory(Path::new("/"))?;
    for component in absolute.components() {
        match component {
            Component::RootDir | Component::CurDir => {}
            Component::Normal(name) => directory = open_at(&directory, name, true)?,
            _ => return Err(store::invalid("parent components are unsupported")),
        }
    }
    fs::canonicalize(absolute)
}

fn disjoint(paths: &[&Path]) -> io::Result<()> {
    for (index, left) in paths.iter().enumerate() {
        for right in paths.iter().skip(index + 1) {
            if left.starts_with(right) || right.starts_with(left) {
                return Err(store::invalid(
                    "store, merged, upper, lower, and work trees must be disjoint",
                ));
            }
        }
    }
    Ok(())
}

fn assign_ids(manifest: &mut Manifest, base: &Manifest, origins: &BTreeMap<String, String>) {
    let mut used = BTreeSet::new();
    // Same-name entries have first claim, including atomic editor replacements.
    for (path, entry) in manifest.iter_mut() {
        if let Some(old) = base.get(path)
            && used.insert(old.id.clone())
        {
            entry.id.clone_from(&old.id);
        }
    }
    // Origins are identity hints only, including copied-up origins. Duplicate
    // hints can never duplicate an ID or steal a surviving same-path identity.
    // A counterfeit upper hint can claim an otherwise removed base identity;
    // this experimental advisory identity scheme is not an authenticated rename
    // journal. Such hints can never authorize skipping upper content hashing.
    for (path, entry) in manifest.iter_mut() {
        if entry.id.is_empty()
            && let Some(old) = origins.get(path).and_then(|original| base.get(original))
            && used.insert(old.id.clone())
        {
            entry.id.clone_from(&old.id);
        }
        while entry.id.is_empty() {
            let id = fresh_id(path);
            if used.insert(id.clone()) {
                entry.id = id;
            }
        }
    }
}

fn fresh_id(path: &str) -> String {
    let mut hash = blake3::Hasher::new();
    hash.update(path.as_bytes());
    hash.update(&std::process::id().to_le_bytes());
    hash.update(&NONCE.fetch_add(1, Ordering::Relaxed).to_le_bytes());
    hash.update(
        &SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos()
            .to_le_bytes(),
    );
    hash.finalize().to_hex().to_string()
}

/// Same refill-before-cut FastCDC algorithm and constants as production. The
/// public writer handles verification, fully synced inode publication, and
/// directory fsync. Per-chunk directory fsync is conservative extra overhead.
fn put_stream(reader: &mut impl Read, objects: &Path, buffer: &mut [u8]) -> Result<EntryKind> {
    assert_eq!(buffer.len(), MAX_CHUNK);
    let (mut filled, mut eof, mut size) = (0, false, 0_u64);
    let mut chunks = Vec::new();
    loop {
        while filled < MAX_CHUNK && !eof {
            match reader.read(&mut buffer[filled..]) {
                Ok(0) => eof = true,
                Ok(length) => filled += length,
                Err(error) if error.kind() == io::ErrorKind::Interrupted => continue,
                Err(error) => return Err(error.into()),
            }
        }
        if filled == 0 {
            break;
        }
        let cut = FastCDC::new(
            &buffer[..filled],
            MIN_CHUNK as _,
            AVG_CHUNK as _,
            MAX_CHUNK as _,
        )
        .next()
        .expect("nonempty input has a chunk")
        .length;
        let EntryKind::File {
            size: stored,
            chunks: published,
        } = content::put_bytes(&buffer[..cut], objects)?
        else {
            unreachable!()
        };
        if stored != cut as u64 || published.len() != 1 {
            return Err(
                store::invalid("production chunker disagrees with streaming boundary").into(),
            );
        }
        chunks.extend(published);
        size = size
            .checked_add(cut as u64)
            .ok_or_else(|| store::invalid("file size overflow"))?;
        buffer.copy_within(cut..filled, 0);
        filled -= cut;
    }
    Ok(EntryKind::File { size, chunks })
}

#[derive(Debug, Clone, Eq, PartialEq)]
struct Mount {
    id: String,
    root: PathBuf,
    point: PathBuf,
    options: BTreeSet<String>,
    filesystem: String,
    source: String,
    super_options: BTreeMap<String, String>,
}

#[derive(Debug, Eq, PartialEq)]
struct Binding {
    overlay: Mount,
    lower: Mount,
    metacopy_off: bool,
}

fn current_binding(root: &Path, merged: &Path, upper: &Path, lower: &Path) -> Result<Binding> {
    // Linux ovl_show_options prints metacopy only when it differs from the
    // current module default. An omitted option alone therefore proves nothing.
    // https://github.com/torvalds/linux/blob/master/fs/overlayfs/params.c
    let before = fs::read_to_string("/sys/module/overlay/parameters/metacopy").ok();
    let mounts = parse_mountinfo(&fs::read_to_string("/proc/self/mountinfo")?)?;
    let after = fs::read_to_string("/sys/module/overlay/parameters/metacopy").ok();
    let default_off = before.as_deref().map(str::trim) == Some("N") && before == after;
    let binding = validate_binding(&mounts, root, merged, upper, lower, default_off)?;
    let work = Path::new(&binding.overlay.super_options["workdir"]);
    if real_directory(work)? != work || fs::metadata(work)?.dev() != fs::metadata(upper)?.dev() {
        return Err(store::invalid("invalid overlay work directory").into());
    }
    Ok(binding)
}

fn validate_binding(
    mounts: &[Mount],
    root: &Path,
    merged: &Path,
    upper: &Path,
    lower: &Path,
    default_off: bool,
) -> io::Result<Binding> {
    let exact = |point: &Path| -> io::Result<Mount> {
        let mut matches = mounts.iter().filter(|mount| mount.point == point);
        let mount = matches
            .next()
            .ok_or_else(|| store::invalid("path is not an exact mountpoint"))?;
        if matches.next().is_some() {
            return Err(store::invalid("stacked mounts unsupported"));
        }
        Ok(mount.clone())
    };
    let overlay = exact(merged)?;
    let lower_mount = exact(lower)?;
    let options = &overlay.super_options;
    if overlay.filesystem != "overlay"
        || overlay.root != Path::new("/")
        || options.contains_key("userxattr")
        || options.contains_key("volatile")
        || options
            .get("fsync")
            .is_some_and(|value| value == "volatile")
        || options.contains_key("lowerdir+")
        || options.contains_key("datadir+")
        || options.get("lowerdir").map(Path::new) != Some(lower)
        || options.get("upperdir").map(Path::new) != Some(upper)
        || lower_mount.filesystem != "fuse"
        || lower_mount.source != "sprig-cas-prototype"
        || lower_mount.super_options.get("user_id").map(String::as_str) != Some("0")
        || lower_mount.root != Path::new("/")
        || !lower_mount.options.contains("ro")
    {
        return Err(store::invalid("unsupported overlay/lower binding"));
    }
    let work = Path::new(
        options
            .get("workdir")
            .ok_or_else(|| store::invalid("overlay workdir missing"))?,
    );
    disjoint(&[root, merged, upper, lower, work])?;
    for path in [root, merged, upper, lower, work] {
        if !path.is_absolute()
            || path
                .as_os_str()
                .as_bytes()
                .iter()
                .any(|byte| matches!(byte, b':' | b',' | b'\\'))
        {
            return Err(store::invalid("ambiguous overlay path unsupported"));
        }
        if mounts
            .iter()
            .any(|mount| mount.point != path && mount.point.starts_with(path))
        {
            return Err(store::invalid(
                "nested mounts within capture trees unsupported",
            ));
        }
    }
    let metacopy_off = match options.get("metacopy").map(String::as_str) {
        Some("off") => true,
        None => default_off,
        _ => {
            return Err(store::invalid(
                "metacopy enabled or unknown option unsupported",
            ));
        }
    };
    Ok(Binding {
        overlay,
        lower: lower_mount,
        metacopy_off,
    })
}

fn parse_mountinfo(input: &str) -> io::Result<Vec<Mount>> {
    input
        .lines()
        .map(|line| {
            let (left, right) = line
                .split_once(" - ")
                .ok_or_else(|| store::invalid("invalid mountinfo"))?;
            let left: Vec<_> = left.split_ascii_whitespace().collect();
            let right: Vec<_> = right.split_ascii_whitespace().collect();
            if left.len() < 6 || right.len() != 3 {
                return Err(store::invalid("invalid mountinfo fields"));
            }
            let mut super_options = BTreeMap::new();
            for part in right[2].split(',') {
                let (key, value) = part.split_once('=').unwrap_or((part, ""));
                let value = decode_mount(value)?
                    .into_string()
                    .map_err(|_| store::invalid("non-UTF-8 mount option"))?;
                if super_options.insert(key.to_owned(), value).is_some() {
                    return Err(store::invalid("duplicate mount option unsupported"));
                }
            }
            Ok(Mount {
                id: left[0].into(),
                root: PathBuf::from(decode_mount(left[3])?),
                point: PathBuf::from(decode_mount(left[4])?),
                options: left[5].split(',').map(str::to_owned).collect(),
                filesystem: right[0].into(),
                source: decode_mount(right[1])?
                    .into_string()
                    .map_err(|_| store::invalid("non-UTF-8 mount source"))?,
                super_options,
            })
        })
        .collect()
}

fn decode_mount(input: &str) -> io::Result<OsString> {
    let bytes = input.as_bytes();
    let mut output = Vec::with_capacity(bytes.len());
    let mut index = 0;
    while index < bytes.len() {
        if bytes[index] == b'\\' {
            if index + 3 >= bytes.len()
                || !bytes[index + 1..index + 4]
                    .iter()
                    .all(|byte| (b'0'..=b'7').contains(byte))
            {
                return Err(store::invalid("invalid mountinfo escape"));
            }
            let value = (bytes[index + 1] - b'0') as u16 * 64
                + (bytes[index + 2] - b'0') as u16 * 8
                + (bytes[index + 3] - b'0') as u16;
            if value == 0 || value > 255 {
                return Err(store::invalid("invalid mountinfo escape byte"));
            }
            output.push(value as u8);
            index += 4;
        } else {
            output.push(bytes[index]);
            index += 1;
        }
    }
    Ok(OsString::from_vec(output))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{Cursor, Write};
    use std::os::unix::fs::symlink;

    struct Fixture(PathBuf);
    impl Fixture {
        fn new() -> Self {
            let path = Path::new(env!("CARGO_MANIFEST_DIR"))
                .join("target/test-work")
                .join(format!(
                    "capture-{}-{}",
                    std::process::id(),
                    NONCE.fetch_add(1, Ordering::Relaxed)
                ));
            fs::create_dir_all(&path).unwrap();
            Self(path)
        }
    }
    impl Drop for Fixture {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    fn entry(id: &str, kind: EntryKind) -> Entry {
        Entry {
            id: id.into(),
            mode: 0o644,
            modified_ns: 0,
            kind,
        }
    }

    #[test]
    fn mount_binding_is_exact_and_metacopy_is_not_assumed() {
        let text = "1 0 0:1 / / rw - tmpfs tmpfs rw\n\
            2 1 0:2 / /lower ro,nosuid,nodev - fuse sprig-cas-prototype ro,user_id=0,group_id=0\n\
            3 1 0:3 / /merged rw - overlay overlay rw,lowerdir=/lower,upperdir=/upper,workdir=/work,nouserxattr\n";
        let mounts = parse_mountinfo(text).unwrap();
        let check = |mounts: &[Mount], default| {
            validate_binding(
                mounts,
                Path::new("/store"),
                Path::new("/merged"),
                Path::new("/upper"),
                Path::new("/lower"),
                default,
            )
        };
        assert!(!check(&mounts, false).unwrap().metacopy_off);
        assert!(check(&mounts, true).unwrap().metacopy_off);
        let mut changed = mounts.clone();
        changed[2]
            .super_options
            .insert("metacopy".into(), "off".into());
        assert!(check(&changed, false).unwrap().metacopy_off);
        for (key, value) in [
            ("metacopy", "on"),
            ("userxattr", ""),
            ("lowerdir", "/lower:/second"),
            ("upperdir", "/other"),
            ("workdir", "/store/work"),
        ] {
            let mut changed = mounts.clone();
            changed[2].super_options.insert(key.into(), value.into());
            assert!(check(&changed, true).is_err(), "accepted {key}={value}");
        }
        let mut changed = mounts.clone();
        changed[1].options.remove("ro");
        assert!(check(&changed, true).is_err());
        let mut changed = mounts.clone();
        changed[1].super_options.remove("user_id");
        assert!(check(&changed, true).is_err());
        changed[1]
            .super_options
            .insert("user_id".into(), "1000".into());
        assert!(check(&changed, true).is_err());
        let mut changed = mounts.clone();
        let mut child = changed[0].clone();
        child.point = PathBuf::from("/upper/nested");
        changed.push(child);
        assert!(check(&changed, true).is_err());
        assert_eq!(
            decode_mount(r"/a\040b\134c").unwrap(),
            OsStr::new("/a b\\c")
        );
        assert!(decode_mount(r"/a\999").is_err());
    }

    #[test]
    fn upper_absence_never_follows_symlinks_or_accepts_permission_errors() {
        let fixture = Fixture::new();
        let upper_path = fixture.0.join("upper");
        fs::create_dir(&upper_path).unwrap();
        fs::create_dir(upper_path.join("dir")).unwrap();
        fs::write(upper_path.join("dir/file"), "upper").unwrap();
        symlink("dir", upper_path.join("alias")).unwrap();
        symlink("missing", upper_path.join("dangling")).unwrap();
        let upper = open_directory(&upper_path).unwrap();
        assert_eq!(upper_state(&upper, "dir/file"), UpperState::Present);
        assert_eq!(upper_state(&upper, "dir/new"), UpperState::Absent);
        assert_eq!(upper_state(&upper, "missing/child"), UpperState::Absent);
        assert_eq!(upper_state(&upper, "alias/absent"), UpperState::Unknown);
        assert_eq!(upper_state(&upper, "dangling/child"), UpperState::Unknown);
        assert_eq!(upper_state(&upper, "dangling"), UpperState::Present);
        assert_eq!(
            absence_or_unknown(io::Error::from_raw_os_error(libc::EACCES)),
            UpperState::Unknown
        );
        assert_eq!(
            absence_or_unknown(io::Error::from_raw_os_error(libc::EIO)),
            UpperState::Unknown
        );
        assert!(real_directory(&upper_path.join("alias")).is_err());
        synthetic_origin_proof();
    }

    // Isolated proof-engine fixture only: no mount creation and no public
    // constructor that bypasses runtime mount validation.
    fn synthetic_origin_proof() {
        let fixture = Fixture::new();
        let lower = fixture.0.join("lower");
        let merged = fixture.0.join("merged");
        let upper = fixture.0.join("upper");
        let library = fixture.0.join("library");
        fs::create_dir_all(lower.join("old")).unwrap();
        fs::create_dir(&upper).unwrap();
        fs::write(lower.join("old/file"), "original").unwrap();
        symlink(
            OsString::from_vec(vec![0xff, b'/', b'x']),
            lower.join("link"),
        )
        .unwrap();
        store::import(&lower, &library).unwrap();
        let (store, base) = ObjectStore::load(&library, OsStr::new("manifest.json")).unwrap();
        let digest = blake3::hash(&serde_json::to_vec(&base).unwrap())
            .to_hex()
            .to_string();
        content::materialize(&base, &library.join("objects"), &merged).unwrap();
        let write_origin = |path: &Path, original: &str| {
            let bytes = serde_json::to_vec(&[digest.as_str(), original]).unwrap();
            let file = File::open(path).unwrap();
            let name = CString::new(ORIGIN_XATTR).unwrap();
            // SAFETY: live descriptor, CString and readable bytes; test-owned file.
            let result = unsafe {
                libc::fsetxattr(
                    file.as_raw_fd(),
                    name.as_ptr(),
                    bytes.as_ptr().cast(),
                    bytes.len(),
                    0,
                )
            };
            assert_eq!(result, 0, "{}", io::Error::last_os_error());
        };
        write_origin(&lower.join("old/file"), "old/file");
        write_origin(&merged.join("old/file"), "old/file");
        write_origin(&merged.join("old"), "old");
        fs::rename(merged.join("old"), merged.join("new")).unwrap();
        let upper_fd = open_directory(&upper).unwrap();
        let lower_fd = open_directory(&lower).unwrap();
        let run = || {
            let mut context = Capture {
                base: &base,
                digest: &digest,
                store: &store,
                upper: &upper_fd,
                lower: &lower_fd,
                objects: library.join("objects"),
                buffer: vec![0; MAX_CHUNK],
                manifest: Manifest::new(),
                origins: BTreeMap::new(),
                stats: CaptureStats {
                    lower_reuse_enabled: true,
                    ..Default::default()
                },
            };
            let started = Instant::now();
            context.walk(&merged, "").unwrap();
            let elapsed = started.elapsed().as_secs_f64();
            let json = context.stats.json();
            let timings = json["timings"].as_object().unwrap();
            assert_eq!(timings.len(), 12);
            let sum: f64 = timings
                .values()
                .map(|value| {
                    let seconds = value.as_f64().unwrap();
                    assert!(seconds.is_finite() && seconds >= 0.0);
                    seconds
                })
                .sum();
            // Setup, walk_total and finalize are zero in this direct walk
            // fixture. The nine disjoint walk categories fit within elapsed.
            assert!(sum <= elapsed);
            assign_ids(&mut context.manifest, &base, &context.origins);
            content::validate_manifest(&context.manifest).unwrap();
            CaptureResult {
                manifest: context.manifest,
                stats: context.stats,
            }
        };
        let captured = run();
        assert_eq!(captured.stats.files_reused, 1);
        assert_eq!(captured.stats.bytes_hashed, 0);
        assert_eq!(captured.manifest["new/file"].kind, base["old/file"].kind);
        assert_eq!(captured.manifest["new/file"].id, base["old/file"].id);
        assert_eq!(captured.manifest["new"].id, base["old"].id);
        assert_eq!(
            captured.manifest["link"].kind,
            EntryKind::Symlink {
                target: vec![0xff, b'/', b'x']
            }
        );
        // Simulate a copied-up file retaining the exact origin, size and mtime.
        // Its payload is changed, so relying on those hints would be unsound.
        let modified = fs::metadata(merged.join("new/file"))
            .unwrap()
            .modified()
            .unwrap();
        fs::write(merged.join("new/file"), "modified").unwrap();
        File::open(merged.join("new/file"))
            .unwrap()
            .set_times(std::fs::FileTimes::new().set_modified(modified))
            .unwrap();
        fs::create_dir(upper.join("new")).unwrap();
        fs::write(upper.join("new/file"), "modified").unwrap();
        write_origin(&upper.join("new/file"), "old/file");
        let captured = run();
        assert_eq!(captured.stats.files_reused, 0);
        assert_eq!(captured.stats.bytes_hashed, 8);
        assert_ne!(captured.manifest["new/file"].kind, base["old/file"].kind);
        assert_eq!(captured.manifest["new/file"].id, base["old/file"].id);
        // Even with proven upper absence, an unvalidated lower origin cannot
        // authorize reuse. Here a wrong-but-well-formed original path is used.
        fs::remove_file(upper.join("new/file")).unwrap();
        write_origin(&lower.join("old/file"), "old");
        let captured = run();
        assert_eq!(captured.stats.files_reused, 0);
        assert_eq!(captured.stats.bytes_hashed, 8);
        assert_eq!(captured.stats.fallback_files, 1);
        assert!(parse_origin(br#"["wrong","old/file"]"#, &digest, &base).is_none());
        assert!(parse_origin(br#"[1,2]"#, &digest, &base).is_none());
    }

    #[test]
    fn production_chunk_boundaries_match_and_existing_corruption_is_rejected() {
        let fixture = Fixture::new();
        let objects = fixture.0.join("objects");
        let mut random = 0x523c_2d34_a88a_u64;
        let data: Vec<u8> = (0..(MAX_CHUNK * 9 + 31))
            .map(|_| {
                random ^= random << 13;
                random ^= random >> 7;
                random ^= random << 17;
                random as u8
            })
            .collect();
        let mut buffer = vec![0; MAX_CHUNK];
        for size in [
            0,
            1,
            MIN_CHUNK - 1,
            MIN_CHUNK,
            AVG_CHUNK + 1,
            MAX_CHUNK,
            data.len(),
        ] {
            let expected = content::put_bytes(&data[..size], &objects).unwrap();
            assert_eq!(
                put_stream(&mut Cursor::new(&data[..size]), &objects, &mut buffer).unwrap(),
                expected
            );
        }
        // Stream a file beyond the production merge helper's 16 MiB limit. No
        // whole-file read/allocation is used by either capture implementation.
        let source = fixture.0.join("source");
        fs::create_dir(&source).unwrap();
        let mut file = File::create(source.join("large")).unwrap();
        for _ in 0..75 {
            file.write_all(&data[..MAX_CHUNK]).unwrap();
        }
        drop(file);
        let (expected, _) = content::capture(&source, &objects, &content::Observed::new()).unwrap();
        let streamed = put_stream(
            &mut File::open(source.join("large")).unwrap(),
            &objects,
            &mut buffer,
        )
        .unwrap();
        assert_eq!(streamed, expected["large"].kind);
        let EntryKind::File { chunks, .. } = streamed else {
            unreachable!()
        };
        let target = objects.join(&chunks[0]);
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(&target, fs::Permissions::from_mode(0o600)).unwrap();
        fs::write(target, "corrupt").unwrap();
        assert!(
            put_stream(
                &mut File::open(source.join("large")).unwrap(),
                &objects,
                &mut buffer
            )
            .is_err()
        );
    }

    #[test]
    fn same_path_identity_wins_and_origin_duplicates_get_fresh_ids() {
        let base = Manifest::from([
            ("".into(), entry("root", EntryKind::Directory)),
            (
                "a".into(),
                entry(
                    "a-id",
                    EntryKind::File {
                        size: 0,
                        chunks: vec![],
                    },
                ),
            ),
            ("old".into(), entry("rename-id", EntryKind::Directory)),
        ]);
        let mut fresh = Manifest::from([
            ("".into(), entry("", EntryKind::Directory)),
            (
                "a".into(),
                entry(
                    "",
                    EntryKind::File {
                        size: 0,
                        chunks: vec![],
                    },
                ),
            ),
            (
                "copy".into(),
                entry(
                    "",
                    EntryKind::File {
                        size: 0,
                        chunks: vec![],
                    },
                ),
            ),
            ("new".into(), entry("", EntryKind::Directory)),
            ("new-copy".into(), entry("", EntryKind::Directory)),
        ]);
        let origins = BTreeMap::from([
            ("copy".into(), "a".into()),
            ("new".into(), "old".into()),
            ("new-copy".into(), "old".into()),
        ]);
        assign_ids(&mut fresh, &base, &origins);
        assert_eq!(fresh["a"].id, "a-id");
        assert_eq!(fresh["new"].id, "rename-id");
        assert_ne!(fresh["copy"].id, "a-id");
        assert_ne!(fresh["new-copy"].id, "rename-id");
        content::validate_manifest(&fresh).unwrap();

        // The immutable lower and logical previous checkpoint are different
        // bases after the first checkpoint. Same-path upper-only IDs must not
        // change on repeated captures against that still-mounted lower.
        fresh.insert(
            "upper-only".into(),
            entry(
                "random-capture-id",
                EntryKind::File {
                    size: 0,
                    chunks: vec![],
                },
            ),
        );
        let mut previous = fresh.clone();
        previous.get_mut("upper-only").unwrap().id = "checkpoint-id".into();
        previous.remove("new");
        previous.get_mut("a").unwrap().id = "rename-id".into();
        let mut captured = CaptureResult {
            manifest: fresh,
            stats: CaptureStats::default(),
        };
        captured.reconcile_identities(&previous).unwrap();
        assert_eq!(captured.manifest["upper-only"].id, "checkpoint-id");
        assert_eq!(captured.manifest["a"].id, "rename-id");
        assert_ne!(captured.manifest["new"].id, "rename-id");
        let checkpoint = captured.manifest.clone();
        // Simulate fresh capture IDs, retaining unchanged content and metadata.
        for (path, entry) in captured.manifest.iter_mut() {
            entry.id = fresh_id(path);
        }
        captured.reconcile_identities(&checkpoint).unwrap();
        assert_eq!(captured.manifest, checkpoint);
    }
}
