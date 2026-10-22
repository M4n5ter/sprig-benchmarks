#!/usr/bin/env bash
set -euo pipefail
[[ "${GITHUB_ACTIONS:-}" == true && -n "${RUNNER_TEMP:-}" && "$RUNNER_TEMP" = /* ]]
root=$(mktemp -d "$RUNNER_TEMP/sprig-btrfs-smoke-XXXXXX")
image="$root/fs.img"; mountpoint="$root/mount"
mkdir "$mountpoint"; truncate -s 2G "$image"
[[ -f "$image" && ! -L "$image" && ! -b "$image" ]]
cleanup() { if mountpoint -q "$mountpoint"; then sudo umount "$mountpoint"; fi; }
trap cleanup EXIT
# Only this newly created regular file is formatted, never a discovered device.
sudo mkfs.btrfs -d single -m dup "$image" > results/btrfs-mkfs.txt
sudo mount -o loop,noatime "$image" "$mountpoint"
findmnt -T "$mountpoint" > results/btrfs-mount.txt
sudo python3 feasibility/btrfs_smoke.py "$mountpoint" "$PWD/results/btrfs-smoke.json"
sudo /usr/bin/python3 feasibility/native_snapshot.py smoke --root "$mountpoint/native-functional-store" --source "$root/native-functional-input" > results/native-functional-smoke.json
