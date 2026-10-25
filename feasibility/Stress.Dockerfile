# Stress-only runtime, not comparable to the old plain-Ubuntu runtime series.
# Workflow supplies exact official Ubuntu digest, records built image ID/packages,
# and charges entire deployed image + runtime state in whole-filesystem Used.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
RUN apt-get update && apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/*
COPY tree_oracle.py /opt/bench/tree_oracle.py
