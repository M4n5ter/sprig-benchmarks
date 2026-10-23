//! Unmounted diagnostic: exact recurring trees must reuse immutable manifests.
use sprig::content;
use sprig_cas_projection_prototype::{commit::Transaction, store};
use std::path::Path;
fn main() -> store::Result<()> {
    let args: Vec<_> = std::env::args().collect();
    let source = Path::new(&args[1]);
    let root = Path::new(&args[2]);
    store::import(source, root)?;
    let mut tx = Transaction::open(root)?;
    let initial = tx.resolve_base("manifest.json")?.manifest;
    let path = "regular/s000/f192.dat";
    let mut alternate = initial.clone();
    alternate.get_mut(path).ok_or("missing fixture path")?.kind =
        content::put_bytes(&vec![b'B'; 49_152], &root.join("objects"))?;
    for step in 0..100 {
        let base = tx.head().head.clone();
        let manifest = if step % 2 == 0 { &alternate } else { &initial };
        tx.publish(&base, manifest.clone(), "recurring tree", None)?;
    }
    assert_eq!(tx.history(1000)?.len(), 101);
    let manifests = std::fs::read_dir(root)?
        .filter_map(Result::ok)
        .filter(|e| e.file_name().to_string_lossy().ends_with(".manifest.zst"))
        .count();
    assert_eq!(manifests, 2);
    assert_eq!(tx.revision(&tx.head().head)?.manifest, initial);
    println!("{{\"commits\":100,\"history\":101,\"distinct_manifests\":{manifests}}}");
    Ok(())
}
