use std::collections::BTreeMap;
use std::env;
use std::ffi::{OsStr, OsString};
use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::os::unix::fs::OpenOptionsExt;
use std::path::{Component, Path};

use sprig_cas_projection_prototype::{capture, commit, fuse, store};

const USAGE: &str = "Experimental CAS projection and commit engine (not full Sprig)\n\n  sprig-cas-projection-prototype import --source DIR --root NEW_DIR\n  sprig-cas-projection-prototype mount --root DIR --mountpoint EMPTY_DIR [--manifest FILENAME] [--allow-other]\n\nMount runs in the foreground on an explicitly authorized Linux root CI runner only. --allow-other is off by default and explicitly exposes\nread access to other users, subject to file modes; intended for isolated root CI OverlayFS tests.\nExperiment commands: capture/checkpoint --root DIR --projection-base FILENAME --merged DIR --upper DIR --lower DIR [--base COMMIT_OR_MANIFEST] [--output NEW_FILENAME]; write --root DIR --base REF --path PATH --text TEXT; head/history --root DIR. Expected CAS requires both --expected-head and --expected-generation. No configuration or persistent helper is installed. One direct mount attempt; no helper fallback. External ordinary unmount only; no lazy/force cleanup.";

fn main() {
    if let Err(error) = run() {
        eprintln!(
            "{}",
            serde_json::json!({"event": "error", "error": error.to_string()})
        );
        std::process::exit(1);
    }
}

