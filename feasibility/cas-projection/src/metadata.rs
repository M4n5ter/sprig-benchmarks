//! Bounded lossless storage for immutable manifest JSON bytes.
//!
//! Identities remain hashes of the uncompressed JSON. File opening and manifest
//! model validation belong to the caller; this module only validates the codec.

use std::io::{self, Read, Write};

use crate::store::Result;

pub(crate) const MAX_METADATA_BYTES: usize = 256 * 1024 * 1024;
const WINDOW_LOG: u32 = 20;

/// Match the production metadata encoder's level, window and checksum settings.
pub(crate) fn encode(bytes: &[u8]) -> Result<Vec<u8>> {
    check_size(bytes.len(), MAX_METADATA_BYTES)?;
    let mut encoder = zstd::stream::write::Encoder::new(Vec::new(), 1)?;
    encoder.window_log(WINDOW_LOG)?;
    encoder.include_checksum(true)?;
    encoder.set_pledged_src_size(Some(bytes.len() as u64))?;
    encoder.write_all(bytes)?;
    let compressed = encoder.finish()?;
    check_size(compressed.len(), MAX_METADATA_BYTES)?;
    Ok(compressed)
}

pub(crate) fn decode(bytes: &[u8]) -> Result<Vec<u8>> {
    decode_bounded(bytes, MAX_METADATA_BYTES)
}

fn decode_bounded(bytes: &[u8], limit: usize) -> Result<Vec<u8>> {
    check_size(bytes.len(), MAX_METADATA_BYTES)?;
    let mut decoder = zstd::stream::read::Decoder::with_buffer(bytes)?.single_frame();
    decoder.window_log_max(WINDOW_LOG)?;
    // Never allocate from an untrusted pledged frame size. Read through EOF
    // (including the epilogue/checksum), unless the decoded limit is exceeded.
    let mut decoded = Vec::new();
    (&mut decoder)
        .take(limit as u64 + 1)
        .read_to_end(&mut decoded)?;
    check_size(decoded.len(), limit)?;
    if !decoder.finish().is_empty() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "trailing data after metadata frame",
        )
        .into());
    }
    Ok(decoded)
}

fn check_size(size: usize, limit: usize) -> io::Result<()> {
    if size > limit {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "manifest exceeds the prototype's metadata limit",
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bounded_single_frame_rejects_corruption_truncation_and_trailing_data() {
        let raw = br#"{"file":"metadata"}"#;
        let frame = encode(raw).unwrap();
        assert_eq!(decode(&frame).unwrap(), raw);
        assert_eq!(decode_bounded(&frame, raw.len()).unwrap(), raw);
        assert!(decode_bounded(&frame, raw.len() - 1).is_err());
        assert!(decode(b"{}").is_err());
        assert!(decode(&[]).is_err());
        for length in 0..frame.len() {
            assert!(decode(&frame[..length]).is_err());
        }
        let mut corrupt = frame.clone();
        *corrupt.last_mut().unwrap() ^= 1;
        assert!(decode(&corrupt).is_err());
        let mut trailing = frame.clone();
        trailing.push(0);
        assert!(decode(&trailing).is_err());
        let mut concatenated = frame.clone();
        concatenated.extend_from_slice(&frame);
        assert!(decode(&concatenated).is_err());
        assert!(check_size(MAX_METADATA_BYTES + 1, MAX_METADATA_BYTES).is_err());
    }
}
