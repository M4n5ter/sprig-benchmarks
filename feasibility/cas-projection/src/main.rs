use std::collections::BTreeMap;
use std::env;
use std::ffi::{OsStr, OsString};
use std::path::Path;

use sprig_cas_projection_prototype::{fuse, store};

const USAGE: &str = "Experimental read-only CAS projection (not full Sprig)\n\n  sprig-cas-projection-prototype import --source DIR --root NEW_DIR\n  sprig-cas-projection-prototype mount --root DIR --mountpoint EMPTY_DIR [--manifest FILENAME] [--allow-other]\n\nMount runs in the foreground on an explicitly authorized Linux root CI runner only. --allow-other is off by default and explicitly exposes\nread access to other users, subject to file modes; intended for isolated root CI OverlayFS tests.\nNo configuration or persistent helper is installed. One direct mount attempt; no helper fallback. External ordinary unmount only; no lazy/force cleanup.";

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
    if command != "import" && command != "mount" {
        return Err("expected import or mount; use --help".into());
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
        } else {
            option == "--root" || option == "--manifest" || option == "--mountpoint"
        };
        if !valid {
            return Err(
                format!("unknown or duplicate option: {}", option.to_string_lossy()).into(),
            );
        }
        let value = arguments
            .next()
            .ok_or_else(|| format!("missing value for {}", option.to_string_lossy()))?;
        if value.is_empty() || value.to_string_lossy().starts_with("--") {
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
    } else {
        let manifest = values
            .get(OsStr::new("--manifest"))
            .map_or(OsStr::new("manifest.json"), |name| name.as_os_str());
        fuse::mount(
            root,
            manifest,
            Path::new(required("--mountpoint")?),
            allow_other,
        )?;
    }
    Ok(())
}
