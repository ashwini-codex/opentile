# Verification plan — spec promise → test → coverage bin → assertion

Sources: `docs/02-numerics-spec.md`, `docs/03-interface-spec.md`, `docs/01-architecture.md`. Tests named are the ones that *can fail* if the promise is broken.

| Spec promise | Test | Coverage bin | Assertion / checker |
|---|---|---|---|
| INT8 two's complement operands | `tests/test_models.py`, `test_pe` exhaustive, directed `alt_signs` | `op_extreme`, `sign_neg` | Python/C++ refs; PE `acc == acc_d + prod_d` |
| Product exact signed 16-bit; (−128)×(−128)=16384 | `test_pe` wave / exhaustive | `op_extreme`, `acc_large` | `formal/pe_props.sv` cover + assert |
| INT32 wrap | `test_pe` wrap (131072×16384) | excluded at tile K≤64 (impossible) | PE wrap test; tile exclusion in `05-coverage-model.md` |
| C = wrap32(Σ A[i,k] B[k,j]), no sat/requant | models + tile scoreboard | `acc_*` | `tb.Scoreboard.check` vs `gemm_int8` |
| Summation order irrelevant | model associativity test | — | pytest |
| K in 1..K_MAX | `SUITE=err`, kmax | `K1` `K2` `Ktyp` `KMAX` `err_k` | TB busy=0 + bit0 |
| K=0 / K>K_MAX → K_RANGE, no txn | err suite | `err_k` | `err_code_o[0]`, `busy_o=0` |
| Output-stationary; t=i+j+k | cycle traces, `trace_compare` | `fsm_COMPUTE` | cycle model vs DUT trace |
| Compute length K+R+C−2 | latency | `fsm_COMPUTE_DRAIN` | `count_latency` vs formula |
| clr in IDLE+LOAD; en only COMPUTE | array stall, tile timing | `fsm_LOAD` `fsm_COMPUTE` | architecture + TB timing |
| Packed LSB = element 0 | golden 2×2 K=3 | — | trace index n=i·C+j |
| AXI-Stream fire = valid && ready | `tb.run_txn` | `bp_*` | snap-before-edge |
| Hold tdata/tlast while valid && !ready | `broken_bpress`, stall3 | `bp_stall3` `bp_long` | TB hold check; `tile_props` C-hold |
| A row-major R·K; B row-major K·C; C row-major R·C | directed + scoreboard | `size_*` | beat layout in `tb.py` |
| TLAST only on last beat; sticky flags; txn continues | `test_tile_rtl` tlast | `err_atlast` `err_btlast` | flags + GEMM still matches |
| Independent A/B streams | concurrent LOAD | `fsm_LOAD` | both tready in LOAD |
| start accepted only in IDLE; busy=0 on done | err busy_probe | `fsm_IDLE` `fsm_STORE_IDLE` | `busy_o` on `done_o` |
| err cleared on accepted start | err then run_txn; mutant M19 | `err_k` then clean txn | `err_code_o==0` after good start |
| Reset → IDLE, abandon C | reset_mid | `fsm_IDLE` | idle outputs then GEMM |
| 4×4 K=4 latency 45 | latency suite | `size_4x4` | `make sim` |
| Sizes 2/4/8 | `tests/run_sizes.py` | `size_2x2` `size_4x4` `size_8x8` | random + latency |
| Skew inside array | nonskew catch | — | `trace_compare` t=1 |
| PE clr > en > hold | `test_pe` control | pe formal covers | `pe_props.sv` |
| C TLAST on last beat only | scoreboard tlasts | `fsm_STORE` | `tb.Scoreboard` |
| No AXI-Lite / multi-outstanding | out of scope | excluded | `08-what-these-numbers-do-not-show.md` |
| E4M3 decode classes (zero/sub/normal/max/NaN) | `test_pe` fp8_cov / exhaustive | `fp8_zero` `fp8_subnormal` `fp8_normal` `fp8_max` `fp8_nan` | `gemm_e4m3` vs DUT `acc` bits |
| Product sign XOR; mixed signs | fp8_cov `0x38×0xB8` | `fp8_mixed_signs` | scoreboard FP32 bits |
| Cancellation of nonzero terms → +0 | fp8_cov / cancel wave | `fp8_cancel` | K=2 `1+(−1)` → `00000000` |
| −0 iff every valid product is −0 | `test_array_fp8` SUITE=neg0 | — | padding `valid=0` so drain +0 does not count |
| 43-bit acc; 40-bit wraps at K=11×448² | `tests/test_fp8_acc_width.py`; mutant F07 | — | wrap40 −1986560 vs 2207744 |
| One FP32 RNE, ties to even | `test_fp8_tie`; mutant F11 | — | `42800000` vs ties-up `42800001` |
