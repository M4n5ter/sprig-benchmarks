//! Durable import and bounded, verified object reads.

use std::collections::HashMap;
use std::ffi::{CString, OsStr};
use std::fs::{self, DirBuilder, File, OpenOptions};
use std::io::{self, Read, Write};
use std::os::fd::{AsRawFd, FromRawFd};
use std::os::unix::ffi::OsStrExt;
use std::os::unix::fs::{DirBuilderExt, OpenOptionsExt};
use std::path::{Component, Path};

use sprig::content::{self, Manifest, Observed};

pub type Result<T> = std::result::Result<T, content::Error>;
pub const MAX_CHUNK_BYTES: usize = 256 * 1024;
pub const CACHE_BYTES: usize = 16 * 1024 * 1024;
const MAX_MANIFEST_BYTES: u64 = 256 * 1024 * 1024;

/// Captures a trusted, quiescent source into a fresh library root. On failure,
/// incomplete objects may remain, but no partial manifest is published.
pub fn import(source: &Path, root: &Path) -> Result<serde_json::Value> {
    let source = fs::canonicalize(source)?;
    let parent = root
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or(Path::new("."));
    let parent = fs::canonicalize(parent)?;
    let name = root
        .file_name()
        .ok_or_else(|| invalid("root needs a new directory name"))?;
    let root = parent.join(name);
    if root.starts_with(&source) {
        return Err(invalid("library root must be outside the captured source").into());
    }
    DirBuilder::new().mode(0o700).create(&root)?;
    File::open(&parent)?.sync_all()?;
    let (manifest, _) = content::capture(&source, &root.join("objects"), &Observed::new())?;
    let temporary = root.join("manifest.json.pending");
    let mut output = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(&temporary)?;
    serde_json::to_writer(&mut output, &manifest)?;
    output.write_all(b"\n")?;
    output.sync_all()?;
    fs::rename(&temporary, root.join("manifest.json"))?;
    File::open(&root)?.sync_all()?;
    let hashes = content::referenced_chunks(&manifest);
    let stored_bytes: u64 = hashes
        .iter()
        .map(|hash| fs::metadata(root.join("objects").join(hash)).map(|m| m.len()))
        .collect::<io::Result<Vec<_>>>()?
        .iter()
        .sum();
    let logical_bytes: u64 = manifest
        .values()
        .map(|entry| match entry.kind {
            content::EntryKind::File { size, .. } => size,
            _ => 0,
        })
        .sum();
    Ok(
        serde_json::json!({"event": "imported", "root": root, "manifest": "manifest.json", "entries": manifest.len(), "unique_chunks": hashes.len(), "logical_bytes": logical_bytes, "stored_object_bytes": stored_bytes}),
    )
}

/// Holds directory descriptors so object lookup never follows leaf symlinks.
/// Ancestor directories and the library itself must remain trusted and immutable.
pub struct ObjectStore {
    objects: File,
}

impl ObjectStore {
    pub fn load(root: &Path, manifest_name: &OsStr) -> Result<(Self, Manifest)> {
        if Path::new(manifest_name).components().count() != 1
            || !matches!(
                Path::new(manifest_name).components().next(),
                Some(Component::Normal(_))
            )
        {
            return Err(
                invalid("manifest must be a single filename inside the library root").into(),
            );
        }
        // Strip trailing separators before O_NOFOLLOW, so `symlink/` cannot
        // silently turn the final symlink into an ancestor during open.
        let normalized_root: std::path::PathBuf = root.components().collect();
        let root = OpenOptions::new()
            .read(true)
            .custom_flags(libc::O_DIRECTORY | libc::O_NOFOLLOW)
            .open(normalized_root)?;
        let mut manifest_file = open_at(&root, manifest_name, false)?;
        if manifest_file.metadata()?.len() > MAX_MANIFEST_BYTES {
            return Err(invalid("manifest exceeds the prototype's 256 MiB metadata limit").into());
        }
        let mut bytes = Vec::new();
        (&mut manifest_file)
            .take(MAX_MANIFEST_BYTES + 1)
            .read_to_end(&mut bytes)?;
        if bytes.len() as u64 > MAX_MANIFEST_BYTES {
            return Err(invalid("manifest grew beyond metadata limit").into());
        }
        let manifest: Manifest = serde_json::from_slice(&bytes)?;
        content::validate_manifest(&manifest)?;
        let objects = open_at(&root, OsStr::new("objects"), true)?;
        Ok((Self { objects }, manifest))
    }

