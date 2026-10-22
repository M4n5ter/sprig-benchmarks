//! Experimental single-writer publication shared by capture and direct writes.
//!
//! The store and its ancestors must remain trusted. This is an immutable CAS
//! history, not a mounted-workspace recovery protocol or a complete SDK.

use std::collections::{BTreeMap, BTreeSet};
use std::ffi::{CString, OsStr};
use std::fs::{self, DirBuilder, File, OpenOptions};
use std::io::{self, Read, Write};
use std::os::fd::{AsRawFd, FromRawFd};
use std::os::unix::ffi::OsStrExt;
use std::os::unix::fs::{DirBuilderExt, MetadataExt, OpenOptionsExt, PermissionsExt};
use std::path::{Component, Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};
use sprig::content::{self, Entry, EntryKind, Manifest};
use sprig::merge::{self, MergeConflict, MergeStrategy};

use crate::store::{MAX_CHUNK_BYTES, Result, invalid, validate_hash};

const MAX_METADATA_BYTES: u64 = 256 * 1024 * 1024;
const IMPORT_MESSAGE: &str = "Initial imported manifest";
static NONCE: AtomicU64 = AtomicU64::new(0);

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Head {
    pub head: String,
    pub generation: u64,
}

/// Decoded immutable revision. `manifest_file` can be passed to the projection.
#[derive(Clone, Debug, Serialize)]
pub struct Revision {
    pub id: String,
    pub manifest_file: String,
    pub manifest: Manifest,
    pub parents: Vec<String>,
    pub clock: u64,
    pub message: String,
}

#[derive(Clone, Debug, Serialize)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum PublishOutcome {
    Published {
        head: Head,
        candidate: String,
        candidate_manifest: String,
        manifest: String,
        merged: bool,
    },
    Noop {
        head: Head,
        manifest: String,
    },
    Conflict {
        head: Head,
        candidate: String,
        candidate_manifest: String,
        conflict_file: String,
        conflicts: Vec<MergeConflict>,
    },
}

/// An explicit compare-and-swap mismatch never publishes a candidate or head.
#[derive(Clone, Debug, Serialize)]
pub struct ExpectedHeadMismatch {
    pub expected: Head,
    pub actual: Head,
}

impl std::fmt::Display for ExpectedHeadMismatch {
    fn fmt(&self, output: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            output,
            "expected head {} at generation {}, found {} at generation {}",
            self.expected.head, self.expected.generation, self.actual.head, self.actual.generation
        )
    }
}

impl std::error::Error for ExpectedHeadMismatch {}

/// The head rename succeeded, but its directory durability was not confirmed.
/// The attempted head may already be visible or durable. Do not retry blindly.
#[derive(Debug)]
pub struct PublicationOutcomeUnknown {
    pub attempted_head: Head,
    pub source: io::Error,
}

impl std::fmt::Display for PublicationOutcomeUnknown {
    fn fmt(&self, output: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            output,
            "publication outcome unknown; reopen and inspect, do not retry: attempted head {} at generation {}; {}",
            self.attempted_head.head, self.attempted_head.generation, self.source
        )
    }
}

impl std::error::Error for PublicationOutcomeUnknown {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        Some(&self.source)
    }
}

/// Keep this value alive across capture AND publication. The nonblocking flock
/// serializes cooperative capture, direct-write, merge, and head writers.
pub struct Transaction {
    root: PathBuf,
    root_dir: File,
    objects_dir: File,
    backups_dir: File,
    _lock: File,
    head: Head,
    // Only successful publication establishes this durability evidence.
    // Rebuilt from the already-validated current revision when reopening.
    durable_objects: BTreeSet<String>,
}

