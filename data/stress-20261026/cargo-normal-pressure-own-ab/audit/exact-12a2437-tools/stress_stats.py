#!/usr/bin/env python3
"""Descriptive nearest-rank latency tails; no percentile of per-run medians."""
import math
import statistics

def latency_summary(samples):
    values = list(samples)
    if not values or any(not isinstance(x, (float, int)) or isinstance(x, bool)
                         or not math.isfinite(x) or x < 0 for x in values):
        raise ValueError('expected nonempty finite nonnegative timings')
    values.sort()
    result = dict(n=len(values), median=statistics.median(values), maximum=values[-1],
                  total=sum(values), quantileMethod='nearest-rank')
    # Do not market one or three paired samples as a useful p99 estimate.
    result['p95'] = values[math.ceil(.95*len(values))-1] if len(values) >= 20 else None
    result['p99'] = values[math.ceil(.99*len(values))-1] if len(values) >= 100 else None
    result['tailCaveat'] = 'descriptive dependent operations, not independent replicates'
    return result