    pub fn chunk_length(&self, hash: &str) -> io::Result<usize> {
        let length = self.open_chunk(hash)?.metadata()?.len();
        if length == 0 || length > MAX_CHUNK_BYTES as u64 {
            return Err(invalid("chunk length is outside 1..=256 KiB"));
        }
        Ok(length as usize)
    }

    fn open_chunk(&self, hash: &str) -> io::Result<File> {
        validate_hash(hash)?;
        open_at(&self.objects, OsStr::new(hash), false)
    }

    fn verified_chunk(&self, hash: &str) -> io::Result<Vec<u8>> {
        let file = self.open_chunk(hash)?;
        let length = file.metadata()?.len();
        if length == 0 || length > MAX_CHUNK_BYTES as u64 {
            return Err(invalid("invalid chunk length"));
        }
        let mut bytes = Vec::with_capacity(length as usize);
        file.take(MAX_CHUNK_BYTES as u64 + 1)
            .read_to_end(&mut bytes)?;
        if bytes.len() as u64 != length || blake3::hash(&bytes).to_hex().as_str() != hash {
            return Err(invalid(format!("corrupt content-addressed object: {hash}")));
        }
        Ok(bytes)
    }
}

fn open_at(directory: &File, name: &OsStr, is_directory: bool) -> io::Result<File> {
    let name = CString::new(name.as_bytes()).map_err(|_| invalid("NUL in filename"))?;
    let flags = libc::O_RDONLY
        | libc::O_CLOEXEC
        | libc::O_NOFOLLOW
        | libc::O_NONBLOCK
        | if is_directory { libc::O_DIRECTORY } else { 0 };
    // SAFETY: directory owns a live descriptor; name is a terminated CString.
    // A successful descriptor is adopted exactly once by File below.
    let descriptor = unsafe { libc::openat(directory.as_raw_fd(), name.as_ptr(), flags) };
    if descriptor < 0 {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: openat returned this new, uniquely owned valid descriptor.
    let file = unsafe { File::from_raw_fd(descriptor) };
    let metadata = file.metadata()?;
    if !(if is_directory {
        metadata.is_dir()
    } else {
        metadata.is_file()
    }) {
        return Err(invalid("unexpected non-regular library entry"));
    }
    Ok(file)
}

pub fn validate_hash(hash: &str) -> io::Result<()> {
    if hash.len() != 64
        || !hash
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        return Err(invalid(
            "chunk address must be 64 lowercase hexadecimal bytes",
        ));
    }
    Ok(())
}

struct CachedChunk {
    bytes: Vec<u8>,
    last_used: u64,
}

/// Content-only memory is capped; metadata and one response buffer are separate.
pub struct ChunkCache {
    chunks: HashMap<String, CachedChunk>,
    bytes: usize,
    limit: usize,
    clock: u64,
    pub hits: u64,
    pub misses: u64,
    pub verified_bytes: u64,
}

impl ChunkCache {
    pub fn new(limit: usize) -> Self {
        Self {
            chunks: HashMap::new(),
            bytes: 0,
            limit,
            clock: 0,
            hits: 0,
            misses: 0,
            verified_bytes: 0,
        }
    }

    pub fn bytes(&self) -> usize {
        self.bytes
    }

    pub fn get<'a>(&'a mut self, store: &ObjectStore, hash: &str) -> io::Result<&'a [u8]> {
        // Validate even cache hits; no caller can use a non-canonical address.
        validate_hash(hash)?;
        self.clock = self
            .clock
            .checked_add(1)
            .ok_or_else(|| invalid("cache clock exhausted"))?;
        if !self.chunks.contains_key(hash) {
            self.misses += 1;
            let bytes = store.verified_chunk(hash)?;
            if bytes.len() > self.limit {
                return Err(invalid("cache limit is smaller than this chunk"));
            }
            while self.bytes + bytes.len() > self.limit {
                let oldest = self
                    .chunks
                    .iter()
                    .min_by_key(|(_, chunk)| chunk.last_used)
                    .map(|(hash, _)| hash.clone())
                    .expect("nonempty cache exceeds limit");
                self.bytes -= self
                    .chunks
                    .remove(&oldest)
                    .expect("oldest chunk exists")
                    .bytes
                    .len();
            }
            self.bytes += bytes.len();
            self.verified_bytes += bytes.len() as u64;
            self.chunks.insert(
                hash.to_owned(),
                CachedChunk {
                    bytes,
                    last_used: self.clock,
                },
            );
        } else {
            self.hits += 1;
        }
        let cached = self
            .chunks
            .get_mut(hash)
            .expect("chunk inserted or already cached");
        cached.last_used = self.clock;
        Ok(&cached.bytes)
    }
}

pub(crate) fn invalid(message: impl Into<String>) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, message.into())
}