impl Transaction {
    /// Initializes history only if head.json is absent, without changing the
    /// original manifest.json. A failed initialization can leave retained files.
    pub fn open(root: &Path) -> Result<Self> {
        if root.as_os_str().is_empty()
            || root
                .components()
                .any(|part| matches!(part, Component::ParentDir))
        {
            return Err(invalid("invalid store root").into());
        }
        let root: PathBuf = root.components().collect();
        let root_dir = open_directory(&root)?;
        let root = fs::canonicalize(root)?;
        // Reject incompatible prior experimental history before creating a lock
        // or directory. This is detection, not migration or repair.
        if let Some(head) = read_optional_json::<Head>(&root_dir, "head.json")? {
            validate_hash(&head.head)?;
            crate::metadata::decode_revision(
                &read_bytes(&root_dir, &format!("{}.revision.zst", head.head))?,
                &head.head,
            )?;
        } else if root.join("commits").exists() || root.join("commit-backups").exists() {
            return Err(
                invalid("incomplete or incompatible history; no migration attempted").into(),
            );
        }

        let lock = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .mode(0o600)
            .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK)
            .open(root.join("commit.lock"))?;
        let metadata = lock.metadata()?;
        if !metadata.is_file() || metadata.mode() & 0o077 != 0 || metadata.nlink() != 1 {
            return Err(
                invalid("commit.lock must be a private, singly linked regular file").into(),
            );
        }
        // SAFETY: lock owns a live descriptor. flock has no pointer arguments.
        if unsafe { libc::flock(lock.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) } != 0 {
            return Err(io::Error::last_os_error().into());
        }
        let objects_dir = open_directory(&root.join("objects"))?;
        let backups_dir = ensure_directory(&root.join("commit-backups"))?;
        root_dir.sync_all()?;
        let existing: Option<Head> = read_optional_json(&root_dir, "head.json")?;
        let mut transaction = Self {
            root,
            root_dir,
            objects_dir,
            backups_dir,
            _lock: lock,
            durable_objects: BTreeSet::new(),
            head: existing.clone().unwrap_or(Head {
                head: String::new(),
                generation: 0,
            }),
        };
        if let Some(head) = existing {
            validate_hash(&head.head)?;
            let current = transaction.revision(&head.head)?;
            transaction.durable_objects = content::referenced_chunks(&current.manifest);
        } else {
            let manifest = transaction.read_manifest("manifest.json")?;
            let revision = transaction.store_revision(&manifest, &[], IMPORT_MESSAGE)?;
            let head = Head {
                head: revision.id,
                generation: 0,
            };
            transaction.publish_head(&head, None)?;
            transaction.head = head;
            transaction.durable_objects = content::referenced_chunks(&manifest);
        }
        Ok(transaction)
    }

    pub fn head(&self) -> &Head {
        &self.head
    }

    /// IDs and filenames must identify an ancestor in the current history DAG.
    /// Retained but unmerged candidates remain readable via `revision`, not
    /// usable as an unrelated three-way merge base. Filenames are root-only.
    pub fn resolve_base(&self, base: &str) -> Result<Revision> {
        let exact_id = if validate_hash(base).is_ok() {
            Some(base)
        } else if let Some(id) = base.strip_suffix(".revision.zst") {
            validate_filename(base)?;
            validate_hash(id)?;
            // Verify address and schema even for a retained non-ancestor.
            self.read_record(id)?;
            Some(id)
        } else {
            None
        };
        let filename = if exact_id.is_some() {
            None
        } else {
            validate_filename(base)?;
            Some(self.read_manifest(base)?)
        };
        let mut pending = vec![self.head.head.clone()];
        let mut visited = BTreeSet::new();
        while let Some(id) = pending.pop() {
            if !visited.insert(id.clone()) {
                continue;
            }
            let record = self.read_record(&id)?;
            if (exact_id == Some(id.as_str())) || filename.as_ref() == Some(&record.manifest) {
                return self.revision(&id);
            }
            pending.extend(record.parents);
        }
        Err(invalid("base is not an ancestor of this store's current head").into())
    }

    pub fn revision(&self, id: &str) -> Result<Revision> {
        let record = self.read_record(id)?;
        Ok(Revision {
            id: id.to_owned(),
            manifest_file: format!("{id}.revision.zst"),
            manifest: record.manifest,
            parents: record.parents,
            clock: record.clock,
            message: record.message,
        })
    }

    /// First-parent history, newest first; each result retains all DAG parents.
    pub fn history(&self, limit: usize) -> Result<Vec<Revision>> {
        let mut history = Vec::new();
        let mut next = Some(self.head.head.clone());
        let mut visited = BTreeSet::new();
        while let Some(id) = next {
            if history.len() == limit {
                break;
            }
            if !visited.insert(id.clone()) {
                return Err(invalid("cycle in commit history").into());
            }
            let revision = self.revision(&id)?;
            next = revision.parents.first().cloned();
            history.push(revision);
        }
        Ok(history)
    }

    /// Publishes a capture or SDK candidate through exactly the same core.
    /// On conflict, keeps the candidate and a structured report but never
    /// publishes the merge fallback or any textual conflict markers.
    pub fn publish(
        &mut self,
        base: &str,
        candidate: Manifest,
        message: &str,
        expected: Option<&Head>,
    ) -> Result<PublishOutcome> {
        self.check_expected(expected)?;
        content::validate_manifest(&candidate)?;
        let base = self.resolve_base(base)?;
        let current = self.revision(&self.head.head)?;
        if candidate == base.manifest || candidate == current.manifest {
            return Ok(self.noop(&current));
        }
        let candidate = self.store_revision(&candidate, &[&base], message)?;
        let (result, merged) = if base.id == current.id {
            (candidate.clone(), false)
        } else {
            let result = merge::merge(
                &base.manifest,
                &current.manifest,
                &candidate.manifest,
                &self.root.join("objects"),
                MergeStrategy::Conflict,
                (current.clock, &current.id),
                (candidate.clock, &candidate.id),
                &[],
            )?;
            if !result.conflicts.is_empty() {
                let name = format!("conflict-{}-{}.json", current.id, candidate.id);
                let conflict_file = format!("commit-backups/{name}");
                let report = PublishOutcome::Conflict {
                    head: self.head.clone(),
                    candidate: candidate.id,
                    candidate_manifest: candidate.manifest_file,
                    conflict_file,
                    conflicts: result.conflicts,
                };
                self.write_immutable(&self.backups_dir, &name, &json_bytes(&report)?)?;
                return Ok(report);
            }
            if result.manifest == current.manifest {
                return Ok(self.noop(&current));
            }
            (
                self.store_revision(&result.manifest, &[&current, &candidate], message)?,
                true,
            )
        };
        let head = Head {
            head: result.id,
            generation: self
                .head
                .generation
                .checked_add(1)
                .ok_or_else(|| invalid("head generation exhausted"))?,
        };
        self.publish_head(&head, Some(&self.head))?;
        self.head = head.clone();
        self.durable_objects = content::referenced_chunks(&result.manifest);
        Ok(PublishOutcome::Published {
            head,
            candidate: candidate.id,
            candidate_manifest: candidate.manifest_file,
            manifest: result.manifest_file,
            merged,
        })
    }

    /// A minimal direct-file mutation, not a complete SDK. Existing regular
    /// files retain identity/mode; new files require an existing parent and use
    /// 0644. Writing identical bytes does not manufacture an mtime-only change.
    pub fn write_file(
        &mut self,
        base: &str,
        path: &str,
        bytes: &[u8],
        message: &str,
        expected: Option<&Head>,
    ) -> Result<PublishOutcome> {
        self.check_expected(expected)?;
        validate_file_path(path)?;
        let mut revision = self.resolve_base(base)?;
        if let Some(entry) = revision.manifest.get(path) {
            if !matches!(entry.kind, EntryKind::File { .. }) {
                return Err(invalid(
                    "direct write requires a regular file, not a directory/symlink",
                )
                .into());
            }
        } else {
            let parent = path.rsplit_once('/').map_or("", |(parent, _)| parent);
            if !matches!(
                revision.manifest.get(parent).map(|entry| &entry.kind),
                Some(EntryKind::Directory)
            ) {
                return Err(invalid("new file requires an existing directory parent").into());
            }
        }
        let kind = content::put_bytes(bytes, &self.root.join("objects"))?;
        match revision.manifest.get_mut(path) {
            Some(entry) if entry.kind != kind => {
                entry.kind = kind;
                entry.modified_ns = now_ns()?;
            }
            Some(_) => {}
            None => {
                let id = loop {
                    let id = unique_name(path);
                    if revision.manifest.values().all(|entry| entry.id != id) {
                        break id;
                    }
                };
                revision.manifest.insert(
                    path.to_owned(),
                    Entry {
                        id,
                        mode: 0o644,
                        modified_ns: now_ns()?,
                        kind,
                    },
                );
            }
        }
        self.publish(&revision.id, revision.manifest, message, expected)
    }

    fn noop(&self, current: &Revision) -> PublishOutcome {
        PublishOutcome::Noop {
            head: self.head.clone(),
            manifest: current.manifest_file.clone(),
        }
    }

    fn check_expected(&self, expected: Option<&Head>) -> Result<()> {
        let actual: Head = read_json(&self.root_dir, "head.json")?;
        let expected = expected.unwrap_or(&self.head);
        if expected != &actual || actual != self.head {
            return Err(Box::new(ExpectedHeadMismatch {
                expected: expected.clone(),
                actual,
            }));
        }
        Ok(())
    }

    fn read_manifest(&self, name: &str) -> Result<Manifest> {
        validate_filename(name)?;
        let bytes = read_bytes(&self.root_dir, name)?;
        if let Some(id) = name.strip_suffix(".revision.zst") {
            return Ok(crate::metadata::decode_revision(&bytes, id)?.manifest);
        }
        if name.ends_with(".zst") {
            return Err(invalid("unsupported manifest format").into());
        }
        let manifest = serde_json::from_slice(&bytes)?;
        content::validate_manifest(&manifest)?;
        Ok(manifest)
    }

    fn read_record(&self, id: &str) -> Result<sprig::Revision> {
        validate_hash(id)?;
        crate::metadata::decode_revision(
            &read_bytes(&self.root_dir, &format!("{id}.revision.zst"))?,
            id,
        )
    }

    fn store_revision(
        &self,
        manifest: &Manifest,
        parents: &[&Revision],
        message: &str,
    ) -> Result<Revision> {
        content::validate_manifest(manifest)?;
        // No unchanged-content rehash: the immutable store remains trusted,
        // as in read-only projection loading. Validate lengths and durability.
        let mut lengths = BTreeMap::new();
        for hash in content::referenced_chunks(manifest) {
            validate_hash(&hash)?;
            let file = open_at(&self.objects_dir, &hash, libc::O_RDONLY)?;
            let length = file.metadata()?.len();
            if length == 0 || length > MAX_CHUNK_BYTES as u64 {
                return Err(invalid("referenced chunk length is outside 1..=256 KiB").into());
            }
            // A published current head proves prior object durability, not
            // integrity. Keep all existing type/length checks above and below.
            // Arbitrary new/orphan candidate objects still require fsync.
            if !self.durable_objects.contains(&hash) {
                file.sync_all()?;
            }
            lengths.insert(hash, length);
        }
        for entry in manifest.values() {
            if let EntryKind::File { size, chunks } = &entry.kind {
                let length = chunks
                    .iter()
                    .try_fold(0_u64, |sum, hash| sum.checked_add(lengths[hash]))
                    .ok_or_else(|| invalid("chunk length overflow"))?;
                if length != *size {
                    return Err(invalid("file size does not match referenced chunks").into());
                }
            }
        }
        self.objects_dir.sync_all()?;
        let mut max_clock = 0;
        for parent in parents {
            max_clock = max_clock.max(parent.clock);
        }
        let record = sprig::Revision {
            manifest: manifest.clone(),
            parents: parents.iter().map(|parent| parent.id.clone()).collect(),
            clock: max_clock
                .checked_add(1)
                .ok_or_else(|| invalid("revision clock exhausted"))?,
            message: message.to_owned(),
        };
        // Exactly the production Revision serialization defines the identity.
        let bytes = serde_json::to_vec(&record)?;
        let encoded = crate::metadata::encode(&bytes)?;
        let id = blake3::hash(&bytes).to_hex().to_string();
        let manifest_file = format!("{id}.revision.zst");
        self.write_immutable(&self.root_dir, &manifest_file, &encoded)?;
        Ok(Revision {
            id,
            manifest_file,
            manifest: manifest.clone(),
            parents: record.parents,
            clock: record.clock,
            message: record.message,
        })
    }

    /// Sync the old generation backup before the one atomic, mutable head.
    /// Errors after rename may mean the new head is visible: reopening the
    /// transaction verifies the actual state; callers must not blindly retry.
    fn publish_head(&self, next: &Head, previous: Option<&Head>) -> Result<()> {
        let actual: Option<Head> = read_optional_json(&self.root_dir, "head.json")?;
        if actual.as_ref() != previous {
            return Err(
                invalid("head changed despite the writer lock; reopen before retrying").into(),
            );
        }
        if let Some(previous) = previous {
            let backup = format!("head-{}-{}.json", previous.generation, previous.head);
            self.write_immutable(&self.backups_dir, &backup, &json_bytes(previous)?)?;
        }
        let pending = format!(".head-{}.pending", unique_name("head"));
        write_new_synced(&self.root_dir, &pending, &json_bytes(next)?)?;
        let from = CString::new(pending)?;
        let to = CString::new("head.json")?;
        let flags = if previous.is_none() {
            libc::RENAME_NOREPLACE
        } else {
            0
        };
        // SAFETY: descriptors and terminated strings live throughout the call.
        if unsafe {
            libc::renameat2(
                self.root_dir.as_raw_fd(),
                from.as_ptr(),
                self.root_dir.as_raw_fd(),
                to.as_ptr(),
                flags,
            )
        } != 0
        {
            return Err(io::Error::last_os_error().into());
        }
        confirm_head_durability(next, self.root_dir.sync_all())
    }

    fn write_immutable(&self, directory: &File, name: &str, bytes: &[u8]) -> Result<()> {
        match read_bytes(directory, name) {
            Ok(existing) if existing == bytes => {
                open_at(directory, name, libc::O_RDONLY)?.sync_all()?;
                directory.sync_all()?;
                return Ok(());
            }
            Ok(_) => {
                return Err(invalid("existing immutable file differs; nothing overwritten").into());
            }
            Err(error) if error.kind() == io::ErrorKind::NotFound => {}
            Err(error) => return Err(error.into()),
        }
        let pending = format!(".commit-{}.pending", unique_name(name));
        write_new_synced(directory, &pending, bytes)?;
        let from = CString::new(pending)?;
        let to = CString::new(name)?;
        // SAFETY: descriptors and terminated strings live throughout the call.
        // NOREPLACE protects immutable records even from uncooperative writers.
        if unsafe {
            libc::renameat2(
                directory.as_raw_fd(),
                from.as_ptr(),
                directory.as_raw_fd(),
                to.as_ptr(),
                libc::RENAME_NOREPLACE,
            )
        } != 0
        {
            return Err(io::Error::last_os_error().into());
        }
        directory.sync_all()?;
        Ok(())
    }
}

