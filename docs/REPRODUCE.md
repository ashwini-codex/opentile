# Reproduce

Needs Docker. Host `make` builds `opentile:dev` and runs inside it unless `IN_IMAGE=1`.

## Pinned image

`Dockerfile`: `ubuntu:24.04` + OSS CAD Suite `2026-10-14`.

- linux-arm64 sha256 `ac908e60bbac62673565250c5ca5cd774c5066c440a418bc108d78da1762f86c`
- linux-x64 sha256 `a6ccc6b96b2d985336a1061c78b2fd2bdd73e0f68690da17db88e00457881a11`
- pip: `cocotb==1.9.2`, `pytest==8.3.5`, `numpy==2.5.4`, `ml_dtypes==0.5.1` (E4M3 decode-only oracle)

```
docker build -t opentile:dev -f Dockerfile .
make versions
make verify
```

`make versions` expected: Verilator 5.053, Yosys 0.70+16, SBY v0.69, z3, cocotb 1.9.2, pytest 8.3.5, g++ 13.x. OpenLane is not in the image.

## Commands

| Command | Expected |
|---|---|
| `make verify` | smoke, lint, models, PE/array/tile sim, formal, Yosys synth, coverage, then `VERIFY COMPLETE` |
| `make smoke-broken` | broken DUT fails; `results.xml` contains `<failure` |
| `make synth` | 4×4 **28421** cells / **5053** DFF; 8×8 **85900** / **11805** |
| `make sim SIZES="2 4 8"` | latency 15 / 45 / 99 |
| `make coverage` | INT8 41/41 bins; FP8 7/7 (K=1 misses only `fp8_cancel`) |
| `make mutation` | INT8 27 killed / 5 equivalent / 32; E4M3 12/12 killed (slow, not in CI) |

CI is the same verify command: `.github/workflows/ci.yml`.

Runtime logs land under `reports/` (gitignored). Optional formula check: `python3 scripts/golden_check.py` → `formula ok`.
