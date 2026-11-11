# OpenTile 1.0 release notes

INT8 output-stationary systolic GEMM tile. Parameterised `tile_top #(R, C, K_MAX)` in SystemVerilog, AXI-Stream A/B in and C out, wrap-32 accumulators, no requantisation.

## How to run
Pinned image `opentile:dev` (`Dockerfile`, OSS CAD Suite 2026-10-14). Same command the CI workflow runs:

```
docker build -t opentile:dev -f Dockerfile .
docker run --rm -v "$PWD":/work -w /work opentile:dev make versions IN_IMAGE=1
docker run --rm -v "$PWD":/work -w /work opentile:dev make verify IN_IMAGE=1
```

Host `make verify` wraps the image. Mutation is extra: `make mutation`. Commands and expected numbers: `docs/REPRODUCE.md`.

## Headline results (every number has a log)
| Item | Value | Log |
|---|---|---|
| 4×4 Yosys cells / DFF | 28421 / 5053 | `make synth` |
| 8×8 Yosys cells / DFF | 85900 / 11805 | `make synth` |
| Cell ratio 8×8/4×4 | 3.0224 | `make synth` |
| Latency 2×2 K=2 | 15 | `make sim SIZES="2 4 8"` |
| Latency 4×4 K=4 | 45 | `make sim SIZES="2 4 8"` |
| Latency 8×8 K=2 | 99 | `make sim SIZES="2 4 8"` |
| Functional bins | 41/41 | `make coverage` |
| Mutation | 27 killed / 5 equivalent / 32 | `make mutation`; `docs/mutation.md` |
| PE formal | BMC20 + prove + cover PASS | `make formal` |
| Tile formal | BMC20 + cover PASS (no k-induction) | `make formal` |

RTL default remains **R=C=4**, `K_MAX=64`. 8×8 is a parameterised instance (`chparam` / `-GR`).

## Limits and known issues
- **Cell counts only.** No OpenLane/OpenROAD/STA in the image (`make versions`: `openlane: not found`). No ns clock, area in µm², or power. See `docs/07-synthesis-report.md` and `docs/08-what-these-numbers-do-not-show.md`.
- **Size.** Legal `R,C` in 1..16, `K_MAX` in 1..4096; 1.0 ships `K_MAX=64`. Scratchpad is FF (`$_DFFE_PP_`). COMPUTE cannot stall; STORE is `R·C` serial beats — that, not the MAC, dominates large-N latency.
- **Formal.** Tile properties are BMC depth 20. A K=64 LOAD is longer than that. PE wrap is proved at the PE, not at the tile (impossible for K≤64).
- **Mutation** is 32 hand edits, not all faults. Five survivors are equivalent (see `docs/mutation.md`).
- **Coverage** of defined bins is not exhaustive INT8×INT8 at every PE.
- **Bugs found in RTL:** none logged (`docs/06-bug-log.md`). Test gaps (M17 latency, M32 A `tready`) were closed with tests, not RTL changes.
- **Out of scope (1.0):** multiple outstanding transactions, interrupts, AXI-Lite, run-time R/C change, mid-txn K change, any format other than INT8 (FP8 is 1.1).

## What 1.0 contains
`rtl/pe.sv`, `rtl/array.sv`, `rtl/tile_top.sv`; Python and C++ refs; cocotb+Verilator TB; SymbiYosys; Yosys synth; coverage and mutation scripts. Specs: `docs/01-architecture.md`, `docs/02-numerics-spec.md`, `docs/03-interface-spec.md`.
