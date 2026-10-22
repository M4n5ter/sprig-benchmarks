//! Mount-independent inode index and random-access reads, testable without FUSE.

use std::collections::{BTreeMap, HashMap};
use std::ffi::{OsStr, OsString};
use std::io;
use std::path::Path;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use fuser::{FileAttr, FileType};
use sprig::content::EntryKind;

use crate::store::{self, ChunkCache, ObjectStore, Result};

pub const ROOT_INODE: u64 = 1;
pub const MAX_READ_BYTES: usize = 1024 * 1024;
/// Advisory source identity, not proof that an OverlayFS upper entry is unchanged.
pub const ORIGIN_XATTR: &str = "user.sprig.prototype.origin";
// Conservative Linux readlink reply bound for the intended 4 KiB-page runner.
pub const MAX_SYMLINK_BYTES: usize = 4095;

struct ChunkSpan {
    hash: String,
    start: u64,
    end: u64,
}

enum Data {
    Directory { children: Vec<DirectoryEntry> },
    File { chunks: Vec<ChunkSpan> },
    Symlink { target: Vec<u8> },
}

struct Node {
    attr: FileAttr,
    parent: u64,
    data: Data,
    origin: Vec<u8>,
}

pub struct DirectoryEntry {
    pub name: OsString,
    pub inode: u64,
    pub kind: FileType,
}

/// Inodes follow lexicographically sorted manifest paths, rooted at 1. They are
/// stable across mounts of the same immutable manifest, not across revisions.
pub struct Projection {
    nodes: Vec<Node>,
    store: ObjectStore,
    cache: ChunkCache,
    logical_bytes: u64,
    unique_chunks: usize,
    read_requests: u64,
    returned_bytes: u64,
}

impl Projection {
    pub fn load(root: &Path, manifest_name: &OsStr, uid: u32, gid: u32) -> Result<Self> {
        let (store, manifest) = ObjectStore::load(root, manifest_name)?;
        // Hash the validated manifest value, not its filename, JSON whitespace,
        // or a branch name that may later refer to a different snapshot.
        let manifest_hash = blake3::hash(&serde_json::to_vec(&manifest)?)
            .to_hex()
            .to_string();
        let paths: BTreeMap<_, _> = manifest
            .keys()
            .enumerate()
            .map(|(index, path)| (path.clone(), index as u64 + ROOT_INODE))
            .collect();
        let mut lengths = HashMap::new();
        let mut nodes = Vec::with_capacity(manifest.len());
        let mut logical_bytes = 0_u64;
        for (path, entry) in manifest {
            if path.split('/').any(|name| name.len() > 255) {
                return Err(store::invalid("manifest component exceeds 255 bytes").into());
            }
            let inode = paths[&path];
            let parent_path = path.rsplit_once('/').map_or("", |(parent, _)| parent);
            let parent = paths[parent_path];
            let modified = modified_time(entry.modified_ns)?;
            let (kind, size, data) = match entry.kind {
                EntryKind::Directory => (
                    FileType::Directory,
                    0,
                    Data::Directory {
                        children: Vec::new(),
                    },
                ),
                EntryKind::File { size, chunks } => {
                    let mut offset = 0_u64;
                    let mut spans = Vec::with_capacity(chunks.len());
                    for hash in chunks {
                        let length = match lengths.get(&hash) {
                            Some(length) => *length,
                            None => {
                                let length = store.chunk_length(&hash)?;
                                lengths.insert(hash.clone(), length);
                                length
                            }
                        };
                        let end = offset
                            .checked_add(length as u64)
                            .ok_or_else(|| store::invalid("file size overflow"))?;
                        spans.push(ChunkSpan {
                            hash,
                            start: offset,
                            end,
                        });
                        offset = end;
                    }
                    if offset != size {
                        return Err(store::invalid(format!(
                            "chunk lengths do not match manifest size at {path:?}"
                        ))
                        .into());
                    }
                    logical_bytes = logical_bytes
                        .checked_add(size)
                        .ok_or_else(|| store::invalid("logical byte count overflow"))?;
                    (FileType::RegularFile, size, Data::File { chunks: spans })
                }
                EntryKind::Symlink { target } => {
                    if target.len() > MAX_SYMLINK_BYTES {
                        return Err(store::invalid(
                            "symlink target exceeds the 4095-byte Linux reply limit",
                        )
                        .into());
                    }
                    (
                        FileType::Symlink,
                        target.len() as u64,
                        Data::Symlink { target },
                    )
                }
            };
            let attr = FileAttr {
                ino: inode,
                size,
                blocks: size.div_ceil(512),
                atime: modified,
                mtime: modified,
                ctime: modified,
                crtime: modified,
                kind,
                perm: entry.mode as u16,
                nlink: if kind == FileType::Directory { 2 } else { 1 },
                uid,
                gid,
                rdev: 0,
                flags: 0,
                blksize: 4096,
            };
            nodes.push(Node {
                attr,
                parent,
                data,
                origin: serde_json::to_vec(&[manifest_hash.as_str(), path.as_str()])?,
            });
            if inode != ROOT_INODE {
                let parent = &mut nodes[(parent - ROOT_INODE) as usize];
                let Data::Directory { children } = &mut parent.data else {
                    unreachable!("manifest parents validated")
                };
                children.push(DirectoryEntry {
                    name: OsString::from(path.rsplit('/').next().expect("nonroot path has a name")),
                    inode,
                    kind,
                });
                if kind == FileType::Directory {
                    parent.attr.nlink = parent
                        .attr
                        .nlink
                        .checked_add(1)
                        .ok_or_else(|| store::invalid("directory link count overflow"))?;
                }
            }
        }
        // Full paths are ordered, but explicit sibling sorting makes the lookup
        // precondition independent from that implementation detail.
        for node in &mut nodes {
            if let Data::Directory { children } = &mut node.data {
                children.sort_by(|left, right| left.name.cmp(&right.name));
            }
        }
        Ok(Self {
            nodes,
            store,
            cache: ChunkCache::new(store::CACHE_BYTES),
            logical_bytes,
            unique_chunks: lengths.len(),
            read_requests: 0,
            returned_bytes: 0,
        })
    }

