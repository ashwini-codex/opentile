# Coverage model

Functional bins are collected by `tests/tb.py` `Coverage` plus `tests/test_coverage.py` FSM sampler. Required list: `scripts/required_bins.txt`. `make coverage` dumps the union under `reports/`.

## Bins (reason)

| Bin | Reason it exists |
|---|---|
| `op_zero` | All-zero GEMM is a classic silent-pass if the DUT never computes |
| `op_pm1` | Distinguishes add from MAC-by-identity |
| `op_extreme` | −128/127; signed vs unsigned product |
| `op_mixed` | Mixed signs in one txn |
| `sign_neg` / `sign_pos` | Sign of the operand population |
| `cross_op_*_{pos,neg}` | Operand class crossed with sign (zero×neg is empty — excluded) |
| `K1` `K2` `Ktyp` `KMAX` | Length of COMPUTE and scratchpad depth |
| `bp_always` `bp_random` `bp_long` `bp_every_other` `bp_stall3` | C-ready patterns from the interface spec |
| `size_2x2` `size_4x4` `size_8x8` | Size sweep; 1×1/nonsquare remain extra not required |
| `err_k` `err_atlast` `err_btlast` | All three `err_code_o` bits |
| `acc_zero` `acc_small` `acc_med` `acc_large` `acc_neg` `acc_pos` | Result magnitude bands (large = \|C\|≥16384) |
| `fsm_{IDLE,LOAD,COMPUTE,DRAIN,STORE}` | Every controller state |
| `fsm_IDLE_LOAD` … `fsm_STORE_IDLE` | Every legal forward transition |
| `fp8_zero` | Signed zero codes (`E=M=0`) |
| `fp8_subnormal` | `E=0`, `M≠0` |
| `fp8_normal` | Finite normal including 1.0 |
| `fp8_max` | Finite max 448 (`0x7E` / `0xFE`) |
| `fp8_nan` | `E=M=all ones` |
| `fp8_mixed_signs` | Product sign from XOR is 1 |
| `fp8_cancel` | K≥2, two+ nonzero products, exact sum +0 |

## Exclusions (allowed)

| Exclusion | Reason |
|---|---|
| Tile INT32 wrap (`acc` near ±2³¹) | Spec: impossible for K≤K_MAX=64; PE wrap is tested at the PE, not at the tile |
| `cross_op_zero_neg` | All-zero operands are not negative |
| `fsm_LOAD_IDLE` without reset | Legal FSM never returns LOAD→IDLE except via reset (reset is a separate path, not a state arc in the sampler) |
| `fsm_COMPUTE_IDLE` etc. skip arcs | Same: only reset; excluded as illegal in spec |
| Back-pressure on A/B during LOAD of 1000 cycles | Spec allows it; `bp_long` is C-side. A/B stall is the DUT `tready=0` while counts short — not a TB bin. Covered indirectly by independent streams |
| Line coverage of `default:` in `unique case` | Unreachable if `state` stays in the enum; mutant M29; `anno/tile_top.sv` `%000000` |
| Verilator `fsm_state`/`fsm_arc` 0% | No SV `covergroup`; FSM bins are the Python sampler (`fsm_*`) |
| `pe.sv` not in `anno/` | Verilator inlines the PE into `array`; points land on `array.sv`/`tile_top.sv` |
| Formal k-induction of `tile_top` | Beat-count auxiliaries are not inductive; BMC20 + cover instead |
| Toggle of unused enum encodings 5–7 | Not part of the 5-state FSM |
| OpenLane / timing bins | No PPA tools in the image |

Nonsquare sizes (2×3, 4×1, …) are collected when those tests run; they are *not* in the required 2/4/8 list.

FP8 required list: `scripts/required_bins_fp8.txt`. A K=1-only sweep is allowed to miss `fp8_cancel` — that is the gap the bin exists to catch.
