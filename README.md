# OpenTile

A parameterised INT8 output-stationary systolic-array matrix-multiply tile in SystemVerilog, with an optional FP8 E4M3 datapath on the PE and array.

**Author:** Ashwini Saravanan

C = A × B. Signed INT8 inputs, 32-bit wrapping accumulation, AXI-Stream A/B in and C out. Default instance is 4×4 with `K_MAX=64`. FP8 E4M3 (`FMT="E4M3"`) accumulates in a 43-bit fixed-point register and emits IEEE binary32.

## Quick start

Requires Docker.

```
docker build -t opentile:dev -f Dockerfile .
make versions
make verify
```

Host `make` rebuilds the image if needed and runs inside it. Tool pins, versions, and expected output: `docs/REPRODUCE.md`. CI runs the same `make verify` in `.github/workflows/ci.yml`.

Mutation testing is separate (slow): `make mutation`.

## Layout

| Path | What |
|---|---|
| `rtl/` | `pe.sv`, `array.sv`, `tile_top.sv` |
| `model/python/`, `model/cpp/` | Independent INT8 and E4M3 reference models |
| `tests/` | cocotb + Verilator testbench, coverage, size sweep |
| `formal/` | SymbiYosys PE and tile properties |
| `docs/` | Specs, decisions, golden example, release notes |
| `scripts/` | Mutation campaign, coverage bins, trace compare |

## Results

Reproduce with `make verify` / `make synth` / `make mutation`. Headline figures:

- 4×4 Yosys: 28421 cells / 5053 DFF; 8×8: 85900 / 11805 (`docs/07-synthesis-report.md`)
- Latencies: 2×2 K=2 = 15; 4×4 K=4 = 45; 8×8 K=2 = 99
- INT8 functional bins 41/41; mutation 27 killed / 5 equivalent / 32
- E4M3 PE exhaustive 65536 pairs; FP8 bins 7/7; E4M3 mutants 12/12
- E4M3 PE Yosys 2049 cells vs INT8 PE 902 (ratio 2.272)

Release notes: `docs/RELEASE-1.0.md`, `docs/RELEASE-1.1.md`.

## Out of scope

Multiple outstanding transactions, interrupts, AXI-Lite, partial tiles (R or C change at run time), K changing mid-transaction. 1.1 adds E4M3 at PE/array (`FMT`); `tile_top` C is still INT32 wrap. No OpenLane timing; Yosys cell counts only (`docs/07-synthesis-report.md`).

## License

Copyright 2026 Ashwini Saravanan. Apache License 2.0. See `LICENSE`.
