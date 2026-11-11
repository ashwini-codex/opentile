# Pinned toolchain for OpenTile.
# OSS CAD Suite 2026-10-14 provides Verilator, Yosys, SymbiYosys, and SMT solvers.
# cocotb/pytest are pip-pinned separately. Digests recorded in docs/REPRODUCE.md.
FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
ARG TARGETARCH
ARG OSS_CAD_TAG=2026-10-14
ARG OSS_CAD_STAMP=20261014
# linux-arm64 and linux-x64 tarball SHA256 from the 2026-10-14 GitHub release assets.
ARG OSS_CAD_SHA256_ARM64=ac908e60bbac62673565250c5ca5cd774c5066c440a418bc108d78da1762f86c
ARG OSS_CAD_SHA256_AMD64=a6ccc6b96b2d985336a1061c78b2fd2bdd73e0f68690da17db88e00457881a11

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential g++ make git ca-certificates curl \
        python3 python3-pip python3-venv python3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    if [ "${TARGETARCH}" = "arm64" ]; then \
      ARCH=linux-arm64; SHA="${OSS_CAD_SHA256_ARM64}"; \
    else \
      ARCH=linux-x64; SHA="${OSS_CAD_SHA256_AMD64}"; \
    fi; \
    curl -fsSL -o /tmp/oss-cad-suite.tgz \
      "https://github.com/YosysHQ/oss-cad-suite-build/releases/download/${OSS_CAD_TAG}/oss-cad-suite-${ARCH}-${OSS_CAD_STAMP}.tgz"; \
    echo "${SHA}  /tmp/oss-cad-suite.tgz" | sha256sum -c -; \
    mkdir -p /opt; \
    tar -xzf /tmp/oss-cad-suite.tgz -C /opt; \
    rm /tmp/oss-cad-suite.tgz

# /usr/local/bin first so pip cocotb-config 1.9.2 wins over the suite's bundled 2.1.0.dev0.
ENV PATH="/usr/local/bin:/opt/oss-cad-suite/bin:/usr/bin:${PATH}"

# Ubuntu 24.04 pip refuses system installs without this flag.
RUN /usr/bin/python3 -m pip install --break-system-packages --no-cache-dir \
        "cocotb==1.9.2" \
        "pytest==8.3.5" \
        "numpy==2.5.4" \
        "ml_dtypes==0.5.1"

WORKDIR /work
