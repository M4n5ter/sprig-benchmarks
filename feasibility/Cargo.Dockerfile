# Build once per paired runner; both products consume the resulting immutable ID.
# BASE_IMAGE must be the inspected official ubuntu:24.04 repository digest.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
RUN apt-get update && apt-get install -y --no-install-recommends build-essential python3 ca-certificates && rm -rf /var/lib/apt/lists/*
COPY toolchain/ /opt/rust/
COPY tree_oracle.py /opt/bench/tree_oracle.py
ENV PATH="/opt/rust/bin:${PATH}"
RUN rustc -Vv && cargo -V && cc --version && python3 --version && test -x /opt/rust/bin/rustc && test -x /opt/rust/bin/cargo
