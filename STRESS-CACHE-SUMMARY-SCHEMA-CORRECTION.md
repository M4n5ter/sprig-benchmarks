# Native cache summary schema correction

Run [40294193428](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40294193428)
at benchmark `afacf84f0c6c80014c0e7c3cc00fac348357afbe` remains a **failed CI run**. Its three
native canaries and nine Latin screen samples completed successfully, but the
final analysis rejected every sample with `invalid measured metric`. No product
measurement was repeated to replace this failure.

## Cause and narrow correction

The inherited production report intentionally records
`metadata_branch_available=true`, `metadata_branch_probe="omitted"`,
`metadata_branch_seconds=null`, `metadata_branch_unavailable_reason=null`.
This field is an explicitly unmeasured probe, not a failed timer and not zero.
The new strict all-`*_seconds` validator did not recognize that existing schema.

The correction recognizes **only that exact omitted marker**, records it under
`notMeasured` in every audited row, and never emits a ratio for it. Other null,
negative, nonfinite, boolean or string timings still fail. A numeric zero under
an omitted marker, or a wrong availability/probe/reason, also fails. No product,
sampler, fixture, workflow, ordering, timing, resource or correctness rule changes.

Root's serial offline validation passed22/22 cache tests plus syntax/whitespace
checks (session10687). Tests now include the real production marker, explicit
not-measured retention, contradictory markers, other null phases and malformed
measured phases in every raw sample.

## Immutable same-sample reanalysis provenance

- Original summary SHA-256: `cde0a3390735f157cbe19c87c988a8b4f3a5a1cfb057a1ca3de611401f906e35`.
- Original summary tool SHA-256: `60c5d970c8944a23c3e57f41d8128bd372fa0a00451a2d30ce65f7f2ce6c3323`.
- Corrected tool SHA-256: `0446c7082cc402613d665fc2cc5bb370f90aa7d0e17f58045cb10c26024041a4`.
- Post-hoc summary SHA-256: `bc16b5a9651717864fa7922df7fdbc183b34d2c1a449e05fc0e631a7a3f65dfa`.
- Raw artifact manifest SHA-256: `b4f363389f85ceafccf93bb98edea4c6f465ae5afa8fcb4224e37e1bbfcd63ac`.
- All217 original artifact files were rehashed unchanged. All three canaries
  and all nine screen samples were revalidated, including144 full-tree oracle
  checks and30 historical readbacks in total, exact source/binary identities,
  archive hashes, normal cleanup and original shared deadlines.

The original failed summary, its nine errors, raw reports and all failed-run
metadata are retained alongside the corrected analysis. “Post-hoc analysis
passed” must never be relabeled as “original CI passed”. Small-N performance
findings belong in the separate screen report; this correction itself is not a
product optimization or a promotion decision.
