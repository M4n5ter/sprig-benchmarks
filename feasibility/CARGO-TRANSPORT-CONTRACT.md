# Cooperative generation-scoped Cargo transport

Status: scratch implementation and mocked validation only. This is a separate revised-transport series, not part of the current lifecycle A/B run and not evidence of a speedup over earlier Cargo measurements. Publication and real-run validation require independent review and the parent's separately authorized harness integration.

## Invocation and immutable inputs

Run cargo_transport_sample.py run with the existing --root, --source, --oracle, --binary, --backend native|projection|writable, --incremental 0|1, --image sha256:<64 lowercase hex>, optional --records, and required --production-sha <40 lowercase hex>.

The explicit source SHA is provenance supplied by the checkout/build harness, not a commit inferred from the executable. The harness must verify it. This adapter does not inherit cargo_sample.py's older hard-coded production label. It does not build or pull any image or product.

The shared image must already contain the same real fixed Cargo/rustc/linker toolchain on PATH, Python 3, bash, and /opt/bench/tree_oracle.py. Docker/containerd persistent roots and the image must already reside on the caller's fresh measured Btrfs filesystem. Existing prepare checks and the default compression policy remain unchanged.

The copied cargo_sample.py, current_sample.py, and cas_sample.py are dependencies, not edits to the benchmark repository. BUILD, PROGRAM, EDIT, ENVIRONMENT, PREFIX and ORACLE are imported unchanged. Offline locked single-job Cargo commands, full target/incremental caches, exact stdout expectations, and full-tree type/mode/mtime/content/symlink/internal-hardlink oracle semantics remain unchanged.

## Compiler sessions

1. After import and fork, start one ordinary container bound to the actual work generation at /work. Its first operation is the fixture oracle. Reuse this container for setup, clean build/run, no-op build/run, source edit/rebuild/run, and the complete pre-checkpoint tree snapshot.
2. Each command uses foreground docker exec with the original bash command and stdin oracle transport. CARGO_HOME, CARGO_TARGET_DIR and TMPDIR remain in /work. No arbitrary background command execution is supported by this bounded fixture.
3. Before checkpoint, cooperatively close and normally remove the work-generation container. Verify the exact sample-label inventory is empty, then invoke the unchanged complete checkpoint CLI and authoritative-path readiness logic. No old bind may cross checkpoint generation replacement.
4. Restore the exact acknowledged revision as second. Start a new compiler container bound to its actual generation. The complete saved oracle runs before any restored program execution or rebuild.
5. Keep this restored session live through restored execution, rebuild and final program execution. Main/source unchanged-tree checks use their own short-lived cooperative sessions; source retains its read-only bind. Those transient sessions finish before physical accounting.
6. At active-space accounting, retain exactly the restored compiler container plus the original three product views. Capture exact container ID, immutable image, labels, /work bind, PID/start-time, state, GraphDriver metadata and log path. This includes the live compiler writable-layer/log overhead in the same whole-filesystem accounting that includes Docker/containerd roots, image and product storage.
7. During final cleanup, close the restored compiler session cooperatively and normally remove it before any product-generation unmount. Use only the inherited normal product CLI cleanup afterward.

The expected successful workload uses four compiler containers in total: work before checkpoint, restored second, main oracle, and source oracle. There is no compiler container for the post-checkpoint work generation because no subsequent workload command uses it. At space, three of the four compiler containers are already removed and second alone remains live.

## Exact identity and failure behavior

Every session gets a unique name/token plus exact sample, session and generation labels. Inspection verifies full container ID, name, immutable image, labels, the sole /work bind and its read/write mode, ordinary security/restart configuration, and original PID/start-time identity. Log paths must remain in the measured filesystem. An unexpected label inventory or binding fails closed.

PID1 is a small Python waiter from the existing image. A single docker exec writes a unique marker in container-local /tmp, outside /work and all fixture/checkpoint oracles. The marker includes that writer process's PID and start-time ticks and is published by atomic rename. PID1 observes /proc and does not exit while that exact marker-writer process remains present. This avoids terminating the marker exec by exiting PID1 too early. No PID is signaled, including signal 0.