    fn node(&self, inode: u64) -> io::Result<&Node> {
        inode
            .checked_sub(ROOT_INODE)
            .and_then(|index| usize::try_from(index).ok())
            .and_then(|index| self.nodes.get(index))
            .ok_or_else(|| io::Error::from_raw_os_error(libc::ENOENT))
    }

    pub fn getattr(&self, inode: u64) -> io::Result<FileAttr> {
        Ok(self.node(inode)?.attr)
    }

    /// JSON `[manifest_digest, original_utf8_path]` for this immutable source.
    /// Copy-up may preserve this hint even after content changes: consumers must
    /// independently validate mount binding and upper-layer absence before reuse.
    pub fn origin(&self, inode: u64) -> io::Result<&[u8]> {
        let node = self.node(inode)?;
        // Linux forbids user.* attributes on symlinks. Advertising one would
        // make OverlayFS copy-up fail while copying its xattr list.
        if node.attr.kind == FileType::Symlink {
            return Err(io::Error::from_raw_os_error(libc::ENODATA));
        }
        Ok(&node.origin)
    }

    pub fn lookup(&self, parent: u64, name: &OsStr) -> io::Result<u64> {
        let node = self.node(parent)?;
        let Data::Directory { children } = &node.data else {
            return Err(io::Error::from_raw_os_error(libc::ENOTDIR));
        };
        if name == "." {
            return Ok(parent);
        }
        if name == ".." {
            return Ok(node.parent);
        }
        children
            .binary_search_by(|entry| entry.name.as_os_str().cmp(name))
            .map(|index| children[index].inode)
            .map_err(|_| io::Error::from_raw_os_error(libc::ENOENT))
    }

    pub fn directory(&self, inode: u64) -> io::Result<(u64, &[DirectoryEntry])> {
        let node = self.node(inode)?;
        match &node.data {
            Data::Directory { children } => Ok((node.parent, children)),
            _ => Err(io::Error::from_raw_os_error(libc::ENOTDIR)),
        }
    }

    pub fn readlink(&self, inode: u64) -> io::Result<&[u8]> {
        match &self.node(inode)?.data {
            Data::Symlink { target } => Ok(target),
            _ => Err(io::Error::from_raw_os_error(libc::EINVAL)),
        }
    }

    pub fn open(&self, inode: u64, flags: i32, directory: bool) -> io::Result<()> {
        let node = self.node(inode)?;
        if flags & libc::O_ACCMODE != libc::O_RDONLY
            || flags & (libc::O_TRUNC | libc::O_CREAT | libc::O_APPEND) != 0
        {
            return Err(io::Error::from_raw_os_error(libc::EROFS));
        }
        match (&node.data, directory) {
            (Data::Directory { .. }, true) | (Data::File { .. }, false) => Ok(()),
            (_, true) => Err(io::Error::from_raw_os_error(libc::ENOTDIR)),
            (Data::Directory { .. }, false) => Err(io::Error::from_raw_os_error(libc::EISDIR)),
            (Data::Symlink { .. }, false) => Err(io::Error::from_raw_os_error(libc::ELOOP)),
        }
    }

