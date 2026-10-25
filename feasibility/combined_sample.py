#!/usr/bin/env python3
"""Fixed candidate, unchanged timed task, separately named post-history space."""
import latest_sample as frozen
from lifecycle_sample import CurrentSample as PostHistoryContract
PRODUCTION_SHA = "2a01fe445b8057ca49b4e8284fdd5583bbb4185c"
frozen.PRODUCTION_SHA = PRODUCTION_SHA
original_report = frozen.production_report

def report():
    value = original_report()
    value['postHistorySpace'] = None
    value['measurementNotes'].append('Original space notes describe activeSpace. A separate postHistorySpace follows all original operations/timers and retained input checks, before cleanup; primary timing and footprint are unchanged.')
    return value

class CombinedSample(frozen.CurrentSample):
    # Same original checks; the additional retained count accounts for completed
    # historical restores only at the new second boundary.
    retained_snapshot = PostHistoryContract.retained_snapshot
    sample_post_history_space = PostHistoryContract.sample_post_history_space

    def execute(self):
        super().execute()
        self.sample_post_history_space()

frozen.production_report = report
frozen.CurrentSample = CombinedSample
if __name__ == '__main__':
    raise SystemExit(frozen.main())