After marker acknowledgment, the host observes natural exit with a 15-second observational deadline. It requires an exited state with zero exit status and PID zero, confirms docker wait returns zero, and observes that the original host PID/start-time identity is gone. It captures PID1 logs, runs docker rm on that exact exited container without force, and verifies absence from the exact sample-label inventory. A reused PID is not mistaken for the original process.

There is no retry after an uncertain create, start, command exec, marker, wait, or removal acknowledgment. Session state is retained, cleanup is blocked, and no product-generation unmount is issued. A failed command exec is conservatively treated as potentially unfinished, even if a compiler error might have produced its exit code. This sacrifices automatic cleanup rather than risking termination of an unobserved writer. Read-only polling observes natural completion; it does not resend an action.

The shutdown observation loop is bounded. Docker CLI calls remain synchronous and are not forcibly killed to manufacture a deadline; a stuck transport can therefore still require external runner diagnosis. There are no docker stop/kill commands, process signals, forced removals, force/lazy unmounts, new capabilities/devices, or network/security setting changes.

## Timings and accounting

- full_task_seconds remains authoritative end-to-end wall time, including preparation, every container start/exec/exit/removal, all oracles, full checkpoint and restore, physical accounting, and final cleanup.
- Existing phase_seconds remain measured around actual operations. A session start is charged to the phase using it first. transport_stop_before_checkpoint records the complete pre-checkpoint release, including observational waits and normal removal. Final cooperative release is inside cleanup and transport_stop_final_cleanup.
- transport_seconds provides raw Docker-operation totals for create, start, inspect, inventory, exec, cooperative marker, exit wait, log capture and removal. compilerSessions records complete startSeconds/stopSeconds. These are diagnostic overlapping views, not values to subtract from whole-wall or phase time.
- convenience_seconds.checkpointCompilerQuiescePlusProduct is directly measured from shutdown start through complete checkpoint/readiness, including intervening inventory checks and acknowledgment bookkeeping. It is not an arithmetic subtraction of transport time.
- convenience_seconds.restoreToCompilerReady is directly measured from restore start through the restored container's successful create/start/exact-bind/PID inspection. It excludes the following complete tree oracle, which still must pass before program execution or rebuild. It therefore reports compiler-start readiness, not verified artifact readiness.
- Those two convenience intervals do not overlap each other, but each overlaps its own underlying phase/transport fields. Do not add composite and component accounting layers.
- The inherited checkpoint aggregate overlaps its checkpoint_cli and checkpoint_readiness breakdown. Do not blindly sum every phase_seconds key.
- Complete stdout/stderr and control/inspection logs stay outside /work but under the measured sample root. The optional external step ledger remains outside the measured filesystem, as in the prior harness. No expected manifest or marker is written into a product workspace.
- Whole-filesystem Used remains primary. Docker removal may have asynchronous storage effects; any bytes still retained at the measurement boundary remain charged rather than assumed reclaimed.

## Validation in this package

python3 -m py_compile cargo_transport_sample.py test_transport_mock.py
python3 test_transport_mock.py

The self-contained tests do not invoke Docker, Sprig, Btrfs, Rust or mounts. They exercise:

- Six native/projection/writable × incremental 0/1 successful lifecycle flows.
- All 16 frozen application commands in order, saved oracle on stdin, full restored verification before executable/build, one live restored compiler at space, four complete cooperative sessions, and compiler release before product unmount.
- Lost create, start, command-exec, marker, wait and removal acknowledgments; bad bind; bounded exit timeout. All block product unmount and prevent repeated shutdown/removal.
- Execution of the PID1 waiter against mocked /proc identities, with the writer still alive and then absent or PID-reused.
- Frozen command/environment constants, ordinary Docker arguments, and absence of kill/signal/force paths.

These checks do not establish real Docker/FUSE/Btrfs behavior, toolchain availability, performance, or kernel compatibility. Those remain for the independently reviewed, authorized runner series.
