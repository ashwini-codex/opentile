# OpenTile 1.1 release notes

1.0 INT8 tile plus **FP8 E4M3** at the PE and array (`FMT="E4M3"`): 43-bit exact acc (LSB=2⁻¹⁸), one IEEE binary32 RNE, canonical qNaN `0x7FC00000`. Default `FMT="INT8"` keeps 1.0 behaviour.

## How to run
Same image and CI command as 1.0:

```
docker build -t opentile:dev -f Dockerfile .
docker run --rm -v "$PWD":/work -w /work opentile:dev make verify IN_IMAGE=1
```

FP8 PE/array: `python3 tests/run_fp8_rtl.py`. FP8 bins: `python3 tests/run_fp8_coverage.py`. FP8 mutants: `python3 scripts/run_mutation_fp8.py` (also from `make mutation`).

## Headline results (every number has a log)
| Item | Value | Log |
|---|---|---|
| E4M3 PE Yosys cells / DFF | 2049 / 63 | `make pe-test` |
| INT8 PE Yosys cells / DFF (with `valid_o`) | 902 / 49 | `make pe-test` |
| Cell ratio E4M3/INT8 PE | 2.272 | `make pe-test` |
| E4M3 PE exhaustive | 65536 pairs PASS | `python3 tests/run_fp8_rtl.py` |
| FP8 required bins | 7/7 (K=1 misses only `fp8_cancel`) | `make coverage` |
| E4M3 mutants | 12 killed / 0 survived / 12 | `make mutation`; `docs/mutation.md` |
| 40-bit acc K=11×448² | 43-bit 2207744 vs 40-bit −1986560 | `tests/test_fp8_acc_width.py`; F07 killed |

1.0 numbers (functional 41/41, INT8 mutation 27/32, latencies 15/45/99) stay in `docs/RELEASE-1.0.md`. Live 4×4/8×8 Yosys after the `valid` pin is 28462/85971 (`make synth`); the 1.0 freeze is 28421/85900.

## What 1.1 adds
- Spec: `docs/02-numerics-spec.md` E4M3 [N].
- Models: `model/python/ref_fp8.py`, `model/cpp/ref_fp8.cpp`.
- RTL: `pe.sv` / `array.sv` parameter `FMT`, `valid` delayed with A.
- Coverage bins and E4M3 mutants.

## Limits
- **`tile_top` is still INT8.** C AXI-Stream is wrap32; E4M3 FP32 bits are on `pe.acc` / `array.acc_o` when `FMT="E4M3"`.
- **No OpenLane timing.** Cell counts only.
- K=1 exhaustive cannot catch a 40-bit acc (448² fits); the K=11 vector is required.
- Out of scope: E5M2, running FP16/FP32 acc, requant to E4M3, `tile_top` FMT.