fn run() -> store::Result<()> {
    let mut arguments = env::args_os().skip(1);
    let Some(command) = arguments.next() else {
        println!("{USAGE}");
        return Ok(());
    };
    if command == "--help" || command == "-h" {
        println!("{USAGE}");
        return Ok(());
    }
    if ![
        "import",
        "mount",
        "capture",
        "checkpoint",
        "write",
        "head",
        "history",
        "verify",
        "read",
    ]
    .iter()
    .any(|name| command == *name)
    {
        return Err(
            "expected import, mount, capture, checkpoint, write, head or history; use --help"
                .into(),
        );
    }
    let mut values = BTreeMap::new();
    let mut allow_other = false;
    while let Some(option) = arguments.next() {
        if option == "--help" || option == "-h" {
            println!("{USAGE}");
            return Ok(());
        }
        if option == "--allow-other" && command == "mount" && !allow_other {
            allow_other = true;
            continue;
        }
        let valid = if command == "import" {
            option == "--source" || option == "--root"
        } else if command == "mount" {
            option == "--root" || option == "--manifest" || option == "--mountpoint"
        } else {
            [
                "--root",
                "--base",
                "--projection-base",
                "--identity-base",
                "--merged",
                "--upper",
                "--lower",
                "--output",
                "--manifest",
                "--message",
                "--path",
                "--text",
                "--expected-head",
                "--expected-generation",
            ]
            .iter()
            .any(|name| option == *name)
        };
        if !valid {
            return Err(
                format!("unknown or duplicate option: {}", option.to_string_lossy()).into(),
            );
        }
        let value = arguments
            .next()
            .ok_or_else(|| format!("missing value for {}", option.to_string_lossy()))?;
        if option != "--text" && (value.is_empty() || value.to_string_lossy().starts_with("--")) {
            return Err(format!("invalid value for {}", option.to_string_lossy()).into());
        }
        if values.insert(option.clone(), value).is_some() {
            return Err(format!("duplicate option: {}", option.to_string_lossy()).into());
        }
    }
    let required = |name: &str| -> store::Result<&OsString> {
        values
            .get(OsStr::new(name))
            .ok_or_else(|| format!("missing {name}").into())
    };
    let root = Path::new(required("--root")?);
    if command == "import" {
        println!("{}", store::import(Path::new(required("--source")?), root)?);
    } else if command == "mount" {
        let manifest = values
            .get(OsStr::new("--manifest"))
            .map_or(OsStr::new("manifest.json"), |name| name.as_os_str());
        fuse::mount(
            root,
            manifest,
            Path::new(required("--mountpoint")?),
            allow_other,
        )?;
    } else {
        let mut transaction = commit::Transaction::open(root)?;
        let optional_text = |name: &str, default: &str| -> store::Result<String> {
            match values.get(OsStr::new(name)) {
                Some(value) => value
                    .to_str()
                    .map(str::to_owned)
                    .ok_or_else(|| format!("{name} must be UTF-8").into()),
                None => Ok(default.to_owned()),
            }
        };
        let base = optional_text("--base", "manifest.json")?;
        let message = optional_text("--message", "Experimental commit")?;
        let expected = match (
            values.get(OsStr::new("--expected-head")),
            values.get(OsStr::new("--expected-generation")),
        ) {
            (None, None) => None,
            (Some(head), Some(generation)) => Some(commit::Head {
                head: head
                    .to_str()
                    .ok_or("expected head must be UTF-8")?
                    .to_owned(),
                generation: generation
                    .to_str()
                    .ok_or("generation must be UTF-8")?
                    .parse()?,
            }),
            _ => return Err("expected head and generation must be provided together".into()),
        };
        let result = if command == "verify" {
            let (_, expected_manifest) = store::ObjectStore::load(root, required("--manifest")?)?;
            let full = sprig::content::capture(
                Path::new(required("--merged")?),
                &root.join("objects"),
                &sprig::content::Observed::new(),
            )?;
            if full.0.len() != expected_manifest.len()
                || full.0.iter().any(|(path, entry)| {
                    expected_manifest.get(path).is_none_or(|expected| {
                        expected.kind != entry.kind
                            || expected.mode != entry.mode
                            || expected.modified_ns != entry.modified_ns
                    })
                })
            {
                return Err(
                    "incremental capture differs from independent full-capture oracle".into(),
                );
            }
            serde_json::json!({"event":"full_capture_verified", "entries":full.0.len(), "identity_comparison":false})
        } else if command == "head" {
            serde_json::to_value(transaction.head())?
        } else if command == "history" {
            serde_json::to_value(transaction.history(10_000)?)?
        } else if command == "read" {
            let revision = if base.len() == 64 && base.bytes().all(|byte| byte.is_ascii_hexdigit())
            {
                transaction.revision(&base)?
            } else {
                transaction.resolve_base(&base)?
            };
            let path = required("--path")?.to_str().ok_or("path must be UTF-8")?;
            let entry = revision
                .manifest
                .get(path)
                .ok_or("file is absent from revision")?;
            let bytes = sprig::content::read_file(entry, &root.join("objects"))?;
            serde_json::json!({"revision":revision.id, "path":path, "bytes":bytes})
        } else if command == "write" {
            let path = required("--path")?.to_str().ok_or("path must be UTF-8")?;
            let text = required("--text")?.to_str().ok_or("text must be UTF-8")?;
            serde_json::to_value(transaction.write_file(
                &base,
                path,
                text.as_bytes(),
                &message,
                expected.as_ref(),
            )?)?
        } else {
            let projection_base = optional_text("--projection-base", "manifest.json")?;
            let identity_manifest = match values.get(OsStr::new("--identity-base")) {
                Some(filename) => store::ObjectStore::load(root, filename)?.1,
                None => transaction.resolve_base(&base)?.manifest,
            };
            let mut captured = capture::capture(
                root,
                OsStr::new(&projection_base),
                Path::new(required("--merged")?),
                Path::new(required("--upper")?),
                Path::new(required("--lower")?),
            )?;
            captured.reconcile_identities(&identity_manifest)?;
            let stats = captured.stats.json();
            if command == "capture" {
                let output = required("--output")?;
                let path = Path::new(output);
                if path.components().count() != 1
                    || !matches!(path.components().next(), Some(Component::Normal(_)))
                {
                    return Err("output must be a new filename inside the library".into());
                }
                let target = root.join(path);
                let nonce = std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)?
                    .as_nanos();
                let temporary =
                    root.join(format!("capture-{}-{nonce}.pending", std::process::id()));
                let mut file = OpenOptions::new()
                    .write(true)
                    .create_new(true)
                    .mode(0o600)
                    .open(&temporary)?;
                serde_json::to_writer(&mut file, &captured.manifest)?;
                file.write_all(b"\n")?;
                file.sync_all()?;
                fs::hard_link(&temporary, &target)?;
                let finish = (|| -> std::io::Result<()> {
                    File::open(root)?.sync_all()?;
                    fs::remove_file(&temporary)?;
                    File::open(root)?.sync_all()
                })();
                if let Err(error) = finish {
                    return Err(format!("capture output {} is visible, but durability/cleanup outcome is unknown; inspect before retrying: {error}", target.display()).into());
                }
                serde_json::json!({"event":"captured", "manifest":output, "stats":stats})
            } else {
                let published =
                    transaction.publish(&base, captured.manifest, &message, expected.as_ref())?;
                serde_json::json!({"event":"checkpoint", "publication":published, "capture":stats})
            }
        };
        println!("{result}");
    }
    Ok(())
}