    /// The kernel checks permissions (including supplementary groups) via the
    /// mandatory default_permissions mount option. This fallback is conservative
    /// when called directly and checks the request's primary uid/gid only.
    pub fn access(&self, inode: u64, uid: u32, gid: u32, mask: i32) -> io::Result<()> {
        let attr = self.getattr(inode)?;
        if mask & !(libc::R_OK | libc::W_OK | libc::X_OK) != 0 {
            return Err(io::Error::from_raw_os_error(libc::EINVAL));
        }
        if mask & libc::W_OK != 0 {
            return Err(io::Error::from_raw_os_error(libc::EROFS));
        }
        let requested = mask as u16;
        let permission = if uid == attr.uid {
            attr.perm >> 6
        } else if gid == attr.gid {
            attr.perm >> 3
        } else {
            attr.perm
        } & 0o7;
        if uid == 0 {
            if mask & libc::X_OK == 0 || attr.kind == FileType::Directory || attr.perm & 0o111 != 0
            {
                return Ok(());
            }
        } else if permission & requested == requested {
            return Ok(());
        }
        Err(io::Error::from_raw_os_error(libc::EACCES))
    }

    /// Allocates only the requested response, never a whole file. Chunk lookup
    /// starts with binary search, then touches just the overlapping spans.
    pub fn read(&mut self, inode: u64, offset: i64, size: u32) -> io::Result<Vec<u8>> {
        if offset < 0 || size as usize > MAX_READ_BYTES {
            return Err(io::Error::from_raw_os_error(libc::EINVAL));
        }
        let index = inode
            .checked_sub(ROOT_INODE)
            .and_then(|n| usize::try_from(n).ok())
            .ok_or_else(|| io::Error::from_raw_os_error(libc::ENOENT))?;
        let node = self
            .nodes
            .get(index)
            .ok_or_else(|| io::Error::from_raw_os_error(libc::ENOENT))?;
        let chunks = match &node.data {
            Data::File { chunks } => chunks,
            Data::Directory { .. } => return Err(io::Error::from_raw_os_error(libc::EISDIR)),
            Data::Symlink { .. } => return Err(io::Error::from_raw_os_error(libc::EINVAL)),
        };
        self.read_requests += 1;
        let start = offset as u64;
        let end = start.saturating_add(size as u64).min(node.attr.size);
        if start >= end {
            return Ok(Vec::new());
        }
        let mut output = Vec::with_capacity((end - start) as usize);
        let first = chunks.partition_point(|chunk| chunk.end <= start);
        for chunk in chunks[first..].iter().take_while(|chunk| chunk.start < end) {
            let bytes = self.cache.get(&self.store, &chunk.hash)?;
            if bytes.len() as u64 != chunk.end - chunk.start {
                return Err(store::invalid("chunk length changed since indexing"));
            }
            let from = start.saturating_sub(chunk.start) as usize;
            let to = (end.min(chunk.end) - chunk.start) as usize;
            output.extend_from_slice(&bytes[from..to]);
        }
        self.returned_bytes += output.len() as u64;
        Ok(output)
    }

    pub fn stats(&self) -> serde_json::Value {
        serde_json::json!({"entries": self.nodes.len(), "logical_bytes": self.logical_bytes, "unique_chunks": self.unique_chunks, "read_requests": self.read_requests, "returned_bytes": self.returned_bytes, "cache_bytes": self.cache.bytes(), "cache_limit_bytes": store::CACHE_BYTES, "cache_hits": self.cache.hits, "cache_misses": self.cache.misses, "verified_chunk_bytes": self.cache.verified_bytes})
    }

    pub fn total_bytes(&self) -> u64 {
        self.logical_bytes
    }
    pub fn inode_count(&self) -> u64 {
        self.nodes.len() as u64
    }
}

fn modified_time(nanoseconds: i128) -> io::Result<SystemTime> {
    // fuser 0.16 does not normalize negative fractional timestamps correctly.
    // Fail closed for all pre-epoch times rather than expose incorrect metadata.
    if nanoseconds < 0 {
        return Err(store::invalid(
            "pre-1970 mtime is unsupported by this fuser 0.16 projection",
        ));
    }
    let seconds = u64::try_from(nanoseconds / 1_000_000_000)
        .map_err(|_| store::invalid("mtime out of range"))?;
    let duration = Duration::new(seconds, (nanoseconds % 1_000_000_000) as u32);
    UNIX_EPOCH
        .checked_add(duration)
        .ok_or_else(|| store::invalid("mtime out of range"))
}
