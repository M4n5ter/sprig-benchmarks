# Checkpoint phase diagnostic

A single instrumented smoke run, not a new repeated performance comparison or a victory claim. [Run 39807922916](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/39807922916), source `36d35ed0bc87792fea68f5d52b7af653102159cb`; the frozen smoke workload, semantics and full historical readbacks passed. [Original raw and phase summary](measurements/2026-10-22-cas-phase-diagnostic/).

For 100 distributed-history checkpoints, the external CLI timer totaled 10,441.758 ms. Capture accounted for 8,652.539 ms (about 83%); publication 1,324.803 ms (about 13%). The remaining external time includes other measured phases, process startup, parsing/serialization and harness overhead. These are elapsed wall intervals, not kernel/remote CPU attribution. Timers add overhead and no estimate is subtracted.

## Disjoint outer phases, total milliseconds

| Phase | ms |
|---|---:|
| base_identity_load_seconds | 88.953 |
| capture_total_seconds | 8652.539 |
| identity_reconcile_seconds | 64.644 |
| publication_total_seconds | 1324.803 |
| transaction_open_seconds | 111.337 |

## Capture detail, total milliseconds

Setup, inclusive walk and finalize are sequential totals. The nine named walk categories are disjoint subsets of walk, so do not add walk again to its components. Lower proof includes its own opens, origin and chunk metadata checks. Unattributed walk time remains recursion, validation, readlink, bookkeeping and timer overhead.

| Interval | ms |
|---|---:|
| content_hash_put_stream_seconds | 649.618 |
| descriptor_close_seconds | 486.449 |
| directory_enumeration_seconds | 1423.746 |
| directory_open_seconds | 609.541 |
| finalize_seconds | 70.610 |
| lower_reusable_proof_seconds | 2233.574 |
| metadata_seconds | 939.659 |
| native_upper_state_seconds | 375.950 |
| origin_xattr_seconds | 1096.618 |
| regular_merged_open_seconds | 449.651 |
| setup_seconds | 128.947 |
| walk_total_seconds | 8442.873 |

The evidence prioritizes capture metadata/proof/traversal work over further optimization of CLI startup or publication alone. It does not authorize dropping namespace checks, object validation, durability or correctness. See [timing definitions](feasibility/cas-projection/TIMINGS.md). Prior repeated [publication results](CAS-PUBLICATION-RESULTS.md) remain unchanged.