fn confirm_head_durability(attempted_head: &Head, result: io::Result<()>) -> Result<()> {
    result.map_err(|source| {
        Box::new(PublicationOutcomeUnknown {
            attempted_head: attempted_head.clone(),
            source,
        }) as content::Error
    })
}

fn validate_filename(name: &str) -> io::Result<()> {
    if name.is_empty() || name.contains('\0') || name.contains('/') || name == "." || name == ".." {
        return Err(invalid(
            "manifest must be a single filename inside this store",
        ));
    }
    Ok(())
}

fn validate_file_path(path: &str) -> io::Result<()> {
    if path.is_empty()
        || path.contains('\0')
        || path
            .split('/')
            .any(|part| part.is_empty() || part == "." || part == "..")
    {
        return Err(invalid(
            "file path must be relative, without empty, dot, or parent components",
        ));
    }
    Ok(())
}

fn open_directory(path: &Path) -> io::Result<File> {
    OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_DIRECTORY | libc::O_NOFOLLOW)
        .open(path)
}

fn ensure_directory(path: &Path) -> io::Result<File> {
    match DirBuilder::new().mode(0o700).create(path) {
        Ok(()) => {}
        Err(error) if error.kind() == io::ErrorKind::AlreadyExists => {}
        Err(error) => return Err(error),
    }
    open_directory(path)
}

