//! Prototype size policy over the shared production metadata codec.
use crate::store::{Result, invalid, validate_hash};
use std::io;
pub(crate) const MAX_METADATA_BYTES: usize = 256 * 1024 * 1024;
pub(crate) fn encode(bytes: &[u8]) -> Result<Vec<u8>> {
    check_size(bytes.len(), MAX_METADATA_BYTES)?;
    let encoded = sprig::metadata::encode(bytes)?;
    check_size(encoded.len(), MAX_METADATA_BYTES)?;
    Ok(encoded)
}
pub(crate) fn decode(bytes: &[u8]) -> Result<Vec<u8>> {
    decode_bounded(bytes, MAX_METADATA_BYTES)
}
fn decode_bounded(bytes: &[u8], limit: usize) -> Result<Vec<u8>> {
    check_size(bytes.len(), MAX_METADATA_BYTES)?;
    sprig::metadata::decode(bytes, Some(limit))
}
fn check_size(size: usize, limit: usize) -> io::Result<()> {
    if size > limit {
        return Err(invalid("metadata exceeds limit"));
    }
    Ok(())
}
/// The on-disk schema is production Revision, never a second adapter model.
pub(crate) fn decode_revision(bytes: &[u8], id: &str) -> Result<sprig::Revision> {
    validate_hash(id)?;
    let bytes = decode(bytes)?;
    if blake3::hash(&bytes).to_hex().as_str() != id {
        return Err(invalid("immutable revision does not match its address").into());
    }
    let revision: sprig::Revision = serde_json::from_slice(&bytes)?;
    if revision.clock == 0 || revision.parents.len() > 2 {
        return Err(invalid("invalid revision clock or parents").into());
    }
    for parent in &revision.parents {
        validate_hash(parent)?;
    }
    sprig::content::validate_manifest(&revision.manifest)?;
    Ok(revision)
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