fn open_at(directory: &File, name: &str, flags: i32) -> io::Result<File> {
    validate_filename(name)?;
    let name = CString::new(OsStr::new(name).as_bytes())?;
    // SAFETY: directory owns a live descriptor and name is terminated. Mode is
    // supplied for O_CREAT; a successful descriptor is adopted exactly once.
    let descriptor = unsafe {
        libc::openat(
            directory.as_raw_fd(),
            name.as_ptr(),
            flags | libc::O_NOFOLLOW | libc::O_CLOEXEC | libc::O_NONBLOCK,
            0o600,
        )
    };
    if descriptor < 0 {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: openat returned a new uniquely owned descriptor.
    let file = unsafe { File::from_raw_fd(descriptor) };
    if !file.metadata()?.is_file() {
        return Err(invalid("expected regular store file"));
    }
    Ok(file)
}

fn read_bytes(directory: &File, name: &str) -> io::Result<Vec<u8>> {
    let file = open_at(directory, name, libc::O_RDONLY)?;
    if file.metadata()?.len() > MAX_METADATA_BYTES {
        return Err(invalid("metadata exceeds 256 MiB limit"));
    }
    let mut bytes = Vec::new();
    file.take(MAX_METADATA_BYTES + 1).read_to_end(&mut bytes)?;
    if bytes.len() as u64 > MAX_METADATA_BYTES {
        return Err(invalid("metadata grew beyond limit"));
    }
    Ok(bytes)
}

fn read_json<T: serde::de::DeserializeOwned>(directory: &File, name: &str) -> Result<T> {
    Ok(serde_json::from_slice(&read_bytes(directory, name)?)?)
}

fn read_optional_json<T: serde::de::DeserializeOwned>(
    directory: &File,
    name: &str,
) -> Result<Option<T>> {
    match read_bytes(directory, name) {
        Ok(bytes) => Ok(Some(serde_json::from_slice(&bytes)?)),
        Err(error) if error.kind() == io::ErrorKind::NotFound => Ok(None),
        Err(error) => Err(error.into()),
    }
}

fn json_bytes<T: Serialize>(value: &T) -> Result<Vec<u8>> {
    let mut bytes = serde_json::to_vec(value)?;
    bytes.push(b'\n');
    if bytes.len() as u64 > MAX_METADATA_BYTES {
        return Err(invalid("serialized metadata exceeds 256 MiB limit").into());
    }
    Ok(bytes)
}

fn write_new_synced(directory: &File, name: &str, bytes: &[u8]) -> io::Result<()> {
    let mut file = open_at(
        directory,
        name,
        libc::O_WRONLY | libc::O_CREAT | libc::O_EXCL,
    )?;
    file.write_all(bytes)?;
    file.set_permissions(fs::Permissions::from_mode(0o444))?;
    file.sync_all()
}

fn now_ns() -> Result<i128> {
    Ok(SystemTime::now()
        .duration_since(UNIX_EPOCH)?
        .as_nanos()
        .try_into()?)
}

fn unique_name(seed: &str) -> String {
    let mut hash = blake3::Hasher::new();
    hash.update(seed.as_bytes());
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

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::fs::symlink;

    fn fixture(label: &str) -> PathBuf {
        let directory = Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("target/test-work")
            .join(format!("commit-{}", unique_name(label)));
        let source = directory.join("source");
        fs::create_dir_all(&source).unwrap();
        fs::write(source.join("file"), b"base\n").unwrap();
        fs::write(source.join("other"), b"other\n").unwrap();
        let root = directory.join("store");
        crate::store::import(&source, &root).unwrap();
        root
    }

    fn bytes(revision: &Revision, path: &str, root: &Path) -> Vec<u8> {
        content::read_file(&revision.manifest[path], &root.join("objects")).unwrap()
    }

    #[test]
    fn shared_publication_preserves_dag_cas_conflict_and_reopen_state() {
        let root = fixture("publication");
        let original = fs::read(root.join("manifest.json")).unwrap();
        let mut transaction = Transaction::open(&root).unwrap();
        assert!(
            Transaction::open(&root).is_err(),
            "a second writer must fail, not wait"
        );
        let initial = transaction.head().clone();
        let base = transaction.resolve_base("manifest.json").unwrap();
        assert_eq!(base.id, initial.head);
        assert_eq!(base.clock, 1);
        assert!(!root.join("commits").exists());
        assert!(fs::read_dir(&root).unwrap().all(|entry| {
            !entry
                .unwrap()
                .file_name()
                .to_string_lossy()
                .ends_with(".manifest.zst")
        }));
        let revision_bytes = fs::read(root.join(&base.manifest_file)).unwrap();
        let decoded = crate::metadata::decode(&revision_bytes).unwrap();
        let core_revision: sprig::Revision = serde_json::from_slice(&decoded).unwrap();
        assert_eq!(core_revision.manifest, base.manifest);
        assert_eq!(serde_json::to_vec(&core_revision).unwrap(), decoded);
        // The same logical revision reuses and fsyncs its existing inode.
        let inode = fs::metadata(root.join(&base.manifest_file)).unwrap().ino();
        assert_eq!(
            transaction
                .store_revision(&base.manifest, &[], IMPORT_MESSAGE)
                .unwrap()
                .id,
            base.id
        );
        assert_eq!(
            fs::metadata(root.join(&base.manifest_file)).unwrap().ino(),
            inode
        );
        assert!(matches!(
            transaction
                .publish(&base.id, base.manifest.clone(), "ignored", None)
                .unwrap(),
            PublishOutcome::Noop { .. }
        ));
        assert_eq!(transaction.head(), &initial);

        assert!(matches!(
            transaction
                .write_file(&base.id, "file", b"head\n", "first", Some(&initial))
                .unwrap(),
            PublishOutcome::Published { merged: false, .. }
        ));
        let first = transaction.head().clone();
        assert_eq!(first.generation, 1);
        let before = fs::read_dir(root.join("objects")).unwrap().count();
        let mismatch = transaction
            .write_file(
                &base.id,
                "blocked",
                b"must not write",
                "CAS",
                Some(&initial),
            )
            .unwrap_err();
        assert!(mismatch.downcast_ref::<ExpectedHeadMismatch>().is_some());
        assert_eq!(fs::read_dir(root.join("objects")).unwrap().count(), before);
        assert_eq!(transaction.head(), &first);

        let outcome = transaction
            .write_file(&base.id, "other", b"independent\n", "merge", None)
            .unwrap();
        let PublishOutcome::Published {
            candidate,
            candidate_manifest,
            manifest,
            merged: true,
            ..
        } = outcome
        else {
            panic!("independent stale changes must merge");
        };
        assert_eq!(
            transaction.revision(&candidate).unwrap().manifest_file,
            candidate_manifest
        );
        assert_ne!(
            candidate_manifest, manifest,
            "local candidate and merged projection differ"
        );
        assert!(root.join(candidate_manifest).is_file());
        let merged_head = transaction.head().clone();
        let merged = transaction.revision(&merged_head.head).unwrap();
        assert_eq!(
            transaction.durable_objects,
            content::referenced_chunks(&merged.manifest)
        );
        let (_, projected) =
            crate::store::ObjectStore::load(&root, OsStr::new(&merged.manifest_file)).unwrap();
        assert_eq!(projected, merged.manifest);
        assert_eq!(merged.parents.len(), 2);
        assert_eq!(merged.clock, 3);
        for parent in &merged.parents {
            assert_eq!(transaction.revision(parent).unwrap().clock, 2);
        }
        assert_eq!(merged.parents[0], first.head);
        assert!(transaction.resolve_base(&merged.parents[1]).is_ok());
        assert_eq!(
            transaction
                .revision(&merged.parents[1])
                .unwrap()
                .parents
                .as_slice(),
            std::slice::from_ref(&base.id)
        );
        assert_eq!(bytes(&merged, "file", &root), b"head\n");
        assert_eq!(bytes(&merged, "other", &root), b"independent\n");
        assert_eq!(merged.manifest["file"].id, base.manifest["file"].id);
        assert_eq!(transaction.history(100).unwrap().len(), 3);
        assert_eq!(
            transaction.resolve_base(&merged.manifest_file).unwrap().id,
            merged.id
        );
        assert!(matches!(
            transaction
                .write_file(&merged.id, "file", b"head\n", "ignored", None)
                .unwrap(),
            PublishOutcome::Noop { .. }
        ));
        assert_eq!(transaction.head(), &merged_head);

        let outcome = transaction
            .write_file(&base.id, "file", b"conflicting\n", "keep candidate", None)
            .unwrap();
        let PublishOutcome::Conflict {
            candidate,
            candidate_manifest,
            conflict_file,
            conflicts,
            ..
        } = outcome
        else {
            panic!("overlapping changes must not publish");
        };
        assert!(!conflicts.is_empty());
        assert!(root.join(conflict_file).is_file());
        assert!(root.join(candidate_manifest).is_file());
        assert_eq!(
            bytes(&transaction.revision(&candidate).unwrap(), "file", &root),
            b"conflicting\n"
        );
        assert!(transaction.resolve_base(&candidate).is_err());
        assert!(
            transaction
                .write_file(
                    &candidate,
                    "unrelated",
                    b"not a common base",
                    "reject",
                    None
                )
                .is_err()
        );
        assert_eq!(
            bytes(
                &transaction.revision(&merged_head.head).unwrap(),
                "file",
                &root
            ),
            b"head\n"
        );
        assert_eq!(transaction.head(), &merged_head);
        assert_eq!(fs::read(root.join("manifest.json")).unwrap(), original);
        assert!(
            root.join(format!("commit-backups/head-0-{}.json", initial.head))
                .is_file()
        );
        assert!(
            root.join(format!("commit-backups/head-1-{}.json", first.head))
                .is_file()
        );
        drop(transaction);
        let reopened = Transaction::open(&root).unwrap();
        assert_eq!(reopened.head(), &merged_head);
        assert_eq!(reopened.history(100).unwrap().len(), 3);
        assert_eq!(
            reopened.durable_objects,
            content::referenced_chunks(&merged.manifest)
        );

        // Exercise only error classification, without inducing a filesystem
        // failure or claiming that the attempted head was actually published.
        let error =
            confirm_head_durability(&merged_head, Err(io::Error::from_raw_os_error(libc::EIO)))
                .unwrap_err();
        let unknown = error.downcast_ref::<PublicationOutcomeUnknown>().unwrap();
        assert_eq!(unknown.attempted_head, merged_head);
        assert_eq!(unknown.source.raw_os_error(), Some(libc::EIO));
        assert!(std::error::Error::source(unknown).is_some());
        assert!(
            error
                .to_string()
                .contains("publication outcome unknown; reopen and inspect, do not retry")
        );
        // A revision filename is identity, even when later history restores the
        // exact same manifest. Legacy capture JSON remains content-based.
        let repeated_root = fixture("repeated-content");
        let mut repeated = Transaction::open(&repeated_root).unwrap();
        let first = repeated.resolve_base("manifest.json").unwrap();
        repeated
            .write_file(&first.id, "file", b"temporary", "change", None)
            .unwrap();
        let changed = repeated.head().head.clone();
        repeated
            .publish(&changed, first.manifest.clone(), "restore", None)
            .unwrap();
        assert_ne!(repeated.head().head, first.id);
        assert_eq!(
            repeated.resolve_base(&first.manifest_file).unwrap().id,
            first.id
        );
        assert_eq!(
            repeated.resolve_base("manifest.json").unwrap().id,
            repeated.head().head
        );
    }

    #[test]
    fn rejects_unsafe_or_foreign_bases_paths_and_damaged_candidates() {
        let root = fixture("validation");
        let mut transaction = Transaction::open(&root).unwrap();
        let initial = transaction.head().clone();
        let base = transaction.resolve_base("manifest.json").unwrap();
        for path in [
            "",
            "/escape",
            "../escape",
            "a/../escape",
            "a//b",
            "a/./b",
            "a/",
        ] {
            assert!(
                transaction
                    .write_file(&base.id, path, b"x", "invalid", None)
                    .is_err()
            );
        }
        assert!(
            transaction
                .write_file(&base.id, "missing/child", b"x", "invalid", None)
                .is_err()
        );
        assert!(transaction.resolve_base("../manifest.json").is_err());
        let mut foreign = base.manifest.clone();
        foreign.get_mut("file").unwrap().mode ^= 0o100;
        fs::write(
            root.join("unregistered.json"),
            json_bytes(&foreign).unwrap(),
        )
        .unwrap();
        assert!(transaction.resolve_base("unregistered.json").is_err());
        symlink(root.join("manifest.json"), root.join("linked.json")).unwrap();
        assert!(transaction.resolve_base("linked.json").is_err());
        let mut damaged = base.manifest.clone();
        damaged.get_mut("file").unwrap().kind = EntryKind::File {
            size: 1,
            chunks: vec!["0".repeat(64)],
        };
        assert!(
            transaction
                .publish(&base.id, damaged, "missing object", None)
                .is_err()
        );
        let mut wrong_size = base.manifest.clone();
        if let EntryKind::File { size, .. } = &mut wrong_size.get_mut("file").unwrap().kind {
            *size += 1;
        }
        assert!(
            transaction
                .publish(&base.id, wrong_size, "wrong size", None)
                .is_err()
        );
        assert_eq!(transaction.head(), &initial);

        assert!(matches!(
            transaction
                .write_file(&base.id, "new", b"new bytes", "new file", None)
                .unwrap(),
            PublishOutcome::Published { .. }
        ));
        let newest = transaction.revision(&transaction.head().head).unwrap();
        assert_eq!(newest.manifest["new"].mode, 0o644);
        assert_eq!(bytes(&newest, "new", &root), b"new bytes");
        // Durability evidence never skips validation of a known referenced
        // object. Damage only this synthetic fixture, retaining the original.
        let known = content::referenced_chunks(&newest.manifest)
            .into_iter()
            .next()
            .unwrap();
        assert!(transaction.durable_objects.contains(&known));
        let object = root.join("objects").join(&known);
        let retained = root.join("retained-test-object");
        fs::rename(&object, &retained).unwrap();
        let mut changed = newest.manifest.clone();
        changed.get_mut("file").unwrap().mode ^= 0o100;
        let before = transaction.head().clone();
        assert!(
            transaction
                .publish(&newest.id, changed.clone(), "missing durable", None)
                .is_err()
        );
        symlink(&retained, &object).unwrap();
        assert!(
            transaction
                .publish(&newest.id, changed.clone(), "linked durable", None)
                .is_err()
        );
        fs::rename(&object, root.join("retained-test-link")).unwrap();
        fs::create_dir(&object).unwrap();
        assert!(
            transaction
                .publish(&newest.id, changed.clone(), "directory durable", None)
                .is_err()
        );
        fs::rename(&object, root.join("retained-test-directory")).unwrap();
        let damaged = File::create(&object).unwrap();
        for length in [0, MAX_CHUNK_BYTES as u64 + 1, 1] {
            damaged.set_len(length).unwrap();
            assert!(
                transaction
                    .publish(&newest.id, changed.clone(), "damaged durable", None)
                    .is_err()
            );
        }
        assert_eq!(transaction.head(), &before);
        fs::rename(&retained, &object).unwrap();
        drop(transaction);

        // An older experimental history is rejected, never reset or migrated.
        let old_manifest = newest
            .manifest_file
            .replace(".revision.zst", ".manifest.json");
        fs::write(
            root.join(&old_manifest),
            json_bytes(&newest.manifest).unwrap(),
        )
        .unwrap();
        let old_record = json_bytes(&serde_json::json!({
            "manifest": old_manifest, "parents": newest.parents, "message": newest.message,
        }))
        .unwrap();
        let old_id = blake3::hash(&old_record).to_hex().to_string();
        fs::create_dir_all(root.join("commits")).unwrap();
        fs::write(
            root.join("commits").join(format!("{old_id}.json")),
            &old_record,
        )
        .unwrap();
        fs::rename(
            root.join("head.json"),
            root.join("retained-new-format-head"),
        )
        .unwrap();
        let old_head = json_bytes(&Head {
            head: old_id,
            generation: before.generation,
        })
        .unwrap();
        fs::write(root.join("head.json"), &old_head).unwrap();
        let before_names: BTreeSet<_> = fs::read_dir(&root)
            .unwrap()
            .map(|e| e.unwrap().file_name())
            .collect();
        assert!(Transaction::open(&root).is_err());
        let after_names: BTreeSet<_> = fs::read_dir(&root)
            .unwrap()
            .map(|e| e.unwrap().file_name())
            .collect();
        assert_eq!(before_names, after_names);
        assert_eq!(fs::read(root.join("head.json")).unwrap(), old_head);

        let linked_root = root.parent().unwrap().join("linked-store");
        symlink(&root, &linked_root).unwrap();
        assert!(Transaction::open(&linked_root).is_err());
        let bad_lock_root = fixture("linked-lock");
        symlink(
            bad_lock_root.join("manifest.json"),
            bad_lock_root.join("commit.lock"),
        )
        .unwrap();
        assert!(Transaction::open(&bad_lock_root).is_err());
    }
}
